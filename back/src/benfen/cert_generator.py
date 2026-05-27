"""
证书生成器模块
用于生成真实的X.509证书文件和私钥文件
"""
import os
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import ipaddress
import logging

logger = logging.getLogger(__name__)

class CertificateGenerator:
    """证书生成器"""
    
    def __init__(self, output_dir: str = "data/generated_certs"):
        """初始化证书生成器
        
        Args:
            output_dir: 证书输出目录
        """
        # 定义项目根目录和数据目录
        self.back_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = output_dir
        self.cert_types = ["self_signed", "ca_signed", "ca", "expired", "weak"]
        # 修改日志保存路径为back/data/Log/certs_log
        self.log_dir = os.path.join(self.back_dir, "data", "Log", "certs_log")
        self._ensure_output_dir()
        self._ensure_log_dir()
    
    def _ensure_output_dir(self):
        """确保输出目录及其子目录存在"""
        # 创建主目录
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # 创建各类证书的子目录
        for cert_type in self.cert_types:
            cert_dir = os.path.join(self.output_dir, cert_type)
            if not os.path.exists(cert_dir):
                os.makedirs(cert_dir)
    
    def _ensure_log_dir(self):
        """确保日志目录存在"""
        # 使用exist_ok=True确保目录存在而不会抛出异常
        os.makedirs(self.log_dir, exist_ok=True)
    
    def _write_cert_log(self, cert_info):
        """记录证书生成日志
        
        Args:
            cert_info: 证书信息字典
        """
        try:
            logger.info(f"开始记录证书日志，日志目录: {self.log_dir}")
            
            # 确保日志目录存在
            self._ensure_log_dir()
            
            # 计算文件大小
            cert_size = 0
            if cert_info.get('certificate_path') and os.path.exists(cert_info['certificate_path']):
                cert_size = os.path.getsize(cert_info['certificate_path'])
                logger.info(f"证书文件大小: {cert_size} 字节")
            else:
                logger.warning(f"证书文件不存在或路径无效: {cert_info.get('certificate_path')}")
            
            # 构造日志文件路径（按日期）
            log_date = datetime.now().strftime("%Y-%m-%d")
            log_file_path = os.path.join(self.log_dir, f"cert_generation_{log_date}.log")
            logger.info(f"日志文件路径: {log_file_path}")
            
            # 构造日志内容
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "certificate_type": cert_info.get("type"),
                "certificate_filename": cert_info.get("certificate_filename"),
                "common_name": cert_info.get("subject", {}).get("common_name"),
                "key_size": cert_info.get("key_size"),
                "validity_days": cert_info.get("validity_days"),
                "signature_algorithm": cert_info.get("signature_algorithm"),
                "file_size": cert_size,
                "is_expired": cert_info.get("is_expired", False),
                "weak_signature": cert_info.get("weak_signature", False),
                "not_valid_before": cert_info.get("not_valid_before"),
                "not_valid_after": cert_info.get("not_valid_after")
            }
            
            logger.info(f"日志内容: {json.dumps(log_entry, ensure_ascii=False)}")
            
            # 写入日志文件（追加模式，每行一个JSON对象）
            with open(log_file_path, "a") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            logger.info(f"证书日志已成功记录到: {log_file_path}")
        except Exception as e:
            logger.error(f"写入证书日志失败: {str(e)}")
            # 打印完整的错误堆栈
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    def generate_self_signed_certificate(self, 
                                       common_name: str = "example.com",
                                       organization: str = "Example Organization",
                                       country: str = "CN",
                                       key_size: int = 2048,
                                       validity_days: int = 365,
                                       san_domains: Optional[list] = None) -> Dict:
        """生成自签名证书
        
        Args:
            common_name: 通用名称（通常是域名）
            organization: 组织名称
            country: 国家代码
            key_size: RSA密钥长度
            validity_days: 有效期（天数）
            san_domains: 主题备用名称域名列表
            
        Returns:
            包含证书路径和信息的字典
        """
        # 生成私钥
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        # 创建证书主题
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # 创建证书
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer  # 自签名证书，颁发者和主题相同
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=validity_days)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(domain_item) for domain_item in (san_domains or [common_name])
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        # 生成文件名（新格式：证书类型+生成时间+时间戳）
        timestamp = int(time.time())
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
        cert_filename = f"self_signed_{current_datetime}_{timestamp}.pem"
        key_filename = f"self_signed_{current_datetime}_{timestamp}_key.pem"
        
        # 确定目标子文件夹
        cert_type_dir = os.path.join(self.output_dir, "self_signed")
        cert_path = os.path.join(cert_type_dir, cert_filename)
        key_path = os.path.join(cert_type_dir, key_filename)
        
        # 保存证书
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # 保存私钥
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        result = {
            'certificate_path': cert_path,
            'private_key_path': key_path,
            'certificate_filename': cert_filename,
            'private_key_filename': key_filename,
            'subject': {
                'common_name': common_name,
                'organization': organization,
                'country': country
            },
            'issuer': {
                'common_name': common_name,
                'organization': organization,
                'country': country
            },
            'key_size': key_size,
            'validity_days': validity_days,
            'san_domains': san_domains or [common_name],
            'serial_number': str(cert.serial_number),
            'signature_algorithm': 'sha256WithRSAEncryption',
            'not_valid_before': cert.not_valid_before.isoformat(),
            'not_valid_after': cert.not_valid_after.isoformat(),
            'type': 'self_signed'
        }
        
        # 计算文件大小
        cert_size = os.path.getsize(cert_path)
        result['file_size'] = cert_size
        
        # 直接写入日志文件（简化版）
        try:
            # 定义日志目录
            log_dir = os.path.join(self.back_dir, "data", "Log", "certs_log")
            # 确保日志目录存在
            os.makedirs(log_dir, exist_ok=True)
            
            # 构造日志文件路径
            log_file = os.path.join(log_dir, "cert_log.txt")
            
            # 构造日志内容
            log_content = f"{datetime.now().isoformat()} - Generated {result['type']} certificate: {result['certificate_filename']}, Size: {cert_size} bytes\n"
            
            # 写入日志文件
            with open(log_file, "a") as f:
                f.write(log_content)
            
            logger.info(f"日志已写入: {log_file}")
        except Exception as e:
            logger.error(f"写入日志失败: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
        
        logger.info(f"Generated self-signed certificate: {cert_filename}")
        return result
    
    def generate_ca_signed_certificate(self,
                                     common_name: str = "example.com",
                                     organization: str = "Example Organization",
                                     country: str = "CN",
                                     ca_cert_path: Optional[str] = None,
                                     ca_key_path: Optional[str] = None,
                                     key_size: int = 2048,
                                     validity_days: int = 365,
                                     san_domains: Optional[list] = None) -> Dict:
        """生成CA签名的证书
        
        Args:
            common_name: 通用名称
            organization: 组织名称
            country: 国家代码
            ca_cert_path: CA证书路径
            ca_key_path: CA私钥路径
            key_size: RSA密钥长度
            validity_days: 有效期
            san_domains: 主题备用名称域名列表
            
        Returns:
            包含证书路径和信息的字典
        """
        # 如果没有提供CA证书和私钥先生成一个CA
        if not ca_cert_path or not ca_key_path:
            ca_result = self.generate_ca_certificate(
                organization=organization,
                country=country
            )
            ca_cert_path = ca_result['certificate_path']
            ca_key_path = ca_result['private_key_path']
        
        # 加载CA证书和私钥
        with open(ca_cert_path, 'rb') as f:
            ca_cert_data = f.read()
            ca_cert = x509.load_pem_x509_certificate(ca_cert_data, default_backend())
        
        with open(ca_key_path, 'rb') as f:
            ca_key_data = f.read()
            ca_private_key = serialization.load_pem_private_key(
                ca_key_data, password=None, backend=default_backend()
            )
        
        # 生成用户证书的私钥
        user_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        # 创建证书主题
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # 创建证书
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert.subject  # 使用CA证书的主题作为颁发者
        ).public_key(
            user_private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=validity_days)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(domain) for domain in (san_domains or [common_name])
            ]),
            critical=False,
        ).sign(ca_private_key, hashes.SHA256(), default_backend())
        
        # 生成文件名（新格式：证书类型+生成时间+时间戳）
        timestamp = int(time.time())
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
        cert_filename = f"ca_signed_{current_datetime}_{timestamp}.pem"
        key_filename = f"ca_signed_{current_datetime}_{timestamp}_key.pem"
        
        # 确定目标子文件夹
        cert_type_dir = os.path.join(self.output_dir, "ca_signed")
        cert_path = os.path.join(cert_type_dir, cert_filename)
        key_path = os.path.join(cert_type_dir, key_filename)
        
        # 保存证书
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # 保存私钥
        with open(key_path, "wb") as f:
            f.write(user_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        result = {
            'certificate_path': cert_path,
            'private_key_path': key_path,
            'certificate_filename': cert_filename,
            'private_key_filename': key_filename,
            'subject': {
                'common_name': common_name,
                'organization': organization,
                'country': country
            },
            'issuer': {
                'common_name': ca_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
                'organization': ca_cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value,
                'country': ca_cert.subject.get_attributes_for_oid(NameOID.COUNTRY_NAME)[0].value
            },
            'ca_certificate_path': ca_cert_path,
            'key_size': key_size,
            'validity_days': validity_days,
            'san_domains': san_domains or [common_name],
            'serial_number': str(cert.serial_number),
            'signature_algorithm': 'sha256WithRSAEncryption',
            'not_valid_before': cert.not_valid_before.isoformat(),
            'not_valid_after': cert.not_valid_after.isoformat(),
            'type': 'ca_signed'
        }
        
        # 计算文件大小
        cert_size = os.path.getsize(cert_path)
        result['file_size'] = cert_size
        
        # 记录证书生成日志
        self._write_cert_log(result)
        
        logger.info(f"Generated CA-signed certificate: {cert_filename}")
        return result
    
    def generate_ca_certificate(self,
                              organization: str = "Example CA",
                              country: str = "CN",
                              key_size: int = 4096,
                              validity_days: int = 3650) -> Dict:
        """生成CA证书
        
        Args:
            organization: CA组织名称
            country: 国家代码
            key_size: RSA密钥长度
            validity_days: 有效期（CA证书通常较长）
            
        Returns:
            包含证书路径和信息的字典
        """
        # 生成私钥
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        # 创建证书主题
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{organization} Root CA"),
        ])
        
        # 创建证书
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer  # 自签名证书，颁发者和主题相同
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=validity_days)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(f"{organization} Root CA")
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        # 生成文件名（新格式：证书类型+生成时间+时间戳）
        timestamp = int(time.time())
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
        cert_filename = f"ca_{current_datetime}_{timestamp}.pem"
        key_filename = f"ca_{current_datetime}_{timestamp}_key.pem"
        
        # 确定目标子文件夹
        cert_type_dir = os.path.join(self.output_dir, "ca")
        cert_path = os.path.join(cert_type_dir, cert_filename)
        key_path = os.path.join(cert_type_dir, key_filename)
        
        # 保存证书
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # 保存私钥
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        result = {
            'certificate_path': cert_path,
            'private_key_path': key_path,
            'certificate_filename': cert_filename,
            'private_key_filename': key_filename,
            'subject': {
                'common_name': f"{organization} Root CA",
                'organization': organization,
                'country': country
            },
            'issuer': {
                'common_name': f"{organization} Root CA",
                'organization': organization,
                'country': country
            },
            'key_size': key_size,
            'validity_days': validity_days,
            'san_domains': [f"{organization} Root CA"],
            'serial_number': str(cert.serial_number),
            'signature_algorithm': 'sha256WithRSAEncryption',
            'not_valid_before': cert.not_valid_before.isoformat(),
            'not_valid_after': cert.not_valid_after.isoformat(),
            'type': 'ca'
        }
        
        # 计算文件大小
        cert_size = os.path.getsize(cert_path)
        result['file_size'] = cert_size
        
        # 记录证书生成日志
        self._write_cert_log(result)
        
        logger.info(f"Generated CA certificate: {cert_filename}")
        return result
    
    def generate_expired_certificate(self,
                                   common_name: str = "expired.example.com",
                                   organization: str = "Example Organization",
                                   country: str = "CN",
                                   key_size: int = 2048,
                                   days_expired: int = 30) -> Dict:
        """生成过期证书
        
        Args:
            common_name: 通用名称
            organization: 组织名称
            country: 国家代码
            key_size: RSA密钥长度
            days_expired: 过期天数
            
        Returns:
            包含证书路径和信息的字典
        """
        # 生成私钥
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        # 创建证书主题
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # 创建证书（过期）
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc) - timedelta(days=days_expired + 365)
        ).not_valid_after(
            datetime.now(timezone.utc) - timedelta(days=days_expired)  # 已过期
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]),
            critical=False,
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        # 生成文件名（新格式：证书类型+生成时间+时间戳）
        timestamp = int(time.time())
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
        cert_filename = f"expired_{current_datetime}_{timestamp}.pem"
        key_filename = f"expired_{current_datetime}_{timestamp}_key.pem"
        
        # 确定目标子文件夹
        cert_type_dir = os.path.join(self.output_dir, "expired")
        cert_path = os.path.join(cert_type_dir, cert_filename)
        key_path = os.path.join(cert_type_dir, key_filename)
        
        # 保存证书和私钥
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        result = {
            'certificate_path': cert_path,
            'private_key_path': key_path,
            'certificate_filename': cert_filename,
            'private_key_filename': key_filename,
            'subject': {
                'common_name': common_name,
                'organization': organization,
                'country': country
            },
            'issuer': {
                'common_name': common_name,
                'organization': organization,
                'country': country
            },
            'key_size': key_size,
            'days_expired': days_expired,
            'san_domains': [common_name],
            'serial_number': str(cert.serial_number),
            'signature_algorithm': 'sha256WithRSAEncryption',
            'not_valid_before': cert.not_valid_before.isoformat(),
            'not_valid_after': cert.not_valid_after.isoformat(),
            'is_expired': True,
            'type': 'expired'
        }
        
        # 计算文件大小
        cert_size = os.path.getsize(cert_path)
        result['file_size'] = cert_size
        
        # 记录证书生成日志
        self._write_cert_log(result)
        
        logger.warning(f"Generated expired certificate: {cert_filename} (expired {days_expired} days ago)")
        return result
    
    def generate_weak_certificate(self,
                                common_name: str = "weak.example.com",
                                organization: str = "Example Organization",
                                country: str = "CN",
                                key_size: int = 1024,
                                weak_signature: bool = True) -> Dict:
        """生成弱证书（弱密钥或弱签名算法）
        
        Args:
            common_name: 通用名称
            organization: 组织名称
            country: 国家代码
            key_size: RSA密钥长度（使用较短的密钥）
            weak_signature: 是否使用弱签名算法
            
        Returns:
            包含证书路径和信息的字典
        """
        # 生成弱私钥
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        # 创建证书主题
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # 选择签名算法 - 避免使用SHA1，使用SHA256但使用弱密钥
        signature_hash = hashes.SHA256()
        signature_algorithm = 'sha256WithRSAEncryption'
        
        # 创建证书
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]),
            critical=False,
        ).sign(private_key, signature_hash, default_backend())
        
        # 生成文件名（新格式：证书类型+生成时间+时间戳）
        timestamp = int(time.time())
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
        cert_filename = f"weak_{current_datetime}_{timestamp}.pem"
        key_filename = f"weak_{current_datetime}_{timestamp}_key.pem"
        
        # 确定目标子文件夹
        cert_type_dir = os.path.join(self.output_dir, "weak")
        cert_path = os.path.join(cert_type_dir, cert_filename)
        key_path = os.path.join(cert_type_dir, key_filename)
        
        # 保存证书和私钥
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        result = {
            'certificate_path': cert_path,
            'private_key_path': key_path,
            'certificate_filename': cert_filename,
            'private_key_filename': key_filename,
            'subject': {
                'common_name': common_name,
                'organization': organization,
                'country': country
            },
            'issuer': {
                'common_name': common_name,
                'organization': organization,
                'country': country
            },
            'key_size': key_size,
            'signature_algorithm': signature_algorithm,
            'weak_signature': weak_signature,
            'san_domains': [common_name],
            'serial_number': str(cert.serial_number),
            'not_valid_before': cert.not_valid_before.isoformat(),
            'not_valid_after': cert.not_valid_after.isoformat(),
            'type': 'weak'
        }
        
        # 计算文件大小
        cert_size = os.path.getsize(cert_path)
        result['file_size'] = cert_size
        
        # 记录证书生成日志
        self._write_cert_log(result)
        
        logger.warning(f"Generated weak certificate: {cert_filename} (key_size: {key_size}, signature: {signature_algorithm})")
        return result
    
    def list_generated_certificates(self) -> list:
        """列出已生成的证书文件"""
        certificates = []
        if os.path.exists(self.output_dir):
            # 遍历所有子文件夹
            for cert_type in self.cert_types:
                cert_type_dir = os.path.join(self.output_dir, cert_type)
                if os.path.exists(cert_type_dir):
                    for filename in os.listdir(cert_type_dir):
                        if filename.endswith('.pem') and not filename.endswith('_key.pem'):
                            cert_path = os.path.join(cert_type_dir, filename)
                            key_path = cert_path.replace('.pem', '_key.pem')
                            
                            cert_info = {
                                'certificate_filename': filename,
                                'certificate_path': cert_path,
                                'certificate_type': cert_type,
                                'private_key_exists': os.path.exists(key_path),
                                'private_key_path': key_path if os.path.exists(key_path) else None,
                                'file_size': os.path.getsize(cert_path),
                                'created_time': datetime.fromtimestamp(os.path.getctime(cert_path)).isoformat()
                            }
                            certificates.append(cert_info)
        return certificates
    
    def delete_certificate(self, certificate_filename: str) -> bool:
        """删除指定的证书文件
        
        Args:
            certificate_filename: 证书文件名
            
        Returns:
            是否成功删除
        """
        deleted = False
        
        try:
            # 遍历所有子文件夹查找证书
            for cert_type in self.cert_types:
                cert_type_dir = os.path.join(self.output_dir, cert_type)
                cert_path = os.path.join(cert_type_dir, certificate_filename)
                key_path = cert_path.replace('.pem', '_key.pem')
                
                if os.path.exists(cert_path):
                    # 删除证书文件
                    os.remove(cert_path)
                    deleted = True
                
                if os.path.exists(key_path):
                    # 删除私钥文件
                    os.remove(key_path)
                    deleted = True
            
            if deleted:
                logger.info(f"Deleted certificate files: {certificate_filename}")
            else:
                logger.warning(f"Certificate not found: {certificate_filename}")
            
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete certificate {certificate_filename}: {str(e)}")
            return False
    
    def clear_all_certificates(self) -> Dict:
        """清空所有证书文件
        
        Returns:
            包含删除结果的字典
        """
        deleted_files = 0
        deleted_certs = 0
        
        try:
            # 遍历所有子文件夹
            for cert_type in self.cert_types:
                cert_type_dir = os.path.join(self.output_dir, cert_type)
                if os.path.exists(cert_type_dir):
                    # 遍历子文件夹中的所有文件
                    for filename in os.listdir(cert_type_dir):
                        if filename.endswith('.pem'):
                            file_path = os.path.join(cert_type_dir, filename)
                            os.remove(file_path)
                            deleted_files += 1
                            
                            # 统计证书数量（不统计私钥）
                            if not filename.endswith('_key.pem'):
                                deleted_certs += 1
            
            logger.info(f"Cleared all certificates: deleted {deleted_certs} certificates and {deleted_files - deleted_certs} private keys")
            
            return {
                'success': True,
                'deleted_files': deleted_files,
                'deleted_certificates': deleted_certs,
                'message': f"成功清空所有证书，共删除 {deleted_certs} 个证书和 {deleted_files - deleted_certs} 个私钥"
            }
        except Exception as e:
            logger.error(f"Failed to clear all certificates: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': "清空证书失败"
            }
    
    def generate_cert(self, cert_type: str, domain: str, validity_days: int) -> Dict:
        """生成X.509证书
        
        Args:
            cert_type: 证书类型
            domain: 域名
            validity_days: 有效期天数
            
        Returns:
            包含证书信息的字典
        """
        try:
            result = None
            
            logger.info(f"开始生成证书，类型: {cert_type}, 域名: {domain}, 有效期: {validity_days}天")
            
            # 根据证书类型调用对应的生成方法
            if cert_type == 'self-signed':
                result = self.generate_self_signed_certificate(
                    common_name=domain,
                    validity_days=validity_days
                )
            elif cert_type == 'ca':
                result = self.generate_ca_certificate(
                    organization="Example CA",
                    validity_days=validity_days
                )
            elif cert_type == 'ca-signed':
                result = self.generate_ca_signed_certificate(
                    common_name=domain,
                    validity_days=validity_days
                )
            elif cert_type == 'expired':
                result = self.generate_expired_certificate(
                    common_name=domain
                )
            elif cert_type == 'weak':
                result = self.generate_weak_certificate(
                    common_name=domain
                )
            else:
                return {
                    'status': 'error',
                    'message': f"不支持的证书类型: {cert_type}"
                }
            
            logger.info(f"证书生成成功，结果: {result}")
            
            if result:
                return {
                    'status': 'success',
                    'message': f"成功生成{cert_type}证书",
                    'data': result
                }
            else:
                return {
                    'status': 'error',
                    'message': "证书生成失败"
                }
        except Exception as e:
            logger.error(f"Failed to generate certificate: {str(e)}")
            # 打印完整的错误堆栈
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {
                'status': 'error',
                'message': f"证书生成失败: {str(e)}"
            }

# 全局证书生成器实例
cert_generator = CertificateGenerator()
# 为了兼容app.py中的导入，添加一个别名
CertGenerator = CertificateGenerator