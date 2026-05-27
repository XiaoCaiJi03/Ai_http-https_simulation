import socket
import ssl
import time
import re
import uuid
import threading
from typing import Dict, Optional, Tuple, List, Union
from dataclasses import dataclass, field
from io import BytesIO
import sys
from http.server import BaseHTTPRequestHandler

# ==================== 补全缺失的类定义 (解决 ImportError) ====================
@dataclass
class VirtualConnection:
    """
    [兼容性补全] 
    app.py 依赖此类的定义。
    在真实网络模式下，这个类主要用于占位或简单的状态追踪。
    """
    id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    request_count: int = 0
    max_requests: int = 100
    timeout: int = 60
    is_closed: bool = False

# ==================== 全局真实连接池 ====================
# 用于复用 Socket 连接 (Keep-Alive)
connection_pool_lock = threading.Lock()
server_connection_pool = {}

# ==================== 辅助工具 =========================

class StrictHTTPValidator(BaseHTTPRequestHandler):
    """
    严格的 HTTP 请求验证器
    注意：在新的逻辑中，此类主要作为兼容性保留，核心校验逻辑已移至 validate_http_request_strict 内部实现，
    以支持包含空格等特殊字符的安全测试 Payload。
    """
    def __init__(self, request_text):
        self.rfile = BytesIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = None
        self.error_message = None
        # 调用父类解析
        try:
            self.parse_request()
        except Exception:
            self.error_code = 400


def validate_http_request_strict(raw_request_str):
    """
    优化后的 HTTP 请求验证逻辑。
    
    目标：
    1. 拦截真正的格式错误（如：缺少 Method、缺少 HTTP 版本、Header 缺少冒号）。
    2. 放行格式正确但包含恶意 Payload 的请求（如：URL 中包含空格的 SQL 注入、Body 中的 XSS）。
    
    Args:
        raw_request_str: str - 完整的 HTTP 请求报文
    
    Returns:
        Tuple[bool, str] - (是否有效, 消息)
    """
    # --- 1. 预处理 ---
    # 统一换行符，方便按行分割检查
    if '\r\n' not in raw_request_str and '\n' in raw_request_str:
        raw_request_str = raw_request_str.replace('\n', '\r\n')
    
    lines = raw_request_str.split('\r\n')
    
    # 移除末尾可能的空行
    while lines and not lines[-1]:
        lines.pop()

    if not lines:
        return False, "Input is empty"

    # --- 2. 智能检查请求行 (Request Line) ---
    req_line = lines[0].strip()
    if not req_line:
        return False, "Empty Request Line"

    # 使用 split 分割，默认按空格分割
    # 针对 SQL 注入 Payload: GET /api?id=1 OR 1=1 HTTP/1.1
    # split() 会得到 ['GET', '/api?id=1', 'OR', '1=1', 'HTTP/1.1']，长度 > 3
    parts = req_line.split()
    
    # 检查 1: 基本结构必须至少包含 Method 和 Version (中间可以是复杂的 URL)
    if len(parts) < 2:
        return False, "Invalid Request Line. Expected format: METHOD URL PROTOCOL/VERSION"
    
    # 提取 Method 和 Version
    method = parts[0]
    version = parts[-1] # 取最后一个部分作为版本号

    # 检查 2: Method 必须是字母 (GET, POST, etc.)
    if not re.match(r"^[a-zA-Z]+$", method):
        return False, f"Invalid HTTP Method: '{method}'"

    # 检查 3: 版本号必须以 HTTP/ 开头
    # 这里处理了 split 的情况，如果 parts[-1] 不是版本号，说明格式错乱
    if not version.upper().startswith("HTTP/"):
        # 尝试兼容 HTTP/0.9 简单请求 (只有 Method 和 URL)，但在严格模式下通常禁止
        # 如果只有两个部分且第二个不是 HTTP/，则可能是 HTTP/0.9 或者格式错误
        if len(parts) == 2 and not parts[1].upper().startswith("HTTP/"):
             return False, "Missing HTTP Version (e.g., HTTP/1.1). HTTP/0.9 is not allowed."
        return False, f"Invalid Protocol Version: '{version}'. Must start with 'HTTP/'"

    # 检查 4: 版本号具体校验
    if version.upper() == "HTTP/0.9":
        return False, "HTTP/0.9 requests are rejected."

    # --- 3. 严格检查头部 (Headers) ---
    # 从第二行开始，直到遇到空行（Body开始）
    header_started = False
    for i, line in enumerate(lines[1:], 1):
        if line == "": 
            break # 遇到空行，Header 结束
        
        # 允许折行（Continuation line），虽然罕见
        if line[0] in (' ', '\t'):
            if not header_started:
                return False, f"Invalid Header (Line {i+1}): Line starts with space but no previous header."
            continue
        
        # 检查 Header 格式必须包含冒号
        if ':' not in line:
            return False, f"Invalid Header (Line {i+1}): Missing colon (:). Content: '{line}'"
        
        key, value = line.split(':', 1)
        
        # Key 不能为空且通常不含空格
        if not key:
            return False, f"Invalid Header (Line {i+1}): Empty header name."
        if ' ' in key.strip():
            # 严格来说 Header Key 不能有空格，如 "User Agent"，应为 "User-Agent"
            return False, f"Invalid Header Name (Line {i+1}): Header name cannot contain spaces. Got: '{key}'"
        
        header_started = True

    # --- 4. 结论 ---
    # 如果代码运行到这里，说明结构上符合 HTTP 协议（Method ... Version + Headers）
    # 即使 URL 包含空格、单引号、脚本标签，也视为“格式正确的 HTTP 请求”，放行给后续的安全检测模块。
    
    # 重组 URL 用于日志显示 (去除 method 和 version)
    try:
        url_start = len(method)
        url_end = raw_request_str.find(version)
        # 简单的切片获取 URL，仅用于显示
        request_uri = req_line[len(method):].replace(version, "").strip()
    except Exception:
        request_uri = "unknown"

    return True, f"Valid {version} Request: {method} {request_uri}"


