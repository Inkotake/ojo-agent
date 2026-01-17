# Docker 重建时数据安全指南

## 重要结论

✅ **重新构建镜像不会丢失数据**  
❌ **删除容器和卷会丢失数据**

## 数据存储位置

### 1. 数据卷（Volumes）- 持久化存储 ✅

在 `docker-compose.yml` 中定义的数据卷：

```yaml
volumes:
  - ojo-data:/app/data      # 数据库文件
  - ojo-logs:/app/logs      # 日志文件
  - ojo-workspace:/app/workspace  # 工作区数据
```

这些数据存储在 Docker 管理的卷中，**不会因为重建镜像而丢失**。

### 2. 容器内数据 - 临时存储 ⚠️

容器内的其他数据（不在卷中的）会在容器删除时丢失。

## 安全重建流程

### 方式 1: 只重建镜像（推荐）✅

```bash
# 1. 重建镜像（不影响运行中的容器）
docker-compose build

# 2. 停止并重新创建容器（使用新镜像）
docker-compose down
docker-compose up -d

# 数据卷保持不变，数据不会丢失
```

### 方式 2: 使用安全构建脚本 ✅

```bash
# 脚本会自动处理，不会删除数据卷
./scripts/build-docker-safe.sh
```

### 方式 3: 使用更新脚本 ✅

```bash
# 自动检测并安全更新
./scripts/update-remote.sh
```

## 危险操作（会丢失数据）❌

### ⚠️ 不要执行以下命令：

```bash
# ❌ 危险：删除所有容器、网络和卷
docker-compose down -v

# ❌ 危险：删除所有未使用的卷
docker volume prune

# ❌ 危险：删除所有数据
docker system prune -a --volumes
```

## 数据备份

### 备份数据卷

```bash
# 1. 查看数据卷
docker volume ls | grep ojo

# 2. 备份数据库卷
docker run --rm \
  -v ojo-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/ojo-data-$(date +%Y%m%d).tar.gz -C /data .

# 3. 备份工作区卷
docker run --rm \
  -v ojo-workspace:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/ojo-workspace-$(date +%Y%m%d).tar.gz -C /data .
```

### 恢复数据卷

```bash
# 恢复数据库卷
docker run --rm \
  -v ojo-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/ojo-data-20241225.tar.gz -C /data

# 恢复工作区卷
docker run --rm \
  -v ojo-workspace:/data \
  -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/ojo-workspace-20241225.tar.gz -C /data
```

## 数据卷位置

### 查看数据卷物理位置

```bash
# 查看数据卷详细信息
docker volume inspect ojo-data
docker volume inspect ojo-logs
docker volume inspect ojo-workspace

# 输出示例：
# "Mountpoint": "/var/lib/docker/volumes/ojo-data/_data"
```

### 直接访问数据卷

```bash
# 进入数据卷目录（需要 root 权限）
sudo ls -la /var/lib/docker/volumes/ojo-data/_data
sudo ls -la /var/lib/docker/volumes/ojo-workspace/_data
```

## 重建前后对比

### 重建前

```
镜像: ojo:v9.0 (旧版本)
容器: ojo-api (运行中)
数据卷: ojo-data, ojo-logs, ojo-workspace (包含所有数据)
```

### 重建后（安全方式）

```
镜像: ojo:v9.0 (新版本) ✅ 已更新
容器: ojo-api (重新创建) ✅ 使用新镜像
数据卷: ojo-data, ojo-logs, ojo-workspace ✅ 数据完整保留
```

### 重建后（危险方式 -v）

```
镜像: ojo:v9.0 (新版本) ✅
容器: ojo-api (重新创建) ✅
数据卷: ❌ 已删除，数据丢失！
```

## 检查数据是否安全

### 重建前检查

```bash
# 1. 查看数据卷
docker volume ls | grep ojo

# 2. 查看数据卷内容
docker run --rm -v ojo-data:/data alpine ls -la /data

# 3. 备份（可选但推荐）
# 使用上面的备份命令
```

### 重建后验证

```bash
# 1. 检查数据卷是否还在
docker volume ls | grep ojo

# 2. 检查数据是否完整
docker run --rm -v ojo-data:/data alpine ls -la /data

# 3. 检查服务是否正常
docker-compose ps
curl http://localhost:8000/api/health
```

## 完整的安全重建流程

```bash
# 1. 备份数据（推荐）
mkdir -p backup
docker run --rm -v ojo-data:/data -v $(pwd)/backup:/backup \
  alpine tar czf /backup/ojo-data-$(date +%Y%m%d).tar.gz -C /data .

# 2. 查看当前数据卷
docker volume ls | grep ojo

# 3. 重建镜像
docker-compose build

# 4. 停止容器（不删除卷）
docker-compose down

# 5. 启动新容器（使用新镜像，旧数据卷）
docker-compose up -d

# 6. 验证数据
docker-compose logs ojo-api
curl http://localhost:8000/api/health
```

## 常见问题

### Q: 重建镜像会删除我的数据库吗？

**A: 不会**。数据库存储在 `ojo-data` 卷中，重建镜像不会影响卷。

### Q: 如何确认数据是安全的？

**A: 检查数据卷是否存在**:
```bash
docker volume ls | grep ojo
```

如果看到 `ojo-data`, `ojo-logs`, `ojo-workspace`，数据就是安全的。

### Q: 如果误删了数据卷怎么办？

**A: 如果有备份，可以恢复**:
```bash
# 重新创建卷
docker volume create ojo-data

# 恢复备份
docker run --rm -v ojo-data:/data -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/ojo-data-YYYYMMDD.tar.gz -C /data
```

### Q: 可以手动备份数据库文件吗？

**A: 可以**，数据库文件在卷中：
```bash
# 查看数据库文件位置
docker volume inspect ojo-data

# 直接复制（需要 root）
sudo cp -r /var/lib/docker/volumes/ojo-data/_data /backup/ojo-data
```

## 最佳实践

1. **定期备份**: 每天或每周备份数据卷
2. **重建前备份**: 重要操作前先备份
3. **使用脚本**: 使用提供的安全脚本，避免误操作
4. **验证数据**: 重建后验证数据完整性
5. **文档记录**: 记录备份位置和恢复流程

## 自动化备份脚本

创建 `scripts/backup-data.sh`:

```bash
#!/bin/bash
BACKUP_DIR="./backup/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

echo "备份数据卷..."
docker run --rm -v ojo-data:/data -v "$(pwd)/$BACKUP_DIR":/backup \
  alpine tar czf /backup/ojo-data.tar.gz -C /data .

docker run --rm -v ojo-workspace:/data -v "$(pwd)/$BACKUP_DIR":/backup \
  alpine tar czf /backup/ojo-workspace.tar.gz -C /data .

echo "备份完成: $BACKUP_DIR"
```

---

**总结**: 
- ✅ 重建镜像 = 安全，数据保留
- ✅ 使用 `docker-compose down` = 安全，数据保留
- ❌ 使用 `docker-compose down -v` = 危险，数据删除
- 💡 **最佳实践**: 重建前先备份

