# OJO v9.0 Docker Image
# 基于 Python 3.11 的生产部署镜像（多阶段构建，包含前端构建）

# ========== 阶段1: 前端构建 ==========
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制前端依赖文件（利用 Docker 缓存层）
COPY frontend/package*.json ./
RUN npm ci

# 复制前端源代码
COPY frontend/ ./

# 构建前端
RUN npm run build

# ========== 阶段2: Python 依赖构建 ==========
FROM python:3.11-slim AS python-builder

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装（利用缓存层）
# 使用精简的生产环境依赖（不包含 GUI 和浏览器自动化）
WORKDIR /app
COPY requirements_api.txt .
RUN pip install --no-cache-dir --user -r requirements_api.txt

# ========== 阶段3: 生产镜像 ==========
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    TZ=Asia/Shanghai \
    OJO_HOST=0.0.0.0 \
    OJO_PORT=8000 \
    PATH=/root/.local/bin:$PATH

# 只安装运行时依赖（不包含 gcc/g++，从 builder 复制已编译的包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从 python-builder 复制已安装的 Python 包
COPY --from=python-builder /root/.local /root/.local

# 创建工作目录
WORKDIR /app

# 从 frontend-builder 复制前端构建产物（必须在 WORKDIR 之后）
COPY --from=frontend-builder /app/frontend/dist/ ./frontend/dist/

# 复制项目文件（按变更频率分层，利用缓存）
# 先复制不常变的文件
COPY config/ ./config/

# 再复制源代码（变更最频繁）
COPY src/ ./src/

# 创建数据目录
RUN mkdir -p /app/data /app/logs /app/workspace

# 设置数据卷
VOLUME ["/app/data", "/app/logs", "/app/workspace"]

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动命令
WORKDIR /app/src
# 直接运行 api_server.py
CMD ["python", "api_server.py"]
