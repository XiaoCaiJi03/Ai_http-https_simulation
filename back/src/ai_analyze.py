import os
from volcenginesdkarkruntime import Ark
import json
import re

ARK_API_KEY = os.getenv("ARK_API_KEY")
if not ARK_API_KEY:
    print("[WARNING] ARK_API_KEY environment variable not set. AI analysis features will be disabled.")
DEFAULT_MODEL = "doubao-seed-1-6-251015"

ark_client = Ark(api_key=ARK_API_KEY) if ARK_API_KEY else None

def chat_with_ai(prompt, model=DEFAULT_MODEL):
    """
    基础AI调用函数（支持流式响应）
    :param prompt: 用户的提问/生成指令（字符串）
    :param model: 使用的模型名称
    :return: 元组 (success: bool, content: str, reasoning_content: str)
    """

    try:
        if not ark_client:
            return False, "AI 分析功能未启用（ARK_API_KEY 未设置）", ""
        resp = ark_client.chat.completions.create(
            model=model,
            messages=[{"content": prompt, "role": "user"}],
            stream=True,  # 保留流式响应
            stream_options={"include_usage": False},
            thinking={"type": "disabled"},
        )

        # 迭代流式响应，拼接完整内容
        content = ""
        reasoning_content = ""
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content
            # 推理内容同理（如果有）
            if chunk.choices and hasattr(chunk.choices[0].delta, 'reasoning_content'):
                reasoning_content += chunk.choices[0].delta.reasoning_content or ""

        return True, content, reasoning_content
    except Exception as e:
        return False, f"调用出错：{str(e)}", ""


# ========== 核心修改：新增报文分析函数 ==========
def analyze_http_request_response(request_msg: str, response_msg: str):
    """
    分析给定的HTTP请求+响应报文，输出详细的字段解析和异常分析（忽略响应体HTML）
    :param request_msg: 原始HTTP请求报文字符串
    :param response_msg: 原始HTTP响应报文字符串
    :return: 元组 (success: bool, content: str)
    """
    # 定制化Prompt：明确忽略响应体的HTML代码，仅分析响应的状态行、响应头
    prompt = f"""
            # Role
            你是一名资深的网络安全与HTTP协议专家。你的任务是对提供的 HTTP 流量进行深度审计与分析。
            
            # Context
            用户提供了一组 HTTP 请求和响应报文。
            **注意：响应报文的 Body 部分可能已被代码截断或包含大量 HTML/JS 代码。你必须完全忽略响应体（Response Body）的具体内容，只关注协议头部行为。**
            
            # Analysis Requirements
            请严格按照以下三个维度进行分析，输出 markdown 格式：
            
            1. **请求报文透视 (Request Analysis)**
               - 简述请求行（Method, URL, Version）。
               - 解析关键 Header 的作用。
            
            2. **响应头与状态审计 (Response Headers Audit)**
               - 分析状态码含义。
               - **重点分析**：`Set-Cookie` (是否包含 Secure/HttpOnly)、`Connection`、`Server`、`X-Xss-Protection` 等安全或控制字段。
               - **禁止**：不要解读 HTML 文本内容（如不要解释“百度首页包含搜索框”之类的 UI 信息）。
            
            3. **安全与异常诊断 (Security & Diagnostics)**
               - 检查是否存在敏感信息泄露。
               - 总结连接模式（Keep-Alive 或 Close）。
               - 给出整体的安全评分或建议（低/中/高风险）。

    待分析的请求报文：
    {request_msg}

    待分析的响应报文：
    {response_msg}
    """
    # 调用AI进行分析
    success, content, _ = chat_with_ai(prompt)
    return success, content

