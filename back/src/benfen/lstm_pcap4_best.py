import os
import random
import numpy as np
import pandas as pd
import joblib
from scapy.all import IP, TCP, Raw, wrpcap
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import LSTM
from tensorflow.keras import metrics, losses
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from datetime import datetime
import multiprocessing
import time
from typing import List, Optional
import uuid

# 全局配置：禁用无关警告
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'


# ===================== 1. 核心配置（无修改） =====================
class Config:
    """仅保留原有配置，删除所有TLS AI特征相关内容"""
    MODEL_PATH = "back/models/best/lstm_autoencoder_cpu_200k.h5"
    SCALER_PATH = "back/models/best/scaler_cpu_200k.pkl"
    AI_TIMESTEPS = 10
    AI_FEATURES = 9
    AI_FEATURES_LIST = [
        "src_port", "packet_len", "tcp_window", "tls_rand_len",
        "cookie_len", "http_method", "tls_suite", "seq_offset", "ack_offset"
    ]
    FEATURE_MAPPING = {
        "src_port": {"min": 1024, "max": 65535},
        "packet_len": {"min": 50, "max": 500},
        "tcp_window": {"min": 8192, "max": 65535},
        "tls_rand_len": {"fixed": 32},
        "cookie_len": {"min": 10, "max": 20},
        "http_method": {"map": {1: "GET", 2: "POST", 3: "PUT", 4: "DELETE"}, "valid_keys": [1, 2, 3, 4]},
        "tls_suite": {"map": {1: "0x1301", 2: "0x1302"}, "valid_keys": [1, 2]},
        "seq_offset": {"min": 1, "max": 1000},
        "ack_offset": {"min": 1, "max": 1000}
    }

    PROTOCOL_SPEC = {
        "TCP": {"syn_seq_consume": 1, "fin_seq_consume": 1, "ack_seq_consume": 0},
        "TLS1.3": {
            "version_legacy": b"\x03\x03",
            "version_actual": b"\x03\x04",
            "session_id_len": 16,
            "handshake_types": {"client_hello": 1, "server_hello": 2, "encrypted_extensions": 8, "certificate": 11,
                                "finished": 20, "certificate_verify": 15},
            "app_data_type": b"\x17"
        },
        "HTTP": {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            "content_type": "application/json",
            "response_codes": {200: "OK", 201: "Created", 404: "Not Found", 405: "Method Not Allowed"}
        }
    }

    SRC_IP = "192.168.1.101"
    DST_HTTP_IP = "103.235.46.39"
    DST_HTTPS_IP = "121.41.100.89"
    SAVE_DIR_HTTP = "back/data/generated_http"
    SAVE_DIR_HTTPS = "back/data/generated_https"
    SEED = 42

    # 并发配置
    MAX_PROCESSES = max(1, multiprocessing.cpu_count() - 2)
    BATCH_SIZE = 50
    QPS_LIMIT = 100


# ===================== 2. AI模型层（核心修改：兼容两个序列化问题） =====================
class CustomLSTM(LSTM):
    """自定义LSTM类，忽略废弃的time_major参数，解决版本兼容性问题"""

    def __init__(self, *args, **kwargs):
        # 移除废弃的time_major参数（如果存在），不影响其他功能
        kwargs.pop('time_major', None)
        # 调用父类LSTM的初始化方法
        super().__init__(*args, **kwargs)


# 自定义均方误差函数，用于映射旧模型中的keras.metrics.mse
def custom_mse(y_true, y_pred):
    """兼容旧模型的mse度量指标，对应新版本的均方误差计算"""
    return losses.mean_squared_error(y_true, y_pred)


