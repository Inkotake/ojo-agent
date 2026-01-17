# -*- coding: utf-8 -*-
"""
安全工具模块
提供密码验证、登录限制等安全功能
"""

import re
import time
from typing import Dict, Optional, Tuple
from collections import defaultdict
from loguru import logger


# ==================== 密码强度验证 ====================

class PasswordValidator:
    """密码强度验证器"""
    
    MIN_LENGTH = 6
    MAX_LENGTH = 128
    
    # 密码规则（可配置）
    REQUIRE_UPPERCASE = False  # 暂不要求大写
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = False    # 暂不要求特殊字符
    
    SPECIAL_CHARS = r"!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    @classmethod
    def validate(cls, password: str) -> Tuple[bool, str]:
        """
        验证密码强度
        
        Args:
            password: 待验证的密码
            
        Returns:
            (是否通过, 错误信息)
        """
        if not password:
            return False, "密码不能为空"
        
        if len(password) < cls.MIN_LENGTH:
            return False, f"密码长度至少 {cls.MIN_LENGTH} 位"
        
        if len(password) > cls.MAX_LENGTH:
            return False, f"密码长度不能超过 {cls.MAX_LENGTH} 位"
        
        if cls.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            return False, "密码必须包含小写字母"
        
        if cls.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            return False, "密码必须包含大写字母"
        
        if cls.REQUIRE_DIGIT and not re.search(r'\d', password):
            return False, "密码必须包含数字"
        
        if cls.REQUIRE_SPECIAL and not re.search(f'[{re.escape(cls.SPECIAL_CHARS)}]', password):
            return False, "密码必须包含特殊字符"
        
        return True, ""
    
    @classmethod
    def get_strength(cls, password: str) -> str:
        """
        评估密码强度等级
        
        Returns:
            weak/medium/strong
        """
        if not password or len(password) < cls.MIN_LENGTH:
            return "weak"
        
        score = 0
        
        # 长度加分
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        
        # 复杂度加分
        if re.search(r'[a-z]', password):
            score += 1
        if re.search(r'[A-Z]', password):
            score += 1
        if re.search(r'\d', password):
            score += 1
        if re.search(f'[{re.escape(cls.SPECIAL_CHARS)}]', password):
            score += 1
        
        if score <= 2:
            return "weak"
        elif score <= 4:
            return "medium"
        else:
            return "strong"


# ==================== 登录频率限制 ====================

class RateLimiter:
    """
    登录频率限制器
    使用滑动窗口算法限制登录尝试次数
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,  # 5分钟
        lockout_seconds: int = 900  # 15分钟锁定
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        
        # 存储: {identifier: [(timestamp, success), ...]}
        self._attempts: Dict[str, list] = defaultdict(list)
        # 锁定状态: {identifier: lockout_until_timestamp}
        self._lockouts: Dict[str, float] = {}
    
    def _cleanup_old_attempts(self, identifier: str) -> None:
        """清理过期的尝试记录"""
        now = time.time()
        cutoff = now - self.window_seconds
        self._attempts[identifier] = [
            (ts, success) for ts, success in self._attempts[identifier]
            if ts > cutoff
        ]
    
    def is_locked(self, identifier: str) -> Tuple[bool, int]:
        """
        检查是否被锁定
        
        Returns:
            (是否锁定, 剩余锁定秒数)
        """
        if identifier not in self._lockouts:
            return False, 0
        
        lockout_until = self._lockouts[identifier]
        now = time.time()
        
        if now >= lockout_until:
            # 锁定已过期
            del self._lockouts[identifier]
            return False, 0
        
        remaining = int(lockout_until - now)
        return True, remaining
    
    def record_attempt(self, identifier: str, success: bool) -> None:
        """记录登录尝试"""
        now = time.time()
        self._attempts[identifier].append((now, success))
        
        if success:
            # 登录成功，清除失败记录
            self._attempts[identifier] = []
            if identifier in self._lockouts:
                del self._lockouts[identifier]
        else:
            # 登录失败，检查是否需要锁定
            self._cleanup_old_attempts(identifier)
            failed_attempts = sum(
                1 for ts, s in self._attempts[identifier] if not s
            )
            
            if failed_attempts >= self.max_attempts:
                self._lockouts[identifier] = now + self.lockout_seconds
                logger.warning(f"账户 {identifier} 因多次登录失败被锁定 {self.lockout_seconds} 秒")
    
    def get_remaining_attempts(self, identifier: str) -> int:
        """获取剩余尝试次数"""
        self._cleanup_old_attempts(identifier)
        failed_attempts = sum(
            1 for ts, s in self._attempts[identifier] if not s
        )
        return max(0, self.max_attempts - failed_attempts)


# 全局登录限制器实例
login_limiter = RateLimiter(
    max_attempts=5,
    window_seconds=300,
    lockout_seconds=900
)


def validate_password(password: str) -> Tuple[bool, str]:
    """验证密码强度（便捷函数）"""
    return PasswordValidator.validate(password)


def check_login_allowed(identifier: str) -> Tuple[bool, Optional[str]]:
    """
    检查是否允许登录尝试
    
    Args:
        identifier: 用户标识（用户名或IP）
        
    Returns:
        (是否允许, 错误消息)
    """
    is_locked, remaining = login_limiter.is_locked(identifier)
    if is_locked:
        minutes = remaining // 60
        seconds = remaining % 60
        return False, f"账户已锁定，请在 {minutes}分{seconds}秒 后重试"
    
    remaining_attempts = login_limiter.get_remaining_attempts(identifier)
    if remaining_attempts <= 0:
        return False, "登录尝试次数过多，请稍后重试"
    
    return True, None


def record_login_attempt(identifier: str, success: bool) -> None:
    """记录登录尝试（便捷函数）"""
    login_limiter.record_attempt(identifier, success)
