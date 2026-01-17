# Docker 构建和部署指南

## 构建流程

### 多阶段构建说明

Dockerfile 采用多阶段构建，包含三个阶段：

1. **前端构建阶段** (`frontend-builder`)
   - 使用 `node:18-alpine` 作为基础镜像
   - 安装前端依赖并构建前端应用
   - 输出到 `frontend/dist/`

2. **Python 依赖构建阶段** (`python-builder`)
   - 使用 `python:3.11-slim` 作为基础镜像
   - 安装编译依赖并构建 Python 包
   - 输出到 `/root/.local/`

3. **生产镜像阶段**
   - 使用 `python:3.11-slim` 作为运行时镜像
   - 从前面两个阶段复制构建产物
   - 只包含运行时依赖，镜像体积更小

### 本地构建

```bash
# 构建镜像
docker build -t ojo:v9.0 .

# 或者使用构建脚本
./scripts/build-docker-safe.sh
```

### GitHub Actions 自动构建

当以下文件发生变更时，会自动触发构建：

- `Dockerfile`
- `requirements*.txt`
- `src/**` (后端源代码)
- `frontend/src/**` (前端源代码)
- `frontend/package*.json` (前端依赖)
- `frontend/*.config.*` (前端配置文件)
- `config/**` (配置文件)

构建完成后，镜像会自动推送到 GitHub Container Registry (ghcr.io)。

### 镜像标签

GitHub Actions 会自动生成以下标签：

- `latest` - main 分支的最新版本
- `main-<commit-sha>` - 基于 commit SHA 的标签
- `main` - 分支名标签

## 从远端服务器拉取镜像

### 1. 登录 GitHub Container Registry

```bash
# 使用 GitHub Personal Access Token (需要 packages:read 权限)
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

或者使用 GitHub CLI：

```bash
gh auth login
gh auth token | docker login ghcr.io -u USERNAME --password-stdin
```

### 2. 拉取镜像

```bash
# 拉取最新版本
docker pull ghcr.io/YOUR_USERNAME/YOUR_REPO:latest

# 拉取特定标签
docker pull ghcr.io/YOUR_USERNAME/YOUR_REPO:main-abc1234
```

### 3. 运行容器

```bash
# 使用 docker-compose
docker-compose up -d

# 或直接运行
docker run -d \
  --name ojo-api \
  -p 8000:8000 \
  -v ojo-data:/app/data \
  -v ojo-logs:/app/logs \
  -v ojo-workspace:/app/workspace \
  ghcr.io/YOUR_USERNAME/YOUR_REPO:latest
```

## 注意事项

### 构建产物不再跟踪

- `frontend/dist/` 目录已添加到 `.gitignore`
- 构建产物在 Docker 构建时自动生成
- 不需要手动运行 `npm run build` 再提交

### 缓存优化

GitHub Actions 使用 GHA (GitHub Actions) 缓存来加速构建：
- 前端依赖缓存
- Python 依赖缓存
- Docker 层缓存

### 镜像大小优化

- 使用多阶段构建，最终镜像不包含构建工具
- 前端构建产物只包含必要的静态文件
- Python 包只包含运行时依赖

## 故障排查

### 构建失败

1. **前端构建失败**
   ```bash
   # 检查前端依赖是否正确
   cd frontend && npm ci
   ```

2. **Python 依赖安装失败**
   ```bash
   # 检查 requirements_api.txt 是否有效
   pip install -r requirements_api.txt
   ```

3. **Docker 构建超时**
   - 检查网络连接
   - 考虑使用国内镜像源

### 镜像拉取失败

1. **认证失败**
   - 检查 GITHUB_TOKEN 是否有 `packages:read` 权限
   - 确认镜像仓库是公开的，或已授权访问

2. **镜像不存在**
   - 确认 GitHub Actions 构建已完成
   - 检查仓库名称是否正确

## 更新流程

### 自动更新（推荐）

1. 推送代码到 main 分支
2. GitHub Actions 自动构建并推送镜像
3. 在服务器上拉取新镜像并重启容器

```bash
# 在服务器上执行
docker pull ghcr.io/YOUR_USERNAME/YOUR_REPO:latest
docker-compose down
docker-compose up -d
```

### 手动更新

如果需要手动触发构建：

1. 在 GitHub 仓库页面，进入 Actions
2. 选择 "Build and Push Docker Image" workflow
3. 点击 "Run workflow" 按钮