# ========== 新增：AI 流量样本生成函数 ==========
def generate_traffic_samples(count=10):
    """
    调用 AI 生成指定数量的 HTTP 请求样本（混合正常和恶意），用于测试检测模型。
    :param count: 生成的总数量（建议 10-30，太多可能会超时或截断）
    :return: (success: bool, samples: list)
    """

    # 构造 Prompt：要求 AI 生成 JSON 数组格式
    prompt = f"""
    # Role
    你是一名网络安全红队专家和数据生成助手。

    # Task
    请生成 {count} 条原始 HTTP 请求报文样本。

    # Requirements
    1. **数据分布**：请确保样本中约 50% 是正常业务请求（如登录、搜索、静态资源访问），另外 50% 是常见的 Web 攻击请求（如 SQL注入、XSS、命令注入、目录遍历、WebShell上传等）。
    2. **格式要求**：
       - 直接返回一个标准的 **JSON 字符串数组**。
       - 数组中的每个元素是一个字符串，代表一个完整的 HTTP 请求（包含方法、URL、协议版本和必要的 Header）。
       - 不要包含 Markdown 代码块标记（如 ```json），不要包含任何解释性文字。
       - 确保 HTTP 报文中的换行符使用 `\\n` 转义。
    3. **长度控制**：
       - 为了防止超时，Payload 不要过于冗长，保持典型特征即可。
       - 只要生成符合数量要求的数组即可，不需要额外的寒暄。

    # Example Output
    [
      "GET /index.html HTTP/1.1\\nHost: example.com\\nUser-Agent: Mozilla/5.0",
      "POST /login HTTP/1.1\\nHost: target.com\\nContent-Type: application/json\\n\\n{{\\"u\\": \\"admin' OR 1=1--\\"}}"
    ]
    """

    success, content, _ = chat_with_ai(prompt)

    if not success:
        return False, []

    # 数据清洗与解析
    try:
        # 1. 尝试清洗可能存在的 markdown 标记
        cleaned_content = content.replace("```json", "").replace("```", "").strip()

        # 2. 解析 JSON
        samples = json.loads(cleaned_content)

        if isinstance(samples, list):
            return True, samples
        else:
            return False, []
    except json.JSONDecodeError:
        print(f"❌ JSON 解析失败，AI 返回原始内容：{content}")
        # 备用方案：如果 JSON 解析失败，尝试用正则提取简单的请求（仅作容错）
        return False, []
    except Exception as e:
        print(f"❌ 样本生成处理异常: {str(e)}")
        return False, []

# ========== 调整调用逻辑：传入你的实际报文内容 ==========
if __name__ == "__main__":
    print("=== HTTP请求/响应报文详细分析 ===")

    # 你的原始请求报文（整理为字符串，保留原始格式）
    request_message = """GET /index.html HTTP/1.1
        Host: www.example.com
        User-Agent: Simulation-Lab/1.0
        Connection: keep-alive
        Accept: */*"""

    # 你的原始响应报文（整理为字符串，保留原始格式）
    response_message = """HTTP/1.1 200 OK

Bdpagetype: 1

Bdqid: 0xc58efb0704a186f1

Connection: keep-alive

Content-Length: 645387

Content-Type: text/html; charset=utf-8

Date: Wed, 07 Jan 2026 08:43:08 GMT

P3p: CP=" OTI DSP COR IVA OUR IND COM "

P3p: CP=" OTI DSP COR IVA OUR IND COM "

Server: BWS/1.1

Set-Cookie: BAIDUID=0BD894E6A09F3E3979F339C70192FDB3:FG=1; expires=Thu, 31-Dec-37 23:55:55 GMT; max-age=2147483647; path=/; domain=.baidu.com

Set-Cookie: BIDUPSID=0BD894E6A09F3E3979F339C70192FDB3; expires=Thu, 31-Dec-37 23:55:55 GMT; max-age=2147483647; path=/; domain=.baidu.com

Set-Cookie: PSTM=1767775388; expires=Thu, 31-Dec-37 23:55:55 GMT; max-age=2147483647; path=/; domain=.baidu.com

Set-Cookie: BAIDUID=0BD894E6A09F3E39082E263F58CC4BF0:FG=1; max-age=31536000; expires=Thu, 07-Jan-27 08:43:08 GMT; domain=.baidu.com; path=/; version=1; comment=bd

Set-Cookie: BDSVRTM=1; path=/

Set-Cookie: BD_HOME=1; path=/

Tr_id: super_0xc58efb0704a186f1

Traceid: 1767775388174881690614235591479725754097

Vary: Accept-Encoding

X-Ua-Compatible: IE=Edge,chrome=1

X-Xss-Protection: 1;mode=block

        0"""

    # 调用分析函数
    success, content = analyze_http_request_response(request_message, response_message)
    if success:
        print(content)
    else:
        print(f"分析失败：{content}")