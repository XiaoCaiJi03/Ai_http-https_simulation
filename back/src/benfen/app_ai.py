import os
import sys
import multiprocessing
import threading
from datetime import datetime
import json
from uuid import uuid4
from flask import Flask, request, jsonify
from flask_cors import CORS
import glob
import re  # 新增：导入正则表达式模块 re，解决 NameError

# ========== 第一步：先定义目录路径，再添加src到Python搜索路径（核心修复：导入顺序问题） ==========
BACK_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BACK_DIR, 'src')

# 2. 验证src目录是否存在（避免无效路径）
if not os.path.exists(SRC_DIR) or not os.path.isdir(SRC_DIR):
    print(f"❌ 致命错误：src目录不存在（路径：{SRC_DIR}）")
    print(f"🔍 请确保在项目根目录下创建src文件夹，并将respond.py放入其中")
    sys.exit(1)

# 3. 将src目录添加到Python模块搜索路径（优先搜索，解决导入失败）
sys.path.append(SRC_DIR)
print(f"✅ 已添加src目录到Python模块搜索路径：{SRC_DIR}")

# ========== 第二步：导入最新 respond.py 中的所有核心工具函数/类（此时路径已生效） ==========
try:
    from src.respond import (
        handle_http_simulation_entry as handle_http_simulation,
        handle_concurrent_simulation,
        VirtualConnection,
        server_connection_pool as connection_pool
    )
    print("✅ respond.py 核心模块导入成功")
except ImportError as e:
    print(f"❌ 导入 respond.py 失败：{e}")
    print(f"🔍 排查要点：")
    print(f"   1. respond.py 是否位于 {SRC_DIR} 目录下")
    print(f"   2. respond.py 中是否存在以下函数/类：handle_http_simulation、handle_concurrent_simulation、VirtualConnection、connection_pool")
    print(f"   3. respond.py 语法是否正确，无报错")
    sys.exit(1)

# ========== 第三步：补充缺失的 check_connection_header 函数（原有导入缺失，此处实现兼容） ==========
def check_connection_header(raw_http_request: str) -> str:
    """
    检测HTTP请求中的Connection头字段（兼容原有app.py逻辑，补充respond.py中缺失的函数）
    :return: keep-alive / close / unknown
    """
    if not raw_http_request or not isinstance(raw_http_request, str):
        return "unknown"
    
    # 忽略大小写，匹配Connection头
    connection_pattern = r'Connection:\s*([a-zA-Z\-]+)'
    matches = re.findall(connection_pattern, raw_http_request, re.IGNORECASE)
    if not matches:
        return "unknown"
    
    connection_value = matches[-1].lower()  # 取最后一个匹配结果（多请求时以最后一个为准）
    if connection_value == "keep-alive":
        return "keep-alive"
    elif connection_value == "close":
        return "close"
    else:
        return "unknown"

# ========== 关键：导入pcap_to_json.py中的3个核心函数 ==========
try:
    from src.pcap_to_json import (
        find_latest_pcap_file,
        check_tshark_available,
        tshark_export_pcap_to_json
    )
    print("✅ pcap_to_json.py 模块导入成功")
except ImportError as e:
    print(f"❌ 导入 pcap_to_json.py 失败：{e}")
    print(f"🔍 请确保pcap_to_json.py位于{SRC_DIR}目录下")
    sys.exit(1)

# ========== 导入核心仿真模块（保留原有配置） ==========
try:
    from lstm_pcap4_best import (
        Config,
        FullSessionFramework,
        FixedConcurrentSessionManager
    )
    print("✅ lstm_pcap4_best.py 核心模块导入成功")
except ImportError as e:
    print(f"❌ 导入核心代码失败：{e}")
    print(f"🔍 请确认lstm_pcap4_best.py中存在以下类：Config、FullSessionFramework、FixedConcurrentSessionManager")
    sys.exit(1)

# ========== 导入安全模拟模块（新增） ==========
try:
    # 确保导入的是src目录下的模块
    from src.security import HijackSimulator, CertGenerator
    from src.big_simulator import run_big_simulation
    print("✅ 安全模拟模块导入成功")
except ImportError:
    # 如果带src前缀导入失败，尝试直接导入（适用于已添加src到搜索路径的情况）
    try:
        from security import HijackSimulator, CertGenerator
        from big_simulator import run_big_simulation
        print("✅ 安全模拟模块导入成功")
    except ImportError as e:
        print(f"❌ 导入安全模拟模块失败：{e}")
        print(f"🔍 请确认security_scene_code文件夹下的核心文件及big_simulator.py已成功复制到{SRC_DIR}目录")
        sys.exit(1)

