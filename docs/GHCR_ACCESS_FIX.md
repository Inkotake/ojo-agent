# GitHub Container Registry 访问被拒绝问题

## 问题：Error response from daemon: denied

这通常是因为：
1. GitHub Personal Access Token 权限不足
2. 镜像不存在（GitHub Actions 还没构建）
3. 镜像仓库是私有的，需要正确的权限

## 🔍 检查步骤

### 1. 检查 GitHub Actions 是否已构建

访问：https://github.com/Inkotake/ojo/actions

查看是否有成功的构建任务。如果没有，需要先触发构建。

### 2. 检查 Token 权限

GitHub Personal Access Token 需要以下权限：
- ✅ `read:packages` - 读取包
- ✅ `write:packages` - 写入包（如果需要推送）

### 3. 检查镜像是否存在

```bash
# 测试拉取（会显示更详细的错误）
docker pull ghcr.io/inkotake/ojo:latest
```

## 🔧 解决方案

### 方案 1: 重新生成 Token（推荐）

1. 访问：https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选权限：
   - ✅ `read:packages`
   - ✅ `write:packages`（如果需要）
4. 生成并复制新 Token
5. 更新 `.env` 文件中的 `DOCKER_PASSWORD`

### 方案 2: 检查镜像是否已构建

```bash
# 访问 GitHub Actions 页面
# https://github.com/Inkotake/ojo/actions

# 如果没有构建，手动触发：
# 1. 访问 Actions 页面
# 2. 选择 "Build and Push Docker Image" 工作流
# 3. 点击 "Run workflow"
```

### 方案 3: 使用公开镜像（如果仓库是公开的）

如果仓库是公开的，镜像也应该是公开的，不需要登录：

```bash
# 尝试不登录直接拉取
docker pull ghcr.io/inkotake/ojo:latest
```

### 方案 4: 检查镜像标签

GitHub Actions 可能使用了不同的标签：

```bash
# 检查可用的标签
# 访问：https://github.com/Inkotake/ojo/pkgs/container/ojo

# 或者尝试其他标签
docker pull ghcr.io/inkotake/ojo:main
docker pull ghcr.io/inkotake/ojo:main-<commit-sha>
```

## 🚀 快速修复

### 步骤 1: 更新 Token

```bash
cd /opt/ojo

# 编辑 .env 文件
nano .env

# 更新 DOCKER_PASSWORD 为新的 Token
# 保存并退出（Ctrl+X, Y, Enter）
```

### 步骤 2: 重新登录

```bash
# 重新登录
docker logout ghcr.io
echo "ghp_your_new_token" | docker login ghcr.io -u inkotake --password-stdin
```

### 步骤 3: 测试拉取

```bash
# 测试拉取
docker pull ghcr.io/inkotake/ojo:latest
```

### 步骤 4: 如果镜像不存在，触发构建

1. 访问：https://github.com/Inkotake/ojo/actions
2. 选择 "Build and Push Docker Image"
3. 点击 "Run workflow" → "Run workflow"
4. 等待构建完成（5-10分钟）

## 📋 完整检查清单

```bash
# 1. 检查 GitHub Actions 构建状态
# 访问：https://github.com/Inkotake/ojo/actions

# 2. 检查 Token 权限
# 访问：https://github.com/settings/tokens

# 3. 检查镜像是否存在
# 访问：https://github.com/Inkotake/ojo/pkgs/container/ojo

# 4. 测试登录
docker login ghcr.io -u inkotake

# 5. 测试拉取
docker pull ghcr.io/inkotake/ojo:latest
```

## ⚠️ 常见错误

### 错误 1: "denied: permission denied"

**原因**: Token 权限不足或已过期

**解决**: 重新生成 Token，确保有 `read:packages` 权限

### 错误 2: "manifest unknown"

**原因**: 镜像不存在或标签不对

**解决**: 
1. 检查 GitHub Actions 是否已构建
2. 检查镜像标签是否正确
3. 访问 https://github.com/Inkotake/ojo/pkgs/container/ojo 查看可用标签

### 错误 3: "unauthorized"

**原因**: 登录失败

**解决**: 
```bash
# 重新登录
docker logout ghcr.io
docker login ghcr.io -u inkotake
# 输入 Token 作为密码
```

---

**推荐**: 先检查 GitHub Actions 是否已构建镜像，然后更新 Token 权限。

