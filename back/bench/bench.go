// bench — Go 原生高并发 HTTP 压测工具
// 每个 worker 使用独立持久 TCP 连接，避免 Windows 端口耗尽

package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

type Stats struct {
	Speed         int     `json:"speed"`
	BytesPerSec   int64   `json:"bytesPerSec"`
	SuccessCount  int64   `json:"successCount"`
	FailedCount   int64   `json:"failedCount"`
	TotalBytes    int64   `json:"totalBytes"`
	TotalRequests int64   `json:"totalRequests"`
	Duration      float64 `json:"duration"`
	Concurrency   int     `json:"concurrency"`
	TargetURL     string  `json:"targetURL"`
}

// counter 通过 atomic 操作并发安全地统计请求数和字节数
type counter struct {
	success int64 // 成功请求数，通过 atomic 操作
	failed  int64 // 失败请求数，通过 atomic 操作
	bytes   int64 // 总传输字节数，通过 atomic 操作
}

type workerState struct {
	conn   net.Conn
	reader *bufio.Reader
	dialed bool // 标记连接是否已建立，与 conn 分离以便 close 后可重连
}

func (ws *workerState) dial(host string) error {
	if ws.dialed {
		return nil
	}
	conn, err := net.DialTimeout("tcp", host, 10*time.Second)
	if err != nil {
		return err
	}
	ws.conn = conn
	ws.reader = bufio.NewReaderSize(conn, 4096)
	ws.dialed = true
	return nil
}

func (ws *workerState) close() {
	if ws.dialed && ws.conn != nil {
		ws.conn.Close()
		ws.dialed = false
	}
}

func worker(ctx context.Context, host string, reqBytes []byte, wg *sync.WaitGroup, c *counter) {
	defer wg.Done()

	var ws workerState
	defer ws.close()

	// 每个循环一个请求，复用 TCP 连接
	for {
		if ctx.Err() != nil {
			return
		}

		// 建立 TCP 连接（含重试）
		if !ws.dialed {
			maxRetries := 3
			for retry := 0; retry < maxRetries; retry++ {
				if err := ws.dial(host); err != nil {
					if retry == maxRetries-1 {
						atomic.AddInt64(&c.failed, 1)
						return
					}
					time.Sleep(time.Duration(retry+1) * time.Second)
					continue
				}
				break
			}
		}

		// 设置超时
		if err := ws.conn.SetDeadline(time.Now().Add(10 * time.Second)); err != nil {
			atomic.AddInt64(&c.failed, 1)
			ws.conn.Close()
			ws.dialed = false
			continue
		}

		// 发送请求
		if _, err := ws.conn.Write(reqBytes); err != nil {
			atomic.AddInt64(&c.failed, 1)
			ws.close()
			continue // 断线重连
		}

		// 解析 HTTP 响应
		statusOK := false
		contentLength := int64(-1)
		chunked := false
		var respBytes int64

		// 读状态行
		statusLine, err := ws.reader.ReadString('\n')
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			atomic.AddInt64(&c.failed, 1)
			ws.close()
			continue
		}
		respBytes += int64(len(statusLine))

		// 解析状态码
		parts := strings.Fields(statusLine)
		if len(parts) >= 2 {
			statusCode := parts[1]
			if len(statusCode) >= 1 && statusCode[0] == '2' {
				statusOK = true
			}
		}

		// 读响应头
		headerOK := true
		for {
			headerLine, err := ws.reader.ReadString('\n')
			if err != nil {
				atomic.AddInt64(&c.failed, 1)
				headerOK = false
				break
			}
			respBytes += int64(len(headerLine))
			headerLine = strings.TrimRight(headerLine, "\r\n")
			if headerLine == "" {
				break // 空行 = 头结束
			}

			lower := strings.ToLower(headerLine)
			if strings.HasPrefix(lower, "content-length:") {
				val := strings.TrimSpace(headerLine[15:])
				if v, e := strconv.Atoi(val); e == nil {
					contentLength = int64(v)
				}
			}
			if strings.HasPrefix(lower, "transfer-encoding:") && strings.Contains(lower, "chunked") {
				chunked = true
			}
		}

		if !headerOK {
			ws.close()
			continue
		}

		// 读响应体
		bodyOK := true
		if chunked {
			for {
				line, err := ws.reader.ReadString('\n')
				if err != nil {
					atomic.AddInt64(&c.failed, 1)
					bodyOK = false
					break
				}
				respBytes += int64(len(line))
				line = strings.TrimSpace(line)
				size, err := strconv.ParseInt(line, 16, 64)
				if err != nil {
					atomic.AddInt64(&c.failed, 1)
					bodyOK = false
					break
				}
				if size == 0 {
					if _, err := ws.reader.Discard(2); err != nil {
						atomic.AddInt64(&c.failed, 1)
						bodyOK = false
						break
					}
					respBytes += 2
					break
				}
				discardSize := int(size) + 2
				if int64(discardSize) != size+2 || discardSize < 0 {
					atomic.AddInt64(&c.failed, 1)
					bodyOK = false
					break
				}
				if _, err := ws.reader.Discard(discardSize); err != nil {
					atomic.AddInt64(&c.failed, 1)
					bodyOK = false
					break
				}
				respBytes += size + 2
			}
		} else if contentLength > 0 {
			discardSize := int(contentLength)
			if int64(discardSize) != contentLength || discardSize < 0 {
				atomic.AddInt64(&c.failed, 1)
				bodyOK = false
			} else if _, err := ws.reader.Discard(discardSize); err != nil {
				atomic.AddInt64(&c.failed, 1)
				bodyOK = false
			} else {
				respBytes += contentLength
			}
		}

		if !bodyOK {
			ws.close()
			continue
		}

		atomic.AddInt64(&c.bytes, respBytes)

		if statusOK {
			atomic.AddInt64(&c.success, 1)
		} else {
			atomic.AddInt64(&c.failed, 1)
		}
	}
}

