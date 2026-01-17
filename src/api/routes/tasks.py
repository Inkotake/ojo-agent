# -*- coding: utf-8 -*-
"""
任务管理 API 路由 v9.0

所有任务相关的 CRUD 操作，使用 TaskService 处理业务逻辑。
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from typing import Dict, List, Optional
from loguru import logger

from api.dependencies import get_current_user, require_admin
from api.schemas import TaskCreateRequest
from core.database import get_database


router = APIRouter()


# ==================== 辅助函数 ====================

def _validate_upload_adapter(user_id: int, adapter_name: str) -> None:
    """验证上传适配器配置是否完整
    
    Args:
        user_id: 用户ID
        adapter_name: 适配器名称
        
    Raises:
        HTTPException: 配置不完整时抛出
    """
    db = get_database()
    config = db.get_user_adapter_config(user_id, adapter_name)
    
    if not config:
        raise HTTPException(
            status_code=400,
            detail=f"上传适配器 {adapter_name} 未配置，请先在「适配器设置」中配置"
        )
    
    # 从适配器获取必填字段验证（动态获取，不硬编码）
    try:
        from services.oj.registry import get_global_registry
        registry = get_global_registry()
        adapter = registry.get_adapter(adapter_name) if registry else None
        
        if adapter and hasattr(adapter, 'get_config_schema'):
            schema = adapter.get_config_schema()
            required_fields = [
                field for field, info in schema.items() 
                if isinstance(info, dict) and info.get('required', False)
            ]
            
            missing = [f for f in required_fields if not config.get(f)]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"{adapter_name} 适配器配置不完整，缺少: {', '.join(missing)}"
                )
    except HTTPException:
        raise  # 验证失败，继续抛出
    except Exception as e:
        logger.debug(f"[Tasks API] 适配器 schema 获取失败，跳过字段验证: {e}")


# ==================== 任务 CRUD ====================

@router.post("")
async def create_tasks(
    request: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """创建批处理任务
    
    支持两种请求格式：
    - 新格式: problems=[{id, adapter}, ...] - 每个题目指定独立适配器
    - 旧格式: problem_ids=[...] + source_adapter - 全局适配器
    """
    from services.task_service import get_task_service, TaskConfig
    
    user_id = current_user["user_id"]
    task_service = get_task_service()
    
    # 解析请求：优先使用新格式（每题独立适配器）
    if request.problems:
        problem_ids = [p.id for p in request.problems]
        problem_adapters = {p.id: p.adapter for p in request.problems}
        logger.info(f"[Tasks API] 新格式请求: {len(problem_ids)} 题目")
        logger.info(f"[Tasks API] 适配器映射: {problem_adapters}")
    else:
        problem_ids = request.problem_ids
        problem_adapters = None
        logger.debug(f"[Tasks API] 旧格式请求: {len(problem_ids)} 题目")
    
    # 验证上传适配器配置（仅当启用上传且指定了非空目标适配器时）
    if request.enable_upload and request.target_adapter and request.target_adapter.strip():
        logger.debug(f"[Tasks API] 验证上传适配器: {request.target_adapter}")
        _validate_upload_adapter(user_id, request.target_adapter)
    
    # 构建任务配置
    config = TaskConfig(
        enable_fetch=request.enable_fetch,
        enable_generation=request.enable_generation,
        enable_upload=request.enable_upload,
        enable_solve=request.enable_solve,
        source_adapter=request.source_adapter,
        target_adapter=request.target_adapter,
        problem_adapters=problem_adapters,
        llm_provider=request.llm_provider  # 统一LLM（生成+求解）
    )
    
    # 创建任务记录
    tasks = task_service.create_tasks(
        user_id=user_id,
        problem_ids=problem_ids,
        config=config
    )
    
    # 异步执行
    background_tasks.add_task(
        task_service.execute_tasks,
        tasks, config, user_id
    )
    
    return {
        "status": "success",
        "message": f"已创建 {len(tasks)} 个任务",
        "tasks": tasks
    }


@router.get("")
async def list_tasks(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100,
    current_user: Dict = Depends(get_current_user)
):
    """获取任务列表"""
    from services.task_service import get_task_service
    
    task_service = get_task_service()
    tasks = task_service.get_user_tasks(
        user_id=current_user["user_id"],
        search=search,
        status_filter=status_filter,
        limit=limit
    )
    
    return {"tasks": tasks, "total": len(tasks)}


@router.get("/{task_id}")
async def get_task(task_id: int, current_user: Dict = Depends(get_current_user)):
    """获取任务详情"""
    from services.task_service import get_task_service
    
    task_service = get_task_service()
    task = task_service.get_task(
        task_id=task_id,
        user_id=current_user["user_id"],
        is_admin=current_user.get("role") == "admin"
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task


@router.get("/{task_id}/logs")
async def get_task_logs(task_id: int, current_user: Dict = Depends(get_current_user)):
    """获取任务日志"""
    from services.task_service import get_task_service
    
    task_service = get_task_service()
    logs = task_service.get_task_logs(
        task_id=task_id,
        user_id=current_user["user_id"],
        is_admin=current_user.get("role") == "admin"
    )
    
    return {"logs": logs}


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """删除任务
    
    删除流程：
    1. 立即删除数据库记录（保证数据一致性）
    2. 取消正在运行的任务
    3. 后台删除本地数据（不阻塞响应）
    """
    from services.task_service import get_task_service
    from api.websocket_manager import get_ws_manager
    
    task_service = get_task_service()
    user_id = current_user["user_id"]
    
    # 先获取任务信息（用于后续删除本地数据）
    task = task_service.get_task(task_id, user_id, current_user.get("role") == "admin")
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或无权删除")
    
    problem_id = task.get("problem_id")
    
    # 删除数据库记录（立即执行，快速返回）
    success = task_service.delete_task(
        task_id=task_id,
        user_id=user_id,
        is_admin=current_user.get("role") == "admin"
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或无权删除")
    
    # 后台删除本地数据（不阻塞响应）
    if problem_id:
        background_tasks.add_task(
            task_service.delete_task_data,
            task_id=task_id,
            problem_id=problem_id,
            user_id=user_id
        )
    
    # 广播删除事件
    ws_manager = get_ws_manager()
    await ws_manager.broadcast({"type": "task.deleted", "task_id": task_id})
    
    return {"status": "success", "message": f"任务 {task_id} 已删除（本地数据将在后台清理）"}


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: int,
    request: Dict = Body(...),
    current_user: Dict = Depends(get_current_user)
):
    """重试任务（原地重试，不创建新任务）"""
    from services.task_service import get_task_service
    
    module = request.get("module", "all")
    task_service = get_task_service()
    
    result_task_id = await task_service.retry_task(
        task_id=task_id,
        user_id=current_user["user_id"],
        module=module,
        is_admin=current_user.get("role") == "admin"
    )
    
    if not result_task_id:
        raise HTTPException(status_code=400, detail="任务不存在、正在运行或无权操作")
    
    return {"status": "success", "task_id": result_task_id, "module": module, "retry_in_place": True}
