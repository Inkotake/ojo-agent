#!/bin/bash
# Docker Compose 命令包装器
# 自动检测使用 docker-compose 还是 docker compose

# 检查 docker compose 插件（新版本）
if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
# 检查 docker-compose 独立命令（旧版本）
elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
else
    echo "错误: 未找到 docker-compose 或 docker compose 命令"
    echo ""
    echo "请安装 Docker Compose:"
    echo "  新版本 Docker: 已包含 compose 插件，使用 'docker compose'"
    echo "  旧版本: 安装 docker-compose"
    echo "    sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "    sudo chmod +x /usr/local/bin/docker-compose"
    exit 1
fi