func main() {
	concurrency := flag.Int("c", 100, "并发连接数")
	duration := flag.Int("t", 10, "压测时长（秒）")
	urlStr := flag.String("url", "http://localhost:12568/index.html", "目标 URL")
	outputJSON := flag.Bool("json", false, "以 JSON 格式输出")
	flag.Parse()

	if *concurrency <= 0 {
		fmt.Fprintln(os.Stderr, "错误：并发数必须大于 0")
		os.Exit(1)
	}
	if *duration <= 0 {
		fmt.Fprintln(os.Stderr, "错误：压测时长必须大于 0")
		os.Exit(1)
	}
	if *urlStr == "" {
		fmt.Fprintln(os.Stderr, "错误：目标 URL 不能为空")
		os.Exit(1)
	}

	// 解析 URL
	parsed, err := urlParse(*urlStr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		os.Exit(1)
	}
	host := parsed.host
	path := parsed.path

	// 防止 CRLF 注入
	if strings.ContainsAny(path, "\r\n") || strings.ContainsAny(host, "\r\n") {
		fmt.Fprintln(os.Stderr, "错误：URL 中包含非法字符")
		os.Exit(1)
	}

	// 预构建请求报文
	reqBytes := []byte(fmt.Sprintf("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: bench\r\nAccept: */*\r\nConnection: keep-alive\r\n\r\n", path, host))

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(*duration)*time.Second)
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	c := &counter{}
	var wg sync.WaitGroup

	if !*outputJSON {
		fmt.Printf("Benchmarking: %s (be patient)\n", *urlStr)
		fmt.Printf("Concurrency: %d, Duration: %d sec\n", *concurrency, *duration)
		fmt.Println("------------------------ Results ------------------------")
	}

	startTime := time.Now()

	for i := 0; i < *concurrency; i++ {
		wg.Add(1)
		go worker(ctx, host, reqBytes, &wg, c)
	}

	select {
	case <-ctx.Done():
	case <-sigCh:
		fmt.Println("\nInterrupted, shutting down gracefully...")
		cancel()
	}

	wg.Wait()

	elapsed := time.Since(startTime).Seconds()
	success := atomic.LoadInt64(&c.success)
	failed := atomic.LoadInt64(&c.failed)
	totalBytes := atomic.LoadInt64(&c.bytes)
	totalReqs := success + failed

	var speed int
	var bytesPerSec int64
	if elapsed > 0 {
		speed = int(float64(totalReqs) / elapsed)
		bytesPerSec = int64(float64(totalBytes) / elapsed)
	}

	result := Stats{
		Speed:         speed,
		BytesPerSec:   bytesPerSec,
		SuccessCount:  success,
		FailedCount:   failed,
		TotalBytes:    totalBytes,
		TotalRequests: totalReqs,
		Duration:      elapsed,
		Concurrency:   *concurrency,
		TargetURL:     *urlStr,
	}

	if *outputJSON {
		jsonBytes, err := json.MarshalIndent(result, "", "  ")
		if err != nil {
			fmt.Fprintf(os.Stderr, "JSON序列化失败: %v\n", err)
			return
		}
		fmt.Println(string(jsonBytes))
	} else {
		fmt.Printf("Speed=%d reqs/sec, %d bytes/sec.\n", speed, bytesPerSec)
		fmt.Printf("Requests: %d succeeded, %d failed.\n", success, failed)
		fmt.Println()
		fmt.Println("Go bench completed!")
	}

	if totalReqs > 0 && success > 0 {
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}

// 简单 URL 解析（不依赖 net/url，减少动态依赖）
type parsedURL struct {
	host string
	path string
}

func urlParse(raw string) (parsedURL, error) {
	// 移除协议头
	host := raw
	if idx := strings.Index(host, "://"); idx >= 0 {
		host = host[idx+3:]
	}
	// 分离 host 和 path
	path := "/"
	if idx := strings.Index(host, "/"); idx >= 0 {
		path = host[idx:]
		host = host[:idx]
	}
	// 移除片段标识符
	if idx := strings.Index(path, "#"); idx != -1 {
		path = path[:idx]
	}
	if host == "" {
		return parsedURL{}, fmt.Errorf("无效 URL: %s", raw)
	}
	// 默认端口
	if !strings.Contains(host, ":") {
		host = host + ":80"
	}
	return parsedURL{host: host, path: path}, nil
}
