# -*- coding: utf-8 -*-
"""
管理员API路由
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from loguru import logger

from core.database import get_database
from api.dependencies import require_admin

router = APIRouter()


class SystemStats(BaseModel):
    total_users: int
    total_tasks: int
    active_tasks: int
    completed_tasks: int
    cpu_usage: float
    memory_usage: float


@router.get("/tasks/global")
async def get_global_tasks(user: dict = Depends(require_admin)):
    """获取所有用户的任务（管理员专属）"""
    db = get_database()
    tasks = db.get_all_tasks(limit=100)
    
    # 格式化任务数据
    formatted_tasks = []
    for task in tasks:
        formatted_tasks.append({
            "id": task["id"],
            "user": task.get("username"),
            "user_id": task.get("user_id"),
            "problem_id": task["problem_id"],
            "source_oj": task.get("source_oj"),
            "target_oj": task.get("target_oj"),
            "status": task["status"],
            "progress": task["progress"],
            "stage": task["stage"],
            "error_message": task.get("error_message"),
            "uploaded_url": task.get("uploaded_url"),
            "created_at": task["created_at"],
            "updated_at": task["updated_at"]
        })
    
    return {"tasks": formatted_tasks}


@router.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    """获取用户列表（管理员专属）"""
    db = get_database()
    users = db.get_all_users()
    
    # 格式化用户数据
    formatted_users = []
    for u in users:
        formatted_users.append({
            "id": u["id"],
            "username": u["username"],
            "email": u["email"],
            "role": u["role"],
            "status": u["status"],
            "last_login": u["last_login"]
        })
    
    return {"users": formatted_users}


@router.get("/system/stats", response_model=SystemStats)
async def get_system_stats(user: dict = Depends(require_admin)):
    """获取系统统计（管理员专属）"""
    import psutil
    
    db = get_database()
    
    # 获取统计数据
    cursor = db.conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status < 4")
    active_tasks = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 4")
    completed_tasks = cursor.fetchone()[0]
    
    # 系统资源
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory_usage = psutil.virtual_memory().percent
    
    return {
        "total_users": total_users,
        "total_tasks": total_tasks,
        "active_tasks": active_tasks,
        "completed_tasks": completed_tasks,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage
    }


@router.get("/activities")
async def get_activities(limit: int = 50, user: dict = Depends(require_admin)):
    """获取活动日志（管理员专属）"""
    db = get_database()
    activities = db.get_recent_activities(limit=limit)
    
    return {"activities": activities}


@router.post("/users/{user_id}/status")
async def update_user_status(
    user_id: int, 
    status: str,
    admin: dict = Depends(require_admin)
):
    """更新用户状态（管理员专属）"""
    if status not in ["active", "inactive", "banned"]:
        raise HTTPException(status_code=400, detail="无效的状态")
    
    db = get_database()
    cursor = db.conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
    db.conn.commit()
    
    # 记录活动
    db.log_activity(admin["user_id"], "update_user_status", target=f"user_{user_id}", 
                    details={"new_status": status})
    
    logger.info(f"管理员 {admin['username']} 更新用户 {user_id} 状态为 {status}")
    
    return {"message": "用户状态已更新"}


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: ResetPasswordRequest,
    admin: dict = Depends(require_admin)
):
    """重置用户密码（管理员专属）"""
    from services.auth_service import get_auth_service
    
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少6个字符")
    
    db = get_database()
    auth_service = get_auth_service()
    
    # 检查用户是否存在
    cursor = db.conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 加密并更新密码
    hashed_password = auth_service.hash_password(request.new_password)
    db.update_user_password(user_id, hashed_password)
    
    # 记录活动
    db.log_activity(admin["user_id"], "reset_user_password", target=f"user_{user_id}")
    
    logger.info(f"管理员 {admin['username']} 重置了用户 {user[0]} 的密码")
    
    return {"message": "密码已重置"}


@router.get("/llm-config")
async def get_llm_config_admin(admin: dict = Depends(require_admin)):
    """获取 LLM 全局配置（管理员专属，可以看到明文 API Key）
    
    NOTE: 
    - Provider分配已移至用户任务界面
    - 用户在批处理界面选择一个LLM，统一用于数据生成和求解
    - OCR固定使用SiliconFlow
    - 并发控制已移至「并发管理」页面
    - 仅支持：DeepSeek, OpenAI兼容, 硅基流动（OCR）
    """
    from services.unified_config import ConfigService
    from services.secret_service import get_secret_service
    from services.llm.provider_registry import get_all_providers, provider_to_dict
    
    config_service = ConfigService()
    secret_service = get_secret_service()
    db = get_database()
    providers = get_all_providers()
    
    # 基础配置
    config = {
        # Parameters
        "temperature_generation": config_service.get("temperature_generation", 0.7),
        "temperature_solution": config_service.get("temperature_solution", 0.7),
        "request_timeout_minutes": config_service.get("request_timeout_minutes", 5),
        
        # Proxy
        "proxy_enabled": config_service.get("proxy_enabled", False),
        "http_proxy": config_service.get("http_proxy", ""),
        "https_proxy": config_service.get("https_proxy", ""),
        
        # SSL
        "verify_ssl": config_service.get("verify_ssl", True),
        
        # Provider 定义（前端用于动态渲染）
        "providers": [provider_to_dict(p) for p in providers.values()],
    }
    
    # 动态加载每个 Provider 的配置
    cursor = db.conn.cursor()
    
    for provider_id, provider in providers.items():
        # API URL
        config[provider.api_url_field] = config_service.get(
            provider.api_url_field, provider.default_api_url
        )
        
        # Model
        config[provider.model_field] = config_service.get(
            provider.model_field, provider.default_model
        )
        
        # API Key（加密存储）
        api_key_db_field = provider.api_key_field
        try:
            cursor.execute(
                "SELECT value FROM system_configs WHERE key = ?", 
                (api_key_db_field,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    config[provider.api_key_field] = secret_service.decrypt(row[0])
                    config[f"{provider.api_key_field}_configured"] = True
                except:
                    config[provider.api_key_field] = ""
                    config[f"{provider.api_key_field}_configured"] = False
            else:
                config[provider.api_key_field] = ""
                config[f"{provider.api_key_field}_configured"] = False
        except Exception as e:
            logger.warning(f"获取 {provider_id} API Key 失败: {e}")
            config[provider.api_key_field] = ""
            config[f"{provider.api_key_field}_configured"] = False
    
    logger.info(f"管理员 {admin['username']} 查看了 LLM 配置")
    
    return {"config": config}
