#!/bin/bash
# OJO v9.0 远程服务器更新脚本
# 在服务器上执行，安全更新代码和重启服务

set -e

# 检测 docker-compose 命令（兼容新旧版本）
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "错误: 未找到 docker-compose 或 docker compose 命令"
    echo "请安装 Docker Compose 或使用新版本 Docker（包含 compose 插件）"
    exit 1
fi

# 加载 .env 文件（如果存在）
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "=========================================="
echo "  OJO v9.0 远程更新"
echo "=========================================="

# 检查资源
echo "[1/6] 检查系统资源..."
DISK_AVAIL=$(df -h / | awk 'NR==2 {print $4}')
MEM_AVAIL=$(free -h | awk 'NR==2 {print $7}')
echo "  磁盘可用: ${DISK_AVAIL}"
echo "  内存可用: ${MEM_AVAIL}"

# 备份当前版本
echo "[2/6] 备份当前配置..."
if [ -f docker-compose.yml ]; then
    cp docker-compose.yml docker-compose.yml.bak
    echo "  ✓ 配置已备份"
fi

# 拉取代码
echo "[3/6] 拉取最新代码..."
git fetch origin
git pull origin main

if [ $? -ne 0 ]; then
    echo "  ✗ 代码拉取失败，请检查网络连接"
    exit 1
fi
echo "  ✓ 代码已更新"

# 检查是否有 Dockerfile 变更
if git diff HEAD~1 HEAD --name-only | grep -q Dockerfile; then
    echo "[4/6] 检测到 Dockerfile 变更，需要重新构建..."
    
    # 检查是否配置了镜像仓库
    if [ -n "${DOCKER_REGISTRY}" ] && [ -n "${DOCKER_NAMESPACE}" ]; then
        echo "  使用镜像仓库拉取（推荐）..."
        IMAGE="${DOCKER_REGISTRY}/${DOCKER_NAMESPACE}/ojo:v9.0"
        
        # 登录镜像仓库（如果需要）
        if [ -n "${DOCKER_USERNAME}" ] && [ -n "${DOCKER_PASSWORD}" ]; then
            echo "  登录镜像仓库..."
            echo "${DOCKER_PASSWORD}" | docker login ${DOCKER_REGISTRY} -u "${DOCKER_USERNAME}" --password-stdin
        fi
        
        # 拉取最新镜像
        echo "  拉取镜像: ${IMAGE}"
        docker pull ${IMAGE}
        
        # 标记镜像
        docker tag ${IMAGE} ojo:v9.0
        
        # 重启服务
        echo "[5/6] 重启服务..."
        docker-compose down
        sleep 2
        docker-compose up -d
    else
        echo "  使用本地构建（未配置镜像仓库）..."
        chmod +x scripts/build-docker-safe.sh
        ./scripts/build-docker-safe.sh
    fi
else
    echo "[4/6] 无需重新构建镜像"
    
    # 只重启服务
    echo "[5/6] 重启服务..."
    ${DOCKER_COMPOSE} down
    sleep 2
    ${DOCKER_COMPOSE} up -d
fi

# 等待服务启动
echo "[6/6] 等待服务启动..."
sleep 5

# 检查服务状态
if ${DOCKER_COMPOSE} ps | grep -q "Up"; then
    echo ""
    echo "=========================================="
    echo "  ✓ 更新完成！"
    echo "=========================================="
    echo "查看日志: ${DOCKER_COMPOSE} logs -f ojo-api"
    echo "检查健康: curl http://localhost:8000/api/health"
else
    echo ""
    echo "=========================================="
    echo "  ⚠ 服务可能未正常启动"
    echo "=========================================="
    echo "查看日志: ${DOCKER_COMPOSE} logs ojo-api"
    exit 1
fi