# ========== 初始化安全模拟模块实例（新增） ==========
hijack_simulator = HijackSimulator()
# cert_forge = CertForge()  # 注释掉cert_forge实例化
cert_generator = CertGenerator()
try:
    big_simulator = run_big_simulation  # 使用函数而非类
    print("✅ big_simulator.py 模块导入成功")
except Exception as e:
    print(f"❌ big_simulator导入失败：{e}")
    sys.exit(1)

# ========== 创建证书存储目录（新增） ==========
CERT_STORE_DIR = os.path.join(BACK_DIR, 'certs')
os.makedirs(CERT_STORE_DIR, exist_ok=True)
print(f"✅ 证书存储目录已创建/验证：{CERT_STORE_DIR}")

# ========== 初始化Flask应用 ==========
app = Flask(__name__)
CORS(app)  # 解决跨域问题

# ========== 全局配置与目录路径（自动创建所有必要目录） ==========
# 原有仿真文件目录
JSON_FILE_ROOT_PATH = os.path.join(BACK_DIR, "data", "pcap_to_json")
HTTP_DIR_FLAG = "ai_http"
HTTPS_DIR_FLAG = "ai_https"

# 历史记录日志目录（核心：存储仿真历史）
HISTORY_LOG_DIR = os.path.join(BACK_DIR, "data", "generated_log")

# 初始化Config（仿真核心配置）
config = Config()
multiprocessing.freeze_support()

# 自动创建目录（避免写入失败）
os.makedirs(JSON_FILE_ROOT_PATH, exist_ok=True)
os.makedirs(config.SAVE_DIR_HTTP, exist_ok=True)
os.makedirs(config.SAVE_DIR_HTTPS, exist_ok=True)
os.makedirs(HISTORY_LOG_DIR, exist_ok=True)
print(f"✅ 所有必要目录已创建/验证完成")

# ========== 全局变量 ==========
json_dir_name = None  # 存储最新生成的JSON目录名
dir_lock = threading.Lock()
TSHARK_PATH = r"E:\Program Files\Wireshark\tshark.exe"  # Wireshark路径

# ========== 工具函数（通用：ID生成、时间格式化、文件操作） ==========
def generate_unique_id() -> str:
    """生成唯一记录ID（UUID4，保证不重复）"""
    return str(uuid4()).replace('-', '')

def format_timestamp(timestamp: datetime = None) -> str:
    """格式化时间戳为前端需要的格式（YYYY-MM-DD HH:mm:ss）"""
    if not timestamp:
        timestamp = datetime.now()
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

# ========== 工具函数（历史记录：读写/删除） ==========
def save_simulation_history(history_data: dict) -> bool:
    """保存仿真历史记录到generated_log目录（每个记录一个JSON文件）"""
    try:
        # 补充必要字段（兼容前端，避免报错）
        record_id = generate_unique_id()
        current_time = datetime.now()
        current_timestamp = format_timestamp(current_time)
        
        # 强制补充核心字段，解决排序和显示报错
        history_data.setdefault("recordId", record_id)
        history_data.setdefault("timestamp", current_timestamp)
        if "request" not in history_data:
            history_data["request"] = {}
        history_data["request"].setdefault("url", "-")
        history_data.setdefault("isHijacked", False)
        history_data.setdefault("wireshark", {})
        history_data["wireshark"].setdefault("enabled", True)
        history_data.setdefault("response", {})
        history_data["response"].setdefault("statusCode", 200)

        # 构造日志文件路径
        log_file_path = os.path.join(HISTORY_LOG_DIR, f"{record_id}.json")

        # 写入JSON文件（格式化存储，便于阅读）
        with open(log_file_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"❌ 保存仿真历史记录失败：{str(e)}")
        return False

def get_all_history_records():
    """读取所有历史记录，按时间倒序排序"""
    history_records = []
    try:
        # 扫描所有.json日志文件
        log_file_pattern = os.path.join(HISTORY_LOG_DIR, "*.json")
        log_file_paths = glob.glob(log_file_pattern)

        # 逐个解析JSON文件
        for file_path in log_file_paths:
            if not os.path.isfile(file_path):
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                record = json.load(f)
                history_records.append(record)

        # 按仿真时间倒序排序（最新记录在前）
        history_records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return history_records
    except Exception as e:
        print(f"❌ 读取所有历史记录失败：{str(e)}")
        return []

