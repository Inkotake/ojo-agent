# GitHub Actions 快速开始（5分钟配置）

> 最简单的配置方式，适合快速上手

## 🎯 两种方案选择

### 方案 A: GitHub Container Registry（最简单，推荐）

**无需额外配置，推送代码即可自动构建！**

### 方案 B: 阿里云容器镜像服务（国内服务器推荐）

**需要配置 3 个 GitHub Secrets**

---

## 🚀 方案 A: GitHub Container Registry（推荐）

### 步骤 1: 推送代码（自动触发构建）

```bash
# 代码已包含工作流文件，直接推送即可
git push origin main
```

### 步骤 2: 查看构建

1. 访问 GitHub 仓库
2. 点击 "Actions" 标签
3. 等待构建完成（约 5-10 分钟）

### 步骤 3: 服务器配置

```bash
cd /opt/ojo

# 创建或编辑 .env 文件
cat > .env << 'EOF'
DOCKER_REGISTRY=ghcr.io
DOCKER_NAMESPACE=your-github-username/ojo
DOCKER_IMAGE_TAG=latest
DOCKER_USERNAME=your-github-username
DOCKER_PASSWORD=ghp_your_personal_access_token
JWT_SECRET_KEY=your-secret-key
OJO_ENCRYPTION_KEY=your-encryption-key
EOF

# 注意：脚本会自动加载 .env 文件，无需手动 export

# 获取 GitHub Personal Access Token:
# GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
# 勾选 read:packages 和 write:packages

# 从镜像仓库更新
chmod +x scripts/update-from-registry.sh
./scripts/update-from-registry.sh
```

**完成！** 🎉

---

## 🚀 方案 B: 阿里云容器镜像服务

### 步骤 1: 创建镜像仓库

1. 登录 [阿里云容器镜像服务](https://cr.console.aliyun.com/)
2. 创建命名空间（如：`ojo`）
3. 创建镜像仓库（如：`ojo-api`）
4. 设置固定密码（用于 GitHub Actions）

### 步骤 2: 配置 GitHub Secrets

1. 访问 GitHub 仓库 → Settings → Secrets and variables → Actions
2. 添加 3 个 Secrets：

```
ACR_USERNAME = 你的阿里云用户名
ACR_PASSWORD = 你在镜像仓库设置的固定密码
ACR_NAMESPACE = 命名空间/仓库名（如：my-namespace/ojo-api）
```

### 步骤 3: 触发构建

```bash
git push origin main
```

### 步骤 4: 服务器配置

```bash
cd /opt/ojo

# 创建或编辑 .env 文件
cat > .env << 'EOF'
DOCKER_REGISTRY=registry.cn-hangzhou.aliyuncs.com
DOCKER_NAMESPACE=your-namespace/ojo-api
DOCKER_IMAGE_TAG=v9.0
DOCKER_USERNAME=your-aliyun-username
DOCKER_PASSWORD=your-aliyun-password
JWT_SECRET_KEY=your-secret-key
OJO_ENCRYPTION_KEY=your-encryption-key
EOF

# 注意：脚本会自动加载 .env 文件，无需手动 export

# 从镜像仓库更新
chmod +x scripts/update-from-registry.sh
./scripts/update-from-registry.sh
```

**完成！** 🎉

---

## 🔄 日常使用

### 开发流程

```bash
# 1. 修改代码
# 2. 提交并推送
git push origin main

# 3. 等待 GitHub Actions 构建完成（5-10分钟）
# 4. 在服务器上更新
cd /opt/ojo
./scripts/update-from-registry.sh
```

## ✅ 验证

### 检查构建状态

访问 GitHub 仓库 → Actions → 查看最新构建

### 检查服务器

```bash
docker-compose ps
docker-compose logs -f ojo-api
curl http://localhost:8000/api/health
```

## 📚 详细文档

- [完整教程](GITHUB_ACTIONS_TUTORIAL.md) - 详细步骤和故障排查
- [服务器快速指南](SERVER_QUICK_GUIDE.md) - 服务器端操作

---

**就这么简单！** 配置一次，之后只需 `git push` 和 `./scripts/update-from-registry.sh` 🚀

