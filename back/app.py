#/back/app.py
import os
import sys
import time
from datetime import datetime
import json
from uuid import uuid4
from flask import Flask, request, jsonify
from flask_cors import CORS
import glob
import re
from src.ai_analyze import analyze_http_request_response, generate_traffic_samples

# ========== 第一步：目录路径定义与环境配置 ==========
BACK_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BACK_DIR, 'src')

# 验证src目录
if not os.path.exists(SRC_DIR) or not os.path.isdir(SRC_DIR):
    print(f"❌ 致命错误：src目录不存在（路径：{SRC_DIR}）")
    sys.exit(1)

sys.path.append(SRC_DIR)

# ========== 第二步：导入核心模块（仅保留 respond, security, big_simulator） ==========
try:
    # --- 核心修改：正确导入 respond.py 中的函数 ---
    from src.respond import (
        handle_http_simulation_entry as handle_http_simulation, # 导入并重命名，匹配下方调用
        handle_concurrent_simulation,
        VirtualConnection,
        server_connection_pool as connection_pool # 重命名导入，适配变量名
    )
    from src.security import HijackSimulator, CertGenerator, TlsSimulationManager
    # 导入大并发模拟模块
    from src.big_simulator import run_big_simulation
    # 导入恶意报文检测模块
    from src.malicious_detector import predict_http_request
    print("✅ 核心模块导入成功")
except ImportError as e:
    print(f"❌ 模块导入失败：{e}")
    sys.exit(1)

# ========== 第三步：初始化辅助工具 ==========
def check_connection_header(raw_http_request: str) -> str:
    if not raw_http_request or not isinstance(raw_http_request, str):
        return "unknown"
    connection_pattern = r'Connection:\s*([a-zA-Z\-]+)'
    matches = re.findall(connection_pattern, raw_http_request, re.IGNORECASE)
    if not matches:
        return "unknown"
    connection_value = matches[-1].lower()
    return "keep-alive" if connection_value == "keep-alive" else "close" if connection_value == "close" else "unknown"

hijack_simulator = HijackSimulator()
cert_generator = CertGenerator()
tls_simulator = TlsSimulationManager()

# ========== 初始化Flask应用 ==========
app = Flask(__name__)
# 优化CORS配置，处理预检请求
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": "*",
        "expose_headers": "*"
    }
})

# 处理OPTIONS请求，确保预检请求返回200状态码
@app.before_request
def handle_options():
    if request.method == 'OPTIONS':
        return '', 200

