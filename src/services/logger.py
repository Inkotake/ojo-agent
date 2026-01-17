# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional
from loguru import logger
from pathlib import Path


def _normalize_level(level: Optional[str]) -> str:
    """标准化日志级别（内部辅助）"""
    return (level or "INFO").upper()


def configure_logger(level: str = "INFO"):
    """配置日志（支持环境变量指定日志目录）"""
    import os
    # 优先使用环境变量，其次使用 /app/logs（Docker），最后使用当前目录
    logs_dir = os.getenv("OJO_LOGS_DIR")
    if not logs_dir:
        logs_path = Path("/app/logs")
        if logs_path.exists():
            logs_dir = str(logs_path)
        else:
            logs_dir = "logs"
    
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    
    try:
        logger.remove()
    except Exception:
        pass
    normalized_level = _normalize_level(level)
    log_file = logs_path / "app.log"
    logger.add(str(log_file), rotation="5 MB", retention=5, enqueue=True, encoding="utf-8", level=normalized_level)
    logger.add(lambda m: print(m, end=""), level=normalized_level)
    return logger
