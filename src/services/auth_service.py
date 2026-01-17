# -*- coding: utf-8 -*-
"""
认证服务 v9.0 - 统一认证入口

特性：
1. bcrypt 密码哈希
2. JWT Token 签发/验证
3. 登录频率限制
4. 密钥安全管理
"""

import os
import secrets
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict
from loguru import logger

try:
    import jwt
except ImportError:
    raise ImportError("请安装 PyJWT: pip install pyjwt")

try:
    import bcrypt
except ImportError:
    raise ImportError("请安装 bcrypt: pip install bcrypt")


class RateLimiter:
    """登录频率限制器"""
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300, lockout_seconds: int = 900):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._attempts: Dict[str, list] = defaultdict(list)
        self._lockouts: Dict[str, datetime] = {}
        self._lock = threading.Lock()
    
    def allow(self, identifier: str) -> Tuple[bool, str]:
        """检查是否允许登录尝试"""
        with self._lock:
            now = datetime.now()
            
            # 检查是否被锁定
            if identifier in self._lockouts:
                lockout_until = self._lockouts[identifier]
                if now < lockout_until:
                    remaining = int((lockout_until - now).total_seconds())
                    return False, f"账号已被锁定，请 {remaining} 秒后重试"
                else:
                    del self._lockouts[identifier]
            
            # 清理过期的尝试记录
            cutoff = now - timedelta(seconds=self.window_seconds)
            self._attempts[identifier] = [t for t in self._attempts[identifier] if t > cutoff]
            
            # 检查尝试次数
            if len(self._attempts[identifier]) >= self.max_attempts:
                self._lockouts[identifier] = now + timedelta(seconds=self.lockout_seconds)
                return False, f"登录尝试过多，账号已被锁定 {self.lockout_seconds // 60} 分钟"
            
            return True, ""
    
    def record_attempt(self, identifier: str, success: bool):
        """记录登录尝试"""
        with self._lock:
            if success:
                # 成功登录，清除记录
                self._attempts.pop(identifier, None)
                self._lockouts.pop(identifier, None)
            else:
                # 失败，记录尝试
                self._attempts[identifier].append(datetime.now())


class AuthServiceError(Exception):
    """认证服务错误基类"""
    pass


class InvalidCredentialsError(AuthServiceError):
    """凭证无效"""
    pass


class UserDisabledError(AuthServiceError):
    """用户已禁用"""
    pass


