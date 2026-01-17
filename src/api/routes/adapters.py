"""
适配器管理API
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from pydantic import BaseModel

from services.oj.registry import get_global_registry
from api.dependencies import get_current_user_optional

router = APIRouter()


class AdapterInfo(BaseModel):
    """适配器信息"""
    name: str
    display_name: str
    version: str
    capabilities: List[str]
    health: Dict[str, Any]
    status: str = "online"
    config_schema: Dict[str, Any] = {}
    config_values: Dict[str, Any] = {}
    has_config: bool = False


class AdaptersResponse(BaseModel):
    """适配器列表响应"""
    adapters: List[AdapterInfo]


@router.get("", response_model=AdaptersResponse)
@router.get("/", response_model=AdaptersResponse)
async def list_adapters(current_user: dict = Depends(get_current_user_optional)):
    """
    列出所有适配器
    
    Returns:
        适配器列表（包含用户配置状态）
    """
    try:
        from core.database import get_database
        
        registry = get_global_registry()
        db = get_database()
        user_id = current_user.get("user_id") if current_user else None
        adapters = []
        
        for adapter_name in ['shsoj', 'hydrooj', 'codeforces', 'luogu', 'atcoder', 'aicoders', 'manual']:
            adapter = registry.get_adapter(adapter_name)
            if adapter:
                # 获取健康状态
                health = {}
                if hasattr(adapter, 'health_check'):
                    try:
                        health = adapter.health_check()
                    except:
                        health = {"healthy": False, "status": "error"}
                
                # 获取配置信息
                config_schema = {}
                config_values = {}
                has_config = False
                
                if hasattr(adapter, 'get_config_schema'):
                    try:
                        config_schema = adapter.get_config_schema()
                        has_config = bool(config_schema)
                    except:
                        pass
                
                # 获取用户保存的配置
                if user_id and has_config:
                    try:
                        saved_config = db.get_user_adapter_config(user_id, adapter_name)
                        for key, schema in config_schema.items():
                            value = saved_config.get(key, '')
                            if schema.get('type') == 'password' and value:
                                config_values[key] = '********'
                                config_values[f'_{key}_configured'] = True
                            elif value:
                                config_values[key] = value
                                config_values[f'_{key}_configured'] = True
                    except:
                        pass
                
                adapters.append({
                    "name": adapter.name,
                    "display_name": adapter.display_name,
                    "version": getattr(adapter, 'version', '9.0.0'),
                    "capabilities": [cap.name.lower() for cap in adapter.capabilities],
                    "health": health,
                    "status": "online" if health.get("healthy", True) else "offline",
                    "config_schema": config_schema,
                    "config_values": config_values,
                    "has_config": has_config
                })
        
        return {"adapters": adapters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{adapter_name}/health")
async def check_adapter_health(adapter_name: str):
    """
    检查适配器健康状态
    
    Args:
        adapter_name: 适配器名称
    
    Returns:
        健康状态信息
    """
    try:
        registry = get_global_registry()
        adapter = registry.get_adapter(adapter_name)
        
        if not adapter:
            raise HTTPException(status_code=404, detail=f"适配器不存在: {adapter_name}")
        
        if hasattr(adapter, 'health_check'):
            health = adapter.health_check()
        else:
            health = {"healthy": True, "status": "unknown"}
        
        return health
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

