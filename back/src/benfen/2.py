import sys
from http.server import BaseHTTPRequestHandler
from io import BytesIO

class StrictHTTPValidator(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.rfile = BytesIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = None
        self.error_message = None
        # 调用父类解析
        self.parse_request()

    def send_error(self, code, message=None, explain=None):
        self.error_code = code
        self.error_message = message or explain
    
    def log_message(self, format, *args):
        pass

def validate_http_request_strict(raw_request_str):
    # --- 1. 预处理 ---
    # 统一换行符，方便按行分割检查
    if '\r\n' not in raw_request_str and '\n' in raw_request_str:
        raw_request_str = raw_request_str.replace('\n', '\r\n')
    
    lines = raw_request_str.split('\r\n')
    
    # 移除末尾可能的空行，防止索引溢出，但在判断 Body 分隔时要注意
    while lines and not lines[-1]:
        lines.pop()

    if not lines:
        return False, "Input is empty"

    # --- 2. 严格检查请求行 (Request Line) ---
    req_line = lines[0]
    parts = req_line.split()
    
    # 检查 1: 必须包含 3 部分：METHOD URL VERSION
    if len(parts) != 3:
        if len(parts) == 2:
            return False, "Missing HTTP Version (e.g., HTTP/1.1). HTTP/0.9 is not allowed in strict mode."
        return False, "Invalid Request Line format. Expected: METHOD URL PROTOCOL/VERSION"

    method, path, version = parts

    # 检查 2: 版本号必须以 HTTP/ 开头
    if not version.upper().startswith("HTTP/"):
        return False, f"Invalid Protocol Version: '{version}'. Must start with 'HTTP/'"

    # --- 3. 严格检查头部 (Headers) ---
    # 从第二行开始，直到遇到空行（Body开始）
    header_started = False
    for i, line in enumerate(lines[1:], 1):
        if line == "": 
            break # 遇到空行，Header 结束
        
        # 检查 3: Header 格式必须是 Key: Value
        # 注意：HTTP 允许折行（以空格开头），但现代 HTTP 很少用，严格模式下可以报错或跳过
        if line[0] in (' ', '\t'):
            # 这是一个折行（Continuation line），检查上一行是否存在
            if not header_started:
                return False, f"Invalid Header (Line {i+1}): Line starts with space but no previous header."
            continue
        
        if ':' not in line:
            return False, f"Invalid Header (Line {i+1}): Missing colon (:). Content: '{line}'"
        
        key, value = line.split(':', 1)
        if not key:
            return False, f"Invalid Header (Line {i+1}): Empty header name."
        
        header_started = True

    # --- 4. 使用标准库进行语义解析 (兜底检查) ---
    # 前面的正则/字符串检查通过后，再用标准库检查逻辑是否合法
    request_bytes = raw_request_str.encode('utf-8')
    try:
        handler = StrictHTTPValidator(request_bytes)
        if handler.error_code:
            return False, f"Parser Error {handler.error_code}: {handler.error_message}"
        
        # 再次确认版本号不是 0.9 (标准库解析后的确认)
        if handler.request_version == 'HTTP/0.9':
             return False, "HTTP/0.9 requests are rejected."

        return True, f"Valid {handler.request_version} Request: {handler.command} {handler.path}"

    except Exception as e:
        return False, f"Exception: {str(e)}"

if __name__ == "__main__":
    print("="*60)
    print("HTTP 请求语法检测器 (严格模式)")
    print("请输入原始 HTTP 请求报文 (输入 'END' 单独一行结束输入):")
    print("="*60)

    input_lines = []
    while True:
        try:
            line = input()
            if line.strip() == 'END':
                break
            input_lines.append(line)
        except EOFError:
            break
    
    raw_request = "\n".join(input_lines)
    
    # 补全末尾换行以便解析
    if raw_request and not raw_request.endswith("\n"):
        raw_request += "\n\n"

    print("-" * 25 + " 检测结果 " + "-" * 25)
    
    is_valid, message = validate_http_request_strict(raw_request)
    
    if is_valid:
        print(f"✅ 语法正确\n详情: {message}")
    else:
        print(f"❌ 语法错误\n原因: {message}")
