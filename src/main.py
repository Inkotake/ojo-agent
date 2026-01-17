# -*- coding: utf-8 -*-
"""
OJO v7.0 - OJ批处理助手
主入口：Web API服务器模式

运行方式:
    python src/main.py              # 启动API服务器
    python src/main.py --port 8080  # 指定端口
    python src/main.py --cli        # CLI模式（批量处理）
"""

from __future__ import annotations
import sys
import os
import argparse
from pathlib import Path

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 未安装时跳过

# 确保UTF-8编码
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# 设置Python路径
def setup_path():
    """设置Python路径"""
    script_path = Path(__file__).resolve()
    src_dir = script_path.parent
    project_root = src_dir.parent
    
    # 添加路径
    for p in [str(project_root), str(src_dir)]:
        if p not in sys.path:
            sys.path.insert(0, p)
    
    return project_root

PROJECT_ROOT = setup_path()

# 版本信息
VERSION = "7.0.0"
BANNER = f"""
╔══════════════════════════════════════════════════════════╗
║               OJO v{VERSION} - OJ批处理助手               ║
║                  Web API Server Mode                     ║
╚══════════════════════════════════════════════════════════╝
"""


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """启动API服务器"""
    print(BANNER)
    print(f"启动API服务器: http://{host}:{port}")
    print(f"API文档: http://{host}:{port}/docs")
    print(f"WebSocket: ws://{host}:{port}/ws")
    print("-" * 60)
    
    try:
        import uvicorn
        uvicorn.run(
            "api.server:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except ImportError:
        print("\n[错误] 缺少依赖: uvicorn")
        print("请运行: pip install uvicorn[standard] fastapi")
        sys.exit(1)


def run_cli(args):
    """CLI模式 - 批量处理"""
    from services.unified_config import ConfigManager
    from services.pipeline import PipelineRunner
    
    print(BANNER)
    print("CLI模式 - 批量处理")
    print("-" * 60)
    
    # 解析题目ID
    if not args.ids:
        print("[错误] 请指定题目ID: --ids 1001,1002,1003")
        sys.exit(1)
    
    problem_ids = []
    for part in args.ids.split(','):
        part = part.strip()
        if '-' in part:
            # 范围: 1001-1010
            try:
                start, end = map(int, part.split('-'))
                problem_ids.extend([str(i) for i in range(start, end + 1)])
            except ValueError:
                problem_ids.append(part)
        else:
            problem_ids.append(part)
    
    print(f"题目ID列表: {problem_ids}")
    print(f"启用模块: gen={args.gen}, upload={args.upload}, solve={args.solve}")
    print("-" * 60)
    
    # 加载配置（从数据库读取，ConfigManager 是兼容层）
    cfg_mgr = ConfigManager()
    cfg_mgr.load_or_init()
    
    # 创建Pipeline
    def log_callback(pid, msg):
        print(f"[{pid}] {msg}")
    
    pipeline = PipelineRunner(cfg_mgr, log_cb=log_callback)
    
    # 执行
    modules = {
        "gen": args.gen,
        "upload": args.upload,
        "solve": args.solve,
        "training": False
    }
    
    success = pipeline.run(problem_ids, modules)
    
    print("-" * 60)
    if success:
        print("✓ 所有任务完成")
    else:
        print("✗ 部分任务失败，请查看日志")
    
    return 0 if success else 1


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="OJO v7.0 - OJ批处理助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python src/main.py                      # 启动API服务器 (默认端口8000)
  python src/main.py --port 8080          # 指定端口
  python src/main.py --cli --ids 1001,1002 --gen --upload --solve
        """
    )
    
    # 模式选择
    parser.add_argument("--cli", action="store_true", help="CLI模式（批量处理）")
    
    # 服务器选项
    parser.add_argument("--host", default="0.0.0.0", help="服务器地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口 (默认: 8000)")
    parser.add_argument("--reload", action="store_true", help="开发模式（自动重载）")
    
    # CLI选项
    parser.add_argument("--ids", help="题目ID列表 (逗号分隔，支持范围如1001-1010)")
    parser.add_argument("--config", help="配置文件路径 (已废弃，配置从数据库读取)")
    parser.add_argument("--gen", action="store_true", help="启用数据生成")
    parser.add_argument("--upload", action="store_true", help="启用数据上传")
    parser.add_argument("--solve", action="store_true", help="启用代码求解")
    parser.add_argument("--all", action="store_true", help="启用所有模块")
    
    args = parser.parse_args()
    
    # 处理 --all 参数
    if args.all:
        args.gen = True
        args.upload = True
        args.solve = True
    
    # 配置已存储在数据库中，无需检查 config.json
    # config.json 仅用于首次迁移，由 ConfigService 自动处理
    
    # 从环境变量读取配置
    debug_mode = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')
    host = os.getenv('HOST', args.host)
    port = int(os.getenv('PORT', args.port))
    reload = args.reload or debug_mode
    
    # 根据模式运行
    if args.cli:
        return run_cli(args)
    else:
        if debug_mode:
            print("[DEV] 调试模式已启用，代码修改后自动重载")
        run_server(host, port, reload)
        return 0


if __name__ == "__main__":
    sys.exit(main())
