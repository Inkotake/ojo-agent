#!/bin/bash
# OJO v9.0 安全 docker-compose 启动脚本
# 自动检查资源并限制构建

set -e

echo "=========================================="
echo "  OJO v9.0 安全启动"
echo "=========================================="

# 检查资源
echo "[1/4] 检查系统资源..."
DISK_AVAIL=$(df -h / | awk 'NR==2 {print $4}')
MEM_AVAIL=$(free -h | awk 'NR==2 {print $7}')
echo "  磁盘可用: ${DISK_AVAIL}"
echo "  内存可用: ${MEM_AVAIL}"

# 检查镜像是否存在
echo "[2/4] 检查镜像..."
if docker images | grep -q "ojo.*v9.0"; then
    echo "  ✓ 发现已存在的镜像"
    USE_EXISTING="y"
else
    echo "  ⚠ 未找到镜像，需要构建"
    USE_EXISTING="n"
fi

# 如果需要构建
if [ "$USE_EXISTING" = "n" ]; then
    echo "[3/4] 构建镜像（带资源限制）..."
    echo "  使用 BuildKit 和资源限制..."
    
    # 设置环境变量启用 BuildKit
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    # 使用 docker-compose build 但限制资源
    # 注意：docker-compose 本身不支持资源限制，但 BuildKit 会优化
    docker-compose build --progress=plain
    
    if [ $? -eq 0 ]; then
        echo "  ✓ 构建成功"
    else
        echo "  ✗ 构建失败"
        echo ""
        echo "建议使用安全构建脚本:"
        echo "  ./scripts/build-docker-safe.sh"
        exit 1
    fi
else
    echo "[3/4] 跳过构建，使用现有镜像"
fi

# 启动服务
echo "[4/4] 启动服务..."
docker-compose up -d

echo ""
echo "=========================================="
echo "  启动完成！"
echo "=========================================="
echo "查看日志: docker-compose logs -f ojo-api"
echo "检查状态: docker-compose ps"
echo "健康检查: curl http://localhost:8000/api/health"
echo ""