class AIModel:
    def __init__(self, config: Config):
        self.config = config
        self.model = None
        self.scaler = None
        self._load_model()
        random.seed(config.SEED)

    def _load_model(self):
        try:
            # 核心修改：自定义对象映射，同时解决两个序列化问题
            # 1. CustomLSTM：解决time_major参数废弃问题
            # 2. mse/mean_squared_error：解决keras.metrics.mse无法反序列化问题
            custom_objects_map = {
                'LSTM': CustomLSTM,
                'mse': custom_mse,
                'mean_squared_error': custom_mse,
                'MeanSquaredError': metrics.MeanSquaredError
            }

            # 加载模型时指定自定义对象映射
            self.model = load_model(self.config.MODEL_PATH, custom_objects=custom_objects_map)
            self.scaler = joblib.load(self.config.SCALER_PATH)
            # 仅保留原有HTTP特征列表，删除TLS特征相关逻辑
            self.scaler.feature_names_in_ = self.config.AI_FEATURES_LIST
            print(f"✅ AI模型加载成功（{self.config.AI_TIMESTEPS}步×{self.config.AI_FEATURES}维）")
        except Exception as e:
            print(f"⚠️ AI模型降级为增强随机数：{e}")
            self.model = None

    def generate_features(self, session_id: int, specified_method: str = None) -> dict:
        base_input = np.random.normal(0, 1, (1, self.config.AI_TIMESTEPS, self.config.AI_FEATURES))
        for t in range(self.config.AI_TIMESTEPS):
            base_input[0, t] = [
                random.randint(1024, 65535),
                random.randint(50, 500),
                random.randint(8192, 65535),
                32,
                random.randint(10, 20),
                random.choice([1, 2, 3, 4]),
                random.choice([1, 2]),
                random.randint(1, 1000),
                random.randint(1, 1000)
            ]

        if self.model is not None:
            try:
                flat = base_input.reshape(-1, self.config.AI_FEATURES)
                flat_df = pd.DataFrame(flat, columns=self.config.AI_FEATURES_LIST)
                norm_flat = self.scaler.transform(flat_df)
                norm_input = norm_flat.reshape(1, self.config.AI_TIMESTEPS, self.config.AI_FEATURES)
                pred = self.model.predict(norm_input, verbose=0)[0, -1, :]
                pred_df = pd.DataFrame([pred], columns=self.config.AI_FEATURES_LIST)
                pred = self.scaler.inverse_transform(pred_df)[0]
            except Exception as e:
                print(f"⚠️ AI预测失败，使用随机值：{e}")
                pred = base_input[0, -1, :]
        else:
            pred = base_input[0, -1, :]

        features = {}
        for i, name in enumerate(self.config.AI_FEATURES_LIST):
            mapping = self.config.FEATURE_MAPPING[name]
            if "fixed" in mapping:
                features[name] = mapping["fixed"]
            elif "map" in mapping:
                if name == "http_method" and specified_method is not None:
                    method_map = mapping["map"]
                    method_map_rev = {v: k for k, v in method_map.items()}
                    if specified_method not in method_map_rev:
                        print(f"⚠️ 指定方法{specified_method}不存在，默认使用GET")
                        val = 1
                    else:
                        val = method_map_rev[specified_method]
                    print(f"🔍 调试：指定方法={specified_method} → val={val}")
                else:
                    val = round(pred[i])
                    valid_keys = mapping.get("valid_keys", [1])
                    val = max(valid_keys[0], min(valid_keys[-1], val))

                method_map = mapping["map"]
                if val not in method_map:
                    print(f"⚠️ val={val}不在映射表中，使用默认值{valid_keys[0]}")
                    val = valid_keys[0]

                features[name] = method_map[val]
                print(f"🔍 调试：name={name} → val={val} → 映射值={features[name]}")
            else:
                val = round(pred[i])
                if name == "src_port":
                    features[name] = max(1024, min(65535, val))
                else:
                    features[name] = max(mapping["min"], min(mapping["max"], val))

        port_offset = session_id % 1000
        features["src_port"] = features["src_port"] + port_offset
        if features["src_port"] > 65535:
            features["src_port"] = 65535 - port_offset

        return features

    def generate_tls_features(self, session_id: str) -> dict:
        """复用现有9维HTTP模型生成TLS参数，彻底消除特征不匹配警告"""
        # 1. 用现有模型生成HTTP特征（模型训练过这些特征，无警告）
        temp_session_id = int(session_id[-8:], 16)
        http_feat = self.generate_features(temp_session_id)

        # 2. 从HTTP特征映射TLS参数（核心逻辑）
        tls_features = {}
        # 映射→TLS随机数字节
        tls_features["tls_ch_random_byte1"] = (http_feat["src_port"] % 256)
        tls_features["tls_ch_random_byte2"] = (http_feat["packet_len"] % 256)
        tls_features["tls_sh_random_byte1"] = (http_feat["tcp_window"] % 256)
        tls_features["tls_sh_random_byte2"] = (http_feat["cookie_len"] % 256)

        # 映射→椭圆曲线（基于src_port奇偶性）
        curve_val = 1 if (http_feat["src_port"] % 2) == 0 else 2
        tls_features["tls_elliptic_curve"] = 0x0017 if curve_val == 1 else 0x0018

        # 映射→SNI长度（2-10）
        sni_len = max(2, min(10, http_feat["cookie_len"] % 9 + 2))
        tls_features["tls_sni_length"] = sni_len

        # 映射→证书签名长度（200-300）
        sig_len = max(200, min(300, (http_feat["packet_len"] * 2) + 100))
        tls_features["tls_cv_signature_len"] = sig_len

        # 映射→密码套件（基于tcp_window奇偶性）
        suite_val = 1 if (http_feat["tcp_window"] % 2) == 0 else 2
        tls_features["tls_cipher_suite"] = 0x1301 if suite_val == 1 else 0x1302

        # 3. 生成完整TLS参数
        ch_random = bytearray(os.urandom(32))
        ch_random[0] = tls_features["tls_ch_random_byte1"] % 256
        ch_random[1] = tls_features["tls_ch_random_byte2"] % 256
        tls_features["ch_random"] = bytes(ch_random)

        sh_random = bytearray(os.urandom(32))
        sh_random[0] = tls_features["tls_sh_random_byte1"] % 256
        sh_random[1] = tls_features["tls_sh_random_byte2"] % 256
        tls_features["sh_random"] = bytes(sh_random)

        sni_chars = random.choices(b'abcdefghijklmnopqrstuvwxyz', k=tls_features["tls_sni_length"])
        tls_features["sni"] = bytes(sni_chars)

        tls_features["cv_signature"] = os.urandom(tls_features["tls_cv_signature_len"])
        tls_features["finished_verify_data"] = os.urandom(32)
        tls_features["client_finished_verify"] = os.urandom(32)

        print(
            f"🔍 TLS特征生成完成（LSTM生效，会话ID={session_id}）：椭圆曲线=0x{tls_features['tls_elliptic_curve']:04x} | SNI={tls_features['sni'].decode()} | 签名长度={tls_features['tls_cv_signature_len']}")
        return tls_features


