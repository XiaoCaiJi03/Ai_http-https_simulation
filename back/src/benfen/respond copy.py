"""
响应模块：模拟 HTTP1.1和HTTPS 服务端响应逻辑，支持 Keep-Alive 连接复用，
并能根据请求方法和路径返回不同的响应内容。还有绘制响应时间图的功能。
"""

import time
import uuid
import datetime
import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# --- 仿真内核模型：模拟 TCP 连接状态 ---
@dataclass
class VirtualConnection:
    """模拟服务端视角的 TCP 连接状态，支持 Keep-Alive 特性（含超时自动断开）"""
    id: str
    created_at: float = field(default_factory=time.time)  # 连接创建时间
    last_active: float = field(default_factory=time.time)  # 最后活动时间
    request_count: int = 0  # 该连接上的请求计数
    max_requests: int = 100  # Keep-Alive 最大请求数限制
    timeout: int = 60  # Keep-Alive 超时时间（秒）
    is_closed: bool = False  # 连接是否已关闭

    def is_expired(self) -> bool:
        """检查连接是否因超时过期（超过 Keep-Alive 超时时间无活动）"""
        return (time.time() - self.last_active) > self.timeout

    def touch(self) -> None:
        """更新连接最后活动时间，累加请求计数，达到最大请求数则自动关闭连接"""
        self.last_active = time.time()
        self.request_count += 1
        if self.request_count >= self.max_requests:
            self.is_closed = True

# --- 全局内存连接池：用于复用 TCP 连接（模拟 Keep-Alive 连接复用） ---
connection_pool: Dict[str, VirtualConnection] = {}

# --- 全局配置：HTTP 响应相关常量 ---
HTTP_SERVER = "PySim/1.0 (HTTP/1.1 Simulator)"
HTTP_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"
VALID_HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]

# --- 全局清理函数（主动断开所有过期连接） ---
def cleanup_expired_connections() -> None:
    """遍历全局连接池，主动清理所有过期（超时）或已关闭的连接"""
    expired_conn_ids = []
    for conn_id, conn in connection_pool.items():
        if conn.is_expired():
            conn.is_closed = True
            expired_conn_ids.append(conn_id)
        elif conn.is_closed:
            expired_conn_ids.append(conn_id)
    
    # 批量删除过期/已关闭的连接
    for conn_id in expired_conn_ids:
        if conn_id in connection_pool:
            del connection_pool[conn_id]

# --- 连接管理工具函数：获取或创建连接 ---
def get_or_create_connection(conn_id: Optional[str] = None) -> VirtualConnection:
    """尝试从连接池中复用有效连接，无有效连接则创建新连接并加入连接池"""
    cleanup_expired_connections()
    
    if conn_id and conn_id in connection_pool:
        conn = connection_pool[conn_id]
        if conn.is_expired() or conn.is_closed:
            del connection_pool[conn_id]
        else:
            return conn
    
    new_conn_id = f"TCP-{uuid.uuid4().hex[:8].upper()}"
    new_conn = VirtualConnection(id=new_conn_id)
    connection_pool[new_conn_id] = new_conn
    return new_conn