def get_history_record_by_id(record_id: str) -> dict or None:
    """根据ID查询单条历史记录"""
    try:
        log_file_path = os.path.join(HISTORY_LOG_DIR, f"{record_id}.json")
        if not os.path.exists(log_file_path) or not os.path.isfile(log_file_path):
            return None
        with open(log_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取单条历史记录失败（ID：{record_id}）：{str(e)}")
        return None

def delete_history_record_by_id(record_id: str) -> bool:
    """根据ID删除单条历史记录"""
    try:
        log_file_path = os.path.join(HISTORY_LOG_DIR, f"{record_id}.json")
        if not os.path.exists(log_file_path) or not os.path.isfile(log_file_path):
            return False
        os.remove(log_file_path)
        return True
    except Exception as e:
        print(f"❌ 删除历史记录失败（ID：{record_id}）：{str(e)}")
        return False

# ========== 工具函数（仿真文件：读取最新目录JSON列表） ==========
def get_latest_dir_json_files() -> tuple:
    """读取最新生成目录下的所有JSON文件（返回：总数，文件列表）"""
    json_file_list = []

    # 1. 加锁读取最新目录名
    with dir_lock:
        target_dir = json_dir_name

    # 2. 校验最新目录是否存在
    if not target_dir:
        return 0, []  # 还未生成任何目录

    # 3. 拼接最新目录的完整路径
    target_dir_full_path = os.path.join(JSON_FILE_ROOT_PATH, target_dir)
    if not os.path.exists(target_dir_full_path) or not os.path.isdir(target_dir_full_path):
        return 0, []

    # 4. 仅遍历最新目录下的JSON文件
    for root, dirs, files in os.walk(target_dir_full_path):
        for file in files:
            if file.lower().endswith(".json"):
                json_file_list.append({
                    "fileName": file,
                    "fileFullPath": os.path.join(root, file)
                })

    return len(json_file_list), json_file_list

# ========== 核心接口（仿真：单会话/大并发，整合最新 respond.py 功能） ==========
@app.route('/api/run_simulation', methods=['POST'])
def run_simulation():
    """接收前端仿真请求，执行HTTP/HTTPS单会话/大并发仿真（整合最新 respond.py 功能）"""
    global json_dir_name

    try:
        # 1. 接收并解析前端参数（对齐最新逻辑：移除手动connection_mode，保留client_conn_id）
        request_data = request.get_json()
        if not request_data:
            return jsonify({
                "code": 400,
                "message": "请求参数不能为空（需传递JSON格式数据）",
                "data": None
            })

        # 原有参数
        is_https = request_data.get('is_https', False)
        hijack_enable = request_data.get('hijack_enable', False)
        is_concurrent = request_data.get('is_concurrent', False)
        num_concurrent = int(request_data.get('num_concurrent', 500))
        full_http_request = request_data.get('full_http_request', '')

        # 最新参数：仅保留client_conn_id（用于连接复用）
        client_conn_id = request_data.get('connection_id')

        # 2. 参数合法性校验
        if is_concurrent and (num_concurrent < 10 or num_concurrent > 2000):
            return jsonify({
                "code": 400,
                "message": "并发会话数必须在10~2000之间",
                "data": None
            })

        # 3. 并发仿真逻辑（调用最新 respond.py 的 handle_concurrent_simulation）
        if is_concurrent:
            # 调用最新 respond.py 并发处理函数（httpResponseContent 置空）
            concurrent_result = handle_concurrent_simulation(num_concurrent)

            # 保存大并发仿真历史记录（整合最新字段）
            history_data = {
                "request": {
                    "url": f"concurrent_{num_concurrent}_sessions",
                    "method": "GET",
                    "isHttps": is_https,
                    "isHijacked": hijack_enable,
                    "full_http_request": full_http_request,
                    "connection_id": client_conn_id
                },
                "wireshark": {
                    "enabled": True,
                    "result": {
                        "packets": []
                    }
                },
                "response": {
                    "statusCode": 200,
                    "httpResponseContent": concurrent_result.get("httpResponseContent", "")
                },
                "sessionId": concurrent_result.get("sessionId", ""),
                "concurrent": concurrent_result.get("concurrent", {}),
                "mode": concurrent_result.get("mode", "concurrent")
            }
            save_simulation_history(history_data)

            # 返回成功结果
            return jsonify({
                "code": 200,
                "message": f"大并发仿真成功（已生成{num_concurrent}个会话的PCAP文件）",
                "data": concurrent_result
            })

        # 4. 单会话 HTTP/1.1 深度仿真（调用最新 respond.py 的 handle_http_simulation）
        else:
            framework = FullSessionFramework(config)
            save_dir = config.SAVE_DIR_HTTPS if is_https else config.SAVE_DIR_HTTP
            pcap_search_dir = config.SAVE_DIR_HTTPS if is_https else config.SAVE_DIR_HTTP

            # 生成会话PCAP文件（保留原有核心功能）
            session_id = framework.generate_https_session(specified_method="GET") if is_https else framework.generate_http_session(specified_method="GET")
            os.makedirs(pcap_search_dir, exist_ok=True)

            # 调用外部函数：查找最新PCAP
            latest_pcap = find_latest_pcap_file(pcap_search_dir)
            if not latest_pcap:
                raise Exception("未生成任何PCAP文件，仿真失败")

            # 调用外部函数：PCAP转JSON（拆分报文）
            success, local_dir_name = tshark_export_pcap_to_json(
                pcap_file_path=latest_pcap,
                output_dir=JSON_FILE_ROOT_PATH,
                tshark_path=TSHARK_PATH
            )

            # 校验转JSON是否成功
            if not success or not local_dir_name:
                raise Exception("PCAP转JSON失败，无法继续返回仿真结果")

            # 更新全局最新JSON目录名
            with dir_lock:
                json_dir_name = local_dir_name

            # ========== 整合最新 respond.py 核心功能：自动识别Connection头+Pipeline+meta字段 ==========
            http_simulation_result = handle_http_simulation(
                raw_content=full_http_request,
                client_conn_id=client_conn_id  # 仅传递连接ID，其余自动识别
            )

            # 补充原有字段，兼容前端显示
            http_simulation_result.update({
                "isHttps": is_https,
                "hijackEnable": hijack_enable
            })

            # 保存单会话仿真历史记录（整合最新 meta 字段）
            history_data = {
                "request": {
                    "url": f"{save_dir}/{local_dir_name}",
                    "isHijacked": hijack_enable,
                    "full_http_request": full_http_request,
                    "connection_id": client_conn_id,
                    "connection_header": check_connection_header(full_http_request)  # 调用补充的函数
                },
                "wireshark": {
                    "enabled": True,
                    "result": {
                        "packets": []
                    }
                },
                "response": {
                    "statusCode": 200,
                    "httpResponseContent": http_simulation_result.get("httpResponseContent", ""),
                    "responses": http_simulation_result.get("responses", []),
                    "meta": http_simulation_result.get("meta", {})  # 新增：保存meta字段（用于前端动画）
                },
                "sessionId": http_simulation_result.get("sessionId", ""),
                "connectionStatus": http_simulation_result.get("connectionStatus", "closed"),
                "keepAliveInfo": http_simulation_result.get("keepAliveInfo", {}),
                "meta": http_simulation_result.get("meta", {})
            }
            save_simulation_history(history_data)

            # 返回成功结果（包含最新 meta 字段，支持前端动画展示）
            return jsonify({
                "code": 200,
                "message": "单会话 HTTP/1.1 深度仿真成功（已生成PCAP及JSON文件）",
                "data": http_simulation_result
            })

    # 在app.py的run_simulation接口的except块中修改：
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()  # 获取详细堆栈信息
        print(f"仿真失败详细错误：{error_detail}")
        return jsonify({
            "code": 500,
            "message": f"仿真失败：{str(e)}",
            "data": None
        })

# ========== 核心接口（前端JSON文件列表/内容查询） ==========
@app.route('/api/get_pcap_json_list', methods=['GET'])
def get_pcap_json_list():
    """获取最新生成目录下的JSON文件列表（前端报文详情依赖）"""
    try:
        file_total, file_list = get_latest_dir_json_files()

        # 构造前端需要的文件列表格式
        frontend_file_list = [{"fileName": item["fileName"], "fileKey": item["fileFullPath"]} for item in file_list]

        if file_total == 0:
            with dir_lock:
                target_dir = json_dir_name
            if not target_dir:
                return jsonify({
                    "code": 200,
                    "message": "暂未生成任何仿真JSON文件，请先执行仿真",
                    "data": {
                        "total": 0,
                        "fileList": []
                    }
                })
            else:
                return jsonify({
                    "code": 200,
                    "message": f"最新目录「{target_dir}」下无JSON文件",
                    "data": {
                        "total": 0,
                        "fileList": []
                    }
                })

        # 返回结果
        return jsonify({
            "code": 200,
            "message": f"获取最新目录「{json_dir_name}」下的JSON文件列表成功",
            "data": {
                "total": file_total,
                "fileList": frontend_file_list,
                "latestDirName": json_dir_name
            }
        })
    except Exception as e:
        print(f"❌ 获取JSON文件列表失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取JSON文件列表失败：{str(e)}",
            "data": None
        })

