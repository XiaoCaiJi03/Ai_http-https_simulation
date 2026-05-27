"""
大并发压测模块 — Go 原生引擎版
================================
替换原 WSL + webbench (Ubuntu) 方案，使用 Go 编写的 bench 工具进行压测。
Go 二进制原生运行于 Windows，无需 WSL/Ubuntu 环境。

依赖：
  - Go (编译阶段)，如已提供预编译 bench.exe 则无需 Go
  - 目标 HTTP 服务运行于 http://localhost:12568/index.html（可配置）
"""

import subprocess
import sys
import re
import time
import os
import json

# ==================== 配置项 ====================
# Go 源码目录（bench.go + go.mod 所在路径）
BENCH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench")
# Go 二进制路径（编译后）
BENCH_BINARY = os.path.join(BENCH_DIR, "bench.exe")
# 默认目标地址（用户可在请求中覆盖）
DEFAULT_TARGET_URL = "http://localhost:60110/index.html"
# ===============================================


def ensure_bench_binary() -> bool:
    """
    确保 bench.exe 已编译。
    如二进制不存在或源码更新，自动调用 go build 编译。
    返回 True 表示就绪，False 表示编译失败。
    """
    # 检查二进制是否存在
    if os.path.exists(BENCH_BINARY):
        # 可选：检查源码时间戳是否更新（简单起见直接信任已编译的）
        return True

    print("[INFO] bench.exe 未找到，正在编译 Go 压测引擎...")
    
    # 检查 go 是否可用
    try:
        subprocess.run(
            ["go", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("[❌] 未找到 Go 编译器。请安装 Go (https://go.dev/dl/) 或提供预编译的 bench.exe")
        return False

    try:
        result = subprocess.run(
            ["go", "build", "-ldflags=-w -s", "-o", BENCH_BINARY, "bench.go"],
            cwd=BENCH_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore',
            timeout=120
        )
        if result.returncode == 0:
            print(f"[✅] Go 压测引擎编译成功: {BENCH_BINARY}")
            return True
        else:
            print(f"[❌] Go 编译失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"[❌] Go 编译异常: {e}")
        return False


def run_big_simulation(request_data: dict) -> dict:
    """
    大并发模拟的实现函数，供 app.py 调用。
    
    参数:
        request_data: {
            "concurrency": 1000,   # 并发数
            "duration": 10,        # 测试时长（秒）
            "target_url": "..."    # 可选，目标URL
        }
    
    返回:
        {
            "status": "success" | "error",
            "message": "...",
            "data": {
                "stats": {
                    "startTime": float,
                    "endTime": float,
                    "duration": float,
                    "requestCount": int,
                    "concurrency": int,
                    "throughput": int,     # pages/min
                    "bytesPerSec": int,    # bytes/sec
                    "stdout": str          # 完整输出文本
                }
            }
        }
    """
    print(f"[DEBUG] 收到大并发模拟请求: {request_data}")
    print("===== Go 原生大并发压测引擎 =====")

    # 提取参数
    concur = int(request_data.get("concurrency", 1000))
    test_time = int(request_data.get("duration", 10))
    target_url = request_data.get("target_url", DEFAULT_TARGET_URL)
    # 验证URL格式，防止命令注入
    url_pattern = re.compile(r'^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=]+$')
    if not url_pattern.match(target_url):
        return {"status": "error", "message": "无效的目标URL格式"}
    
    # 参数校验
    if concur <= 0:
        return {"status": "error", "message": "并发数必须大于 0"}
    if test_time <= 0:
        return {"status": "error", "message": "测试时长必须大于 0"}

    # 确保 Go 二进制已编译
    if not ensure_bench_binary():
        return {"status": "error", "message": "Go 压测引擎编译失败，请检查 Go 环境"}
    
    try:
        # 构建命令行(使用 -json 输出，便于解析)
        cmd = [
            BENCH_BINARY,
            "-c", str(concur),
            "-t", str(test_time),
            "-url", target_url,
            "-json",
        ]
        print(f"[INFO] 执行压测命令: {' '.join(cmd)}")
        print("------------------------ 压测结果 ------------------------")

        start_time = time.time() * 1000

        # 执行 Go 压测程序
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='ignore',
            bufsize=1,
            universal_newlines=True,
        )

        # 读取完整输出（最大等待 = 测试时长 + 30s 余量）
        stdout, _ = proc.communicate(timeout=test_time + 60)
        end_time = time.time() * 1000
        elapsed_ms = end_time - start_time

        if stdout:
            print(stdout)

        # 解析 JSON 输出
        speed = 0
        bytes_per_sec = 0
        request_count = 0
        failed_count = 0
        total_bytes = 0
        if not stdout:
            return {"status": "error", "message": "压测程序无输出"}
        try:
            # 查找 JSON 部分（输出中可能包含非 JSON 前缀行）
            json_start = stdout.find('{')
            if json_start >= 0:
                json_str = stdout[json_start:]
                stats = json.loads(json_str)
                speed = stats.get("speed", 0)
                bytes_per_sec = stats.get("bytesPerSec", 0)
                request_count = stats.get("successCount", 0)
                failed_count = stats.get("failedCount", 0)
                total_bytes = stats.get("totalBytes", 0)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[WARN] JSON 解析失败，回退文本解析: {e}")
            # 回退文本解析
            for line in stdout.splitlines():
                if "Speed=" in line:
                    speed_match = re.search(r"Speed=(\d+)\s+pages/min", line)
                    bytes_match = re.search(r"(\d+)\s+bytes/sec", line)
                    if speed_match:
                        speed = int(speed_match.group(1))
                    if bytes_match:
                        bytes_per_sec = int(bytes_match.group(1))
                elif "Requests:" in line:
                    request_match = re.search(r"Requests:\s+(\d+)\s+succeeded", line)
                    if request_match:
                        request_count = int(request_match.group(1))

        print(f"[INFO] 压测完成，耗时: {elapsed_ms:.0f}ms")
        print(f"[INFO] 吞吐量: {speed} pages/min, {bytes_per_sec} bytes/sec")
        print(f"[INFO] 请求数: {request_count} succeeded, {failed_count} failed")

        return {
            "status": "success",
            "message": "大并发模拟已完成",
            "data": {
                "stats": {
                    "startTime": start_time,
                    "endTime": end_time,
                    "duration": elapsed_ms,
                    "requestCount": request_count,
                    "failedCount": failed_count,
                    "totalBytes": total_bytes,
                    "concurrency": concur,
                    "throughput": speed,
                    "bytesPerSec": bytes_per_sec,
                    "stdout": stdout
                }
            }
        }

    except Exception as e:
        print(f"[❌] 压测出错: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        # 确保子进程已清理
        if 'proc' in locals() and proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        print("[INFO] 资源已释放")


if __name__ == "__main__":
    # 命令行直接运行模式（测试用）
    print("===== Go 原生大并发压测引擎（命令行模式）=====")
    if not ensure_bench_binary():
        sys.exit(1)

    try:
        concur = input("并发数（默认 1000）：").strip() or "1000"
        test_time = input("测试秒数（默认 10）：").strip() or "10"
        target_url = input(f"目标URL（默认 {DEFAULT_TARGET_URL}）：").strip() or DEFAULT_TARGET_URL
    except Exception:
        concur, test_time, target_url = "1000", "10", DEFAULT_TARGET_URL

    result = run_big_simulation({
        "concurrency": int(concur),
        "duration": int(test_time),
        "target_url": target_url,
    })
    print(f"\n结果: {result.get('status')}")
    if result.get("data") and result["data"].get("stats"):
        s = result["data"]["stats"]
        print(f"  吞吐量: {s.get('throughput', 0)} pages/min")
        print(f"  字节率: {s.get('bytesPerSec', 0)} bytes/sec")
        print(f"  成功请求: {s.get('requestCount', 0)}")