# ========== 第四步：注册TLS1.3相关路由 ==========
@app.route('/api/security/tls13/simulate', methods=['POST'])
def simulate_tls13_route():
    try:
        from src.security import tls_simulator as security_tls_simulator
        data = request.json or {}
        msg = data.get('message', 'Secret Data Transfer')
        result = security_tls_simulator.execute_simulation(msg_content=msg)
        if "error" in result:
            return jsonify({"code": 500, "msg": result["error"]}), 500
        return jsonify({"code": 200, "msg": "TLS Simulation Complete", "data": result})
    except Exception as e:
        print(f"❌ TLS Route Error: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)}), 500

@app.route('/api/security/tls13/check-tshark', methods=['GET'])
def check_tshark_route():
    """检查 tshark 状态的 API"""
    try:
        from src.security import tls_simulator as security_tls_simulator
        info = security_tls_simulator.get_tshark_info()
        return jsonify({"code": 200, "data": info})
    except Exception as e:
        print(f"❌ Check Tshark Error: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)}), 500

@app.route('/api/security/tls13/test-capture', methods=['POST'])
def test_capture_route():
    """测试抓包功能"""
    try:
        from src.security import tls_simulator as security_tls_simulator
        from src.security import TSHARK_AVAILABLE, TLS_PCAP_DIR
        
        if not TSHARK_AVAILABLE:
            return jsonify({"code": 500, "msg": "tshark 不可用"})
        
        # 简单测试：抓包 3 秒
        test_pcap = os.path.join(TLS_PCAP_DIR, f"test_{int(time.time())}.pcap")
        
        interface = security_tls_simulator._get_loopback_interface()
        
        stdout, stderr, returncode = security_tls_simulator._run_tshark_command([
            "-i", interface,
            "-a", "duration:3",
            "-w", test_pcap,
            "-q"
        ], timeout=10)
        
        result = {
            "interface": interface,
            "pcap_path": test_pcap,
            "pcap_exists": os.path.exists(test_pcap),
            "pcap_size": os.path.getsize(test_pcap) if os.path.exists(test_pcap) else 0,
            "returncode": returncode,
            "stderr": stderr
        }
        
        # 清理测试文件
        if os.path.exists(test_pcap):
            os.remove(test_pcap)
            
        return jsonify({"code": 200, "data": result})
        
    except Exception as e:
        print(f"❌ Test Capture Error: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)}), 500

# ========== 目录路径配置（彻底脱离 Config 类） ==========
# 将原本依赖 config 的路径改为本地定义，保持功能一致
DATA_DIR = os.path.join(BACK_DIR, "data")
HISTORY_LOG_DIR = os.path.join(DATA_DIR, "generated_log")
CERT_STORE_DIR = os.path.join(BACK_DIR, 'certs')
GENERATED_CERTS_DIR = os.path.join(DATA_DIR, 'generated_certs')

os.makedirs(HISTORY_LOG_DIR, exist_ok=True)
os.makedirs(CERT_STORE_DIR, exist_ok=True)
os.makedirs(GENERATED_CERTS_DIR, exist_ok=True)

# ========== 工具函数 ==========
def generate_unique_id() -> str:
    return str(uuid4()).replace('-', '')

def format_timestamp(timestamp: datetime = None) -> str:
    if timestamp is None:
        timestamp = datetime.now()
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def save_simulation_history(history_data: dict) -> bool:
    try:
        record_id = generate_unique_id()
        current_timestamp = format_timestamp()
        history_data.setdefault("recordId", record_id)
        history_data.setdefault("timestamp", current_timestamp)
        log_file_path = os.path.join(HISTORY_LOG_DIR, f"{record_id}.json")
        with open(log_file_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ 保存历史失败：{str(e)}")
        return False

# ========== 核心仿真接口（已移除 PCAP/LSTM 调用） ==========
@app.route('/api/run_simulation', methods=['POST'])
def run_simulation():
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({"code": 400, "message": "参数为空"})

        is_https = request_data.get('is_https', False)
        is_concurrent = request_data.get('is_concurrent', False)
        try:
            num_concurrent = int(request_data.get('num_concurrent', 500))
            test_duration = int(request_data.get('test_duration', 10))
        except (ValueError, TypeError):
            return jsonify({"code": 400, "message": "参数格式错误，并发数和时长必须为整数"}), 400
        full_http_request = request_data.get('full_http_request', '')
        client_conn_id = request_data.get('connection_id')
        # 新增：恶意报文检测选项
        check_malicious = request_data.get('check_malicious', False)
        # 新增：是否继续发送（当检测到恶意报文时，用户选择是否继续发送）
        continue_sending = request_data.get('continue_sending', False)

        # 新增：HTTP 报文语法检测
        if full_http_request.strip() and not is_concurrent:
            from src.respond import validate_http_request_strict
            is_valid, message = validate_http_request_strict(full_http_request)
            if not is_valid:
                return jsonify({
                    "code": 400,
                    "message": "HTTP 报文语法错误",
                    "data": {
                        "error": message
                    }
                })

        # 新增：恶意报文检测逻辑
        if check_malicious and not continue_sending:
            # 调用恶意报文检测函数
            malicious_result = predict_http_request(full_http_request)
            # 如果检测结果为恶意请求，返回检测结果，不进行仿真
            if malicious_result['预测结果'] == '恶意请求':
                return jsonify({
                    "code": 200,
                    "message": "检测到恶意请求",
                    "data": {
                        "malicious_check_result": malicious_result,
                        "need_confirm": True # 需要前端确认是否继续发送
                    }
                })

        # 原有仿真逻辑
        if is_concurrent:
            result = handle_concurrent_simulation(num_concurrent)
        else:
            # 调用重命名后的函数
            # 注意：respond.py 中的函数不接收 is_https，这里已去除
            raw_result = handle_http_simulation(
                raw_content=full_http_request,
                client_conn_id=client_conn_id
            )

            # 【重要】适配数据结构，构造前端需要的格式
            response_list = raw_result.get("responses", [])
            first_response = response_list[0] if response_list else ""

            result = {
                "sessionId": raw_result.get("sessionId"),
                "httpResponseContent": first_response, # 取第一个响应作为主要内容
                "responses": response_list,            # 传递完整响应列表
                "connectionStatus": raw_result.get("status"),
                # 手动补充 keepAliveInfo，因为 respond.py 简化版未返回
                "keepAliveInfo": { "used": 0, "max": 100, "timeout": 60 },
                "meta": { "isPipeline": len(response_list) > 1 }
            }

        history_data = {
            "request": {"url": "engine_simulation", "full_http_request": full_http_request},
            "response": {"statusCode": 200, "httpResponseContent": result.get("httpResponseContent", "")},
            "meta": result.get("meta", {})
        }

        save_simulation_history(history_data)
        return jsonify({"code": 200, "message": "仿真成功", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)})


# =========================================================
# 【修改】AI 分析接口 (增加 Body 截断逻辑)
# =========================================================
@app.route('/api/analyze_interaction', methods=['POST'])
def analyze_interaction_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "message": "请求参数为空"})

        req_msg = data.get('request_msg', '')
        res_raw = data.get('response_msgs', '')

        # --- 核心修改 START: 清洗响应报文，移除过长的 Body ---
        def clean_response(raw_res):
            if not isinstance(raw_res, str):
                raw_res = str(raw_res)

            # 尝试分离 Headers 和 Body
            # HTTP 协议规定 Headers 和 Body 之间由两个 CRLF (\r\n\r\n) 分隔
            if '\r\n\r\n' in raw_res:
                headers, body = raw_res.split('\r\n\r\n', 1)
                # 截断 Body，只保留前 200 个字符用于示意，或者直接丢弃
                preview_body = body[:200] + '... [Body Truncated by Backend]' if body else ''
                return headers + '\r\n\r\n' + preview_body
            # 如果是 \n\n 分隔 (兼容性处理)
            elif '\n\n' in raw_res:
                headers, body = raw_res.split('\n\n', 1)
                preview_body = body[:200] + '... [Body Truncated by Backend]' if body else ''
                return headers + '\n\n' + preview_body
            else:
                # 如果找不到分隔符，说明可能全是 Header 或者格式特殊
                # 如果总长度太大，强行截断
                if len(raw_res) > 2000:
                    return raw_res[:2000] + '... [Content Truncated]'
                return raw_res

        # 处理响应列表或单字符串
        if isinstance(res_raw, list):
            # 对列表中的每个响应都进行清洗
            cleaned_res_list = [clean_response(r) for r in res_raw]
            res_msg = "\n\n--- Next Response ---\n\n".join(cleaned_res_list)
        else:
            res_msg = clean_response(res_raw)
        # --- 核心修改 END ---

        if not req_msg:
            return jsonify({"code": 400, "message": "缺少请求报文内容"})

        # 将清洗后的 res_msg 传给 AI
        success, analysis_result = analyze_http_request_response(req_msg, res_msg)

        if success:
            return jsonify({
                "code": 200,
                "message": "分析成功",
                "data": {
                    "analysis": analysis_result
                }
            })
        else:
            return jsonify({"code": 500, "message": "AI 模型处理失败", "data": {"analysis": analysis_result}})

    except Exception as e:
        print(f"❌ AI接口报错: {str(e)}")
        return jsonify({"code": 500, "message": str(e)})

# ========== 新增：恶意检测专属分析接口 ==========
@app.route('/api/malicious/analyze', methods=['POST'])
def analyze_malicious_request():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "message": "请求参数为空"})

        http_request = data.get('http_request', '')
        if not http_request.strip():
            return jsonify({"code": 400, "message": "HTTP请求内容不能为空"})

        # 调用 malicious_detector.py 中的预测函数
        # predict_http_request 内部会自动初始化模型
        result = predict_http_request(http_request)

        # 构造返回数据
        return jsonify({
            "code": 200,
            "message": "检测完成",
            "data": {
                "result": result['预测结果'],
                "confidence": result['置信度'],
                "prob_normal": result['正常请求概率'],
                "prob_malicious": result['恶意请求概率'],
                "timestamp": format_timestamp()
            }
        })
    except Exception as e:
        print(f"❌ 恶意检测接口报错: {str(e)}")
        return jsonify({"code": 500, "message": f"检测失败: {str(e)}"})