@app.route('/api/get_pcap_json_content', methods=['POST'])
def get_pcap_json_content():
    """获取指定JSON文件的内容（前端报文详情解析依赖）"""
    try:
        # 接收前端传递的文件路径
        request_data = request.get_json()
        if not request_data or not request_data.get("fileKey"):
            return jsonify({
                "code": 400,
                "message": "请传递有效的文件路径（fileKey）",
                "data": None
            })

        file_full_path = request_data.get("fileKey", "")
        # 防止路径遍历
        if not file_full_path:
            return jsonify({
                "code": 400,
                "message": "文件路径不能为空",
                "data": None
            })
        file_full_path = os.path.normpath(file_full_path)
        if not file_full_path.startswith(JSON_FILE_ROOT_PATH):
            return jsonify({
                "code": 400,
                "message": "非法文件路径",
                "data": None
            })
        print(f"接收到的fileKey：{file_full_path}")
        print(f"文件是否存在：{os.path.exists(file_full_path)}")
        file_name = os.path.basename(file_full_path)

        # 校验文件是否存在
        if not os.path.exists(file_full_path) or not os.path.isfile(file_full_path):
            return jsonify({
                "code": 404,
                "message": f"JSON文件「{file_name}」不存在",
                "data": None
            })

        # 读取并解析JSON文件内容
        with open(file_full_path, "r", encoding="utf-8") as f:
            json_content = json.load(f)

        return jsonify({
            "code": 200,
            "message": f"获取JSON文件「{file_name}」内容成功",
            "data": {
                "fileName": file_name,
                "jsonContent": json_content
            }
        })
    except Exception as e:
        print(f"❌ 获取JSON文件内容失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取JSON文件内容失败：{str(e)}",
            "data": None
        })

