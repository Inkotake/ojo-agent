# -*- coding: utf-8 -*-
"""
用户配置API路由
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from loguru import logger

from core.database import get_database
from .auth import get_current_user

router = APIRouter()


class PlatformConfig(BaseModel):
    platform: str
    cookie: Optional[str] = None
    token: Optional[str] = None


class UserPreferences(BaseModel):
    auto_download: Optional[bool] = None
    keep_cache: Optional[bool] = None


@router.get("/user/config")
async def get_user_config(user: dict = Depends(get_current_user)):
    """获取用户配置"""
    db = get_database()
    configs = db.get_user_config(user["id"])
    
    # 格式化配置
    platform_configs = {}
    preferences = {
        "auto_download": True,
        "keep_cache": True
    }
    
    if isinstance(configs, list):
        for config in configs:
            platform = config["platform"]
            platform_configs[platform] = {
                "cookie": "***" if config.get("cookie") else "",  # 隐藏敏感信息
                "token": "***" if config.get("token") else "",
                "has_cookie": bool(config.get("cookie")),
                "has_token": bool(config.get("token"))
            }
            # 获取偏好设置（从第一个配置）
            if config.get("auto_download") is not None:
                preferences["auto_download"] = bool(config["auto_download"])
            if config.get("keep_cache") is not None:
                preferences["keep_cache"] = bool(config["keep_cache"])
    
    return {
        "platforms": platform_configs,
        "preferences": preferences
    }


@router.post("/user/config/platform")
async def save_platform_config(
    config: PlatformConfig,
    user: dict = Depends(get_current_user)
):
    """保存平台配置"""
    db = get_database()
    
    db.save_user_config(
        user_id=user["id"],
        platform=config.platform,
        cookie=config.cookie,
        token=config.token
    )
    
    # 记录活动
    db.log_activity(user["id"], "update_platform_config", target=config.platform)
    
    logger.info(f"用户 {user['username']} 更新了 {config.platform} 配置")
    
    return {"message": f"{config.platform} 配置已保存"}


@router.post("/user/config/preferences")
async def save_preferences(
    preferences: UserPreferences,
    user: dict = Depends(get_current_user)
):
    """保存用户偏好设置"""
    db = get_database()
    
    # 更新所有平台的偏好设置（或创建一个通用配置）
    db.save_user_config(
        user_id=user["id"],
        platform="general",
        auto_download=preferences.auto_download,
        keep_cache=preferences.keep_cache
    )
    
    # 记录活动
    db.log_activity(user["id"], "update_preferences")
    
    logger.info(f"用户 {user['username']} 更新了偏好设置")
    
    return {"message": "偏好设置已保存"}


@router.delete("/user/config/platform/{platform}")
async def delete_platform_config(
    platform: str,
    user: dict = Depends(get_current_user)
):
    """删除平台配置"""
    db = get_database()
    cursor = db.conn.cursor()
    
    cursor.execute("""
        DELETE FROM user_configs 
        WHERE user_id = ? AND platform = ?
    """, (user["id"], platform))
    db.conn.commit()
    
    # 记录活动
    db.log_activity(user["id"], "delete_platform_config", target=platform)
    
    logger.info(f"用户 {user['username']} 删除了 {platform} 配置")
    
    return {"message": f"{platform} 配置已删除"}

