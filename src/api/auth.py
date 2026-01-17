# -*- coding: utf-8 -*-
"""
认证工具模块 v9.0 - 统一转发到 AuthService

本模块保留向后兼容的导出接口，实际逻辑由 AuthService 实现。
"""

from typing import Dict, Optional
from loguru import logger

# 从 AuthService 导入所有函数（保持 API 兼容）
from services.auth_service import (
    get_auth_service,
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
    get_jwt_secret_key,
    AuthService,
    AuthServiceError,
    InvalidCredentialsError,
    UserDisabledError,
    RateLimitExceededError,
    TokenError,
)


def get_current_user(token: str) -> Optional[Dict]:
    """
    从 token 获取当前用户信息（带错误处理）
    
    Args:
        token: JWT token 字符串
        
    Returns:
        用户信息字典，如果 token 无效返回 None
    """
    return get_auth_service().get_current_user(token)


# 导出所有符号
__all__ = [
    'get_auth_service',
    'hash_password',
    'verify_password',
    'create_access_token',
    'verify_token',
    'get_jwt_secret_key',
    'get_current_user',
    'AuthService',
    'AuthServiceError',
    'InvalidCredentialsError',
    'UserDisabledError',
    'RateLimitExceededError',
    'TokenError',
]