# ========== 历史记录接口（保留原有逻辑，兼容最新字段） ==========
@app.route('/api/history/list', methods=['GET'])
def get_history_list():
    """分页查询仿真历史记录（兼容前端分页组件）"""
    try:
        # 接收分页参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        if page < 1 or size < 1:
            return jsonify({
                "code": 400,
                "message": "分页参数不合法（page≥1，size≥1）",
                "data": None
            })

        # 读取所有历史记录并分页
        all_records = get_all_history_records()
        total = len(all_records)
        start_index = (page - 1) * size
        end_index = start_index + size
        paginated_records = all_records[start_index:end_index]

        # 返回分页结果
        return jsonify({
            "code": 200,
            "message": "查询历史记录列表成功",
            "data": {
                "list": paginated_records,
                "pagination": {
                    "total": total
                }
            }
        })
    except Exception as e:
        print(f"❌ 查询历史记录列表失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"查询历史记录列表失败：{str(e)}",
            "data": None
        })

@app.route('/api/history/detail/<string:record_id>', methods=['GET'])
def get_history_detail(record_id: str):
    """根据ID查询单条仿真历史记录详情"""
    try:
        record = get_history_record_by_id(record_id)
        if not record:
            return jsonify({
                "code": 404,
                "message": f"未找到ID为{record_id}的仿真记录",
                "data": None
            })

        return jsonify({
            "code": 200,
            "message": "查询仿真记录详情成功",
            "data": record
        })
    except Exception as e:
        print(f"❌ 查询仿真记录详情失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"查询仿真记录详情失败：{str(e)}",
            "data": None
        })

@app.route('/api/history/delete/<string:record_id>', methods=['DELETE'])
def delete_history_record(record_id: str):
    """根据ID删除单条仿真历史记录"""
    try:
        success = delete_history_record_by_id(record_id)
        if not success:
            return jsonify({
                "code": 404,
                "message": f"删除失败：未找到ID为{record_id}的仿真记录",
                "data": None
            })

        return jsonify({
            "code": 200,
            "message": f"成功删除ID为{record_id}的仿真记录",
            "data": None
        })
    except Exception as e:
        print(f"❌ 删除仿真记录失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"删除仿真记录失败：{str(e)}",
            "data": None
        })

# ========== 安全模拟接口（保留原有逻辑，无修改） ==========
@app.route('/api/security/hijack/simulate', methods=['POST'])
def simulate_hijack():
    """运行请求劫持模拟"""
    try:
        # 接收请求参数
        request_data = request.get_json()
        if not request_data:
            return jsonify({
                "code": 400,
                "message": "请求参数不能为空",
                "data": None
            })

        hijack_type = request_data.get('hijackType')
        target_url = request_data.get('targetUrl')
        hijack_content = request_data.get('hijackContent')

        # 参数校验
        if not hijack_type or not target_url:
            return jsonify({
                "code": 400,
                "message": "劫持类型和目标URL不能为空",
                "data": None
            })

        # 调用劫持模拟器
        result = hijack_simulator.run_hijack_simulation(
            hijack_type, target_url, hijack_content
        )

        # 返回结果
        if result.get('status') == 'success':
            return jsonify({
                "code": 200,
                "message": result.get('message'),
                "data": result
            })
        else:
            return jsonify({
                "code": 500,
                "message": result.get('message'),
                "data": None
            })
    except Exception as e:
        print(f"❌ 请求劫持模拟失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"请求劫持模拟失败：{str(e)}",
            "data": None
        })

