#!/bin/bash
# OJO v9.0 安全 Docker 构建脚本
# 防止构建时服务器卡住

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
echo "  OJO v9.0 安全 Docker 构建"
echo "=========================================="

# 检查资源
echo "[1/5] 检查系统资源..."
DISK_AVAIL=$(df -h / | awk 'NR==2 {print $4}' | sed 's/G//')
MEM_AVAIL=$(free -g | awk 'NR==2 {print $7}')

echo "  磁盘可用: ${DISK_AVAIL}GB"
echo "  内存可用: ${MEM_AVAIL}GB"

if [ "${DISK_AVAIL%.*}" -lt 5 ]; then
    echo "[警告] 磁盘空间不足 5GB，建议清理后再构建"
    read -p "是否继续? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 备份数据（可选但推荐）
echo "[2/5] 数据备份..."
if docker volume ls | grep -q ojo-data; then
    read -p "是否备份数据? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        if [ -f "scripts/backup-data.sh" ]; then
            chmod +x scripts/backup-data.sh
            ./scripts/backup-data.sh
        else
            echo "  ⚠ 备份脚本不存在，跳过"
        fi
    fi
else
    echo "  ⚠ 未找到数据卷，跳过备份"
fi

# 清理旧的构建缓存（可选）
echo "[3/5] 清理 Docker 构建缓存..."
read -p "是否清理旧的构建缓存? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker builder prune -f
    echo "  缓存已清理"
fi

# 停止现有容器（如果运行中）
echo "[4/5] 检查运行中的容器..."
if docker ps | grep -q ojo-api; then
    echo "  发现运行中的容器，正在停止..."
    ${DOCKER_COMPOSE} down
    sleep 2
fi

# 构建镜像（带资源限制）
echo "[5/5] 开始构建 Docker 镜像（带资源限制）..."
echo "  这可能需要几分钟，请耐心等待..."

# 使用 buildkit 和资源限制
DOCKER_BUILDKIT=1 docker build \
    --memory=2g \
    --cpus=2 \
    --progress=plain \
    -t ojo:v9.0 \
    -f Dockerfile \
    .

if [ $? -eq 0 ]; then
    echo "  ✓ 构建成功"
else
    echo "  ✗ 构建失败"
    exit 1
fi

# 启动服务
echo "[5/5] 启动服务..."
${DOCKER_COMPOSE} up -d

echo ""
echo "=========================================="
echo "  构建完成！"
echo "=========================================="
echo "查看日志: ${DOCKER_COMPOSE} logs -f ojo-api"
echo "检查状态: ${DOCKER_COMPOSE} ps"
echo ""

