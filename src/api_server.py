#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OJO API服务器 v9.0
提供REST API和WebSocket接口

统一入口文件，使用 api/server.py 作为应用实例。
"""

import sys
import os
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from loguru import logger


def main():
    """启动API服务器"""
    # 从环境变量读取配置
    host = os.getenv("OJO_HOST", "0.0.0.0")
    port = int(os.getenv("OJO_PORT", "8000"))
    debug = os.getenv("OJO_DEBUG", "").lower() in ("true", "1", "yes")
    
    logger.info("=" * 60)
    logger.info("OJO v9.0 API服务器启动")
    logger.info(f"地址: http://{host}:{port}")
    logger.info(f"API文档: http://{host}:{port}/docs")
    logger.info(f"WebSocket: ws://{host}:{port}/ws")
    logger.info(f"调试模式: {debug}")
    logger.info("=" * 60)
    
    # 启动uvicorn服务器（使用 api/server.py 作为统一入口）
    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        log_level="info",
        reload=debug,
        timeout_keep_alive=600,  # 增加keep-alive超时（10分钟），支持大文件下载
        timeout_graceful_shutdown=30  # 优雅关闭超时
    )


if __name__ == "__main__":
    main()