@app.route('/api/security/hijack/logs', methods=['GET'])
def get_hijack_logs():
    """获取请求劫持日志"""
    try:
        logs = hijack_simulator.get_hijack_logs()
        return jsonify({
            "code": 200,
            "message": "获取请求劫持日志成功",
            "data": logs
        })
    except Exception as e:
        print(f"❌ 获取请求劫持日志失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取请求劫持日志失败：{str(e)}",
            "data": None
        })

@app.route('/api/security/hijack/logs/clear', methods=['DELETE'])
def clear_hijack_logs():
    """清空请求劫持日志"""
    try:
        hijack_simulator.clear_hijack_logs()
        return jsonify({
            "code": 200,
            "message": "清空请求劫持日志成功",
            "data": None
        })
    except Exception as e:
        print(f"❌ 清空请求劫持日志失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"清空请求劫持日志失败：{str(e)}",
            "data": None
        })

# @app.route('/api/security/cert/forge', methods=['POST'])  # 注释掉cert_forge相关API
# def forge_cert():
#     """运行证书伪造"""
#     try:
#         # 接收请求参数
#         request_data = request.get_json()
#         if not request_data:
#             return jsonify({
#                 "code": 400,
#                 "message": "请求参数不能为空",
#                 "data": None
#             })

#         forge_type = request_data.get('forgeType')
#         domain = request_data.get('domain')
#         validity_days = request_data.get('validityDays', 30)

#         # 参数校验
#         if not forge_type or not domain:
#             return jsonify({
#                 "code": 400,
#                 "message": "伪造类型和域名不能为空",
#                 "data": None
#             })

#         # 调用证书伪造器
#         result = cert_forge.run_cert_forge(
#             forge_type, domain, validity_days
#         )

#         # 返回结果
#         if result.get('status') == 'success':
#             return jsonify({
#                 "code": 200,
#                 "message": result.get('message'),
#                 "data": result
#             })
#         else:
#             return jsonify({
#                 "code": 500,
#                 "message": result.get('message'),
#                 "data": None
#             })
#     except Exception as e:
#         print(f"❌ 证书伪造失败：{str(e)}")
#         return jsonify({
#             "code": 500,
#             "message": f"证书伪造失败：{str(e)}",
#             "data": None
#         })

# @app.route('/api/security/cert/forge/logs', methods=['GET'])  # 注释掉cert_forge相关API
# def get_forge_logs():
#     """获取证书伪造日志"""
#     try:
#         logs = cert_forge.get_forge_logs()
#         return jsonify({
#             "code": 200,
#             "message": "获取证书伪造日志成功",
#             "data": logs
#         })
#     except Exception as e:
#         print(f"❌ 获取证书伪造日志失败：{str(e)}")
#         return jsonify({
#             "code": 500,
#             "message": f"获取证书伪造日志失败：{str(e)}",
#             "data": None
#         })

# @app.route('/api/security/cert/forge/logs/clear', methods=['DELETE'])  # 注释掉cert_forge相关API
# def clear_forge_logs():
#     """清空证书伪造日志"""
#     try:
#         cert_forge.clear_forge_logs()
#         return jsonify({
#             "code": 200,
#             "message": "清空证书伪造日志成功",
#             "data": None
#         })
#     except Exception as e:
#         print(f"❌ 清空证书伪造日志失败：{str(e)}")
#         return jsonify({
#             "code": 500,
#             "message": f"清空证书伪造日志失败：{str(e)}",
#             "data": None
#         })

