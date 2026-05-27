"""
请求劫持仿真模块
"""
import time
import random
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class HijackSimulator:
    """请求劫持仿真器"""
    
    def __init__(self):
        self.hijack_attempts: list = []
    
    def simulate_hijack(self, original_request: Dict, hijack_type: str = "mitm") -> Dict:
        """模拟请求劫持"""
        
        hijack_result = {
            'type': hijack_type,
            'timestamp': time.time(),
            'original_request': original_request,
            'hijacked_request': None,
            'detected': False
        }
        
        if hijack_type == "mitm":
            # Man-in-the-Middle攻击
            hijacked = self._mitm_hijack(original_request)
            hijack_result['hijacked_request'] = hijacked
            hijack_result['detected'] = self._detect_hijack(original_request, hijacked)
            
        elif hijack_type == "session":
            # 会话劫持
            hijacked = self._session_hijack(original_request)
            hijack_result['hijacked_request'] = hijacked
            hijack_result['detected'] = self._detect_session_hijack(original_request, hijacked)
            
        elif hijack_type == "cookie":
            # Cookie劫持
            hijacked = self._cookie_hijack(original_request)
            hijack_result['hijacked_request'] = hijacked
            hijack_result['detected'] = self._detect_cookie_hijack(original_request, hijacked)
        
        self.hijack_attempts.append(hijack_result)
        logger.warning(f"Hijack simulation: {hijack_type}, Detected: {hijack_result['detected']}")
        
        return hijack_result
    
    def _mitm_hijack(self, request: Dict) -> Dict:
        """模拟中间人攻击"""
        hijacked = request.copy()
        
        # 修改请求目标
        hijacked['headers'] = hijacked.get('headers', {}).copy()
        hijacked['headers']['Host'] = 'evil.example.com'
        
        # 注入恶意内容
        if 'body' in hijacked:
            body_str = hijacked['body']
            if isinstance(body_str, str):
                hijacked['body'] = body_str + '&malicious=injected'
        
        # 记录被劫持的信息
        hijacked['hijacked'] = True
        hijacked['original_host'] = request.get('headers', {}).get('Host', 'unknown')
        
        return hijacked
    
    def _session_hijack(self, request: Dict) -> Dict:
        """模拟会话劫持"""
        hijacked = request.copy()
        
        # 替换Session ID
        cookies = hijacked.get('cookies', {}).copy()
        if 'session_id' in cookies:
            # 使用猜测或窃取的会话ID
            cookies['session_id'] = self._generate_stolen_session_id(cookies['session_id'])
        else:
            cookies['session_id'] = self._generate_stolen_session_id()
        
        hijacked['cookies'] = cookies
        hijacked['hijacked'] = True
        hijacked['hijack_method'] = 'session_theft'
        
        return hijacked
    
    def _cookie_hijack(self, request: Dict) -> Dict:
        """模拟Cookie劫持"""
        hijacked = request.copy()
        
        # 修改或注入Cookie
        cookies = hijacked.get('cookies', {}).copy()
        cookies['auth_token'] = 'stolen_token_12345'
        cookies['user_id'] = '999'
        
        hijacked['cookies'] = cookies
        hijacked['hijacked'] = True
        hijacked['hijack_method'] = 'cookie_theft'
        
        return hijacked
    
    def _generate_stolen_session_id(self, original: Optional[str] = None) -> str:
        """生成模拟的窃取会话ID"""
        import uuid
        if original:
            # 模拟部分匹配的会话ID（时序攻击场景）
            return original[:16] + str(uuid.uuid4())[:16]
        return str(uuid.uuid4())
    
    def _detect_hijack(self, original: Dict, hijacked: Dict) -> bool:
        """检测劫持（基于请求特征）"""
        # 检测Host变化
        orig_host = original.get('headers', {}).get('Host', '')
        hijack_host = hijacked.get('headers', {}).get('Host', '')
        if orig_host != hijack_host and orig_host:
            return True
        
        # 检测可疑的注入内容
        orig_body = original.get('body', '')
        hijack_body = hijacked.get('body', '')
        if 'malicious' in hijack_body.lower() and 'malicious' not in orig_body.lower():
            return True
        
        return False
    
    def _detect_session_hijack(self, original: Dict, hijacked: Dict) -> bool:
        """检测会话劫持"""
        orig_session = original.get('cookies', {}).get('session_id')
        hijack_session = hijacked.get('cookies', {}).get('session_id')
        
        if orig_session and hijack_session and orig_session != hijack_session:
            # 检查IP地址是否变化（实际场景中）
            # 这里简化处理，假设检测到不同的会话ID
            return True
        
        return False
    
    def _detect_cookie_hijack(self, original: Dict, hijacked: Dict) -> bool:
        """检测Cookie劫持"""
        orig_cookies = original.get('cookies', {})
        hijack_cookies = hijacked.get('cookies', {})
        
        # 检测新增的可疑Cookie
        new_cookies = set(hijack_cookies.keys()) - set(orig_cookies.keys())
        if 'auth_token' in new_cookies or 'user_id' in new_cookies:
            return True
        
        # 检测Cookie值异常变化
        for key in orig_cookies:
            if key in hijack_cookies and orig_cookies[key] != hijack_cookies[key]:
                if key in ['auth_token', 'session_id']:
                    return True
        
        return False
    
    def get_hijack_statistics(self) -> Dict:
        """获取劫持统计信息"""
        if not self.hijack_attempts:
            return {}
        
        detected = sum(1 for h in self.hijack_attempts if h['detected'])
        types = [h['type'] for h in self.hijack_attempts]
        
        return {
            'total_attempts': len(self.hijack_attempts),
            'detected_count': detected,
            'detection_rate': detected / len(self.hijack_attempts) if self.hijack_attempts else 0,
            'type_distribution': {t: types.count(t) for t in set(types)}
        }
    
    def run_hijack_simulation(self, hijack_type: str, target_url: str, hijack_content: str) -> Dict:
        """运行请求劫持模拟（兼容app.py中的调用）"""
        try:
            # 创建模拟的原始请求
            original_request = {
                'url': target_url,
                'method': 'GET',
                'headers': {
                    'Host': target_url.split('/')[2] if '://' in target_url else target_url,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                },
                'body': '',
                'cookies': {
                    'session_id': 'original_session_12345',
                    'user_id': '123'
                }
            }
            
            # 调用实际的劫持模拟方法
            result = self.simulate_hijack(original_request, hijack_type)
            
            # 转换结果格式以匹配app.py的预期
            return {
                'status': 'success',
                'message': '请求劫持模拟成功',
                'hijack_type': hijack_type,
                'target_url': target_url,
                'hijack_content': hijack_content,
                'result': result
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'请求劫持模拟失败: {str(e)}'
            }

# 全局劫持仿真器实例
hijack_simulator = HijackSimulator()