# ========== 【修改后】AI 生成样本并批量检测接口 ==========
@app.route('/api/malicious/generate_analyze', methods=['POST'])
def generate_analyze_traffic():
    try:
        data = request.get_json()
        count = int(data.get('count', 20))
        if count > 50: count = 50
        if count < 1: count = 5

        # 1. 调用 AI 生成样本
        ai_success, samples = generate_traffic_samples(count)

        if not ai_success or not samples:
            return jsonify({"code": 500, "message": "AI 生成样本失败，请重试"})

        # 2. 使用本地模型进行检测统计
        total_count = 0
        malicious_count = 0
        normal_count = 0

        # --- 新增：用于存储详情的列表 ---
        detail_list = []

        for index, req_text in enumerate(samples):
            req_text = req_text.strip()
            if not req_text:
                continue

            # 调用预测函数
            result = predict_http_request(req_text)

            # 统计
            total_count += 1
            if result['预测结果'] == '恶意请求':
                malicious_count += 1
            else:
                normal_count += 1

            # --- 新增：保存详细信息 ---
            detail_list.append({
                "id": index + 1,
                "content": req_text,  # 原始报文
                "result": result['预测结果'],  # 正常/恶意
                "confidence": result['置信度'],
                "malicious_prob": result['恶意请求概率']
            })

        return jsonify({
            "code": 200,
            "message": "AI 生成及检测完成",
            "data": {
                "total": total_count,
                "malicious": malicious_count,
                "normal": normal_count,
                "details": detail_list  # 将详情返回给前端
            }
        })

    except Exception as e:
        print(f"❌ 批量生成检测失败: {str(e)}")
        return jsonify({"code": 500, "message": f"处理失败: {str(e)}"})