@app.route('/api/security/cert/generate', methods=['POST'])
def generate_cert():
    """生成X.509证书"""
    try:
        # 接收请求参数
        request_data = request.get_json()
        if not request_data:
            return jsonify({
                "code": 400,
                "message": "请求参数不能为空",
                "data": None
            })

        cert_type = request_data.get('certType', 'self-signed')
        domain = request_data.get('domain', 'example.com')
        validity_days = request_data.get('validityDays', 30)
        organization = request_data.get('organization', 'Example Organization')
        country = request_data.get('country', 'CN')
        key_size = request_data.get('keySize', 2048)

        # 调用证书生成器
        result = cert_generator.generate_cert(
            cert_type, domain, validity_days, organization, country, key_size
        )

        # 记录证书生成日志
        if result.get('status') == 'success':
            try:
                # 构造日志目录路径
                log_dir = os.path.join(BACK_DIR, "data", "Log", "certs_log")
                # 确保日志目录存在
                os.makedirs(log_dir, exist_ok=True)
                
                # 构造日志文件路径
                log_file_path = os.path.join(log_dir, "cert_generation.log")
                
                # 从result.data中提取证书信息
                cert_info = result.get('data', {})
                cert_filename = cert_info.get('certificate_filename')
                cert_size = cert_info.get('file_size', 0)
                cert_type = cert_info.get('type', cert_type)
                
                # 构造日志内容
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "certificate_type": cert_type,
                    "certificate_filename": cert_filename,
                    "domain": domain,
                    "validity_days": validity_days,
                    "file_size": cert_size,
                    "status": "success"
                }
                
                # 写入日志文件
                with open(log_file_path, "a") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                
                print(f"📝 证书生成日志已记录到：{log_file_path}")
            except Exception as log_e:
                print(f"❌ 写入证书日志失败：{str(log_e)}")

        # 返回结果
        if result.get('status') == 'success':
            return jsonify({
                "code": 200,
                "message": result.get('message'),
                "data": result
            })
        else:
            return jsonify({
                "code": 500,
                "message": result.get('message'),
                "data": None
            })
    except Exception as e:
        print(f"❌ 证书生成失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"证书生成失败：{str(e)}",
            "data": None
        })

@app.route('/api/security/cert/list', methods=['GET'])
def get_cert_list():
    """获取已生成的证书列表"""
    try:
        # 定义证书存储的根目录
        CERT_ROOT_DIR = os.path.join(BACK_DIR, 'data', 'generated_certs')
        cert_list = []
        
        # 扫描证书存储目录及其子目录
        if os.path.exists(CERT_ROOT_DIR) and os.path.isdir(CERT_ROOT_DIR):
            for root, dirs, files in os.walk(CERT_ROOT_DIR):
                for file in files:
                    if file.endswith('.pem'):
                        # 构造证书文件的完整路径
                        file_path = os.path.join(root, file)
                        # 获取证书文件的元数据
                        file_stat = os.stat(file_path)
                        created_time = datetime.fromtimestamp(file_stat.st_ctime).isoformat()
                        file_size = file_stat.st_size
                        
                        # 从文件名中解析证书类型
                        # 文件名格式：{cert_type}_{domain}_{timestamp}.pem
                        cert_type = 'self_signed'  # 默认类型
                        if file.startswith('ca_'):
                            cert_type = 'ca'
                        elif file.startswith('ca_signed_'):
                            cert_type = 'ca_signed'
                        elif file.startswith('expired_'):
                            cert_type = 'expired'
                        elif file.startswith('weak_'):
                            cert_type = 'weak'
                        
                        # 添加证书信息到列表
                        # 生成对应的私钥文件名：将.pem替换为_key.pem
                        key_filename = file.replace('.pem', '_key.pem')
                        cert_list.append({
                            'certificate_type': cert_type,
                            'certificate_filename': file,
                            'key_filename': key_filename,
                            'created_time': created_time,
                            'file_size': file_size
                        })
        
        # 按创建时间倒序排序
        cert_list.sort(key=lambda x: x['created_time'], reverse=True)
        
        return jsonify({
            "code": 200,
            "message": "获取证书列表成功",
            "data": cert_list
        })
    except Exception as e:
        print(f"❌ 获取证书列表失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取证书列表失败：{str(e)}",
            "data": None
        })

@app.route('/api/security/cert/content', methods=['POST'])
def get_cert_content():
    """获取证书文件的内容"""
    try:
        # 接收请求参数
        request_data = request.get_json()
        if not request_data or not request_data.get('certificate_filename'):
            return jsonify({
                "code": 400,
                "message": "请提供证书文件名",
                "data": None
            })
        
        # 获取证书文件名
        cert_filename = request_data.get('certificate_filename')
        
        # 定义证书存储的根目录
        CERT_ROOT_DIR = os.path.join(BACK_DIR, 'data', 'generated_certs')
        cert_file_path = None
        
        # 查找证书文件
        for root, dirs, files in os.walk(CERT_ROOT_DIR):
            if cert_filename in files:
                cert_file_path = os.path.join(root, cert_filename)
                break
        
        if not cert_file_path or not os.path.exists(cert_file_path):
            return jsonify({
                "code": 404,
                "message": f"证书文件不存在：{cert_filename}",
                "data": None
            })
        
        # 读取证书文件内容
        with open(cert_file_path, 'r') as f:
            cert_content = f.read()
        
        return jsonify({
            "code": 200,
            "message": "获取证书内容成功",
            "data": {
                "content": cert_content
            }
        })
    except Exception as e:
        print(f"❌ 获取证书内容失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取证书内容失败：{str(e)}",
            "data": None
        })





