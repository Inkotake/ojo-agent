# 服务器端更新操作指南

> 本文档专门为服务器管理员提供，包含完整的更新流程和注意事项。

## 📋 快速开始

### 首次部署

```bash
# 1. 克隆项目
cd /opt
git clone <repository-url> ojo
cd ojo

# 2. 配置环境变量
cp .env.example .env
nano .env  # 编辑并设置必要的密钥

# 3. 使用安全构建脚本
chmod +x scripts/build-docker-safe.sh
./scripts/build-docker-safe.sh
```

### 日常更新

```bash
# 进入项目目录
cd /opt/ojo

# 使用智能更新脚本（推荐）
chmod +x scripts/update-remote.sh
./scripts/update-remote.sh
```

## 🔄 更新流程详解

### 场景 1: 代码更新（最常见）

**适用情况**: 只修改了 Python 源代码，没有修改 Dockerfile 或 requirements.txt

```bash
cd /opt/ojo

# 方式 1: 使用更新脚本（自动检测）
./scripts/update-remote.sh

# 方式 2: 手动更新
git pull origin main
docker-compose restart ojo-api
```

**结果**: 不需要重新构建镜像，只需重启容器，数据不会丢失 ✅

### 场景 2: 依赖更新

**适用情况**: 修改了 requirements.txt 或 Dockerfile

```bash
cd /opt/ojo

# 使用安全构建脚本
./scripts/build-docker-safe.sh
```

**结果**: 会重新构建镜像，但数据卷保持不变，数据不会丢失 ✅

### 场景 3: 紧急修复

**适用情况**: 需要快速修复 Bug，只修改了代码

```bash
cd /opt/ojo
git pull origin main
docker-compose restart ojo-api
```

**结果**: 最快速度更新，无需构建 ✅

## 📦 数据安全

### ✅ 安全操作（数据不会丢失）

```bash
# 1. 重建镜像
docker-compose build

# 2. 停止并重启容器
docker-compose down
docker-compose up -d

# 3. 重启容器
docker-compose restart ojo-api
```

### ❌ 危险操作（会丢失数据）

```bash
# ⚠️ 不要执行这些命令！
docker-compose down -v          # 会删除数据卷
docker volume prune             # 会删除未使用的卷
docker system prune -a --volumes # 会删除所有数据
```

### 💾 备份数据

**定期备份**（建议每天或每周）:

```bash
cd /opt/ojo
chmod +x scripts/backup-data.sh
./scripts/backup-data.sh
```

**备份位置**: `./backup/YYYYMMDD_HHMMSS/`

**恢复数据**:

```bash
./scripts/restore-data.sh ./backup/20241225_120000
```

## 🛠️ 常用命令

### 检查服务状态

```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f ojo-api

# 查看最近 100 行日志
docker-compose logs --tail=100 ojo-api

# 健康检查
curl http://localhost:8000/api/health
```

### 检查数据卷

```bash
# 查看所有数据卷
docker volume ls | grep ojo

# 查看数据卷详细信息
docker volume inspect ojo-data
docker volume inspect ojo-workspace
```

### 检查资源使用

```bash
# 查看磁盘空间
df -h

# 查看内存使用
free -h

# 查看 Docker 资源使用
docker stats ojo-api
```

## 🔧 故障排查

### 问题 1: 服务无法启动

```bash
# 1. 查看日志
docker-compose logs ojo-api

# 2. 检查端口占用
netstat -tulpn | grep 8000

# 3. 检查镜像是否存在
docker images | grep ojo

# 4. 重新构建（如果需要）
./scripts/build-docker-safe.sh
```

### 问题 2: 构建时服务器卡住

```bash
# 1. 通过云控制台重启服务器

# 2. 清理 Docker 资源
docker system prune -a -f
docker builder prune -f

# 3. 使用安全构建脚本
./scripts/build-docker-safe.sh
```

### 问题 3: 数据丢失

```bash
# 1. 检查数据卷是否存在
docker volume ls | grep ojo

# 2. 如果有备份，恢复数据
./scripts/restore-data.sh <备份目录>

# 3. 如果没有备份，检查卷的物理位置
docker volume inspect ojo-data
# 查看 "Mountpoint" 字段
```

### 问题 4: 磁盘空间不足

```bash
# 1. 清理 Docker 未使用的资源
docker system prune -a

# 2. 清理旧的日志
docker-compose logs --tail=0 ojo-api > /dev/null

# 3. 清理旧的备份（保留最近 7 天）
find ./backup -type d -mtime +7 -exec rm -rf {} \;
```

## 📅 维护计划

### 每日检查

```bash
# 1. 检查服务状态
docker-compose ps

# 2. 检查健康状态
curl http://localhost:8000/api/health

# 3. 查看错误日志
docker-compose logs --tail=50 ojo-api | grep -i error
```

### 每周维护

```bash
# 1. 备份数据
./scripts/backup-data.sh

# 2. 清理旧日志
docker-compose logs --tail=0 ojo-api > /dev/null

# 3. 检查磁盘空间
df -h
```

### 每月维护

```bash
# 1. 更新系统包（可选）
apt-get update && apt-get upgrade -y

# 2. 清理 Docker 资源
docker system prune -a

# 3. 检查并更新代码
git pull origin main
./scripts/update-remote.sh
```

## 🚀 性能优化

### 限制资源使用

在 `docker-compose.yml` 中已配置资源限制：

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

如需调整，编辑 `docker-compose.yml` 后重启：

```bash
docker-compose down
docker-compose up -d
```

### 监控资源使用

```bash
# 实时监控
docker stats ojo-api

# 查看历史资源使用（需要安装 cAdvisor）
# 或使用云监控服务
```

## 📚 相关文档

- [何时需要重新构建](WHEN_TO_REBUILD.md) - 判断是否需要重建镜像
- [数据安全指南](DATA_SAFETY.md) - 数据备份和恢复
- [构建安全指南](BUILD_SAFETY.md) - 防止构建时卡住
- [Linux 部署指南](DEPLOYMENT_LINUX.md) - 完整部署文档

## ⚡ 快速参考

```bash
# 更新代码（不重建）
git pull && docker-compose restart ojo-api

# 更新代码（自动检测是否需要重建）
./scripts/update-remote.sh

# 重建镜像（安全方式）
./scripts/build-docker-safe.sh

# 备份数据
./scripts/backup-data.sh

# 查看日志
docker-compose logs -f ojo-api

# 重启服务
docker-compose restart ojo-api

# 停止服务
docker-compose down

# 启动服务
docker-compose up -d
```

---

**重要提示**: 
- ✅ 使用提供的脚本，避免手动操作
- ✅ 定期备份数据
- ❌ 不要使用 `docker-compose down -v`
- ❌ 不要在服务器上直接使用 `docker build`（使用安全脚本）