# ========== 安全模拟接口：请求劫持 ==========
@app.route('/api/security/hijack/simulate', methods=['POST'])
def simulate_hijack():
    try:
        data = request.get_json()
        result = hijack_simulator.run_hijack_simulation(data.get('hijackType'), data.get('targetUrl'), data.get('hijackContent'))
        return jsonify({"code": 200, "message": "成功", "data": result}) if result.get('status') == 'success' else jsonify({"code": 500, "message": result.get('message')})
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)})

@app.route('/api/security/hijack/logs', methods=['GET'])
def get_hijack_logs():
    return jsonify({"code": 200, "data": hijack_simulator.get_hijack_logs()})

# ========== 证书生成接口 ==========
@app.route('/api/security/cert/generate', methods=['POST'])
def generate_cert():
    try:
        data = request.get_json()
        result = cert_generator.generate_cert(
            data.get('certType', 'self-signed'), data.get('domain', 'example.com'),
            data.get('validityDays', 30), data.get('organization', 'Example'),
            data.get('country', 'CN'), data.get('keySize', 2048)
        )

        # 保存证书生成历史记录
        history_data = {
            "operation": "certificate_generation",
            "request": {
                "certType": data.get('certType', 'self-signed'),
                "domain": data.get('domain', 'example.com'),
                "validityDays": data.get('validityDays', 30),
                "organization": data.get('organization', 'Example'),
                "country": data.get('country', 'CN'),
                "keySize": data.get('keySize', 2048)
            },
            "response": {
                "certificate_filename": result.get('certificate_filename', ''),
                "certificate_type": result.get('type', ''),
                "status": "success"
            }
        }
        save_simulation_history(history_data)

        return jsonify({"code": 200, "message": "生成成功", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)})

# ========== 核心修复：证书列表接口 (修复 ca-signed 显示问题) ==========
@app.route('/api/security/cert/list', methods=['GET'])
def get_cert_list():
    """获取生成的证书列表，供前端 SecuritySimulation.vue 调用"""
    try:
        cert_list = []
        if os.path.exists(GENERATED_CERTS_DIR):
            # 使用 os.walk 遍历所有子目录
            for root, dirs, files in os.walk(GENERATED_CERTS_DIR):
                for file in files:
                    if file.endswith('.pem') and not file.endswith('_key.pem'):
                        file_path = os.path.join(root, file)
                        stat = os.stat(file_path)

                        # --- 核心修复逻辑开始 ---
                        # 根据文件名特征判断证书类型，解决之前全部显示为 self_signed 的问题
                        c_type = 'self-signed' # 默认值

                        if 'expired' in file:
                            c_type = 'expired'
                        elif 'weak' in file:
                            c_type = 'weak'
                        # 必须先判断 ca-signed，因为它可能同时也包含 ca 关键字
                        elif 'ca-signed' in file or ('ca' in file and 'signed' in file):
                            c_type = 'ca-signed'
                        # 最后判断 ca
                        elif 'ca' in file and 'signed' not in file:
                            c_type = 'ca'
                        elif 'self_signed' in file:
                            c_type = 'self-signed'
                        # --- 核心修复逻辑结束 ---

                        cert_list.append({
                            'certificate_type': c_type,
                            'certificate_filename': file,
                            'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            'file_size': stat.st_size
                        })

        # 按创建时间倒序排列
        cert_list.sort(key=lambda x: x['created_time'], reverse=True)
        return jsonify({"code": 200, "message": "获取成功", "data": cert_list})
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)})