# ========== 大并发模拟接口（保留原有逻辑，无修改） ==========
@app.route('/api/simulate', methods=['POST'])
def simulate_big_concurrent():
    """运行大并发模拟（HTTP/1.1/2/3 + 高延迟/丢包，与big_simulator.py对接）"""
    try:
        # 1. 接收请求参数
        request_data = request.get_json()
        if not request_data:
            return jsonify({
                "code": 400,
                "message": "请求参数不能为空（需传递JSON格式数据）",
                "data": None
            })

        # 2. 参数合法性前置校验
        if 'requests' in request_data:
            requests_val = request_data['requests']
            if not (isinstance(requests_val, int) and requests_val > 0):
                return jsonify({
                    "code": 400,
                    "message": "请求数必须为正整数",
                    "data": None
                })

        if 'http1Connections' in request_data:
            http1_connections = request_data['http1Connections']
            if not (isinstance(http1_connections, int) and http1_connections > 0):
                return jsonify({
                    "code": 400,
                    "message": "HTTP/1.1并发连接数必须为正整数",
                    "data": None
                })

        # 3. 调用big_simulator的核心方法
        print(f"📢 调用big_simulator处理大并发请求")
        result = big_simulator(request_data)

        # 4. 返回结果
        if result.get('status') == 'success':
            return jsonify({
                "code": 200,
                "message": result.get('message', "大并发模拟执行成功"),
                "data": result.get('data', {})
            })
        else:
            error_msg = result.get('message', "大并发模拟执行失败")
            return jsonify({
                "code": 500,
                "message": error_msg,
                "data": None
            })

    except AttributeError as e:
        # 捕获big_simulator中方法缺失的异常
        print(f"❌ big_simulator.py中缺失必要方法：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"大并发模拟模块异常：缺失核心方法（{str(e)}），请检查big_simulator.py",
            "data": None
        })
    except Exception as e:
        print(f"❌ 大并发模拟失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"大并发模拟失败：{str(e)}",
            "data": None
        })

@app.route('/api/stats', methods=['GET'])
def get_simulation_stats():
    """获取大并发模拟最新统计数据（对接big_simulator.py）"""
    try:
        # 调用big_simulator的获取统计方法
        stats = big_simulator.get_latest_stats()
        return jsonify({
            "code": 200,
            "message": "获取模拟统计数据成功",
            "data": {
                "stats": stats
            }
        })
    except AttributeError as e:
        print(f"❌ big_simulator.py中缺失get_latest_stats方法：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取统计数据失败：缺失核心方法（{str(e)}）",
            "data": None
        })
    except Exception as e:
        print(f"❌ 获取模拟统计数据失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取模拟统计数据失败：{str(e)}",
            "data": None
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """服务健康检查（增强：标记最新 respond.py 功能）"""
    try:
        return jsonify({
            "code": 200,
            "message": "服务健康",
            "data": {
                "status": "ok",
                "timestamp": format_timestamp(),
                "port": 5000,
                "module": {
                    "big_simulator": "loaded",
                    "pcap_to_json": "loaded",
                    "security_modules": "loaded",
                    "respond": "loaded (自动识别Connection/Pipeline+meta动画字段)",
                    "connection_pool_size": len(connection_pool)
                }
            }
        })
    except Exception as e:
        print(f"❌ 健康检查失败：{str(e)}")
        return jsonify({
            "code": 500,
            "message": f"健康检查失败：{str(e)}",
            "data": None
        })

# ========== 启动Flask服务 ==========
if __name__ == '__main__':
    print("=" * 80)
    print("🚀 HTTP/HTTPS仿真后端服务启动成功（整合最新HTTP/1.1深度仿真）")
    print(f"🌐 访问地址：http://localhost:5000")
    print(f"📁 PCAP文件保存路径 - HTTP：{config.SAVE_DIR_HTTP}")
    print(f"📁 PCAP文件保存路径 - HTTPS：{config.SAVE_DIR_HTTPS}")
    print(f"📁 JSON文件生成路径：{JSON_FILE_ROOT_PATH}")
    print(f"📁 历史记录存储路径：{HISTORY_LOG_DIR}")
    print(f"📁 证书存储路径：{CERT_STORE_DIR}")
    print(f"📌 tshark程序路径：{TSHARK_PATH}")
    print(f"📌 依赖文件：pcap_to_json.py（已成功导入）")
    print(f"📌 大并发模拟模块：big_simulator.py（已成功导入，路径：{SRC_DIR}）")
    print(f"📌 响应模拟模块：respond.py（已成功导入，支持自动识别Connection/Pipeline+meta动画）")
    print("📌 新增功能：自动解析Connection头、Pipeline自动识别、meta字段（前端动画）、连接关闭逻辑强化")
    print("=" * 80)

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False  # 生产环境关闭debug，避免安全风险
    )