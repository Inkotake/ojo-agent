# -*- coding: utf-8 -*-
"""
认证API路由 v9.0

统一使用 AuthService 和 api.dependencies 进行认证。
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from core.database import get_database
from api.dependencies import get_current_user, require_admin  # 统一使用 dependencies

router = APIRouter()

# 重新导出供其他模块使用
__all__ = ['router', 'get_current_user', 'require_admin']


# ==================== 数据模型 ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    invite_code: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    status: str


# ==================== 路由 ====================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """用户登录 - 使用 AuthService"""
    from services.auth_service import get_auth_service
    
    auth_service = get_auth_service()
    db = get_database()
    
    # 检查频率限制
    allowed, msg = auth_service.check_rate_limit(request.username)
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)
    
    # 查找用户
    user = db.get_user_by_username(request.username)
    if not user:
        auth_service.record_login_attempt(request.username, False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 验证密码
    if not auth_service.verify_password(request.password, user["password"]):
        auth_service.record_login_attempt(request.username, False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 检查用户状态
    if user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    # 登录成功
    auth_service.record_login_attempt(request.username, True)
    
    # 更新最后登录时间
    db.update_last_login(user["id"])
    db.log_activity(user["id"], "login", details={"role": user["role"]})
    
    # 生成 token
    token = auth_service.create_token(user["id"], user["username"], user["role"])
    
    logger.info(f"用户登录: {user['username']} ({user['role']})")
    
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "status": user["status"]
        }
    }


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """用户登出"""
    db = get_database()
    db.log_activity(user["user_id"], "logout")
    
    logger.info(f"用户登出: {user['username']}")
    
    return {"message": "登出成功"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    # 从数据库获取完整用户信息
    db = get_database()
    full_user = db.get_user_by_username(user["username"])
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return {
        "id": full_user["id"],
        "username": full_user["username"],
        "email": full_user.get("email"),
        "role": full_user["role"],
        "status": full_user["status"]
    }


@router.get("/check")
async def check_auth(user: dict = Depends(get_current_user)):
    """检查认证状态"""
    return {
        "authenticated": True,
        "user": {
            "username": user["username"],
            "role": user["role"]
        }
    }


@router.post("/register")
async def register(request: RegisterRequest):
    """用户注册（需要邀请码）"""
    from services.auth_service import get_auth_service
    from datetime import datetime
    
    auth_service = get_auth_service()
    db = get_database()
    
    # 验证用户名长度
    if len(request.username) < 3 or len(request.username) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名长度需在3-20个字符之间"
        )
    
    # 验证密码长度
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码长度至少6个字符"
        )
    
    # 检查用户名是否已存在
    existing_user = db.get_user_by_username(request.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 验证邀请码
    invite_code = db.get_invite_code(request.invite_code)
    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码无效"
        )
    
    if invite_code.get('used_by'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已被使用"
        )
    
    if invite_code.get('expires_at'):
        expires = datetime.fromisoformat(invite_code['expires_at']) if isinstance(invite_code['expires_at'], str) else invite_code['expires_at']
        if expires < datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邀请码已过期"
            )
    
    # 创建用户
    hashed_password = auth_service.hash_password(request.password)
    user_id = db.create_user(request.username, hashed_password, role='user')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户创建失败"
        )
    
    # 标记邀请码已使用
    db.use_invite_code(request.invite_code, user_id)
    
    logger.info(f"新用户注册: {request.username}，使用邀请码: {request.invite_code}")
    db.log_activity(user_id, "register", details={"invite_code": request.invite_code})
    
    # 自动登录
    user = db.get_user_by_username(request.username)
    token = auth_service.create_token(user["id"], user["username"], user["role"])
    
    return {
        "message": "注册成功",
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "status": user["status"]
        }
    }


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """修改密码"""
    from services.auth_service import get_auth_service
    
    auth_service = get_auth_service()
    db = get_database()
    
    # 获取完整用户信息
    user = db.get_user_by_username(current_user["username"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 验证旧密码
    if not auth_service.verify_password(request.old_password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )
    
    # 验证新密码长度
    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码长度至少6个字符"
        )
    
    # 更新密码
    hashed_password = auth_service.hash_password(request.new_password)
    success = db.update_user_password(current_user["user_id"], hashed_password)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码更新失败"
        )
    
    logger.info(f"用户 {current_user['username']} 修改了密码")
    db.log_activity(current_user["user_id"], "change_password")
    
    return {"message": "密码修改成功"}
