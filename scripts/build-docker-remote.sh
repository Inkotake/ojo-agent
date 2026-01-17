#!/bin/bash
# OJO v9.0 远程构建脚本（推荐方案）
# 在本地构建后推送到镜像仓库，服务器直接拉取

set -e

REGISTRY="${DOCKER_REGISTRY:-registry.cn-hangzhou.aliyuncs.com}"
NAMESPACE="${DOCKER_NAMESPACE:-your-namespace}"
IMAGE_NAME="ojo"
IMAGE_TAG="v9.0"
FULL_IMAGE="${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "=========================================="
echo "  OJO v9.0 远程构建（推送到镜像仓库）"
echo "=========================================="
echo "镜像: ${FULL_IMAGE}"
echo ""

# 检查是否已登录
if ! docker info | grep -q "Username"; then
    echo "[1/4] 登录 Docker 镜像仓库..."
    echo "请先配置 DOCKER_REGISTRY 和 DOCKER_NAMESPACE 环境变量"
    echo "然后执行: docker login ${REGISTRY}"
    exit 1
fi

# 构建镜像
echo "[2/4] 在本地构建镜像..."
DOCKER_BUILDKIT=1 docker build \
    --progress=plain \
    -t ${IMAGE_NAME}:${IMAGE_TAG} \
    -f Dockerfile \
    .

# 标记镜像
echo "[3/4] 标记镜像..."
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE}

# 推送镜像
echo "[4/4] 推送到镜像仓库..."
docker push ${FULL_IMAGE}

echo ""
echo "=========================================="
echo "  构建完成！"
echo "=========================================="
echo "在服务器上执行以下命令拉取镜像："
echo ""
echo "  docker pull ${FULL_IMAGE}"
echo "  docker tag ${FULL_IMAGE} ojo:v9.0"
echo "  docker-compose up -d"
echo ""