# ===================== 3. 会话管理器（无修改） =====================
class SessionManager:
    def __init__(self, config: Config, ai_model: AIModel, process_id: int = 0):
        self.config = config
        self.ai = ai_model
        self.sessions = {}
        self.process_id = process_id

    def create_session(self, session_type: str, specified_method: str = None) -> str:
        session_id = f"{self.process_id}_{uuid.uuid4().hex[:8]}"
        feat = self.ai.generate_features(int(session_id[-8:], 16), specified_method=specified_method)
        client_init_seq = random.randint(1000000, 9999999)
        server_init_seq = random.randint(1000000, 9999999)

        self.sessions[session_id] = {
            "type": session_type, "feat": feat,
            "src_port": feat["src_port"],
            "client_seq": client_init_seq, "server_seq": server_init_seq,
            "client_ack": server_init_seq, "server_ack": client_init_seq,
            "dst_ip": self.config.DST_HTTP_IP if session_type == "http" else self.config.DST_HTTPS_IP,
            "dst_port": 80 if session_type == "http" else 443,
            "cookie": f"SESSIONID_{random.randint(10 ** feat['cookie_len'], 10 ** (feat['cookie_len'] + 1) - 1)}",
            "tls_sid": os.urandom(self.config.PROTOCOL_SPEC["TLS1.3"]["session_id_len"])
        }
        print(
            f"✅ 创建{session_type}会话（ID={session_id}）| 端口={self.sessions[session_id]['src_port']} | 方法={feat['http_method']} | Cookie={self.sessions[session_id]['cookie'][:10]}...")
        return session_id

    def get_session(self, session_id: str) -> dict:
        if session_id not in self.sessions:
            raise ValueError(f"会话ID {session_id} 不存在")
        return self.sessions[session_id]

    def update_tcp_seq_ack(self, session_id: str, is_client: bool, pkt_type: str, data_len: int = 0):
        s = self.get_session(session_id)
        tcp_spec = self.config.PROTOCOL_SPEC["TCP"]

        if is_client:
            if pkt_type == "SYN":
                s["client_seq"] += tcp_spec["syn_seq_consume"]
            elif pkt_type == "FIN":
                s["client_seq"] += tcp_spec["fin_seq_consume"]
            elif pkt_type == "DATA":
                s["client_seq"] += data_len
            s["server_ack"] = s["client_seq"]
        else:
            if pkt_type == "SYN":
                s["server_seq"] += tcp_spec["syn_seq_consume"]
            elif pkt_type == "FIN":
                s["server_seq"] += tcp_spec["fin_seq_consume"]
            elif pkt_type == "DATA":
                s["server_seq"] += data_len
            s["client_ack"] = s["server_seq"]


