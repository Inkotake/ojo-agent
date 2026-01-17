# -*- coding: utf-8 -*-
"""
OJO v9.0 - FastAPI 服务器（精简入口）

职责：
1. 创建 FastAPI 应用
2. 配置中间件（CORS、异常处理）
3. 注册路由模块
4. 挂载静态文件
5. 事件总线集成

所有业务逻辑已移至 services/ 层。
"""

import sys
import os
from pathlib import Path

# 确保导入路径正确
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(src_dir.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime
from loguru import logger

# ==================== 创建应用 ====================

app = FastAPI(
    title="OJO v9.0 API",
    description="OJ批处理助手 - 统一架构版",
    version="9.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ==================== CORS 中间件 ====================

def get_cors_origins() -> list:
    """获取允许的 CORS 来源"""
    origins_str = os.getenv("CORS_ORIGINS", "")
    if origins_str:
        return [o.strip() for o in origins_str.split(",") if o.strip()]
    
    if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        return ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]
    
    return []

cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ==================== 全局异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    # 使用 repr() 避免花括号被 loguru 解释为格式占位符
    logger.error("未处理的异常: {}", repr(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "服务器内部错误"}
    )

# ==================== 注册路由 ====================

from api.routes import auth, adapters, config, admin, problems, training, wash, concurrency, system, websocket as ws_routes, tasks, invite_codes, workspace, project

# 核心路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(adapters.router, prefix="/api/adapters", tags=["适配器"])
app.include_router(config.router, prefix="/api/config", tags=["配置"])
app.include_router(admin.router, prefix="/api/admin", tags=["管理"])
app.include_router(system.router, prefix="/api/system", tags=["系统"])
app.include_router(invite_codes.router, prefix="/api/invite-codes", tags=["邀请码"])

# 业务路由
app.include_router(tasks.router, prefix="/api/tasks", tags=["任务"])
app.include_router(problems.router, prefix="/api/problems", tags=["题目"])
app.include_router(training.router, prefix="/api/training", tags=["题单"])
app.include_router(wash.router, prefix="/api/wash", tags=["数据清洗"])
app.include_router(concurrency.router, prefix="/api/concurrency", tags=["并发控制"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["工作区"])
app.include_router(project.router, prefix="/api", tags=["项目信息"])

# WebSocket 路由
app.include_router(ws_routes.router, tags=["WebSocket"])

# ==================== 适配器配置 ====================

from api.dependencies import get_current_user, require_admin
from fastapi import Depends, HTTPException, Body
from typing import Dict

@app.get("/api/adapters/{adapter_name}/config", tags=["适配器"])
async def get_adapter_config(adapter_name: str, current_user: Dict = Depends(get_current_user)):
    """获取适配器配置"""
    from services.oj.registry import get_global_registry
    from core.database import get_database
    
    registry = get_global_registry()
    adapter = registry.get_adapter(adapter_name)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"适配器不存在: {adapter_name}")
    
    db = get_database()
    saved_config = db.get_user_adapter_config(current_user["user_id"], adapter_name)
    config_schema = adapter.get_config_schema() if hasattr(adapter, 'get_config_schema') else {}
    
    # 隐藏密码字段
    config_values = {}
    for key, schema in config_schema.items():
        value = saved_config.get(key, schema.get('default', ''))
        if schema.get('type') == 'password' and value:
            config_values[key] = '********'
        else:
            config_values[key] = value
    
    return {"config": config_values, "schema": config_schema}

@app.post("/api/adapters/{adapter_name}/config", tags=["适配器"])
async def save_adapter_config(
    adapter_name: str,
    request: Dict = Body(...),
    current_user: Dict = Depends(get_current_user)
):
    """保存适配器配置"""
    from services.oj.registry import get_global_registry
    from core.database import get_database
    
    registry = get_global_registry()
    adapter = registry.get_adapter(adapter_name)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"适配器不存在: {adapter_name}")
    
    db = get_database()
    config = request.get("config", {})
    
    # 获取现有配置，保留未更新的密码
    existing = db.get_user_adapter_config(current_user["user_id"], adapter_name)
    schema = adapter.get_config_schema() if hasattr(adapter, 'get_config_schema') else {}
    
    for key, sch in schema.items():
        if sch.get('type') == 'password' and config.get(key) == '********':
            config[key] = existing.get(key, '')
    
    # 重要：对字符串字段进行 trim，避免前后空格导致登录失败
    for key, value in config.items():
        if isinstance(value, str):
            config[key] = value.strip()
    
    db.save_user_adapter_config(current_user["user_id"], adapter_name, config)
    
    return {"status": "success", "message": f"适配器 {adapter_name} 配置已保存"}