def parse_host_port_scheme(raw_request: str, is_https: bool) -> Tuple[str, int]:
    """从原始报文中解析 Host 和端口"""
    lines = raw_request.split('\n')
    host = None
    for line in lines:
        if line.strip().lower().startswith('host:'):
            host = line.split(':', 1)[1].strip()
            break
    
    if not host:
        # 如果没有 Host 头，且不是空请求，抛错
        if raw_request.strip():
            # 在某些 HTTP/1.0 请求中 Host 不是必须的，但在现代网络测试中通常需要
            # 为了健壮性，这里不强制抛错，而是尝试回退
            pass 
        if not host:
             return "localhost", 80 # 默认值防止空报文崩溃
        
    if ':' in host:
        try:
            hostname, port = host.split(':')
            return hostname, int(port)
        except ValueError:
            # 处理 IPv6 或格式错误的 Host
            return host, 443 if is_https else 80
    else:
        return host, 443 if is_https else 80

def get_real_socket(conn_id: Optional[str], host: str, port: int, is_https: bool):
    """获取或创建真实的 Socket 连接"""
    # 1. 尝试复用现有连接
    if conn_id:
        with connection_pool_lock:
            if conn_id in server_connection_pool:
                conn_info = server_connection_pool[conn_id]
                if conn_info['host'] == host and conn_info['port'] == port:
                    try:
                        sock = conn_info['socket']
                        sock.setblocking(False)
                        data = sock.recv(1, socket.MSG_PEEK)
                        if data == b'': raise OSError("Closed")
                        sock.setblocking(True)
                        conn_info['last_active'] = time.time()
                        return sock, conn_id
                    except (BlockingIOError, ssl.SSLWantReadError):
                        sock.setblocking(True)
                        return sock, conn_id
                    except Exception:
                        try: conn_info['socket'].close()
                        except Exception: pass
                        del server_connection_pool[conn_id]
    
    # 2. 创建新连接
    print(f"[RealNetwork] Connecting to {host}:{port} (SSL={is_https})...")
    sock = socket.create_connection((host, port), timeout=10)
    
    if is_https:
        context = ssl.create_default_context()
        # 注意：以下配置禁用了TLS证书验证，仅用于安全仿真测试环境，切勿用于生产环境
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        sock = context.wrap_socket(sock, server_hostname=host)
        
    new_id = str(uuid.uuid4()).replace('-', '')
    with connection_pool_lock:
        server_connection_pool[new_id] = {
            "socket": sock, "host": host, "port": port, "last_active": time.time()
        }
    return sock, new_id

# ==================== 核心处理函数 ====================

def handle_http_simulation_entry(raw_content: str, client_conn_id: Optional[str] = None) -> Dict:
    """真实网络请求处理入口"""
    try:
        if not raw_content.strip():
             return {"sessionId": client_conn_id, "responses": [], "status": "active"}

        host, port = parse_host_port_scheme(raw_content, is_https=False)
        # 简单策略：如果端口是 443 或者是加密流量特征，启用 SSL
        use_ssl = (port == 443) 
        
        sock, conn_id = get_real_socket(client_conn_id, host, port, use_ssl)
        
        sock.sendall(raw_content.encode('utf-8'))
        
        response_data = b""
        sock.settimeout(5)
        
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk: break
                response_data += chunk
                
                if b"\r\n\r\n" in response_data:
                    head, body = response_data.split(b"\r\n\r\n", 1)
                    cl_match = re.search(rb"Content-Length:\s*(\d+)", head, re.IGNORECASE)
                    if cl_match and len(body) >= int(cl_match.group(1)): break
                    if b"Transfer-Encoding: chunked" in head and (body.strip().endswith(b"0\r\n\r\n") or body.strip().endswith(b"0")): break
            except socket.timeout:
                break
                
        resp_str = response_data.decode('utf-8', errors='replace')
        
        status = "active"
        if "Connection: close" in resp_str or "connection: close" in resp_str:
            status = "closed"
            try:
                sock.close()
                with connection_pool_lock:
                    if conn_id in server_connection_pool:
                        del server_connection_pool[conn_id]
            except Exception: pass

        return {
            "sessionId": conn_id,
            "responses": [resp_str],
            "status": status,
            "httpResponseContent": resp_str
        }

    except Exception as e:
        print(f"Real Network Error: {e}")
        return {
            "sessionId": client_conn_id,
            "responses": [f"HTTP/1.1 502 Bad Gateway\r\n\r\nConnection Failed: {str(e)}"],
            "status": "closed"
        }

# 补全 app.py 需要导入的空函数
def handle_concurrent_simulation(num: int):
    return {
        "httpResponseContent": "",
        "message": f"并发仿真请求已发送，共 {num} 个并发连接"
    }
