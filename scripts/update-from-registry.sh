#!/bin/bash
# OJO v9.0 从镜像仓库更新脚本
# 适用于使用 GitHub Actions 或其他 CI/CD 构建镜像的场景

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
    echo "[信息] 加载 .env 文件..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# 配置镜像仓库（从环境变量读取，默认使用 GitHub Container Registry）
REGISTRY="${DOCKER_REGISTRY:-ghcr.io}"
NAMESPACE="${DOCKER_NAMESPACE:-inkotake/ojo}"
IMAGE_TAG="${DOCKER_IMAGE_TAG:-latest}"
FULL_IMAGE="${REGISTRY}/${NAMESPACE}:${IMAGE_TAG}"

echo "=========================================="
echo "  OJO v9.0 从镜像仓库更新"
echo "=========================================="
echo "镜像: ${FULL_IMAGE}"
echo ""

# 检查环境变量（GitHub Container Registry 使用默认值，不需要强制配置）
# 如果使用其他镜像仓库，需要在 .env 中配置
if [ "${REGISTRY}" != "ghcr.io" ] && ([ -z "${DOCKER_REGISTRY}" ] || [ -z "${DOCKER_NAMESPACE}" ]); then
    echo "错误: 未配置镜像仓库信息"
    echo ""
    echo "请在 .env 文件中设置:"
    echo "  DOCKER_REGISTRY=ghcr.io"
    echo "  DOCKER_NAMESPACE=inkotake/ojo"
    echo "  DOCKER_IMAGE_TAG=latest"
    echo "  DOCKER_USERNAME=your-username"
    echo "  DOCKER_PASSWORD=your-password"
    exit 1
fi

# 登录镜像仓库（如果需要）
if [ -n "${DOCKER_USERNAME}" ] && [ -n "${DOCKER_PASSWORD}" ]; then
    echo "[1/5] 登录镜像仓库..."
    echo "${DOCKER_PASSWORD}" | docker login ${REGISTRY} -u "${DOCKER_USERNAME}" --password-stdin
    echo "  ✓ 登录成功"
else
    echo "[1/5] 跳过登录（使用公开镜像或已登录）"
fi

# 备份数据（可选）
echo "[2/5] 数据备份..."
if docker volume ls | grep -q ojo-data; then
    read -p "是否备份数据? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        if [ -f "scripts/backup-data.sh" ]; then
            chmod +x scripts/backup-data.sh
            ./scripts/backup-data.sh
        fi
    fi
fi

# 停止服务
echo "[3/5] 停止服务..."
${DOCKER_COMPOSE} down
sleep 2

# 拉取最新镜像
echo "[4/5] 拉取最新镜像..."
docker pull ${FULL_IMAGE}

# 标记镜像
echo "  标记镜像..."
docker tag ${FULL_IMAGE} ojo:v9.0

# 启动服务
echo "[5/5] 启动服务..."
${DOCKER_COMPOSE} up -d

# 等待服务启动
echo ""
echo "等待服务启动..."
sleep 5

# 检查服务状态
if ${DOCKER_COMPOSE} ps | grep -q "Up"; then
    echo ""
    echo "=========================================="
    echo "  ✓ 更新完成！"
    echo "=========================================="
    echo "查看日志: ${DOCKER_COMPOSE} logs -f ojo-api"
    echo "检查健康: curl http://localhost:8000/api/health"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "  ⚠ 服务可能未正常启动"
    echo "=========================================="
    echo "查看日志: ${DOCKER_COMPOSE} logs ojo-api"
    exit 1
fi