# ==================== 管理员路由 ====================

@app.post("/api/admin/users", tags=["管理"])
async def admin_create_user(request: Dict = Body(...), admin: Dict = Depends(require_admin)):
    """创建用户（管理员）"""
    from services.auth_service import get_auth_service
    
    auth_service = get_auth_service()
    try:
        user_id = auth_service.create_user(
            username=request["username"],
            password=request["password"],
            role=request.get("role", "user"),
            email=request.get("email", "")
        )
        return {"status": "success", "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/users/{user_id}", tags=["管理"])
async def admin_delete_user(user_id: int, admin: Dict = Depends(require_admin)):
    """删除用户（管理员）"""
    from core.database import get_database
    
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    db = get_database()
    cursor = db.conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.conn.commit()
    
    return {"status": "success", "message": f"用户 {user_id} 已删除"}

@app.put("/api/admin/users/{user_id}/role", tags=["管理"])
async def admin_update_role(
    user_id: int,
    request: Dict = Body(...),
    admin: Dict = Depends(require_admin)
):
    """更新用户角色（管理员）"""
    from core.database import get_database
    
    role = request.get("role")
    if role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="无效的角色")
    
    db = get_database()
    cursor = db.conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    db.conn.commit()
    
    return {"status": "success", "message": f"用户角色已更新为 {role}"}

@app.delete("/api/admin/tasks/{task_id}", tags=["管理"])
async def admin_delete_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    admin: Dict = Depends(require_admin)
):
    """删除任务（管理员）
    
    删除流程：
    1. 立即删除数据库记录（保证数据一致性）
    2. 取消正在运行的任务
    3. 后台删除本地数据（不阻塞响应）
    """
    from services.task_service import get_task_service
    
    task_service = get_task_service()
    
    # 先获取任务信息（用于后续删除本地数据）
    task = task_service.get_task(task_id, None, is_admin=True)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="任务不存在")
    
    problem_id = task.get("problem_id")
    user_id = task.get("user_id")
    
    # 删除数据库记录（立即执行，快速返回）
    success = task_service.delete_task(
        task_id=task_id,
        user_id=user_id or 0,
        is_admin=True
    )
    
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="任务删除失败")
    
    # 后台删除本地数据（不阻塞响应）
    if problem_id and user_id:
        background_tasks.add_task(
            task_service.delete_task_data,
            task_id=task_id,
            problem_id=problem_id,
            user_id=user_id
        )
    
    return {"status": "success", "message": f"任务 {task_id} 已删除（本地数据将在后台清理）"}

# ==================== 健康检查 ====================

@app.get("/api/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "9.0.0"
    }

# ==================== 统计接口 ====================

@app.get("/api/stats", tags=["系统"])
async def get_stats(current_user: Dict = Depends(get_current_user)):
    """获取用户统计"""
    from services.task_service import get_task_service
    
    task_service = get_task_service()
    return task_service.get_user_stats(current_user["user_id"])

@app.get("/api/stats/usage", tags=["系统"])
async def get_usage_stats(current_user: Dict = Depends(get_current_user)):
    """获取使用统计（前端兼容）"""
    from services.task_service import get_task_service
    
    task_service = get_task_service()
    stats = task_service.get_user_stats(current_user["user_id"])
    return {"usage": stats, "user_id": current_user["user_id"]}

# ==================== 配置兼容路由 ====================

@app.get("/api/config", tags=["配置"])
async def get_config_compat(current_user: Dict = Depends(get_current_user)):
    """获取用户配置（前端兼容）"""
    from services.unified_config import get_config
    from core.database import get_database
    
    db = get_database()
    cfg = get_config()
    
    # 返回合并的配置
    # NOTE: llm_provider_generation 和 llm_provider_solution 已废弃
    # 现在用户在任务界面选择统一的 llm_provider
    return {
        "config": {
            # 不再返回废弃的 provider 分配字段
            # "llm_provider_generation": cfg.llm_provider_generation,  # 已废弃
            # "llm_provider_solution": cfg.llm_provider_solution,  # 已废弃
            # 并发控制已移至并发管理页面
            # "llm_max_concurrency": cfg.llm_max_concurrency,  # 已移至并发管理页面
            "deepseek_api_key": "***" if cfg.deepseek_api_key else "",
            "gemini_api_key": "***" if cfg.gemini_api_key else "",
            "temperature_generation": cfg.temperature_generation,
            "temperature_solution": cfg.temperature_solution,
        }
    }