class RateLimitExceededError(AuthServiceError):
    """频率限制"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class TokenError(AuthServiceError):
    """Token 错误"""
    pass


class AuthService:
    """
    认证服务 - 唯一认证入口
    
    职责：
    1. 密码哈希和验证 (bcrypt)
    2. JWT Token 管理
    3. 登录频率限制
    4. 用户认证状态管理
    """
    
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24 * 7  # 7天
    
    _instance: Optional['AuthService'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db=None):
        if self._initialized:
            return
        
        self._db = db
        self._jwt_secret: Optional[str] = None
        self._rate_limiter = RateLimiter()
        self._initialized = True
        
        logger.info("[AuthService] 认证服务初始化完成")
    
    def set_database(self, db):
        """设置数据库实例"""
        self._db = db
    
    @property
    def db(self):
        """获取数据库实例（懒加载）"""
        if self._db is None:
            from core.database import get_database
            self._db = get_database()
        return self._db
    
    @property
    def jwt_secret(self) -> str:
        """获取 JWT 密钥（懒加载，优先数据库）"""
        if self._jwt_secret:
            return self._jwt_secret
        
        # 1. 从数据库获取
        try:
            jwt_key = self.db.get_system_config("jwt_secret_key")
            if jwt_key:
                self._jwt_secret = jwt_key
                return self._jwt_secret
        except Exception as e:
            logger.debug(f"从数据库获取JWT密钥失败: {e}")
        
        # 2. 从环境变量获取
        jwt_key = os.getenv("JWT_SECRET_KEY")
        if jwt_key:
            self._jwt_secret = jwt_key
            return self._jwt_secret
        
        # 3. 生成新密钥并存储
        self._jwt_secret = secrets.token_urlsafe(32)
        try:
            self.db.set_system_config("jwt_secret_key", self._jwt_secret)
            logger.info("[AuthService] 生成新的 JWT 密钥并存储到数据库")
        except Exception as e:
            logger.warning(f"无法存储JWT密钥: {e}，使用临时密钥")
        
        return self._jwt_secret
    
    # ==================== 密码管理 ====================
    
    def hash_password(self, password: str) -> str:
        """密码哈希 (bcrypt)"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """密码验证"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.warning(f"密码验证异常: {e}")
            return False
    
    def validate_password_strength(self, password: str) -> Tuple[bool, str]:
        """验证密码强度"""
        if len(password) < 8:
            return False, "密码长度至少8位"
        if not any(c.isdigit() for c in password):
            return False, "密码必须包含数字"
        if not any(c.isalpha() for c in password):
            return False, "密码必须包含字母"
        return True, ""
    
    # ==================== 频率限制 ====================
    
    def check_rate_limit(self, identifier: str) -> Tuple[bool, str]:
        """
        检查登录频率限制
        
        Args:
            identifier: 用户标识（用户名或IP）
            
        Returns:
            (allowed, message): 是否允许，拒绝时返回原因
        """
        return self._rate_limiter.allow(identifier)
    
    def record_login_attempt(self, identifier: str, success: bool) -> None:
        """
        记录登录尝试
        
        Args:
            identifier: 用户标识
            success: 是否成功
        """
        self._rate_limiter.record_attempt(identifier, success)
    
    # ==================== Token 管理 ====================
    
    def create_token(self, user_id: int, username: str, role: str) -> str:
        """创建 JWT Token"""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        expiration = now + timedelta(hours=self.JWT_EXPIRATION_HOURS)
        
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "exp": expiration,
            "iat": now,
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.JWT_ALGORITHM)
        return token
    
    def verify_token(self, token: str) -> Dict:
        """验证 JWT Token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.JWT_ALGORITHM])
            return {
                "user_id": int(payload.get("sub")),
                "username": payload.get("username"),
                "role": payload.get("role"),
            }
        except jwt.ExpiredSignatureError:
            raise TokenError("Token已过期")
        except jwt.InvalidTokenError as e:
            raise TokenError(f"无效的Token: {e}")
    
    def refresh_token(self, token: str) -> str:
        """刷新 Token（如果有效）"""
        user_info = self.verify_token(token)
        return self.create_token(
            user_info["user_id"],
            user_info["username"],
            user_info["role"]
        )
    
    # ==================== 认证操作 ====================
    
    def login(self, username: str, password: str) -> Dict:
        """
        用户登录
        
        Returns:
            {"token": str, "user": {...}}
        
        Raises:
            RateLimitExceededError: 频率限制
            InvalidCredentialsError: 凭证无效
            UserDisabledError: 用户已禁用
        """
        # 1. 频率限制检查
        allowed, error_msg = self._rate_limiter.allow(username)
        if not allowed:
            raise RateLimitExceededError(error_msg)
        
        # 2. 获取用户
        user = self.db.get_user_by_username(username)
        if not user:
            self._rate_limiter.record_attempt(username, success=False)
            raise InvalidCredentialsError("用户名或密码错误")
        
        # 3. 验证密码
        if not self.verify_password(password, user["password"]):
            self._rate_limiter.record_attempt(username, success=False)
            raise InvalidCredentialsError("用户名或密码错误")
        
        # 4. 检查状态
        if user.get("status") != "active":
            raise UserDisabledError("用户账号已被禁用")
        
        # 5. 记录成功
        self._rate_limiter.record_attempt(username, success=True)
        self.db.update_last_login(user["id"])
        
        # 6. 生成 Token
        token = self.create_token(user["id"], user["username"], user["role"])
        
        logger.info(f"用户登录成功: {username}")
        
        return {
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "email": user.get("email", ""),
                "status": user.get("status", "active")
            }
        }
    
    def get_current_user(self, token: str) -> Optional[Dict]:
        """从 Token 获取当前用户（带错误处理）"""
        try:
            return self.verify_token(token)
        except TokenError:
            return None
    
    # ==================== 用户管理 ====================
    
    def create_user(self, username: str, password: str, role: str = "user", email: str = "") -> int:
        """创建用户"""
        # 检查用户名
        existing = self.db.get_user_by_username(username)
        if existing:
            raise AuthServiceError("用户名已存在")
        
        # 验证密码强度
        valid, msg = self.validate_password_strength(password)
        if not valid:
            raise AuthServiceError(msg)
        
        # 创建用户
        hashed_password = self.hash_password(password)
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, email, role, status, created_at)
            VALUES (?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
        """, (username, hashed_password, email, role))
        self.db.conn.commit()
        
        user_id = cursor.lastrowid
        logger.info(f"创建用户: {username} (id={user_id}, role={role})")
        
        return user_id
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """修改密码"""
        user = self.db.get_user_by_id(user_id)
        if not user:
            raise AuthServiceError("用户不存在")
        
        # 验证旧密码
        if not self.verify_password(old_password, user["password"]):
            raise InvalidCredentialsError("原密码错误")
        
        # 验证新密码强度
        valid, msg = self.validate_password_strength(new_password)
        if not valid:
            raise AuthServiceError(msg)
        
        # 更新密码
        hashed_password = self.hash_password(new_password)
        cursor = self.db.conn.cursor()
        cursor.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user_id)
        )
        self.db.conn.commit()
        
        logger.info(f"用户 {user['username']} 修改了密码")
        return True
    
    def reset_password(self, user_id: int, new_password: str) -> bool:
        """重置密码（管理员操作）"""
        user = self.db.get_user_by_id(user_id)
        if not user:
            raise AuthServiceError("用户不存在")
        
        # 验证新密码强度
        valid, msg = self.validate_password_strength(new_password)
        if not valid:
            raise AuthServiceError(msg)
        
        # 更新密码
        hashed_password = self.hash_password(new_password)
        cursor = self.db.conn.cursor()
        cursor.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user_id)
        )
        self.db.conn.commit()
        
        logger.info(f"重置用户 {user['username']} 的密码")
        return True


# ==================== 全局访问函数 ====================

_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """获取认证服务实例"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# ==================== 兼容旧代码的导出函数 ====================

def hash_password(password: str) -> str:
    """密码哈希（兼容旧代码）"""
    return get_auth_service().hash_password(password)


def verify_password(password: str, hashed: str) -> bool:
    """密码验证（兼容旧代码）"""
    return get_auth_service().verify_password(password, hashed)


def create_access_token(user_id: int, username: str, role: str) -> str:
    """创建访问令牌（兼容旧代码）"""
    return get_auth_service().create_token(user_id, username, role)


def verify_token(token: str) -> Dict:
    """验证令牌（兼容旧代码）"""
    return get_auth_service().verify_token(token)


def get_jwt_secret_key() -> str:
    """获取 JWT 密钥（兼容旧代码）"""
    return get_auth_service().jwt_secret
