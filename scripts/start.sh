#!/bin/bash
# OJO v9.0 启动脚本 (Linux/macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 默认值
OJO_HOST="${OJO_HOST:-0.0.0.0}"
OJO_PORT="${OJO_PORT:-8000}"
OJO_DEBUG="${OJO_DEBUG:-false}"

echo "=========================================="
echo "  OJO v9.0 - OJ批处理助手"
echo "=========================================="
echo "服务器地址: http://$OJO_HOST:$OJO_PORT"
echo "API文档: http://$OJO_HOST:$OJO_PORT/docs"
echo "调试模式: $OJO_DEBUG"
echo "=========================================="

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python 3.9+"
    exit 1
fi

# 检查虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "[信息] 已激活虚拟环境"
fi

# 检查依赖
pip install -q -r requirements.txt

# 启动服务
cd src
python api_server.py
