# 代码同步到服务器指南

> 快速将本地修改同步到生产服务器

## 🎯 推荐方式：GitHub Actions 自动构建（最推荐）⭐

### 优势
- ✅ 服务器零构建，避免卡住
- ✅ 自动构建，无需手动操作
- ✅ 快速更新，几秒钟完成
- ✅ 构建失败不影响服务器

### 步骤

#### 1. 推送代码到 GitHub

```bash
# 在本地项目目录
cd E:\Projects\ojo

# 确认所有更改已提交
git status

# 推送到 GitHub
git push origin main
```

#### 2. 等待 GitHub Actions 构建完成

1. 访问：https://github.com/Inkotake/ojo/actions
2. 查看 "Build and Push Docker Image" 工作流
3. 等待构建完成（绿色 ✓，约 5-10 分钟）

#### 3. 在服务器上拉取镜像

```bash
# SSH 登录服务器
ssh your-server

# 进入项目目录
cd /opt/ojo

# 使用镜像仓库更新脚本（推荐）
chmod +x scripts/update-from-registry.sh
./scripts/update-from-registry.sh
```

**或者手动更新：**

```bash
cd /opt/ojo

# 1. 登录 GitHub Container Registry
docker login ghcr.io -u inkotake
# 输入你的 GitHub Token

# 2. 拉取最新镜像
docker pull ghcr.io/inkotake/ojo:latest

# 3. 标记镜像
docker tag ghcr.io/inkotake/ojo:latest ojo:v9.0

# 4. 重启服务
docker-compose restart ojo-api
```

---

## 🔧 方式 2: 直接在服务器上更新（适合小改动）

### 适用情况
- 只修改了 Python 源代码（src/）
- 没有修改 Dockerfile 或 requirements.txt
- 服务器网络良好，可以快速 git pull

### 步骤

```bash
# SSH 登录服务器
ssh your-server

# 进入项目目录
cd /opt/ojo

# 1. 备份数据（可选但推荐）
./scripts/backup-data.sh

# 2. 拉取最新代码
git pull origin main

# 3. 重启服务（代码在容器内，需要重启）
docker-compose restart ojo-api

# 4. 查看日志确认
docker-compose logs -f ojo-api
```

**注意**: 如果修改了 `requirements.txt` 或 `Dockerfile`，需要重新构建镜像：

```bash
# 使用安全构建脚本
./scripts/build-docker-safe.sh
```

---

## 🚀 方式 3: 本地构建并推送（适合测试）

### 步骤

```bash
# 在本地项目目录
cd E:\Projects\ojo

# 1. 构建并推送到镜像仓库
chmod +x scripts/build-docker-remote.sh
./scripts/build-docker-remote.sh

# 2. 在服务器上拉取
ssh your-server
cd /opt/ojo
./scripts/update-from-registry.sh
```

---

## 📋 更新检查清单

### 更新前
- [ ] 确认所有更改已提交到 Git
- [ ] 确认 GitHub Actions 构建成功（如果使用方式1）
- [ ] 备份服务器数据（可选但推荐）

### 更新中
- [ ] 拉取最新代码/镜像
- [ ] 检查环境变量配置（.env 文件）
- [ ] 重启服务

### 更新后
- [ ] 检查服务状态：`docker-compose ps`
- [ ] 查看日志：`docker-compose logs -f ojo-api`
- [ ] 测试前端访问
- [ ] 测试 API 健康检查：`curl http://localhost:8000/api/health`

---

## 🐛 常见问题

### 问题 1: git pull 卡住

**解决**: 使用 ZIP 下载方式
```bash
# 在服务器上
cd /opt/ojo
wget https://github.com/Inkotake/ojo/archive/refs/heads/main.zip
unzip main.zip
# 手动复制文件...
```

### 问题 2: Docker 镜像拉取失败

**检查**:
1. GitHub Token 是否有 `read:packages` 权限
2. 镜像是否已构建成功（查看 GitHub Actions）
3. 网络连接是否正常

**解决**: 参考 `docs/GHCR_ACCESS_FIX.md`

### 问题 3: 服务启动失败

**检查日志**:
```bash
docker-compose logs ojo-api
```

**常见原因**:
- 环境变量未配置
- 数据库文件权限问题
- 端口被占用

---

## 📝 当前更新内容 (v9.1)

本次更新包含：
- ✅ LLM 配置精简（用户在任务界面选择）
- ✅ 移除任务 Provider 分配
- ✅ 移除并发控制（移至独立页面）
- ✅ 联网搜索功能禁用
- ✅ 前端页面优化

**更新后验证**:
1. 访问前端，检查任务页面是否有 LLM 选择器
2. 检查设置页面是否显示迁移提示
3. 检查 LLM 配置页面是否已简化

---

## 🔗 相关文档

- [服务器快速指南](SERVER_QUICK_GUIDE.md)
- [GitHub Actions 设置](GITHUB_ACTIONS_SETUP.md)
- [部署文档](DEPLOYMENT_LINUX.md)
- [数据安全](DATA_SAFETY.md)