# ===================== 4. 协议生成器（已修复语法错误） =====================
class FullProtocolGenerator:
    def __init__(self, config: Config, session_mgr: SessionManager):
        self.config = config
        self.session = session_mgr

    def tcp_3way_handshake(self, session_id: str) -> list:
        s = self.session.get_session(session_id)
        pkts = []
        syn = IP(src=self.config.SRC_IP, dst=s["dst_ip"]) / TCP(
            sport=s["src_port"], dport=s["dst_port"], flags="S",
            seq=s["client_seq"], ack=0, window=s["feat"]["tcp_window"]
        )
        pkts.append(syn)
        self.session.update_tcp_seq_ack(session_id, is_client=True, pkt_type="SYN")

        syn_ack = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="SA",
            seq=s["server_seq"], ack=s["server_ack"], window=s["feat"]["tcp_window"]
        )
        pkts.append(syn_ack)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="SYN")

        ack = IP(src=self.config.SRC_IP, dst=s["dst_ip"]) / TCP(
            sport=s["src_port"], dport=s["dst_port"], flags="A",
            seq=s["client_seq"], ack=s["client_ack"], window=s["feat"]["tcp_window"]
        )
        pkts.append(ack)
        print(f"✅ TCP三次握手完成（会话ID={session_id}）")
        return pkts

    def tcp_4way_teardown(self, session_id: str) -> list:
        s = self.session.get_session(session_id)
        pkts = []
        fin_ack1 = IP(src=self.config.SRC_IP, dst=s["dst_ip"]) / TCP(
            sport=s["src_port"], dport=s["dst_port"], flags="FA",
            seq=s["client_seq"], ack=s["client_ack"], window=s["feat"]["tcp_window"]
        )
        pkts.append(fin_ack1)
        self.session.update_tcp_seq_ack(session_id, is_client=True, pkt_type="FIN")

        ack1 = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="A",
            seq=s["server_seq"], ack=s["server_ack"], window=s["feat"]["tcp_window"]
        )
        pkts.append(ack1)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="ACK")

        fin_ack2 = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="FA",
            seq=s["server_seq"], ack=s["server_ack"], window=s["feat"]["tcp_window"]
        )
        pkts.append(fin_ack2)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="FIN")

        ack2 = IP(src=self.config.SRC_IP, dst=s["dst_ip"]) / TCP(
            sport=s["src_port"], dport=s["dst_port"], flags="A",
            seq=s["client_seq"], ack=s["client_ack"], window=s["feat"]["tcp_window"]
        )
        pkts.append(ack2)
        print(f"✅ TCP四次挥手完成（会话ID={session_id}）")
        return pkts

    def tls13_full_handshake(self, session_id: str) -> list:
        s = self.session.get_session(session_id)
        feat = s["feat"]
        pkts = []
        tls_spec = self.config.PROTOCOL_SPEC["TLS1.3"]

        # 获取LSTM生成的TLS特征
        tls_feat = self.session.ai.generate_tls_features(session_id)
        tls_elliptic_curves = [tls_feat["tls_elliptic_curve"]]
        tls_supported_versions = [0x0304]  # TLS1.3

        # ========== 1. Client Hello（修复长度计算） ==========
        ch_random = tls_feat["ch_random"]
        ch_sess_id = s["tls_sid"]
        # 密码套件：转为2字节（TLS_AES_128_GCM_SHA256=0x1301，TLS_AES_256_GCM_SHA384=0x1302）
        ch_cipher_suites = tls_feat["tls_cipher_suite"].to_bytes(2, 'big')
        ch_compression = b"\x00"  # 仅支持null压缩

        # 修复：Supported Versions扩展（TLS1.3必选扩展）
        # 扩展格式：Type(2) + Length(2) + Version List Length(1) + Versions(n*2)
        supported_versions_content = bytes([1]) + b"".join([v.to_bytes(2, 'big') for v in tls_supported_versions])
        ch_ext_supported_versions = (
                b"\x00\x2b"  # Extension Type: supported_versions (43)
                + len(supported_versions_content).to_bytes(2, 'big')  # 修复：2字节长度
                + supported_versions_content
        )

        # 修复：Session Ticket扩展（可选）
        ch_ext_sess_ticket = (
                b"\x00\x23"  # Extension Type: session_ticket (35)
                + b"\x00\x00"  # 修复：2字节长度（空内容）
        )

        # 修复：扩展总长度（2字节）
        ch_extensions_list = [ch_ext_supported_versions, ch_ext_sess_ticket]
        ch_extensions = b"".join(ch_extensions_list)
        ch_extensions_length = len(ch_extensions).to_bytes(2, 'big')  # 修复：2字节编码

        # Client Hello内容（严格按RFC 8446格式）
        ch_content = (
                tls_spec["version_legacy"]  # 0x0303（TLS1.2兼容）
                + ch_random  # 32字节随机数
                + bytes([len(ch_sess_id)])  # Session ID长度（1字节）
                + ch_sess_id
                + len(ch_cipher_suites).to_bytes(2, 'big')  # 密码套件长度（2字节）
                + ch_cipher_suites
                + bytes([len(ch_compression)])  # 压缩方法长度（1字节）
                + ch_compression
                + ch_extensions_length  # 修复：扩展总长度（2字节）
                + ch_extensions
        )

        # Client Hello握手消息（3字节长度）
        ch_handshake = (
                bytes([tls_spec["handshake_types"]["client_hello"]])  # Handshake Type: 1
                + len(ch_content).to_bytes(3, 'big')  # 3字节长度
                + ch_content
        )

        # TLS Record层（2字节长度）
        ch_record = (
                b"\x16"  # Content Type: Handshake (22)
                + tls_spec["version_legacy"]  # 0x0303
                + len(ch_handshake).to_bytes(2, 'big')  # 修复：2字节长度
                + ch_handshake
        )

        ch_pkt = IP(src=self.config.SRC_IP, dst=s["dst_ip"]) / TCP(
            sport=s["src_port"], dport=s["dst_port"], flags="PA",
            seq=s["client_seq"], ack=s["client_ack"], window=feat["tcp_window"]
        ) / Raw(load=ch_record)
        pkts.append(ch_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=True, pkt_type="DATA", data_len=len(ch_record))

        # ========== 2. Server Hello（重点修复supported_groups扩展） ==========
        sh_random = tls_feat["sh_random"]
        sh_sess_id = s["tls_sid"]
        sh_cipher_suite = tls_feat["tls_cipher_suite"].to_bytes(2, 'big')
        sh_compression = b"\x00"  # null压缩

        # ✅ 修复：supported_groups扩展（严格按RFC 8446格式）
        # 步骤1：生成椭圆曲线字节（每个曲线2字节）
        elliptic_curves_bytes = b"".join([c.to_bytes(2, 'big') for c in tls_elliptic_curves])
        # 步骤2：List Length = 曲线字节总长度（1字节uint8）
        list_length = bytes([len(elliptic_curves_bytes)])  # 关键修复：1字节编码，而非数值直接使用
        # 步骤3：扩展内容 = List Length + 曲线字节
        supported_groups_content = list_length + elliptic_curves_bytes
        # 步骤4：扩展总长度 = 扩展内容的长度（2字节）
        supported_groups_ext_length = len(supported_groups_content).to_bytes(2, 'big')
        # 步骤5：完整扩展 = 类型 + 总长度 + 内容
        sh_ext_supported_groups = (
                b"\x00\x0a"  # Extension Type: supported_groups (10)
                + supported_groups_ext_length  # 扩展总长度（2字节）
                + supported_groups_content  # 扩展内容（List Length + 曲线）
        )

        # 修复：扩展总长度
        sh_extensions_list = [sh_ext_supported_groups]
        sh_extensions = b"".join(sh_extensions_list)
        sh_extensions_length = len(sh_extensions).to_bytes(2, 'big')  # 2字节编码

        # Server Hello内容（严格按RFC 8446格式）
        sh_content = (
                tls_spec["version_legacy"]  # 0x0303
                + sh_random  # 32字节随机数
                + bytes([len(sh_sess_id)])  # Session ID长度（1字节）
                + sh_sess_id
                + sh_cipher_suite  # 密码套件（2字节）
                + sh_compression  # 压缩方法（1字节）
                + sh_extensions_length  # 扩展总长度（2字节）
                + sh_extensions
        )

        # Server Hello握手消息
        sh_handshake = (
                bytes([tls_spec["handshake_types"]["server_hello"]])  # Handshake Type: 2
                + len(sh_content).to_bytes(3, 'big')  # 3字节长度
                + sh_content
        )

        # TLS Record层
        sh_record = (
                b"\x16"  # Content Type: Handshake (22)
                + tls_spec["version_legacy"]  # 0x0303
                + len(sh_handshake).to_bytes(2, 'big')  # 修复：2字节长度
                + sh_handshake
        )

        sh_pkt = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="PA",
            seq=s["server_seq"], ack=s["server_ack"], window=feat["tcp_window"]
        ) / Raw(load=sh_record)
        pkts.append(sh_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="DATA", data_len=len(sh_record))

        # ========== 3. Encrypted Extensions（保留，无报错） ==========
        sni = tls_feat["sni"]
        # 修复：SNI扩展格式
        sni_content = bytes([0]) + len(sni).to_bytes(2, 'big') + sni  # Type: host_name(0) + 长度 + SNI
        ee_ext_sni = (
                b"\x00\x00"  # Extension Type: server_name (0)
                + len(sni_content).to_bytes(2, 'big')  # 修复：2字节长度
                + sni_content
        )
        ee_extensions_list = [ee_ext_sni]
        ee_extensions = b"".join(ee_extensions_list)
        ee_extensions_length = len(ee_extensions).to_bytes(2, 'big')

        ee_content = ee_extensions_length + ee_extensions
        ee_handshake = (
                bytes([tls_spec["handshake_types"]["encrypted_extensions"]])  # Handshake Type: 8
                + len(ee_content).to_bytes(3, 'big')
                + ee_content
        )
        ee_record = (
                b"\x16"
                + tls_spec["version_actual"]  # 0x0304
                + len(ee_handshake).to_bytes(2, 'big')
                + ee_handshake
        )
        ee_pkt = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="PA",
            seq=s["server_seq"], ack=s["server_ack"], window=feat["tcp_window"]
        ) / Raw(load=ee_record)
        pkts.append(ee_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="DATA", data_len=len(ee_record))

        # ========== 4. Certificate（修复证书长度） ==========
        # 修复：使用合规的dummy证书（长度合理）
        dummy_cert = (
            b"\x30\x82\x01\x22\x30\x82\x01\x0a\x02\x01\x00\x30\x0d\x06\x09"
            b"\x2a\x86\x48\x86\xf7\x0d\x01\x01\x0b\x05\x00\x30\x13\x06\x03"
            b"\x55\x04\x03\x13\x0c\x65\x78\x61\x6d\x70\x6c\x65\x2e\x63\x6f\x6d\x00"
        )
        # 修复：证书长度（3字节编码）
        cert_length = len(dummy_cert).to_bytes(3, 'big')
        # 证书列表格式：总长度(3) + 证书1长度(3) + 证书1内容
        cert_content = (
                (len(cert_length + dummy_cert)).to_bytes(3, 'big')  # 证书列表总长度
                + cert_length
                + dummy_cert
        )

        cert_handshake = (
                bytes([tls_spec["handshake_types"]["certificate"]])  # Handshake Type: 11
                + len(cert_content).to_bytes(3, 'big')  # 3字节长度
                + cert_content
        )
        cert_record = (
                b"\x16"
                + tls_spec["version_actual"]  # 0x0304
                + len(cert_handshake).to_bytes(2, 'big')  # 修复：2字节长度
                + cert_handshake
        )
        cert_pkt = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="PA",
            seq=s["server_seq"], ack=s["server_ack"], window=feat["tcp_window"]
        ) / Raw(load=cert_record)
        pkts.append(cert_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="DATA", data_len=len(cert_record))

        # ========== 5. Certificate Verify（保留） ==========
        cv_algorithm = b"\x04\x03"  # ECDSA secp256r1 SHA256
        cv_signature = tls_feat["cv_signature"]
        cv_content = (
                cv_algorithm
                + len(cv_signature).to_bytes(2, 'big')
                + cv_signature
        )
        cv_handshake = (
                b"\x0f"  # Handshake Type: certificate_verify (15)
                + len(cv_content).to_bytes(3, 'big')
                + cv_content
        )
        cv_record = (
                b"\x16"
                + tls_spec["version_actual"]
                + len(cv_handshake).to_bytes(2, 'big')
                + cv_handshake
        )
        cv_pkt = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="PA",
            seq=s["server_seq"], ack=s["server_ack"], window=feat["tcp_window"]
        ) / Raw(load=cv_record)
        pkts.append(cv_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="DATA", data_len=len(cv_record))

        # ========== 6. Finished（保留） ==========
        finished_verify_data = tls_feat["finished_verify_data"]
        finished_handshake = (
                bytes([tls_spec["handshake_types"]["finished"]])  # Handshake Type: 20
                + len(finished_verify_data).to_bytes(3, 'big')
                + finished_verify_data
        )
        finished_record = (
                b"\x16"
                + tls_spec["version_actual"]
                + len(finished_handshake).to_bytes(2, 'big')
                + finished_handshake
        )
        finished_pkt = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="PA",
            seq=s["server_seq"], ack=s["server_ack"], window=feat["tcp_window"]
        ) / Raw(load=finished_record)
        pkts.append(finished_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="DATA", data_len=len(finished_record))

        # ========== 7. Client Finished（保留） ==========
        client_finished_verify = tls_feat["client_finished_verify"]
        client_fin_handshake = (
                bytes([tls_spec["handshake_types"]["finished"]])
                + len(client_finished_verify).to_bytes(3, 'big')
                + client_finished_verify
        )
        client_fin_record = (
                b"\x16"
                + tls_spec["version_actual"]
                + len(client_fin_handshake).to_bytes(2, 'big')
                + client_fin_handshake
        )
        client_fin_pkt = IP(src=self.config.SRC_IP, dst=s["dst_ip"]) / TCP(
            sport=s["src_port"], dport=s["dst_port"], flags="PA",
            seq=s["client_seq"], ack=s["client_ack"], window=feat["tcp_window"]
        ) / Raw(load=client_fin_record)
        pkts.append(client_fin_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=True, pkt_type="DATA", data_len=len(client_fin_record))

        print(f"✅ TLS1.3七次握手完成（会话ID={session_id}，LSTM生成参数，符合RFC 8446完整规范）")
        return pkts

    def ai_http_request_response(self, session_id: str, is_https=False) -> list:
        s = self.session.get_session(session_id)
        feat = s["feat"]
        pkts = []
        http_spec = self.config.PROTOCOL_SPEC["HTTP"]
        tls_spec = self.config.PROTOCOL_SPEC["TLS1.3"] if is_https else None

        # 修复1：补充未定义的method变量（从会话特征中获取）
        method = feat["http_method"]
        # 兜底：确保method是合法值
        if method not in ["GET", "POST", "PUT", "DELETE"]:
            method = "GET"

        # 修复2：补充未定义的ai_req_data变量（对齐原有逻辑）
        ai_req_data = {
            "ai_src_port": feat["src_port"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "method": method
        }
        req_body = b""

        if method in ["POST", "PUT"]:
            ai_req_data["data"] = {
                "id": random.randint(1000, 9999),
                "content": f"Generated by AI for {method} request"
            }
            req_body = str(ai_req_data).replace("'", '"').encode("utf-8")
        elif method == "DELETE":
            ai_req_data["resource_id"] = random.randint(1, 100)
            req_body = str(ai_req_data).replace("'", '"').encode("utf-8")
        else:
            req_body = b""
            print(f"🔍 调试：GET方法生成，请求体为空（符合HTTP规范）")

        http_request = b""
        http_request += f"{method} /api/resource HTTP/1.1\r\n".encode("utf-8")
        http_request += f"Host: {s['dst_ip']}\r\n".encode("utf-8")
        http_request += f"User-Agent: {http_spec['user_agent']}\r\n".encode("utf-8")
        http_request += f"Cookie: {s['cookie']}\r\n".encode("utf-8")
        if method in ["POST", "PUT"]:
            http_request += f"Content-Type: {http_spec['content_type']}\r\n".encode("utf-8")
            http_request += f"Content-Length: {len(req_body)}\r\n".encode("utf-8")
        http_request += b"\r\n"
        http_request += req_body

        if is_https and tls_spec:  # 增加非空判断，避免None调用属性
            tls_app_header = tls_spec["app_data_type"] + tls_spec["version_actual"] + len(http_request).to_bytes(2,
                                                                                                                 'big')
            http_request = tls_app_header + http_request

        req_pkt = IP(src=self.config.SRC_IP, dst=s["dst_ip"]) / TCP(
            sport=s["src_port"], dport=s["dst_port"], flags="PA",
            seq=s["client_seq"], ack=s["client_ack"], window=65535
        ) / Raw(load=http_request)
        pkts.append(req_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=True, pkt_type="DATA", data_len=len(http_request))

        method_resp_codes = {
            "GET": 200,
            "POST": 201,
            "PUT": 200,
            "DELETE": 200
        }
        resp_code = method_resp_codes.get(method, 200)
        resp_msg = http_spec["response_codes"].get(resp_code, "OK")
        # 修复3：session_id添加引号，符合JSON格式
        resp_body = f'{{"status":"{resp_msg}","session_id":"{session_id}","method":"{method}"}}'.encode("utf-8")

        http_response = b""
        http_response += f"HTTP/1.1 {resp_code} {resp_msg}\r\n".encode("utf-8")
        http_response += b"Server: nginx\r\n"
        http_response += b"Content-Type: application/json\r\n"
        http_response += f"Content-Length: {len(resp_body)}\r\n".encode("utf-8")
        http_response += b"\r\n"
        http_response += resp_body

        if is_https and tls_spec:  # 增加非空判断，避免None调用属性
            tls_app_header = tls_spec["app_data_type"] + tls_spec["version_actual"] + len(http_response).to_bytes(2,
                                                                                                                  'big')
            http_response = tls_app_header + http_response

        resp_pkt = IP(src=s["dst_ip"], dst=self.config.SRC_IP) / TCP(
            sport=s["dst_port"], dport=s["src_port"], flags="PA",
            seq=s["server_seq"], ack=s["server_ack"], window=65535
        ) / Raw(load=http_response)
        pkts.append(resp_pkt)
        self.session.update_tcp_seq_ack(session_id, is_client=False, pkt_type="DATA", data_len=len(http_response))

        print(f"✅ 严格HTTP {method}/{resp_code}完成（会话ID={session_id}，Wireshark可自动识别）")
        return pkts


# ===================== 5. 完整会话框架（无修改） =====================
class FullSessionFramework:
    def __init__(self, config: Config, process_id: int = 0):
        self.config = config
        self.process_id = process_id
        self.ai = AIModel(config)
        self.session_mgr = SessionManager(config, self.ai, process_id=process_id)
        self.proto_gen = FullProtocolGenerator(config, self.session_mgr)
        os.makedirs(config.SAVE_DIR_HTTP, exist_ok=True)
        os.makedirs(config.SAVE_DIR_HTTPS, exist_ok=True)

    def generate_http_session(self, specified_method: str = None) -> str:
        session_id = self.session_mgr.create_session("http", specified_method=specified_method)
        pkts = []
        pkts.extend(self.proto_gen.tcp_3way_handshake(session_id))
        pkts.extend(self.proto_gen.ai_http_request_response(session_id))
        pkts.extend(self.proto_gen.tcp_4way_teardown(session_id))

        method_suffix = specified_method if specified_method else "random"
        save_path = f"{self.config.SAVE_DIR_HTTP}/ai_http_{method_suffix}_session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pcap"
        wrpcap(save_path, pkts)
        print(f"💾 HTTP({method_suffix})会话保存：{save_path} | 总报文数={len(pkts)}")
        return session_id

    def generate_https_session(self, specified_method: str = None) -> str:
        session_id = self.session_mgr.create_session("https", specified_method=specified_method)
        pkts = []
        pkts.extend(self.proto_gen.tcp_3way_handshake(session_id))
        pkts.extend(self.proto_gen.tls13_full_handshake(session_id))
        pkts.extend(self.proto_gen.ai_http_request_response(session_id, is_https=True))
        pkts.extend(self.proto_gen.tcp_4way_teardown(session_id))

        method_suffix = specified_method if specified_method else "random"
        save_path = f"{self.config.SAVE_DIR_HTTPS}/ai_https_{method_suffix}_session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pcap"
        wrpcap(save_path, pkts)
        print(f"💾 HTTPS({method_suffix})会话保存：{save_path} | 总报文数={len(pkts)}")
        return session_id


# ===================== 6. 修复后的并发管理器（核心重构） =====================
# 独立的worker函数（避免类属性序列化问题）
def worker_task(process_id: int, task_type: str, method: str, num_tasks: int, config_dict: dict, counter):
    """
    子进程工作函数
    :param process_id: 进程ID
    :param task_type: http/https
    :param method: HTTP方法
    :param num_tasks: 该进程要生成的会话数
    :param config_dict: Config的字典形式（可序列化）
    :param counter: 进程安全的计数器
    """
    # 重建Config对象
    config = Config()
    for k, v in config_dict.items():
        setattr(config, k, v)

    # 初始化框架
    framework = FullSessionFramework(config, process_id=process_id)
    generate_func = framework.generate_http_session if task_type == "http" else framework.generate_https_session

    # 生成会话
    for _ in range(num_tasks):
        try:
            generate_func(specified_method=method)
            # 进程安全更新计数器
            with counter.get_lock():
                counter.value += 1
            # 限流（控制QPS）
            time.sleep(1 / config.QPS_LIMIT)
        except Exception as e:
            print(f"❌ 进程{process_id}生成会话失败：{e}")


class FixedConcurrentSessionManager:
    def __init__(self, config: Config):
        self.config = config
        # 进程安全的计数器（统计已完成的会话数）
        self.counter = multiprocessing.Value('i', 0)

    def run_concurrent_simulation(self, task_type: str = "https", method: str = "GET", num_concurrent: int = 100):
        """
        运行大并发会话生成（修复序列化问题）
        :param task_type: 会话类型（http/https）
        :param method: HTTP方法（GET/POST/PUT/DELETE）
        :param num_concurrent: 并发会话数
        """
        if num_concurrent <= 0:
            raise ValueError("并发数必须大于0")
        if task_type not in ["http", "https"]:
            raise ValueError("任务类型必须是http或https")

        # 将Config转为字典（可序列化）
        config_dict = {
            k: v for k, v in vars(self.config).items()
            if not k.startswith('_') and isinstance(v, (int, str, dict, list, tuple))
        }

        # 计算每进程任务数
        max_processes = self.config.MAX_PROCESSES
        tasks_per_process = num_concurrent // max_processes
        remaining_tasks = num_concurrent % max_processes

        # 准备进程参数
        processes = []
        start_time = time.time()

        print(f"🚀 启动大并发仿真：{num_concurrent}个{task_type.upper()} {method}会话 | 进程数：{max_processes}")

        # 创建子进程
        for process_id in range(max_processes):
            task_count = tasks_per_process + (1 if process_id < remaining_tasks else 0)
            if task_count <= 0:
                continue

            p = multiprocessing.Process(
                target=worker_task,
                args=(
                    process_id,
                    task_type,
                    method,
                    task_count,
                    config_dict,
                    self.counter  # 共享计数器
                )
            )
            processes.append(p)
            p.start()

        # 监控进度
        while any(p.is_alive() for p in processes):
            time.sleep(1)
            completed = self.counter.value
            elapsed = time.time() - start_time
            qps = completed / elapsed if elapsed > 0 else 0
            print(
                f"\r📊 进度：{completed}/{num_concurrent} | QPS：{qps:.2f} | 剩余进程：{sum(p.is_alive() for p in processes)}",
                end="")

        # 等待所有进程结束
        for p in processes:
            p.join()

        # 最终统计
        elapsed = time.time() - start_time
        qps = self.counter.value / elapsed if elapsed > 0 else 0
        print(f"\n\n🎉 并发任务完成！")
        print(f"📈 总会话数：{self.counter.value} | 耗时：{elapsed:.2f}秒 | 平均QPS：{qps:.2f}")
        print(f"💾 生成文件路径：{self.config.SAVE_DIR_HTTP if task_type == 'http' else self.config.SAVE_DIR_HTTPS}")


# ===================== 测试入口 =====================
if __name__ == "__main__":
    # Windows系统必须加这行（修复多进程启动问题）
    multiprocessing.freeze_support()

    config = Config()
    # 初始化修复后的并发管理器
    concurrent_mgr = FixedConcurrentSessionManager(config)

    # ========== 原有单会话测试（保留，可直接运行） ==========
    framework = FullSessionFramework(config)
    framework.generate_http_session(specified_method="GET")

    # 可选：运行并发测试（取消注释即可）
    # concurrent_mgr.run_concurrent_simulation(
    #     task_type="https",
    #     method="GET",
    #     num_concurrent=500  # 可调整为1000/2000等
    # )