@app.post("/api/config", tags=["配置"])
async def save_config_compat(
    request: Dict = Body(...),
    current_user: Dict = Depends(get_current_user)
):
    """保存用户配置（前端兼容）
    
    所有配置统一通过 update_config 保存：
    - API Key 会被自动加密后单独存储
    - 其他配置保存到 app_config JSON
    """
    from services.unified_config import update_config
    
    key = request.get("key")
    value = request.get("value")
    
    if key and value is not None:
        # 统一使用 update_config，它会自动处理 API Key 的加密存储
        update_config(**{key: value})
        logger.info(f"配置 {key} 已保存")
    
    return {"status": "success", "message": "配置已保存"}

# ==================== 模块适配器设置 ====================

@app.get("/api/module-adapters", tags=["配置"])
async def get_module_adapters(current_user: Dict = Depends(get_current_user)):
    """获取模块适配器设置"""
    from core.database import get_database
    
    db = get_database()
    settings = db.get_user_module_settings(current_user["user_id"])
    
    return {"module_adapter_settings": settings}

@app.post("/api/module-adapters", tags=["配置"])
async def save_module_adapters(
    request: Dict = Body(...),
    current_user: Dict = Depends(get_current_user)
):
    """保存模块适配器设置"""
    from core.database import get_database
    
    db = get_database()
    db.save_user_module_settings(current_user["user_id"], request)
    
    return {"status": "success", "message": "模块适配器设置已保存"}

# ==================== LLM 测试 ====================

@app.post("/api/llm/test", tags=["配置"])
async def test_llm_connection(
    request: Dict = Body(...),
    current_user: Dict = Depends(get_current_user)
):
    """测试 LLM 连接
    
    参数:
        provider: LLM 提供商 ID (deepseek, openai, siliconflow)
        full_test: 是否进行完整测试（发送真实请求），默认 False
    
    模式:
        - full_test=False: 快速检查（仅验证 API Key 是否配置）
        - full_test=True: 完整测试（发送真实请求验证连通性）
    """
    from services.llm.provider_registry import get_provider
    from services.secret_service import get_secret_service
    from services.unified_config import ConfigService
    from core.database import get_database
    
    provider_id = request.get("provider", "deepseek")
    full_test = request.get("full_test", False)
    
    try:
        provider = get_provider(provider_id)
        
        if not provider:
            return {"success": False, "error": f"未知的 Provider: {provider_id}"}
        
        # 从加密存储中读取 API Key
        db = get_database()
        secret_service = get_secret_service()
        config_service = ConfigService()
        
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT value FROM system_configs WHERE key = ?",
            (provider.api_key_field,)
        )
        row = cursor.fetchone()
        
        api_key = ""
        if row and row[0]:
            try:
                api_key = secret_service.decrypt(row[0])
            except Exception:
                pass
        
        if not api_key:
            return {"success": False, "error": f"{provider.name} API Key 未配置"}
        
        # 快速检查模式：只验证 API Key 存在
        if not full_test:
            return {"success": True, "message": f"{provider.name} API Key 已配置"}
        
        # 完整测试模式：发送真实请求
        logger.info(f"[LLM Test] 开始完整测试 {provider.name}")
        
        # 获取配置
        api_url = config_service.get(provider.api_url_field, provider.default_api_url)
        model = config_service.get(provider.model_field, provider.default_model)
        timeout = config_service.get("request_timeout_minutes", 5) * 60
        
        # 创建客户端并发送测试请求
        try:
            if provider_id == "deepseek":
                from services.llm.deepseek import DeepSeekClient
                client = DeepSeekClient(
                    api_key=api_key,
                    base_url=api_url,
                    model=model,
                    timeout=30  # 测试用较短超时
                )
            elif provider_id == "openai":
                from services.llm.openai_compatible import OpenAICompatibleClient
                client = OpenAICompatibleClient(
                    api_key=api_key,
                    base_url=api_url,
                    model=model,
                    timeout=30
                )
            elif provider_id == "siliconflow":
                from services.llm.siliconflow import SiliconFlowClient
                client = SiliconFlowClient(
                    api_key=api_key,
                    base_url=api_url,
                    model=model,
                    timeout=30
                )
            else:
                return {"success": False, "error": f"不支持测试的 Provider: {provider_id}"}
            
            # 发送简单测试请求
            response, _ = client.chat_completion(
                prompt="请回复'OK'两个字母",
                max_tokens=10,
                temperature=0.1
            )
            
            if response and len(response) > 0:
                logger.info(f"[LLM Test] {provider.name} 测试成功: {response[:50]}")
                return {
                    "success": True, 
                    "message": f"{provider.name} 连接正常",
                    "response": response[:100]  # 返回前100字符
                }
            else:
                return {"success": False, "error": "API 返回空响应"}
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[LLM Test] {provider.name} 测试失败: {error_msg}")
            return {"success": False, "error": f"API 请求失败: {error_msg}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/llm/providers", tags=["配置"])
