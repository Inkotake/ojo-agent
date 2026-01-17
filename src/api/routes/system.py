"""
系统管理API
"""

from fastapi import APIRouter
from typing import Dict, Any
import json

router = APIRouter()


@router.get("/info")
async def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    return {
        "version": "7.0.0",
        "name": "OJO - Online Judge Organizer",
        "architecture": "event-driven",
        "status": "running"
    }


@router.get("/config")
async def get_system_config() -> Dict[str, Any]:
    """获取系统配置（脱敏）"""
    try:
        from services.unified_config import get_config
        
        cfg = get_config()
        
        # 返回脱敏后的配置
        return {
            "llm_max_concurrency": cfg.llm_max_concurrency,
            "oj_max_concurrency": cfg.oj_max_concurrency,
            "max_workers": cfg.max_workers,
            "enable_solution_search": cfg.enable_solution_search,
            "log_level": cfg.log_level
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats")
async def get_system_stats() -> Dict[str, Any]:
    """获取系统统计"""
    try:
        # 读取summary.json
        summary_file = Path("summary.json")
        if summary_file.exists():
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)
            # 确保返回字典格式
            if isinstance(summary, list):
                return {
                    "results": summary,
                    "total": len(summary),
                    "success": sum(1 for r in summary if r.get('ok_gen') or r.get('ok_upload') or r.get('ok_solve')),
                    "failed": sum(1 for r in summary if not (r.get('ok_gen') or r.get('ok_upload') or r.get('ok_solve')))
                }
            return summary
        return {"total": 0, "success": 0, "failed": 0, "results": []}
    except Exception as e:
        return {"error": str(e), "total": 0, "success": 0, "failed": 0}

