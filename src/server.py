# -*- coding: utf-8 -*-
"""
OJO v9.0 - Web服务器入口

启动方式:
    python src/server.py

环境变量 (可通过 .env 文件配置):
    DEBUG       - 调试模式，启用热重载 (true/false)
    HOST        - 服务器监听地址 (默认: 0.0.0.0)
    PORT        - 服务器端口 (默认: 8000)
    LOG_LEVEL   - 日志级别 (默认: info)
"""

import os
import sys
from pathlib import Path

# 确保src目录在路径中
src_dir = Path(__file__).parent
project_root = src_dir.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_dir))


def load_env():
    """加载 .env 环境变量"""
    try:
        from dotenv import load_dotenv
        
        # 优先加载项目根目录的 .env
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return True
        
        # 尝试当前目录
        if Path(".env").exists():
            load_dotenv()
            return True
            
        return False
    except ImportError:
        return False


def get_bool_env(key: str, default: bool = False) -> bool:
    """获取布尔类型环境变量"""
    value = os.environ.get(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


def main():
    """启动服务器"""
    import uvicorn
    import signal
    from loguru import logger
    
    # 强制退出计数器
    shutdown_count = 0
    
    def force_exit_handler(signum, frame):
        """双击 Ctrl+C 强制退出"""
        nonlocal shutdown_count
        shutdown_count += 1
        if shutdown_count >= 2:
            logger.warning("收到第二次中断信号，强制退出...")
            os._exit(1)
        else:
            logger.info("收到中断信号，正在优雅关闭... (再按一次强制退出)")
            raise KeyboardInterrupt()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, force_exit_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, force_exit_handler)
    
    # 加载环境变量
    env_loaded = load_env()
    
    # 读取配置
    debug = get_bool_env("DEBUG", False)
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    log_level = os.environ.get("LOG_LEVEL", "info").lower()
    
    # 打印启动信息
    logger.info("=" * 60)
    logger.info("OJO v9.0 - Web服务器启动中...")
    logger.info("=" * 60)
    
    if env_loaded:
        logger.info("✓ 已加载 .env 配置文件")
    
    # 显示配置
    logger.info(f"运行模式: {'开发模式 (热重载)' if debug else '生产模式'}")
    logger.info(f"服务地址: http://{host}:{port}")
    logger.info(f"API 文档: http://{host}:{port}/docs")
    logger.info(f"前端界面: http://{host}:{port}/")
    logger.info(f"日志级别: {log_level.upper()}")
    logger.info("提示: 按 Ctrl+C 优雅关闭，双击强制退出")
    
    # 启动服务器
    try:
        uvicorn.run(
            "api.server:app",
            host=host,
            port=port,
            reload=debug,
            reload_dirs=[str(src_dir)] if debug else None,
            log_level=log_level,
            access_log=debug,  # 开发模式显示访问日志
        )
    except KeyboardInterrupt:
        logger.info("服务器已停止")


if __name__ == "__main__":
    main()