# --- HTTP 报文解析与校验工具函数 ---
def parse_and_validate_http_request(raw_request: str) -> Tuple[bool, int, str, Dict[str, str], str, Dict[str, str]]:
    """
    解析并校验单个 HTTP 请求报文
    :return: (is_valid, status_code, error_msg, headers, body, request_info)
    注意：为了防止解包错误，所有返回路径必须返回 6 个元素
    """
    is_valid = True
    status_code = 200
    error_msg = ""
    headers = {}
    body = ""
    request_info = {} # 默认空字典
    
    if not raw_request or not raw_request.strip():
        return (False, 400, "Empty Request", {}, "", {})

    request_lines = [line.rstrip('\r\n') for line in raw_request.split('\n')]  # 保留行结构
    
    # 步骤1：校验请求行
    if not request_lines or not request_lines[0].strip():
        return (False, 400, "缺少有效请求行", {}, "", {})
    
    request_line = request_lines[0].strip()
    request_parts = request_line.split()
    
    # 兼容性处理：防止 split 后长度不够导致 panic
    # 例如输入 "POST /api/log" (缺少 HTTP/1.1)，len 为 2
    if len(request_parts) < 3:
        return (False, 400, "请求行格式错误（应为：方法 路径 HTTP/1.1）", {}, "", {})
    
    # 获取方法、路径、协议（忽略多余的空格部分）
    method = request_parts[0].upper()
    path = request_parts[1]
    protocol = request_parts[2].upper()
    
    # 校验请求方法
    if method not in VALID_HTTP_METHODS:
        return (False, 405, f"不支持的请求方法：{method}", {}, "", {})
    
    # 校验协议版本 (前端虽然不做限制，但后端仿真器目前仅支持 HTTP/1.1)
    if "HTTP/1.1" not in protocol:
        return (False, 505, "仅支持 HTTP/1.1 协议版本", {}, "", {})
    
    # 步骤2：解析并校验请求头
    header_line_index = 1
    has_empty_line = False
    while header_line_index < len(request_lines):
        line = request_lines[header_line_index]
        
        # 遇到空行，结束头解析
        if line.strip() == "":
            has_empty_line = True
            header_line_index += 1
            break
        
        # 校验头格式
        if ":" not in line:
            # 遇到非法头，返回 400
            return (False, 400, f"请求头格式错误：{line}", {}, "", {})
        
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        headers[key] = value
        
        header_line_index += 1
    
    # 步骤3：校验 HTTP/1.1 强制头（Host）
    if "host" not in headers:
        return (False, 400, "缺少 HTTP/1.1 强制要求的 Host 头", {}, "", {})
    
    if not headers.get("host", "").strip():
        return (False, 400, "Host 头字段值不能为空", {}, "", {})
    
    # 步骤4：解析请求体（空行之后的内容）
    if has_empty_line and header_line_index <= len(request_lines):
        body = "\n".join(request_lines[header_line_index:]).strip()
    
    # 步骤5：检查路径是否合法（简单校验）
    if not path.startswith("/"):
        return (False, 404, "请求路径格式错误（应以 / 开头）", {}, "", {})
    
    # 成功返回 6 个值
    return (is_valid, status_code, error_msg, headers, body, {"method": method, "path": path})

# --- HTTP 错误响应生成函数 ---
def generate_http_error_response(status_code: int, headers: Dict[str, str]) -> str:
    """生成符合 HTTP 标准的错误响应报文"""
    status_messages = {
        400: "Bad Request",
        404: "Not Found",
        405: "Method Not Allowed",
        401: "Unauthorized",
        500: "Internal Server Error",
        505: "HTTP Version Not Supported"
    }
    
    status_msg = status_messages.get(status_code, "Bad Request")
    current_gmt = datetime.datetime.utcnow().strftime(HTTP_DATE_FORMAT)
    connection_header = headers.get("connection", "close").lower()
    
    # 构建错误响应体
    error_body = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{status_code} {status_msg}</title>
</head>
<body>
    <h1>{status_code} {status_msg}</h1>
    <p>请求处理失败：{status_messages.get(status_code)}</p>
    <hr>
    <p>{HTTP_SERVER}</p>