async def get_llm_providers(current_user: Dict = Depends(get_current_user)):
    """获取可用的 LLM Providers"""
    from services.llm.provider_registry import (
        get_all_providers_dict, 
        get_user_selectable_providers,
        provider_to_dict
    )
    
    return {
        "providers": get_all_providers_dict(),
        "user_selectable": [provider_to_dict(p) for p in get_user_selectable_providers()]
    }

# ==================== 静态文件 ====================

project_root = Path(__file__).parent.parent.parent
frontend_dist = project_root / "frontend" / "dist"

def load_frontend_html():
    """加载前端 HTML"""
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        try:
            with open(frontend_dist / "index.html", "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取前端HTML失败: {e}")
    return None

# 挂载静态资源
if frontend_dist.exists() and (frontend_dist / "assets").exists():
    try:
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
        logger.info(f"前端静态文件已挂载: {frontend_dist / 'assets'}")
    except Exception as e:
        logger.error(f"挂载静态文件失败: {e}")

# ==================== 前端路由 ====================

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """根路径 - 返回前端页面"""
    html_content = load_frontend_html()
    if html_content:
        return HTMLResponse(content=html_content)
    return JSONResponse({
        "name": "OJO v9.0 API",
        "version": "9.0.0",
        "status": "running",
        "docs": "/docs",
        "note": "前端未构建，请运行: cd frontend && npm run build"
    })

@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
async def serve_frontend(full_path: str):
    """SPA 路由支持"""
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "ws", "assets/")):
        raise HTTPException(status_code=404, detail="Not found")
    
    html_content = load_frontend_html()
    if html_content:
        return HTMLResponse(content=html_content)
    raise HTTPException(status_code=404, detail="Frontend not built")

# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup_event():
    """服务器启动"""
    logger.info("=" * 50)
    logger.info("OJO v9.0 服务器启动")
    logger.info("=" * 50)
    
    # 初始化事件总线集成
    from core.events import get_event_bus, EventType
    from api.websocket_manager import get_ws_manager
    
    event_bus = get_event_bus()
    ws_manager = get_ws_manager()
    
    async def on_task_event(event):
        """任务事件 -> WebSocket 广播"""
        await ws_manager.broadcast({
            "type": event.type.value if hasattr(event.type, 'value') else str(event.type),
            "task_id": event.data.get("task_id"),
            "problem_id": event.data.get("problem_id"),
            "progress": event.data.get("progress", 0),
            "stage": event.data.get("stage"),
            "data": event.data
        })
    
    event_bus.subscribe(EventType.TASK_STARTED, on_task_event)
    event_bus.subscribe(EventType.TASK_PROGRESS, on_task_event)
    event_bus.subscribe(EventType.TASK_COMPLETED, on_task_event)
    event_bus.subscribe(EventType.TASK_FAILED, on_task_event)

@app.on_event("shutdown")
async def shutdown_event():
    """服务器关闭"""
    logger.info("OJO v9.0 服务器关闭中...")
    
    # 关闭 TaskService（取消所有运行中的任务）
    try:
        from services.task_service import get_task_service
        task_service = get_task_service()
        # 不等待任务完成，快速关闭
        task_service.shutdown(wait=False)
    except Exception as e:
        logger.debug(f"关闭 TaskService: {e}")
    
    # 关闭数据库连接
    try:
        from core.database import get_database
        db = get_database()
        if hasattr(db, 'close'):
            db.close()
    except Exception:
        pass
    
    logger.info("OJO v9.0 服务器已关闭")
