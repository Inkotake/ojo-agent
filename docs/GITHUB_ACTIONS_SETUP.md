# GitHub Actions 自动构建配置指南

> 使用 GitHub Actions 自动构建 Docker 镜像，服务器直接拉取，避免在服务器上构建导致卡住。

## 🎯 方案优势

- ✅ **服务器零构建**: 不在服务器上构建，避免资源耗尽
- ✅ **自动构建**: 代码推送后自动构建镜像
- ✅ **快速更新**: 服务器只需拉取镜像，几秒钟完成
- ✅ **版本管理**: 支持多版本标签（latest, v9.0, commit-sha）

## 📋 配置步骤

### 方式 1: 使用 GitHub Container Registry (推荐，免费)

#### 1. 启用 GitHub Actions

GitHub Actions 已配置在 `.github/workflows/docker-build.yml`，推送代码后自动触发。

#### 2. 查看构建结果

1. 访问 GitHub 仓库
2. 点击 "Actions" 标签
3. 查看构建状态

#### 3. 服务器端配置

```bash
# 在服务器上创建 .env 文件
cd /opt/ojo
cat > .env << EOF
DOCKER_REGISTRY=ghcr.io
DOCKER_NAMESPACE=your-github-username/ojo
DOCKER_IMAGE_TAG=latest
EOF
```

#### 4. 服务器端更新

```bash
# 使用镜像仓库更新脚本
chmod +x scripts/update-from-registry.sh
./scripts/update-from-registry.sh
```

**注意**: GitHub Container Registry 需要登录，使用 Personal Access Token (PAT)。

### 方式 2: 使用阿里云容器镜像服务 (推荐国内服务器)

#### 1. 创建镜像仓库

1. 登录 [阿里云容器镜像服务](https://cr.console.aliyun.com/)
2. 创建命名空间（如：`ojo`）
3. 创建镜像仓库（如：`ojo-api`）

#### 2. 配置 GitHub Secrets

在 GitHub 仓库设置中添加 Secrets：

1. 进入仓库 → Settings → Secrets and variables → Actions
2. 添加以下 Secrets：

```
ACR_USERNAME=你的阿里云用户名
ACR_PASSWORD=你的阿里云密码（或访问凭证）
ACR_NAMESPACE=你的命名空间/ojo-api
```

#### 3. 启用 GitHub Actions

工作流文件已配置在 `.github/workflows/docker-build-aliyun.yml`。

#### 4. 服务器端配置

```bash
# 在服务器上创建 .env 文件
cd /opt/ojo
cat > .env << EOF
DOCKER_REGISTRY=registry.cn-hangzhou.aliyuncs.com
DOCKER_NAMESPACE=your-namespace/ojo-api
DOCKER_IMAGE_TAG=v9.0
DOCKER_USERNAME=your-username
DOCKER_PASSWORD=your-password
EOF
```

#### 5. 服务器端更新

```bash
# 使用镜像仓库更新脚本
chmod +x scripts/update-from-registry.sh
./scripts/update-from-registry.sh
```

### 方式 3: 使用 Docker Hub

#### 1. 配置 GitHub Secrets

```
DOCKERHUB_USERNAME=your-dockerhub-username
DOCKERHUB_TOKEN=your-dockerhub-token
```

#### 2. 修改工作流文件

将 `REGISTRY` 改为 `docker.io`，`IMAGE_NAME` 改为 `your-username/ojo`

## 🚀 使用流程

### 开发流程

1. **本地开发** → 修改代码
2. **提交代码** → `git push origin main`
3. **GitHub Actions** → 自动构建镜像并推送
4. **服务器更新** → 执行 `./scripts/update-from-registry.sh`

### 服务器端日常更新

```bash
cd /opt/ojo

# 方式 1: 使用镜像仓库更新（推荐）
./scripts/update-from-registry.sh

# 方式 2: 使用智能更新脚本（自动检测）
./scripts/update-remote.sh
```

## 📝 工作流说明

### 触发条件

- **自动触发**: 推送到 `main` 分支，且以下文件有变更：
  - `Dockerfile`
  - `requirements.txt`
  - `src/**`
- **手动触发**: 在 GitHub Actions 页面点击 "Run workflow"

### 构建过程

1. 检出代码
2. 设置 Docker Buildx
3. 登录镜像仓库
4. 构建镜像（使用缓存加速）
5. 推送镜像（多个标签）

### 镜像标签

- `latest` - 最新版本（main 分支）
- `v9.0` - 版本标签
- `main-<commit-sha>` - 提交 SHA 标签

## 🔧 服务器端配置

### 修改 docker-compose.yml（可选）

如果使用镜像仓库，可以修改 `docker-compose.yml`：

```yaml
services:
  ojo-api:
    # 取消注释，注释掉 build 部分
    image: ${DOCKER_REGISTRY}/${DOCKER_NAMESPACE}:${DOCKER_IMAGE_TAG:-v9.0}
    # build:
    #   context: .
    #   dockerfile: Dockerfile
```

### 环境变量配置

创建 `.env` 文件：

```bash
# 镜像仓库配置
DOCKER_REGISTRY=registry.cn-hangzhou.aliyuncs.com
DOCKER_NAMESPACE=your-namespace/ojo-api
DOCKER_IMAGE_TAG=v9.0

# 登录凭证（如果需要）
DOCKER_USERNAME=your-username
DOCKER_PASSWORD=your-password

# 其他配置
OJO_HOST=0.0.0.0
OJO_PORT=8000
JWT_SECRET_KEY=your-secret-key
OJO_ENCRYPTION_KEY=your-encryption-key
```

## ✅ 验证配置

### 检查 GitHub Actions

1. 推送代码后，访问 GitHub Actions 页面
2. 查看构建是否成功
3. 检查镜像是否已推送

### 检查服务器端

```bash
# 测试拉取镜像
docker pull ${DOCKER_REGISTRY}/${DOCKER_NAMESPACE}:v9.0

# 查看镜像
docker images | grep ojo

# 更新服务
./scripts/update-from-registry.sh
```

## 🆚 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| GitHub Container Registry | 免费、集成好 | 国内访问慢 | 国外服务器 |
| 阿里云容器镜像服务 | 国内访问快 | 需要付费账户 | 国内服务器 |
| Docker Hub | 全球访问 | 免费账户有限制 | 通用场景 |
| 服务器本地构建 | 无需配置 | 可能卡住 | 不推荐 |

## 📚 相关文档

- [服务器更新指南](SERVER_UPDATE_GUIDE.md) - 服务器端操作
- [构建安全指南](BUILD_SAFETY.md) - 本地构建方案
- [数据安全指南](DATA_SAFETY.md) - 数据保护

---

**推荐**: 生产环境使用 GitHub Actions + 镜像仓库方案，完全避免服务器构建问题！

