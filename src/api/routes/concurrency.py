# -*- coding: utf-8 -*-
"""
并发管理API (管理员)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from loguru import logger

router = APIRouter()


class ConcurrencyConfigRequest(BaseModel):
    """并发配置请求 - 无硬性限制，由用户根据实际情况配置"""
    max_global_tasks: Optional[int] = Field(None, ge=1, description="全局最大并发任务数")
    max_tasks_per_user: Optional[int] = Field(None, ge=1, description="每用户最大并发任务数")
    max_fetch_concurrent: Optional[int] = Field(None, ge=1, description="拉取并发数")
    max_upload_concurrent: Optional[int] = Field(None, ge=1, description="上传并发数")
    max_solve_concurrent: Optional[int] = Field(None, ge=1, description="求解并发数")
    max_llm_concurrent: Optional[int] = Field(None, ge=1, description="LLM请求并发数")
    max_llm_per_provider: Optional[int] = Field(None, ge=1, description="每Provider并发数")
    max_queue_size: Optional[int] = Field(None, ge=1, description="最大队列长度")
    task_timeout_seconds: Optional[int] = Field(None, ge=1, description="任务超时秒数")


class ConcurrencyConfigResponse(BaseModel):
    """并发配置响应"""
    config: Dict[str, Any]
    stats: Dict[str, Any]


@router.get("/config")
async def get_concurrency_config():
    """
    获取并发配置
    
    Returns:
        当前并发配置和统计信息
    """
    try:
        from services.concurrency_manager import get_concurrency_manager
        
        manager = get_concurrency_manager()
        
        return ConcurrencyConfigResponse(
            config=manager.get_config(),
            stats=manager.get_stats()
        )
    except Exception as e:
        logger.error(f"获取并发配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_concurrency_config(request: ConcurrencyConfigRequest):
    """
    更新并发配置 (管理员)
    
    Args:
        request: 新的并发配置
    
    Returns:
        更新后的配置
    """
    try:
        from services.concurrency_manager import get_concurrency_manager
        
        manager = get_concurrency_manager()
        
        # 过滤None值
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        if updates:
            manager.update_config(**updates)
            logger.info(f"并发配置已更新: {updates}")
        
        return {
            "success": True,
            "message": f"已更新 {len(updates)} 项配置",
            "config": manager.get_config()
        }
    except Exception as e:
        logger.error(f"更新并发配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_concurrency_stats():
    """
    获取实时并发统计
    
    Returns:
        各信号量的当前状态
    """
    try:
        from services.concurrency_manager import get_concurrency_manager
        
        manager = get_concurrency_manager()
        
        return {
            "semaphores": manager.get_stats(),
            "config": manager.get_config()
        }
    except Exception as e:
        logger.error(f"获取并发统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue")
async def get_queue_stats():
    """
    获取任务队列统计
    
    Returns:
        队列状态统计
    """
    try:
        from core.database import get_database
        
        db = get_database()
        stats = db.get_queue_stats()
        
        return {
            "queue_stats": stats,
            "pending": stats.get("pending", 0),
            "running": stats.get("running", 0),
            "completed": stats.get("completed", 0),
            "failed": stats.get("failed", 0),
            "total": stats.get("total", 0)
        }
    except Exception as e:
        logger.error(f"获取队列统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/cleanup")
async def cleanup_stale_tasks():
    """
    清理超时任务
    
    Returns:
        清理结果
    """
    try:
        from core.database import get_database
        from services.concurrency_manager import get_concurrency_manager
        
        db = get_database()
        manager = get_concurrency_manager()
        
        cleaned = db.cleanup_stale_tasks(manager.config.task_timeout_seconds)
        
        return {
            "success": True,
            "cleaned_count": cleaned,
            "message": f"清理了 {cleaned} 个超时任务"
        }
    except Exception as e:
        logger.error(f"清理任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/recover")
async def recover_tasks():
    """
    恢复中断的任务（系统重启后使用）
    
    Returns:
        恢复结果
    """
    try:
        from core.database import get_database
        
        db = get_database()
        recovered = db.recover_interrupted_tasks()
        
        return {
            "success": True,
            "recovered_count": recovered,
            "message": f"恢复了 {recovered} 个中断的任务"
        }
    except Exception as e:
        logger.error(f"恢复任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 推荐配置预设
PRESETS = {
    "light": {
        "name": "轻量模式",
        "description": "适合单用户或低负载场景",
        "config": {
            "max_global_tasks": 20,
            "max_tasks_per_user": 10,
            "max_fetch_concurrent": 5,
            "max_upload_concurrent": 3,
            "max_solve_concurrent": 3,
            "max_llm_concurrent": 4,
        }
    },
    "standard": {
        "name": "标准模式",
        "description": "适合5-10人同时使用",
        "config": {
            "max_global_tasks": 50,
            "max_tasks_per_user": 10,
            "max_fetch_concurrent": 10,
            "max_upload_concurrent": 5,
            "max_solve_concurrent": 5,
            "max_llm_concurrent": 8,
        }
    },
    "high": {
        "name": "高负载模式",
        "description": "适合10-20人同时使用",
        "config": {
            "max_global_tasks": 100,
            "max_tasks_per_user": 15,
            "max_fetch_concurrent": 20,
            "max_upload_concurrent": 10,
            "max_solve_concurrent": 10,
            "max_llm_concurrent": 16,
        }
    }
}


@router.get("/presets")
async def get_presets():
    """获取预设配置列表"""
    return {"presets": PRESETS}


@router.post("/presets/{preset_name}")
async def apply_preset(preset_name: str):
    """
    应用预设配置
    
    Args:
        preset_name: 预设名称 (light/standard/high)
    """
    if preset_name not in PRESETS:
        raise HTTPException(status_code=404, detail=f"预设不存在: {preset_name}")
    
    try:
        from services.concurrency_manager import get_concurrency_manager
        
        manager = get_concurrency_manager()
        preset = PRESETS[preset_name]
        manager.update_config(**preset["config"])
        
        logger.info(f"已应用预设配置: {preset_name}")
        
        return {
            "success": True,
            "preset": preset_name,
            "message": f"已应用 {preset['name']}",
            "config": manager.get_config()
        }
    except Exception as e:
        logger.error(f"应用预设失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
