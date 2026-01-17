# -*- coding: utf-8 -*-
"""
API 依赖项定义 v9.0

所有 FastAPI 路由共享的依赖项，包括认证、数据库、配置等。
"""

from typing import Dict, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from api.auth import verify_token
from core.database import get_database, Database


# HTTP Bearer 安全方案
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    获取当前认证用户（必须登录）
    
    Raises:
        HTTPException: 如果 token 无效或过期
    """
    token = credentials.credentials
    try:
        user_info = verify_token(token)
        return user_info
    except Exception as e:
        logger.warning(f"认证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    要求管理员权限
    
    Raises:
        HTTPException: 如果不是管理员
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[Dict]:
    """
    可选的用户认证（不强制要求登录）
    """
    if not authorization:
        return None
    
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            user_info = verify_token(token)
            return user_info
    except Exception:
        pass
    
    return None


def get_db() -> Database:
    """获取数据库实例"""
    return get_database()
