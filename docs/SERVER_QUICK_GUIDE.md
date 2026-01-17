# 服务器端快速操作指南

> 🚀 最简单的操作指南 - 使用 GitHub Actions 自动构建

## 📥 首次部署

```bash
# 1. 克隆项目
cd /opt
git clone <repository-url> ojo
cd ojo

# 2. 配置镜像仓库（选择一种方式）

# 方式 A: 使用阿里云容器镜像服务（推荐国内服务器）
cat > .env << EOF
DOCKER_REGISTRY=registry.cn-hangzhou.aliyuncs.com
DOCKER_NAMESPACE=your-namespace/ojo-api
DOCKER_IMAGE_TAG=v9.0
DOCKER_USERNAME=your-username
DOCKER_PASSWORD=your-password
JWT_SECRET_KEY=your-secret-key
OJO_ENCRYPTION_KEY=your-encryption-key
EOF

# 方式 B: 使用 GitHub Container Registry
cat > .env << EOF
DOCKER_REGISTRY=ghcr.io
DOCKER_NAMESPACE=your-github-username/ojo
DOCKER_IMAGE_TAG=latest
DOCKER_USERNAME=your-github-username
DOCKER_PASSWORD=your-github-token
JWT_SECRET_KEY=your-secret-key
OJO_ENCRYPTION_KEY=your-encryption-key
EOF

# 3. 从镜像仓库拉取并启动
chmod +x scripts/update-from-registry.sh
./scripts/update-from-registry.sh
```

## 🔄 日常更新（超简单！）

```bash
cd /opt/ojo
./scripts/update-from-registry.sh
```

**就这么简单！** 脚本会自动：
- ✅ 从镜像仓库拉取最新镜像
- ✅ 备份数据
- ✅ 重启服务

## 📋 完整操作流程

### 1. 配置 GitHub Actions（只需一次）

#### 使用阿里云容器镜像服务

1. 登录 [阿里云容器镜像服务](https://cr.console.aliyun.com/)
2. 创建命名空间和镜像仓库
3. 在 GitHub 仓库设置中添加 Secrets：
   - `ACR_USERNAME` - 阿里云用户名
   - `ACR_PASSWORD` - 阿里云密码
   - `ACR_NAMESPACE` - 命名空间/仓库名（如：`your-namespace/ojo-api`）

#### 使用 GitHub Container Registry

无需额外配置，GitHub Actions 会自动使用。

### 2. 推送代码触发构建

```bash
# 在本地开发后
git push origin main
```

GitHub Actions 会自动：
- 检测到代码变更
- 构建 Docker 镜像
- 推送到镜像仓库

### 3. 服务器端更新

```bash
cd /opt/ojo
./scripts/update-from-registry.sh
```

## 💾 备份数据

```bash
cd /opt/ojo
./scripts/backup-data.sh
```

## 📊 查看状态

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f ojo-api

# 健康检查
curl http://localhost:8000/api/health
```

## ⚠️ 重要提示

### ✅ 安全操作

```bash
./scripts/update-from-registry.sh    # 从镜像仓库更新
./scripts/update-remote.sh            # 智能更新（自动检测）
docker-compose restart ojo-api        # 重启服务
./scripts/backup-data.sh              # 备份数据
```

### ❌ 不要执行

```bash
docker-compose down -v                # ❌ 会删除数据！
docker volume prune                   # ❌ 会删除数据！
docker build                          # ❌ 可能卡住服务器！
```

## 🆘 遇到问题？

### 问题 1: 无法拉取镜像

```bash
# 检查登录状态
docker login ${DOCKER_REGISTRY}

# 检查环境变量
cat .env | grep DOCKER

# 手动拉取测试
docker pull ${DOCKER_REGISTRY}/${DOCKER_NAMESPACE}:v9.0
```

### 问题 2: GitHub Actions 构建失败

1. 访问 GitHub 仓库 → Actions
2. 查看构建日志
3. 检查 Secrets 配置是否正确

### 问题 3: 服务无法启动

```bash
# 查看日志
docker-compose logs ojo-api

# 检查镜像
docker images | grep ojo

# 检查端口
netstat -tulpn | grep 8000
```

## 📚 详细文档

- [GitHub Actions 配置指南](GITHUB_ACTIONS_SETUP.md) - 完整配置说明
- [服务器更新指南](SERVER_UPDATE_GUIDE.md) - 详细操作说明
- [数据安全指南](DATA_SAFETY.md) - 数据备份和恢复

---

**记住**: 
- 🚀 使用 GitHub Actions 自动构建
- 📥 服务器只需拉取镜像
- ✅ 永远不会卡住服务器！

