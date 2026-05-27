# ==================== 导入模块 ====================
import os
import sys
import time
import json
import threading
import ssl
import socket
import traceback
import logging
import subprocess
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Union

from flask import Flask, request, jsonify
from flask_cors import CORS

# Cryptography Imports
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# ==================== 全局配置 (跨平台适配) ====================

# 1. 系统识别
IS_WINDOWS = os.name == 'nt'
IS_LINUX = sys.platform.startswith('linux')
IS_DOCKER = os.environ.get('RUNNING_IN_DOCKER', 'false').lower() == 'true'

# 2. 目录配置 (使用相对路径 + 环境变量覆盖)
# 优先从环境变量获取基础目录，适配 Docker 挂载
BASE_DIR = os.environ.get('APP_BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.environ.get('APP_DATA_DIR', os.path.join(BASE_DIR, "data"))

# 标准化目录路径
LOG_DIR = os.path.join(DATA_DIR, "Log", "certs_log")
CERT_API_DIR = os.path.join(DATA_DIR, 'generated_certs') 

TLS_BASE_DIR = os.path.join(DATA_DIR, "tls1.3")
TLS_CERTS_DIR = os.path.join(TLS_BASE_DIR, "certs", "P-256")
TLS_KEYLOG_DIR = os.path.join(TLS_BASE_DIR, "key_log")
TLS_PCAP_DIR = os.path.join(TLS_BASE_DIR, "https")

# 3. tshark 路径适配 (跨平台)
if IS_WINDOWS:
    TSHARK_PATH = os.environ.get('TSHARK_PATH', r"E:\Program Files\Wireshark\tshark.exe")
else:
    # Linux/Docker 默认路径
    TSHARK_PATH = os.environ.get('TSHARK_PATH', "/usr/bin/tshark")

TSHARK_AVAILABLE = os.path.exists(TSHARK_PATH)

# 4. 网络配置
SIMULATION_HOST = os.environ.get('SIMULATION_HOST', "127.0.0.1")
SIMULATION_PORT = int(os.environ.get('SIMULATION_PORT', 4433))
TEST_PORT = int(os.environ.get('TEST_PORT', 4433))

# ==================== 日志配置 (跨平台) ====================
logger = logging.getLogger(__name__)

if not TSHARK_AVAILABLE:
    logger.warning(f"tshark 未找到: {TSHARK_PATH}，PCAP 生成将被模拟")

# 补充原代码缺失的测试服务器函数占位
def run_test_server(cert_path, key_path):
    logger.info(f"Mock Server started with {cert_path}")
    while True: time.sleep(10)

def ensure_tls_directories():
    """确保目录存在 (跨平台)"""
    for d in [TLS_CERTS_DIR, TLS_KEYLOG_DIR, TLS_PCAP_DIR, LOG_DIR, CERT_API_DIR]:
        os.makedirs(d, exist_ok=True)

ensure_tls_directories()

# ==================== 核心逻辑：证书生成器 (无修改，已兼容) ====================
class CertificateGenerator:
    """证书生成器 (融合重构优化版 + 保留原有ECC P-256证书生成功能)"""
    
    def __init__(self, output_dir: str = "data/generated_certs"):
        # 适配相对路径/绝对路径
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(BASE_DIR, output_dir)
        self.output_dir = output_dir
        self.cert_types = ["self_signed", "ca_signed", "ca", "expired", "weak"]
        self._ensure_dirs()
        logger.info(f"证书生成器初始化完成，输出目录: {self.output_dir}")

    def _ensure_dirs(self):
        """初始化目录结构"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        for t in self.cert_types:
            os.makedirs(os.path.join(self.output_dir, t), exist_ok=True)

    def _write_cert_log(self, cert_info: Dict):
        """统一日志记录"""
        try:
            log_file = os.path.join(LOG_DIR, f"cert_generation_{datetime.now().strftime('%Y-%m-%d')}.log")
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "file_size": cert_info.get('file_size', 0),
                **{k: v for k, v in cert_info.items() if k not in ['file_size']}
            }
            with open(log_file, "a", encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"日志记录失败: {e}")

    def _save_cert_files(self, type_name: str, filename_base: str, cert, key) -> Dict:
        """通用文件保存逻辑"""
        target_dir = os.path.join(self.output_dir, type_name)
        cert_path = os.path.join(target_dir, f"{filename_base}.pem")
        key_path = os.path.join(target_dir, f"{filename_base}_key.pem")

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        return {
            'cert_path': cert_path, 
            'key_path': key_path, 
            'size': os.path.getsize(cert_path)
        }

    def _generate_key(self, size=2048):
        return rsa.generate_private_key(public_exponent=65537, key_size=size, backend=default_backend())

    def _create_name(self, common_name, org, country):
        return x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

    def _build_and_sign(self, subject, issuer, key_to_sign, signing_key, 
                       not_before, not_after, san_domains=None, 
                       hash_algo=hashes.SHA256(), serial=None):
        """通用证书构建与签名逻辑"""
        builder = x509.CertificateBuilder()
        builder = builder.subject_name(subject)
        builder = builder.issuer_name(issuer)
        builder = builder.public_key(key_to_sign.public_key())
        builder = builder.serial_number(serial or x509.random_serial_number())
        builder = builder.not_valid_before(not_before)
        builder = builder.not_valid_after(not_after)
        
        if san_domains:
            builder = builder.add_extension(
                x509.SubjectAlternativeName([x509.DNSName(d) for d in san_domains]),
                critical=False,
            )
        
        return builder.sign(signing_key, hash_algo, default_backend())

    def _package_result(self, type_name, filename_base, file_info, cert, key_size, **kwargs):
        """封装标准返回结果"""
        result = {
            'type': type_name,
            'certificate_path': file_info['cert_path'],
            'private_key_path': file_info['key_path'],
            'certificate_filename': f"{filename_base}.pem",
            'private_key_filename': f"{filename_base}_key.pem",
            'file_size': file_info['size'],
            'key_size': key_size,
            'serial_number': str(cert.serial_number),
            'not_valid_before': cert.not_valid_before.isoformat(),
            'not_valid_after': cert.not_valid_after.isoformat(),
            **kwargs
        }
        self._write_cert_log(result)
        logger.info(f"生成的证书 ({type_name}): {result['certificate_filename']}")
        return result

    def generate_ecc_p256_cert(self, common_name="localhost", output_dir=TLS_CERTS_DIR):
        try:
            private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
            subject = issuer = self._create_name(common_name, "Simulation Lab", "CN")
            now = datetime.now(timezone.utc)
            
            cert = self._build_and_sign(
                subject, issuer, private_key, private_key, 
                now, now + timedelta(days=365), 
                san_domains=[common_name, "127.0.0.1"]
            )

            cert_path = os.path.join(output_dir, "server.crt")
            key_path = os.path.join(output_dir, "server.key")

            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            logger.info(f"P-256 ECC证书已生成: {cert_path}")
            return cert_path, key_path
        except Exception as e:
            logger.error(f"ECC证书生成失败: {e}")
            raise e

    def generate_self_signed_certificate(self, common_name="example.com", organization="Example Org", 
                                       country="CN", key_size=2048, validity_days=365, san_domains=None):
        key = self._generate_key(key_size)
        subject = issuer = self._create_name(common_name, organization, country)
        now = datetime.now(timezone.utc)
        
        cert = self._build_and_sign(subject, issuer, key, key, now, now + timedelta(days=validity_days), san_domains or [common_name])
        
        ts = int(time.time())
        dt = datetime.now().strftime("%Y%m%d%H%M%S")
        fname = f"self_signed_{dt}_{ts}"
        
        files = self._save_cert_files("self_signed", fname, cert, key)
        return self._package_result("self_signed", fname, files, cert, key_size, subject={'common_name': common_name})

    def generate_ca_certificate(self, organization="Example CA", country="CN", key_size=4096, validity_days=3650):
        key = self._generate_key(key_size)
        cn = f"{organization} Root CA"
        subject = issuer = self._create_name(cn, organization, country)
        now = datetime.now(timezone.utc)
        
        cert = self._build_and_sign(subject, issuer, key, key, now, now + timedelta(days=validity_days), [cn])
        
        ts = int(time.time())
        dt = datetime.now().strftime("%Y%m%d%H%M%S")
        fname = f"ca_{dt}_{ts}"
        
        files = self._save_cert_files("ca", fname, cert, key)
        return self._package_result("ca", fname, files, cert, key_size, subject={'common_name': cn})

    def generate_ca_signed_certificate(self, common_name="example.com", organization="Example Org", country="CN",
                                     ca_cert_path=None, ca_key_path=None, key_size=2048, validity_days=365, san_domains=None):
        if not ca_cert_path or not ca_key_path:
            ca_res = self.generate_ca_certificate(organization, country)
            ca_cert_path, ca_key_path = ca_res['certificate_path'], ca_res['private_key_path']
        
        with open(ca_cert_path, 'rb') as f: ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        with open(ca_key_path, 'rb') as f: ca_key = serialization.load_pem_private_key(f.read(), None, default_backend())

        user_key = self._generate_key(key_size)
        subject = self._create_name(common_name, organization, country)
        now = datetime.now(timezone.utc)
        
        cert = self._build_and_sign(subject, ca_cert.subject, user_key, ca_key, now, now + timedelta(days=validity_days), san_domains or [common_name])
        
        ts = int(time.time())
        dt = datetime.now().strftime("%Y%m%d%H%M%S")
        fname = f"ca_signed_{dt}_{ts}"
        
        files = self._save_cert_files("ca_signed", fname, cert, user_key)
        return self._package_result("ca_signed", fname, files, cert, key_size, subject={'common_name': common_name}, ca_certificate_path=ca_cert_path)

    def generate_expired_certificate(self, common_name="expired.com", organization="Example Org", country="CN", key_size=2048, days_expired=30):
        key = self._generate_key(key_size)
        subject = issuer = self._create_name(common_name, organization, country)
        now = datetime.now(timezone.utc)
        
        not_before = now - timedelta(days=days_expired + 365)
        not_after = now - timedelta(days=days_expired)
        
        cert = self._build_and_sign(subject, issuer, key, key, not_before, not_after, [common_name])
        
        ts = int(time.time())
        dt = datetime.now().strftime("%Y%m%d%H%M%S")
        fname = f"expired_{dt}_{ts}"
        
        files = self._save_cert_files("expired", fname, cert, key)
        return self._package_result("expired", fname, files, cert, key_size, subject={'common_name': common_name}, is_expired=True)

    def generate_weak_certificate(self, common_name="weak.com", organization="Example Org", country="CN", key_size=1024, weak_signature=True):
        key = self._generate_key(key_size)
        subject = issuer = self._create_name(common_name, organization, country)
        now = datetime.now(timezone.utc)
        
        # 修复弱签名逻辑：实际使用 SHA1 (原代码未生效)
        hash_algo = hashes.SHA1() if weak_signature else hashes.SHA256()
        cert = self._build_and_sign(subject, issuer, key, key, now, now + timedelta(days=365), [common_name], hash_algo=hash_algo)
        
        ts = int(time.time())
        dt = datetime.now().strftime("%Y%m%d%H%M%S")
        fname = f"weak_{dt}_{ts}"
        
        files = self._save_cert_files("weak", fname, cert, key)
        return self._package_result("weak", fname, files, cert, key_size, subject={'common_name': common_name}, weak_signature=weak_signature)

    def list_generated_certificates(self) -> list:
        certs = []
        if os.path.exists(self.output_dir):
            for t in self.cert_types:
                d = os.path.join(self.output_dir, t)
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if f.endswith('.pem') and not f.endswith('_key.pem'):
                            p = os.path.join(d, f)
                            key_p = p.replace('.pem', '_key.pem')
                            certs.append({
                                'certificate_filename': f,
                                'certificate_path': p,
                                'certificate_type': t,
                                'private_key_exists': os.path.exists(key_p),
                                'file_size': os.path.getsize(p),
                                'created_time': datetime.fromtimestamp(os.path.getctime(p)).isoformat()
                            })
        return certs

    def delete_certificate(self, filename: str) -> bool:
        for t in self.cert_types:
            path = os.path.join(self.output_dir, t, filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    k_path = path.replace('.pem', '_key.pem')
                    if os.path.exists(k_path): os.remove(k_path)
                    logger.info(f"已删除证书: {filename}")
                    return True
                except Exception as e:
                    logger.error(f"删除失败: {e}")
        return False

    def clear_all_certificates(self) -> Dict:
        count = 0
        try:
            for t in self.cert_types:
                d = os.path.join(self.output_dir, t)
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if f.endswith('.pem'):
                            os.remove(os.path.join(d, f))
                            count += 1
            return {'success': True, 'deleted_files': count, 'message': f"清空完成，删除 {count} 文件"}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def generate_cert(self, cert_type, domain, validity_days, organization="Example Org", country="CN", key_size=2048):
        method_map = {
            'self-signed': self.generate_self_signed_certificate,
            'ca': self.generate_ca_certificate,
            'ca-signed': self.generate_ca_signed_certificate,
            'expired': self.generate_expired_certificate,
            'weak': self.generate_weak_certificate
        }
        
        if cert_type not in method_map:
            return {'status': 'error', 'message': f"不支持类型: {cert_type}"}
        
        try:
            kwargs = {'organization': organization, 'country': country, 'key_size': key_size}
            if cert_type in ['self-signed', 'ca-signed']:
                kwargs.update({'common_name': domain, 'validity_days': validity_days})
            elif cert_type == 'ca':
                kwargs.update({'validity_days': validity_days})
            elif cert_type == 'expired':
                kwargs.update({'common_name': domain})
            elif cert_type == 'weak':
                kwargs.update({'common_name': domain})

            result = method_map[cert_type](**kwargs)
            return {'status': 'success', 'message': '生成成功', 'data': result}
        except Exception as e:
            logger.error(f"生成失败: {traceback.format_exc()}")
            return {'status': 'error', 'message': str(e)}


# ==================== TLS 1.3 仿真器 (跨平台改造) ====================

class TlsSimulationManager:
    def __init__(self):
        self.captured_packets = []
        self.is_capturing = False
        self.server_ready = threading.Event()
        self.stop_server_event = threading.Event()
        self.tshark_process = None
        self.loopback_interface = None
        self._interface_cache = None

    def _run_tshark_command(self, args, timeout=10):
        """安全执行 tshark 命令 (跨平台)"""
        try:
            cmd = [TSHARK_PATH] + args
            logger.debug(f"执行命令: {' '.join(cmd)}")
            
            # 跨平台进程启动配置
            startupinfo = None
            creationflags = 0
            if IS_WINDOWS:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            elif IS_LINUX:
                creationflags = 0  # Linux 无需特殊配置
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                startupinfo=startupinfo,
                creationflags=creationflags,
                encoding='utf-8',
                errors='ignore'
            )
            
            return result.stdout, result.stderr, result.returncode
            
        except subprocess.TimeoutExpired:
            logger.error(f"tshark 命令超时")
            return None, "Timeout", -1
        except Exception as e:
            logger.error(f"tshark 命令执行失败: {e}")
            return None, str(e), -1

    def _get_loopback_interface(self):
        """获取 Loopback 接口 (跨平台)"""
        if self._interface_cache:
            return self._interface_cache
            
        if not TSHARK_AVAILABLE:
            return None
            
        try:
            stdout, stderr, returncode = self._run_tshark_command(["-D"])
            
            if stdout is None or not stdout.strip():
                logger.error(f"tshark -D 无输出, stderr: {stderr}")
                # 跨平台默认 Loopback 接口
                if IS_WINDOWS:
                    self._interface_cache = r"\Device\NPF_Loopback"
                else:  # Linux
                    self._interface_cache = "lo"
                logger.info(f"使用默认 Loopback 接口: {self._interface_cache}")
                return self._interface_cache
            
            logger.debug(f"tshark -D 输出:\n{stdout}")
            
            # 解析接口列表 (跨平台兼容)
            for line in stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                line_lower = line.lower()
                
                # 匹配 Loopback 接口
                if any(keyword in line_lower for keyword in ['loopback', 'lo', 'npcap loopback', 'adapter for loopback']):
                    # 提取接口编号/名称
                    if IS_WINDOWS:
                        # Windows 格式: "1. \Device\NPF_Loopback (Npcap Loopback Adapter)"
                        match = re.match(r'^(\d+)\.', line)
                        if match:
                            interface_num = match.group(1)
                            self._interface_cache = interface_num
                            logger.info(f"检测到 Windows Loopback 接口: {line} (使用编号: {interface_num})")
                            return interface_num
                        # 提取设备路径
                        match = re.search(r'(\\Device\\NPF[^\s\)]+)', line)
                        if match:
                            self._interface_cache = match.group(1)
                            logger.info(f"检测到 Windows Loopback 接口: {self._interface_cache}")
                            return self._interface_cache
                    else:
                        # Linux 格式: "1. lo (Loopback device)"
                        match = re.match(r'^(\d+)\.\s*(\w+)', line)
                        if match:
                            self._interface_cache = match.group(2)  # 直接使用接口名 (lo)
                            logger.info(f"检测到 Linux Loopback 接口: {self._interface_cache}")
                            return self._interface_cache
            
            # 兜底默认值
            if IS_WINDOWS:
                self._interface_cache = r"\Device\NPF_Loopback"
            else:
                self._interface_cache = "lo"
            logger.warning(f"未检测到专用 Loopback 接口，使用默认值: {self._interface_cache}")
            return self._interface_cache
            
        except Exception as e:
            logger.error(f"获取接口失败: {e}")
            traceback.print_exc()
            # 最终兜底
            self._interface_cache = "lo" if IS_LINUX else r"\Device\NPF_Loopback"
            return self._interface_cache

    def _check_npcap_loopback(self):
        """检查 Loopback 可用性 (跨平台)"""
        try:
            if IS_LINUX:
                # Linux 自带 lo 接口，无需检查 Npcap
                logger.info("Linux 系统，使用内置 lo 接口")
                return True
                
            stdout, stderr, returncode = self._run_tshark_command(["-D"])
            
            if stdout:
                has_loopback = any('loopback' in line.lower() for line in stdout.split('\n'))
                if has_loopback:
                    logger.info("Npcap Loopback Adapter 已检测到")
                    return True
                else:
                    logger.warning("未检测到 Npcap Loopback Adapter")
                    logger.warning("请确保安装 Npcap 时勾选了 'Support loopback traffic' 选项")
                    return False
            return False
        except Exception as e:
            logger.error(f"检查 Loopback 失败: {e}")
            return False

    def _run_server(self, cert_path, key_path, port):
        """TLS 服务器线程 (无修改)"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        
        try:
            context.set_ciphers('ECDHE+AESGCM:DHE+AESGCM')
        except Exception:
            pass

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((SIMULATION_HOST, port))
                sock.listen(1)
                logger.info(f"TLS Server listening on {SIMULATION_HOST}:{port}")
                self.server_ready.set()
                sock.settimeout(2.0)
                
                while not self.stop_server_event.is_set():
                    try:
                        conn, addr = sock.accept()
                        with context.wrap_socket(conn, server_side=True) as ssock:
                            logger.info(f"Connection from {addr}")
                            data = ssock.recv(1024)
                            ssock.sendall(b"Hello from TLS 1.3 Server! [ECC: P-256]")
                            time.sleep(0.5)
                            
                    except socket.timeout: 
                        continue
                    except Exception as e: 
                        logger.debug(f"Server connection error: {e}")
        except Exception as e:
            logger.error(f"Server Startup Error: {e}")
        finally:
            logger.info("TLS Server stopped")

    def _run_tshark_capture(self, port, pcap_path, timeout=10):
        """使用 tshark 进行抓包 (跨平台)"""
        if not TSHARK_AVAILABLE:
            logger.warning("tshark 不可用，跳过抓包")
            return False
            
        try:
            interface = self._get_loopback_interface()
            if not interface:
                logger.error("无法获取 Loopback 接口")
                return False
            
            # 构建 tshark 命令 (跨平台过滤规则)
            cmd = [
                TSHARK_PATH,
                "-i", interface,
                "-f", f"tcp port {port}",
                "-w", pcap_path,
                "-a", f"duration:{timeout}",
                "-q"
            ]
            
            # Linux/Docker 额外参数
            if IS_LINUX:
                cmd.insert(1, "-n")  # 禁用名称解析，提升性能
            
            logger.info(f"启动 tshark 抓包命令: {' '.join(cmd)}")
            
            # 跨平台进程启动配置
            startupinfo = None
            creationflags = 0
            if IS_WINDOWS:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW
            elif IS_LINUX:
                creationflags = 0
            
            self.tshark_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            self.is_capturing = True
            logger.info(f"tshark 抓包进程已启动 (PID: {self.tshark_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"启动 tshark 失败: {e}")
            traceback.print_exc()
            return False

    def _run_tshark_capture_alternative(self, port, pcap_path, timeout=10):
        """备用抓包方法 (跨平台)"""
        if not TSHARK_AVAILABLE:
            return False
            
        try:
            interface = self._get_loopback_interface()
            if not interface:
                return False
            
            # 不使用过滤器，抓取所有流量
            cmd = [
                TSHARK_PATH,
                "-i", interface,
                "-w", pcap_path,
                "-a", f"duration:{timeout}",
                "-q"
            ]
            
            # Linux/Docker 额外参数
            if IS_LINUX:
                cmd.insert(1, "-n")
            
            logger.info(f"启动 tshark 抓包 (无过滤): {' '.join(cmd)}")
            
            # 跨平台进程启动配置
            startupinfo = None
            creationflags = 0
            if IS_WINDOWS:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW
            
            self.tshark_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            self.is_capturing = True
            logger.info(f"tshark 抓包进程已启动 (无过滤模式, PID: {self.tshark_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"备用抓包方法失败: {e}")
            return False

    def _stop_tshark_capture(self):
        """停止 tshark 抓包 (跨平台)"""
        if self.tshark_process:
            try:
                # 检查进程是否还在运行
                if self.tshark_process.poll() is None:
                    logger.info("正在停止 tshark...")
                    
                    if IS_WINDOWS:
                        # Windows: 使用 taskkill
                        subprocess.run(
                            ['taskkill', '/F', '/PID', str(self.tshark_process.pid)],
                            capture_output=True,
                            timeout=5
                        )
                    else:
                        # Linux/Docker: 使用 terminate/kill
                        self.tshark_process.terminate()
                        try:
                            self.tshark_process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            self.tshark_process.kill()
                
                # 读取输出
                stdout, stderr = self.tshark_process.communicate(timeout=2)
                if stderr:
                    stderr_text = stderr.decode('utf-8', errors='ignore').strip()
                    if stderr_text:
                        logger.debug(f"tshark stderr: {stderr_text}")
                        
                logger.info("tshark 抓包已停止")
                
            except Exception as e:
                logger.error(f"停止 tshark 时出错: {e}")
            finally:
                self.tshark_process = None
                self.is_capturing = False

    def _parse_pcap_with_tshark(self, pcap_path):
        """解析 pcap 文件 (无修改)"""
        if not TSHARK_AVAILABLE or not os.path.exists(pcap_path):
            return []
            
        try:
            file_size = os.path.getsize(pcap_path)
            logger.info(f"PCAP 文件大小: {file_size} bytes")
            
            if file_size == 0:
                logger.warning("pcap 文件为空")
                return []
            
            if file_size < 100:
                logger.warning(f"pcap 文件太小 ({file_size} bytes)，可能没有捕获到数据")
                return []
            
            # 方法1: 使用 -T fields 格式
            stdout, stderr, returncode = self._run_tshark_command([
                "-r", pcap_path,
                "-T", "fields",
                "-e", "frame.number",
                "-e", "frame.time_relative",
                "-e", "ip.src",
                "-e", "ip.dst",
                "-e", "tcp.srcport",
                "-e", "tcp.dstport",
                "-e", "frame.len",
                "-e", "tcp.flags.str",
                "-e", "tls.record.content_type",
                "-e", "tls.handshake.type",
                "-E", "header=y",
                "-E", "separator=|",
                "-E", "quote=d"
            ], timeout=30)
            
            if returncode != 0:
                logger.error(f"tshark 解析失败: {stderr}")
                return self._parse_pcap_fallback(pcap_path)
            
            if not stdout or not stdout.strip():
                logger.warning("tshark 没有输出")
                return self._parse_pcap_fallback(pcap_path)
            
            # 解析输出
            packets = []
            lines = stdout.strip().split('\n')
            
            # 跳过表头
            for line in lines[1:]:
                if not line.strip():
                    continue
                    
                try:
                    # 去除引号并分割
                    parts = [p.strip('"') for p in line.split('|')]
                    
                    if len(parts) >= 7:
                        pkt_no = parts[0] if parts[0] else str(len(packets) + 1)
                        time_rel = parts[1] if parts[1] else "0.000000"
                        src_ip = parts[2] if parts[2] else "127.0.0.1"
                        dst_ip = parts[3] if parts[3] else "127.0.0.1"
                        src_port = parts[4] if parts[4] else "0"
                        dst_port = parts[5] if parts[5] else "0"
                        frame_len = parts[6] if parts[6] else "0"
                        tcp_flags = parts[7] if len(parts) > 7 and parts[7] else ""
                        tls_content = parts[8] if len(parts) > 8 and parts[8] else ""
                        tls_hs_type = parts[9] if len(parts) > 9 and parts[9] else ""
                        
                        # 构建信息字符串
                        info_parts = [f"Port: {src_port} -> {dst_port}"]
                        
                        if tcp_flags:
                            info_parts.append(f"[{tcp_flags}]")
                        
                        # 确定协议
                        protocol = "TCP"
                        if tls_content:
                            protocol = "TLSv1.3"
                            content_map = {"20": "ChangeCipherSpec", "21": "Alert", "22": "Handshake", "23": "AppData"}
                            for ct in tls_content.split(','):
                                ct = ct.strip()
                                if ct in content_map:
                                    info_parts.append(f"[{content_map[ct]}]")
                        
                        if tls_hs_type:
                            hs_map = {"1": "ClientHello", "2": "ServerHello", "11": "Certificate", 
                                     "13": "CertRequest", "15": "CertVerify", "20": "Finished"}
                            for ht in tls_hs_type.split(','):
                                ht = ht.strip()
                                if ht in hs_map:
                                    info_parts.append(f"[{hs_map[ht]}]")
                        
                        packets.append({
                            "no": int(pkt_no) if pkt_no.isdigit() else len(packets) + 1,
                            "time": time_rel,
                            "source": src_ip,
                            "destination": dst_ip,
                            "protocol": protocol,
                            "length": int(frame_len) if frame_len.isdigit() else 0,
                            "info": " ".join(info_parts),
                            "src_port": src_port,
                            "dst_port": dst_port
                        })
                        
                except Exception as e:
                    logger.debug(f"解析行失败: {line}, 错误: {e}")
                    continue
                    
            logger.info(f"tshark 解析完成，共 {len(packets)} 个数据包")
            return packets
            
        except Exception as e:
            logger.error(f"解析 pcap 失败: {e}")
            traceback.print_exc()
            return []

    def _parse_pcap_fallback(self, pcap_path):
        """备用解析方法 (无修改)"""
        try:
            stdout, stderr, returncode = self._run_tshark_command([
                "-r", pcap_path,
                "-V"
            ], timeout=30)
            
            if not stdout:
                return []
            
            packets = []
            current_pkt = None
            pkt_no = 0
            
            for line in stdout.split('\n'):
                if line.startswith('Frame '):
                    if current_pkt:
                        packets.append(current_pkt)
                    pkt_no += 1
                    # 提取帧长度
                    match = re.search(r'(\d+) bytes', line)
                    frame_len = match.group(1) if match else "0"
                    current_pkt = {
                        "no": pkt_no,
                        "time": "0.000000",
                        "source": "127.0.0.1",
                        "destination": "127.0.0.1",
                        "protocol": "TCP",
                        "length": int(frame_len),
                        "info": f"Frame {pkt_no}"
                    }
                elif current_pkt:
                    if 'Internet Protocol' in line:
                        pass
                    elif 'Source Address:' in line or 'Src:' in line:
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if match:
                            current_pkt['source'] = match.group(1)
                    elif 'Destination Address:' in line or 'Dst:' in line:
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if match:
                            current_pkt['destination'] = match.group(1)
                    elif 'TLSv1.3' in line or 'TLS' in line.upper():
                        current_pkt['protocol'] = 'TLSv1.3'
                        
            if current_pkt:
                packets.append(current_pkt)
                
            logger.info(f"备用解析完成，共 {len(packets)} 个数据包")
            return packets
            
        except Exception as e:
            logger.error(f"备用解析失败: {e}")
            return []

    def _filter_pcap_by_port(self, input_path, output_path, port):
        """过滤 pcap 文件 (无修改)"""
        try:
            stdout, stderr, returncode = self._run_tshark_command([
                "-r", input_path,
                "-Y", f"tcp.port == {port}",
                "-w", output_path
            ], timeout=30)
            
            if returncode == 0 and os.path.exists(output_path):
                return True
            return False
        except Exception as e:
            logger.error(f"过滤 pcap 失败: {e}")
            return False

    def execute_simulation(self, msg_content="Hello TLS 1.3"):
        """执行完整的 TLS 1.3 仿真 (无修改)"""
        ensure_tls_directories()
        
        # 1. 生成证书
        gen = CertificateGenerator()
        cert_path, key_path = gen.generate_ecc_p256_cert()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        keylog_file = os.path.join(TLS_KEYLOG_DIR, f"sslkeylog_{timestamp}.log")
        # 安全警告：设置SSLKEYLOGFILE会影响进程内所有TLS连接的密钥记录，仅用于调试/仿真环境
        os.environ["SSLKEYLOGFILE"] = keylog_file

        pcap_filename = f"trace_{timestamp}.pcap"
        pcap_path = os.path.join(TLS_PCAP_DIR, pcap_filename)
        
        # 临时 pcap 文件（无过滤）
        pcap_temp_path = os.path.join(TLS_PCAP_DIR, f"trace_{timestamp}_temp.pcap")

        # 2. 检查 Loopback
        if TSHARK_AVAILABLE:
            self._check_npcap_loopback()

        # 3. 启动服务器
        self.stop_server_event.clear()
        self.server_ready.clear()
        server_thread = threading.Thread(target=self._run_server, args=(cert_path, key_path, SIMULATION_PORT))
        server_thread.daemon = True
        server_thread.start()
        
        if not self.server_ready.wait(timeout=5):
            return {"error": "Server failed to start"}

        # 4. 启动 tshark 抓包
        tshark_started = False
        if TSHARK_AVAILABLE:
            # 首先尝试使用过滤器
            tshark_started = self._run_tshark_capture(SIMULATION_PORT, pcap_path, timeout=15)
            
            # 如果失败，尝试无过滤模式
            if not tshark_started:
                logger.info("尝试无过滤模式抓包...")
                tshark_started = self._run_tshark_capture_alternative(SIMULATION_PORT, pcap_temp_path, timeout=15)
            
            if tshark_started:
                # 等待 tshark 完全启动
                time.sleep(2)
                logger.info("tshark 已就绪，开始 TLS 通信...")
            else:
                logger.warning("tshark 启动失败，将生成模拟数据包")

        # 5. 执行客户端通信
        client_log = []
        cipher_used = None
        try:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            # 注意：以下配置禁用了TLS证书验证，仅用于安全仿真测试环境，切勿用于生产环境
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE 
            context.keylog_filename = keylog_file

            with socket.create_connection((SIMULATION_HOST, SIMULATION_PORT), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname="localhost") as ssock:
                    cipher_used = ssock.cipher()
                    logger.info(f"Client connected using {ssock.version()}, Cipher: {cipher_used}")
                    
                    ssock.sendall(msg_content.encode('utf-8'))
                    resp = ssock.recv(1024)
                    
                    client_log.append(f"Sent: {msg_content}")
                    client_log.append(f"Received: {resp.decode('utf-8')}")
                    client_log.append(f"Protocol: {ssock.version()}")
                    client_log.append(f"Cipher: {cipher_used}")
                    
                    # 等待以确保所有数据包被捕获
                    time.sleep(2.0)
                    
        except Exception as e:
            logger.error(f"Client Error: {e}")
            client_log.append(f"Error: {str(e)}")
        finally:
            # 6. 停止服务器
            self.stop_server_event.set()
            server_thread.join(timeout=2)
            
            # 7. 等待更多时间让数据包写入
            if tshark_started:
                logger.info("等待 tshark 完成抓包...")
                time.sleep(2)
                self._stop_tshark_capture()
                time.sleep(1)  # 等待文件写入完成

        # 8. 处理 pcap 文件
        # 如果使用了无过滤模式，需要过滤数据包
        if os.path.exists(pcap_temp_path) and not os.path.exists(pcap_path):
            logger.info("过滤临时 pcap 文件...")
            if self._filter_pcap_by_port(pcap_temp_path, pcap_path, SIMULATION_PORT):
                os.remove(pcap_temp_path)
            else:
                # 过滤失败，直接使用临时文件
                os.rename(pcap_temp_path, pcap_path)

        # 9. 解析数据包
        formatted_packets = []
        if tshark_started and os.path.exists(pcap_path):
            formatted_packets = self._parse_pcap_with_tshark(pcap_path)
        
        # 10. 如果没有数据包，生成模拟数据
        if not formatted_packets:
            logger.info("未捕获到数据包，生成模拟数据")
            formatted_packets = self._generate_mock_packets(timestamp)

        # 11. 读取 keylog 内容
        keylog_content = ""
        if os.path.exists(keylog_file):
            with open(keylog_file, 'r', encoding='utf-8') as f:
                keylog_content = f.read()

        return {
            "status": "success",
            "pcap_path": pcap_path if os.path.exists(pcap_path) else "",
            "pcap_size": os.path.getsize(pcap_path) if os.path.exists(pcap_path) else 0,
            "keylog_path": keylog_file,
            "keylog_content": keylog_content,
            "packets": formatted_packets,
            "packet_count": len(formatted_packets),
            "client_log": client_log,
            "cipher_suite": cipher_used[0] if cipher_used else "TLS_AES_256_GCM_SHA384",
            "capture_method": "tshark" if tshark_started else "simulated"
        }

    def _generate_mock_packets(self, timestamp):
        """生成模拟数据包 (无修改)"""
        mock_packets = [
            {"no": 1, "time": "0.000000", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TCP", "length": 66, "info": f"Port: 52000 -> {SIMULATION_PORT} [SYN]"},
            {"no": 2, "time": "0.000100", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TCP", "length": 66, "info": f"Port: {SIMULATION_PORT} -> 52000 [SYN, ACK]"},
            {"no": 3, "time": "0.000200", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TCP", "length": 54, "info": f"Port: 52000 -> {SIMULATION_PORT} [ACK]"},
            {"no": 4, "time": "0.001000", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TLSv1.3", "length": 573, "info": f"Port: 52000 -> {SIMULATION_PORT} [Handshake] [ClientHello]"},
            {"no": 5, "time": "0.002000", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TLSv1.3", "length": 1438, "info": f"Port: {SIMULATION_PORT} -> 52000 [Handshake] [ServerHello]"},
            {"no": 6, "time": "0.003000", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TLSv1.3", "length": 126, "info": f"Port: 52000 -> {SIMULATION_PORT} [Handshake] [Finished]"},
            {"no": 7, "time": "0.004000", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TLSv1.3", "length": 85, "info": f"Port: 52000 -> {SIMULATION_PORT} [AppData]"},
            {"no": 8, "time": "0.005000", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TLSv1.3", "length": 93, "info": f"Port: {SIMULATION_PORT} -> 52000 [AppData]"},
            {"no": 9, "time": "0.006000", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TCP", "length": 54, "info": f"Port: 52000 -> {SIMULATION_PORT} [FIN, ACK]"},
            {"no": 10, "time": "0.006100", "source": "127.0.0.1", "destination": "127.0.0.1", 
             "protocol": "TCP", "length": 54, "info": f"Port: {SIMULATION_PORT} -> 52000 [FIN, ACK]"},
        ]
        return mock_packets

    def get_tshark_info(self):
        """获取 tshark 信息 (跨平台)"""
        info = {
            "tshark_path": TSHARK_PATH,
            "available": TSHARK_AVAILABLE,
            "interfaces": [],
            "loopback_interface": None,
            "version": None,
            "os": "Windows" if IS_WINDOWS else "Linux",
            "docker": IS_DOCKER
        }
        
        if not TSHARK_AVAILABLE:
            return info
            
        try:
            # 获取版本
            stdout, _, _ = self._run_tshark_command(["-v"])
            if stdout:
                info["version"] = stdout.split('\n')[0].strip()
            
            # 获取接口列表
            stdout, _, _ = self._run_tshark_command(["-D"])
            if stdout:
                info["interfaces"] = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
                
                # 查找 loopback
                for iface in info["interfaces"]:
                    if 'loopback' in iface.lower() or (IS_LINUX and 'lo' in iface.lower()):
                        info["loopback_interface"] = iface
                        info["loopback_found"] = True
                        break
                else:
                    info["loopback_found"] = False
                    if IS_WINDOWS:
                        info["warning"] = "未检测到 Npcap Loopback Adapter，请确保安装 Npcap 时勾选了 'Support loopback traffic'"
                    else:
                        info["warning"] = "Linux 系统未检测到 lo 接口，这是异常情况"
                    
        except Exception as e:
            info["error"] = str(e)
            
        return info


# ==================== Hijack 仿真器 (无修改) ====================
class HijackSimulator:
    """请求劫持仿真器"""
    MAX_HIJACK_ATTEMPTS = 1000
    def __init__(self):
        self.attempts = []

    def simulate_hijack(self, original_req: Dict, hijack_type: str = "mitm") -> Dict:
        handlers = {
            "mitm": self._mitm_hijack,
            "session": self._session_hijack,
            "cookie": self._cookie_hijack
        }
        
        handler = handlers.get(hijack_type, self._mitm_hijack)
        hijacked = handler(original_req)
        
        result = {
            'type': hijack_type,
            'timestamp': time.time(),
            'original_request': original_req,
            'hijacked_request': hijacked,
            'detected': self._detect_hijack_generic(original_req, hijacked)
        }
        
        self.attempts.append(result)
        if len(self.attempts) > self.MAX_HIJACK_ATTEMPTS:
            self.attempts = self.attempts[-self.MAX_HIJACK_ATTEMPTS:]
        logger.warning(f"劫持模拟: {hijack_type}, 被检测: {result['detected']}")
        return result

    def _mitm_hijack(self, req):
        h = req.copy()
        h['headers'] = {**h.get('headers', {}), 'Host': 'evil.example.com'}
        if isinstance(h.get('body'), str): h['body'] += '&malicious=injected'
        return {**h, 'hijacked': True, 'original_host': req.get('headers', {}).get('Host')}

    def _session_hijack(self, req):
        h = req.copy()
        import uuid
        h['cookies'] = {**h.get('cookies', {}), 'session_id': str(uuid.uuid4())}
        return {**h, 'hijacked': True, 'method': 'session_theft'}

    def _cookie_hijack(self, req):
        h = req.copy()
        h['cookies'] = {**h.get('cookies', {}), 'auth_token': 'stolen_token_123', 'user_id': '999'}
        return {**h, 'hijacked': True, 'method': 'cookie_theft'}

    def _detect_hijack_generic(self, orig, hijacked):
        if orig.get('headers', {}).get('Host') != hijacked.get('headers', {}).get('Host'): 
            return True
        if 'malicious' in str(hijacked.get('body', '')).lower() and 'malicious' not in str(orig.get('body', '')).lower(): 
            return True
        orig_s = orig.get('cookies', {}).get('session_id')
        hijack_s = hijacked.get('cookies', {}).get('session_id')
        if orig_s and hijack_s and orig_s != hijack_s: 
            return True
        if 'auth_token' in set(hijacked.get('cookies', {})) - set(orig.get('cookies', {})): 
            return True
        return False

    def run_hijack_simulation(self, hijack_type, url, content):
        try:
            req = {
                'url': url, 'method': 'GET', 
                'headers': {'Host': url.split('/')[2] if '://' in url else url, 'User-Agent': 'Mozilla/5.0'},
                'cookies': {'session_id': 'original_session_123', 'user_id': '123'},
                'body': ''
            }
            return {
                'status': 'success', 'message': '模拟成功', 
                'hijack_type': hijack_type, 'target_url': url, 'hijack_content': content,
                'result': self.simulate_hijack(req, hijack_type)
            }
        except Exception as e:
            return {'status': 'error', 'message': f'失败: {str(e)}'}


# ==================== 全局实例（供 app.py 导入使用） ====================
cert_generator = CertificateGenerator()
hijack_simulator = HijackSimulator()
tls_simulator = TlsSimulationManager()
CertGenerator = CertificateGenerator