@app.route('/api/security/cert/content', methods=['POST'])
def get_cert_content():
    try:
        data = request.get_json()
        filename = data.get('certificate_filename', '')
        # 防止路径遍历攻击
        filename = os.path.basename(filename)
        if '..' in filename or filename.startswith('/'):
            return jsonify({"code": 400, "message": "非法文件名"}), 400
        # 递归查找文件，因为文件可能在子目录中
        for root, dirs, files in os.walk(GENERATED_CERTS_DIR):
            if filename in files:
                with open(os.path.join(root, filename), 'r', encoding='utf-8') as f:
                    return jsonify({"code": 200, "data": {"content": f.read()}})
        return jsonify({"code": 404, "message": "文件不存在"})
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)})

# ========== 大并发模拟接口 ==========
@app.route('/api/simulate', methods=['POST'])
def simulate_big_concurrent():
    try:
        print(f"\n[API] 收到大并发模拟请求")
        print(f"[API] 请求IP: {request.remote_addr}")
        print(f"[API] 请求方法: {request.method}")
        print(f"[API] 请求路径: {request.path}")
        
        request_data = request.get_json()
        print(f"[API] 请求数据: {request_data}")
        
        # 记录开始时间
        start_time = time.time()
        
        result = run_big_simulation(request_data)
        
        # 记录结束时间和处理时间
        end_time = time.time()
        process_time = end_time - start_time
        print(f"[API] 处理时间: {process_time:.2f}秒")
        print(f"[API] 处理结果: {result.get('status')}")

        # 保存大并发模拟历史记录
        if result.get('status') == 'success':
            history_data = {
                "operation": "big_concurrent_simulation",
                "request": request_data,
                "response": {
                    "status": "success",
                    "startTime": result['data']['stats']['startTime'],
                    "endTime": result['data']['stats']['endTime'],
                    "duration": result['data']['stats']['duration']
                }
            }
            save_simulation_history(history_data)
            print(f"[API] 保存历史记录成功")
        
        response = jsonify({"code": 200, "data": result.get('data', {})}) if result.get('status') == 'success' else jsonify({"code": 500, "message": result.get('message')})
        print(f"[API] 返回响应: {response}")
        return response
    except Exception as e:
        print(f"[API] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)})

# ========== 历史记录与健康检查 ==========
@app.route('/api/history/list', methods=['GET'])
def get_history_list():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    records = []
    files = glob.glob(os.path.join(HISTORY_LOG_DIR, "*.json"))
    for f in files:
        with open(f, "r", encoding="utf-8") as j:
            records.append(json.load(j))
    records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    total = len(records)
    records = records[(page-1)*page_size : page*page_size]
    return jsonify({"code": 200, "data": {"list": records, "pagination": {"total": total, "page": page, "page_size": page_size}}})

# ========== 日志读取API ==========
@app.route('/api/logs/cert/list', methods=['GET'])
def get_cert_logs_list():
    """获取证书伪造日志列表"""
    cert_log_dir = os.path.join(DATA_DIR, "Log", "certs_log")
    records = []

    # 查找所有证书日志文件
    files = glob.glob(os.path.join(cert_log_dir, "*.log"))
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    # 添加操作类型和简化信息
                    log_entry["operation"] = "certificate_generation"
                    records.append(log_entry)
                except json.JSONDecodeError:
                    continue

    # 按时间倒序排列
    records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify({"code": 200, "data": records})

@app.route('/api/logs/big-concurrent/list', methods=['GET'])
def get_big_concurrent_logs_list():
    """获取大并发模拟日志列表"""
    big_concurrent_log_dir = os.path.join(DATA_DIR, "Log", "big_concurrent_log")
    records = []

    # 查找所有大并发日志文件
    files = glob.glob(os.path.join(big_concurrent_log_dir, "*.log"))
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    # 添加操作类型
                    log_entry["operation"] = "big_concurrent_simulation"
                    records.append(log_entry)
                except json.JSONDecodeError:
                    continue

    # 按时间倒序排列
    records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify({"code": 200, "data": records})

# ========== 压测目标测试页 ==========
@app.route('/', methods=['GET'])
def bench_target():
    return '<html><body><h1>HTTP Stress Test Target</h1></body></html>'

@app.route('/index.html', methods=['GET'])
def bench_target_html():
    return '<html><body><h1>HTTP Stress Test Target</h1></body></html>'

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"code": 200, "data": {"status": "ok", "module": {"respond": "loaded", "security": "loaded"}}})

if __name__ == '__main__':
    print('Backend server starting (waitress, threads=256, backlog=8192)...')
    from waitress import serve
    serve(app, host='0.0.0.0', port=60110, threads=256, backlog=8192)