# -*- coding: utf-8 -*-
"""
AuthService 单元测试
"""

import unittest
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestAuthService(unittest.TestCase):
    """AuthService 测试"""
    
    def test_password_hashing(self):
        """测试密码哈希"""
        from services.auth_service import hash_password, verify_password
        
        password = "test_password_123"
        hashed = hash_password(password)
        
        # 哈希不等于原密码
        self.assertNotEqual(hashed, password)
        # 哈希以 $2b$ 开头（bcrypt）
        self.assertTrue(hashed.startswith("$2b$"))
        # 验证密码
        self.assertTrue(verify_password(password, hashed))
        # 错误密码验证失败
        self.assertFalse(verify_password("wrong_password", hashed))
    
    def test_token_creation_and_verification(self):
        """测试 Token 创建和验证"""
        from services.auth_service import get_auth_service
        
        auth_service = get_auth_service()
        
        # 创建 token
        token = auth_service.create_token(
            user_id=1,
            username="test_user",
            role="user"
        )
        
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 50)  # JWT 通常较长
        
        # 验证 token
        payload = auth_service.verify_token(token)
        self.assertEqual(payload["user_id"], 1)
        self.assertEqual(payload["username"], "test_user")
        self.assertEqual(payload["role"], "user")
    
    def test_invalid_token(self):
        """测试无效 Token"""
        from services.auth_service import get_auth_service, TokenError
        
        auth_service = get_auth_service()
        
        with self.assertRaises(TokenError):
            auth_service.verify_token("invalid_token")
    
    def test_rate_limiter(self):
        """测试登录频率限制"""
        from services.auth_service import RateLimiter
        
        limiter = RateLimiter(max_attempts=3, window_seconds=60, lockout_seconds=60)
        
        # 前3次允许
        for _ in range(3):
            allowed, _ = limiter.allow("test_user_rate")
            self.assertTrue(allowed)
            limiter.record_attempt("test_user_rate", False)
        
        # 第4次被锁定
        allowed, msg = limiter.allow("test_user_rate")
        self.assertFalse(allowed)
        self.assertIn("锁定", msg)
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from services.auth_service import get_auth_service
        
        service1 = get_auth_service()
        service2 = get_auth_service()
        
        self.assertIs(service1, service2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