</body>
</html>
""".strip()
    
    # 构建响应头
    response_headers = [
        f"HTTP/1.1 {status_code} {status_msg}",
        f"Date: {current_gmt}",
        f"Server: {HTTP_SERVER}",
        f"Content-Type: text/html; charset=utf-8",
        f"Content-Length: {len(error_body.encode('utf-8'))}",
        f"Connection: {connection_header}"
    ]
    
    # 拼接完整响应
    return "\r\n".join(response_headers) + "\r\n\r\n" + error_body

# --- 请求类型识别与正常响应生成函数 ---
def judge_request_type_and_generate_response(headers: Dict[str, str], body: str, request_info: Dict[str, str], is_https: bool = False) -> str:
    """
    识别请求类型（登录/普通），生成符合实际的 HTTP 正常响应
    """
    method = request_info["method"]
    path = request_info["path"]
    current_gmt = datetime.datetime.utcnow().strftime(HTTP_DATE_FORMAT)
    connection_header = headers.get("connection", "keep-alive").lower()
    scheme = "https" if is_https else "http"
    
    # 场景1：登录请求识别（/login 或 /api/login 路径 + POST 方法）
    # 兼容前端模板中的 /api/login
    if ("/login" in path) and method == "POST":
        content_type = headers.get("content-type", "").lower()
        response_body = ""
        
        username = ""
        password = ""
        is_secure_login = False

        # 解析登录参数（支持 json 和 form 格式）
        if "application/json" in content_type:
            try:
                login_data = json.loads(body) if body else {}
                username = login_data.get("username", "")
                password = login_data.get("password", "")
                # 兼容前端 HTTPS 模板的 {"secure": true}
                is_secure_login = login_data.get("secure", False)
            except Exception:
                return generate_http_error_response(400, headers)
        elif "application/x-www-form-urlencoded" in content_type:
            from urllib.parse import parse_qs
            login_data = parse_qs(body) if body else {}
            username = login_data.get("username", [""])[0]
            password = login_data.get("password", [""])[0]
        
        # 登录响应校验：
        # 1. 用户名 admin + 密码 123456
        # 2. 或者 用户名 admin + secure=true (前端 HTTPS 模板)
        if username == "admin" and (password == "123456" or is_secure_login):
            # 登录成功
            response_body = json.dumps({
                "code": 200,
                "msg": "Login Successful",
                "data": {
                    "token": f"TOKEN_{uuid.uuid4().hex[:16].upper()}",
                    "expire_at": (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).isoformat(),
                    "protocol": "TLSv1.3" if is_https else "Plaintext"
                }
            })
            content_type = "application/json; charset=utf-8"
        else:
            # 登录失败（401 未授权）
            return generate_http_error_response(401, headers)
    
    # 场景2：普通请求响应
    else:
        response_body = f"""
{{
    "code": 200,
    "msg": "Request Processed Successfully",
    "data": {{
        "method": "{method}",
        "url": "{scheme}://{headers.get('host')}{path}",
        "protocol": "{'HTTPS' if is_https else 'HTTP'}",
        "request_id": "{uuid.uuid4().hex[:8]}",
        "server_time": "{current_gmt}"
    }}
}}
""".strip()
        content_type = "application/json; charset=utf-8"
    
    # 构建正常响应头
    response_headers = [
        f"HTTP/1.1 200 OK",
        f"Date: {current_gmt}",
        f"Server: {HTTP_SERVER}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(response_body.encode('utf-8'))}",
        f"Connection: {connection_header}"
    ]
    
    # 拼接完整响应
    return "\r\n".join(response_headers) + "\r\n\r\n" + response_body

# --- HTTP 请求拆分工具：精准拆分管道化多请求 ---
def split_pipeline_requests(raw_text: str) -> List[str]:
    """从原始文本中精准拆分多个 HTTP 请求（管道化请求），返回单个请求列表"""
    if not raw_text or not raw_text.strip():
        return []
    
    # 正则匹配常见的 HTTP 方法开头
    request_line_pattern = r'(?im)^(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH) \S+ HTTP/1\.1'
    request_starts = [match.start() for match in re.finditer(request_line_pattern, raw_text)]
    
    # 如果没找到标准头，可能是乱码，直接作为一个整体处理（让校验函数去报错）
    if not request_starts:
        return [raw_text]

    split_requests = []
    for idx in range(len(request_starts)):
        start_pos = request_starts[idx]
        end_pos = request_starts[idx+1] if (idx+1) < len(request_starts) else len(raw_text)
        single_request = raw_text[start_pos:end_pos].strip()
        if single_request:
            split_requests.append(single_request)
    
    return split_requests if split_requests else [raw_text.strip()]

# --- 核心业务入口：处理 HTTP 仿真请求 ---
def handle_http_simulation(
    raw_content: str,
    client_conn_id: Optional[str] = None,
    is_https: bool = False
) -> Dict:
    """核心入口：处理 HTTP 仿真请求，支持格式校验和请求类型识别"""
    cleanup_expired_connections()
    request_list = split_pipeline_requests(raw_content)
    is_pipeline_mode = len(request_list) > 1
    response_list: List[str] = []
    
    # 获取或创建连接
    current_connection = get_or_create_connection(client_conn_id)
    if current_connection.is_expired():
        current_connection.is_closed = True
        if current_connection.id in connection_pool:
            del connection_pool[current_connection.id]
    
    # 逐个处理请求（管道模式）
    hol_blocking_delay = 800
    for request_idx, single_request in enumerate(request_list):
        # 如果连接已关闭或过期，停止处理后续管道请求
        if current_connection.is_closed or current_connection.is_expired():
            break
        
        current_connection.touch()
        # 模拟队头阻塞（仅管道模式的第一个请求后不延迟，这里简单模拟整体延迟）
        if is_pipeline_mode and request_idx == 0:
            time.sleep(hol_blocking_delay / 1000)
        
        # 解析并校验 HTTP 请求
        # 注意：这里会解包 6 个值，parse_and_validate_http_request 必须返回 6 个值
        is_valid, status_code, error_msg, headers, body, request_info = parse_and_validate_http_request(single_request)
        
        # 生成响应（错误/正常）
        if not is_valid:
            # 格式错误，生成错误响应并关闭连接
            response = generate_http_error_response(status_code, headers)
            current_connection.is_closed = True
        else:
            # 正常响应，传入 is_https 标记
            response = judge_request_type_and_generate_response(headers, body, request_info, is_https)
            
            # 检查 Connection: close 头
            if headers.get("connection", "").lower() == "close":
                current_connection.is_closed = True

        response_list.append(response)
    
    # 处理连接关闭逻辑（如果任何一个请求触发了 close）
    if current_connection.is_closed:
        if current_connection.id in connection_pool:
            connection_pool[current_connection.id] = current_connection
    
    # 构造返回结果
    current_local_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    single_response_content = response_list[0] if len(response_list) == 1 else ""
    
    return {
        "sessionId": current_connection.id,
        "createTime": current_local_time,
        "httpResponseContent": single_response_content,
        "responses": response_list,
        "connectionStatus": "closed" if current_connection.is_closed else "active",
        "keepAliveInfo": {
            "timeout": current_connection.timeout,
            "max": current_connection.max_requests,
            "used": current_connection.request_count
        },
        "meta": {
            "isPipeline": is_pipeline_mode,
            "holDelay": hol_blocking_delay if is_pipeline_mode else 0
        }
    }

# --- 辅助功能：处理并发压测仿真 ---
def handle_concurrent_simulation(num_concurrent: int) -> Dict:
    """并发压测仿真辅助函数，返回模拟的并发测试结果"""
    time.sleep(1.0)
    
    success_count = int(num_concurrent * 0.99)
    failed_count = num_concurrent - success_count
    elapsed_time = 2.5
    qps_value = num_concurrent / elapsed_time

    return {
        "sessionId": f"LOAD-{uuid.uuid4().hex[:6]}",
        "createTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "httpResponseContent": "",
        "concurrent": {
            "total": num_concurrent,
            "success": success_count,
            "failed": failed_count,
            "elapsed": round(elapsed_time, 2),
            "qps": round(qps_value, 2)
        },
        "mode": "concurrent"
    }
