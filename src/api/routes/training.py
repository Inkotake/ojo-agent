# -*- coding: utf-8 -*-
"""
题单管理API
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger

router = APIRouter()


class TrainingCreateRequest(BaseModel):
    """创建题单请求"""
    title: str
    description: Optional[str] = ""
    author: Optional[str] = None
    problem_ids: Optional[List[str]] = []


class TrainingAddProblemsRequest(BaseModel):
    """添加题目请求"""
    problem_ids: List[str]


class TrainingInfo(BaseModel):
    """题单信息"""
    id: str
    title: str
    description: str
    author: str
    problem_count: int
    created_at: Optional[str] = None


class TrainingResponse(BaseModel):
    """题单响应"""
    success: bool
    message: str
    training_id: Optional[str] = None


@router.post("/create", response_model=TrainingResponse)
async def create_training(request: TrainingCreateRequest, background_tasks: BackgroundTasks):
    """
    创建新题单
    
    Args:
        request: 创建请求
        background_tasks: 后台任务
    
    Returns:
        创建结果
    """
    try:
        from services.unified_config import get_config
        from services.training_service import TrainingService
        from services.oj.registry import get_global_registry
        
        # 加载配置
        cfg = get_config()
        
        # 获取上传适配器（题单功能依赖）
        registry = get_global_registry()
        module_settings = getattr(cfg, "module_adapter_settings", {}).get("upload", {})
        adapter_name = module_settings.get("adapter", "shsoj")
        adapter = registry.get_adapter(adapter_name)
        
        if not adapter:
            raise HTTPException(status_code=400, detail="未配置上传适配器")
        
        # 登录
        auth = adapter.login()
        if not auth:
            raise HTTPException(status_code=401, detail="登录失败")
        
        # 创建题单服务
        training_svc = TrainingService(adapter)
        
        # 创建或查找题单
        ctx = training_svc.create_or_find_training(
            auth,
            gid=getattr(cfg, "training_group_id", None),
            rank=getattr(cfg, "training_rank", 0),
            category_id=getattr(cfg, "training_category_id", None),
            auth_mode=getattr(cfg, "training_auth", 0),
            private_pwd=getattr(cfg, "training_private_pwd", ""),
            status=True,
            title=request.title,
            description=request.description or "",
            author=request.author or cfg.oj_username,
        )
        
        training_id = str(ctx.tid)
        logger.info(f"创建题单成功: {training_id}, title={request.title}")
        
        # 如果有题目，后台添加
        if request.problem_ids:
            background_tasks.add_task(
                _add_problems_to_training,
                adapter_name,
                training_id,
                request.problem_ids
            )
        
        return TrainingResponse(
            success=True,
            message=f"题单创建成功",
            training_id=training_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建题单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{training_id}/add", response_model=TrainingResponse)
async def add_problems_to_training(
    training_id: str, 
    request: TrainingAddProblemsRequest,
    background_tasks: BackgroundTasks
):
    """
    添加题目到题单
    
    Args:
        training_id: 题单ID
        request: 添加请求
        background_tasks: 后台任务
    
    Returns:
        添加结果
    """
    if not request.problem_ids:
        raise HTTPException(status_code=400, detail="题目列表不能为空")
    
    try:
        from services.unified_config import get_config
        
        # 加载配置获取适配器名称
        cfg = get_config()
        
        module_settings = getattr(cfg, "module_adapter_settings", {}).get("upload", {})
        adapter_name = module_settings.get("adapter", "shsoj")
        
        # 后台添加题目
        background_tasks.add_task(
            _add_problems_to_training,
            adapter_name,
            training_id,
            request.problem_ids
        )
        
        logger.info(f"开始添加题目到题单: tid={training_id}, count={len(request.problem_ids)}")
        
        return TrainingResponse(
            success=True,
            message=f"正在添加 {len(request.problem_ids)} 个题目到题单",
            training_id=training_id
        )
        
    except Exception as e:
        logger.error(f"添加题目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_trainings(limit: int = 50):
    """
    获取题单列表
    
    Args:
        limit: 返回数量
    
    Returns:
        题单列表
    """
    try:
        from services.unified_config import get_config
        from services.oj.registry import get_global_registry
        
        # 加载配置
        cfg = get_config()
        
        # 获取适配器
        registry = get_global_registry()
        module_settings = getattr(cfg, "module_adapter_settings", {}).get("upload", {})
        adapter_name = module_settings.get("adapter", "shsoj")
        adapter = registry.get_adapter(adapter_name)
        
        if not adapter or not hasattr(adapter, 'get_training_manager'):
            return {"total": 0, "trainings": [], "message": "适配器不支持题单功能"}
        
        training_mgr = adapter.get_training_manager()
        if not training_mgr or not hasattr(training_mgr, 'list_trainings'):
            return {"total": 0, "trainings": [], "message": "题单功能未实现"}
        
        # 登录并获取列表
        auth = adapter.login()
        trainings = training_mgr.list_trainings(auth, limit=limit)
        
        return {
            "total": len(trainings),
            "trainings": trainings
        }
        
    except Exception as e:
        logger.error(f"获取题单列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{training_id}")
async def delete_training(training_id: str):
    """
    删除题单
    
    Args:
        training_id: 题单ID
    
    Returns:
        删除结果
    """
    try:
        from services.unified_config import get_config
        from services.oj.registry import get_global_registry
        
        cfg = get_config()
        
        registry = get_global_registry()
        module_settings = getattr(cfg, "module_adapter_settings", {}).get("upload", {})
        adapter_name = module_settings.get("adapter", "shsoj")
        adapter = registry.get_adapter(adapter_name)
        
        if not adapter:
            raise HTTPException(status_code=400, detail="适配器未配置")
        
        training_mgr = adapter.get_training_manager()
        if not training_mgr or not hasattr(training_mgr, 'delete_training'):
            raise HTTPException(status_code=400, detail="适配器不支持删除题单")
        
        auth = adapter.login()
        result = training_mgr.delete_training(auth, training_id)
        
        logger.info(f"删除题单: {training_id}")
        
        return {"success": True, "message": f"题单 {training_id} 已删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除题单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _add_problems_to_training(adapter_name: str, training_id: str, problem_ids: List[str]):
    """后台添加题目到题单"""
    try:
        from services.training_service import TrainingService
        from services.oj.registry import get_global_registry
        
        registry = get_global_registry()
        adapter = registry.get_adapter(adapter_name)
        
        if not adapter:
            logger.error(f"适配器不存在: {adapter_name}")
            return
        
        auth = adapter.login()
        training_svc = TrainingService(adapter)
        
        result = training_svc.add_problems(auth, int(training_id), problem_ids)
        
        logger.info(f"添加题目完成: tid={training_id}, success={len(result.get('success', []))}, failed={len(result.get('failed', []))}")
        
    except Exception as e:
        logger.error(f"后台添加题目失败: {e}", exc_info=True)
