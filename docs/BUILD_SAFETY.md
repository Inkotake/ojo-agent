# Docker 构建安全指南

## 问题说明

在服务器上直接执行 `docker build` 时，可能会因为资源占用过高导致：
- SSH 连接断开
- 服务器无响应
- 构建进程卡死

## 解决方案

### 方案 1: 使用安全构建脚本（推荐）

```bash
# 在服务器上执行
cd /opt/ojo
chmod +x scripts/build-docker-safe.sh
./scripts/build-docker-safe.sh
```

**特点**:
- 自动检查系统资源
- 限制构建资源使用（内存 2GB，CPU 2核）
- 构建前清理缓存
- 自动重启服务

### 方案 2: 手动限制资源构建

```bash
# 使用 Docker BuildKit 和资源限制
DOCKER_BUILDKIT=1 docker build \
    --memory=2g \
    --cpus=2 \
    --progress=plain \
    -t ojo:v9.0 \
    -f Dockerfile \
    .
```

### 方案 3: 远程构建（最佳实践）

**步骤 1: 在本地或 CI/CD 环境构建**

```bash
# 配置镜像仓库
export DOCKER_REGISTRY=registry.cn-hangzhou.aliyuncs.com
export DOCKER_NAMESPACE=your-namespace

# 构建并推送
chmod +x scripts/build-docker-remote.sh
./scripts/build-docker-remote.sh
```

**步骤 2: 在服务器上拉取**

```bash
# 登录镜像仓库
docker login registry.cn-hangzhou.aliyuncs.com

# 拉取镜像
docker pull registry.cn-hangzhou.aliyuncs.com/your-namespace/ojo:v9.0

# 标记镜像
docker tag registry.cn-hangzhou.aliyuncs.com/your-namespace/ojo:v9.0 ojo:v9.0

# 启动服务
docker-compose up -d
```

### 方案 4: 使用更新脚本（仅更新代码，不重新构建）

如果只是代码更新，不需要重新构建镜像：

```bash
cd /opt/ojo
chmod +x scripts/update-remote.sh
./scripts/update-remote.sh
```

脚本会自动检测是否需要重新构建镜像。

## 优化措施

### 1. 使用 .dockerignore

已创建 `.dockerignore` 文件，排除不必要的文件，减少构建上下文大小。

### 2. 多阶段构建

Dockerfile 已优化为多阶段构建：
- **builder 阶段**: 安装编译依赖和 Python 包
- **生产阶段**: 只复制运行时需要的文件

这样可以：
- 减少最终镜像大小
- 加快构建速度
- 降低资源占用

### 3. 构建缓存

Docker 会自动使用缓存层，只有变更的部分会重新构建。

### 4. 资源限制

在 `docker-compose.yml` 中已添加运行时资源限制：
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

## 构建前检查清单

在服务器上构建前，请检查：

```bash
# 1. 磁盘空间（至少 5GB）
df -h /

# 2. 内存可用（至少 2GB）
free -h

# 3. CPU 负载
top

# 4. Docker 状态
docker info

# 5. 清理旧镜像和容器（可选）
docker system prune -a
```

## 紧急恢复

如果构建过程中服务器卡住：

1. **通过云控制台重启服务器**
2. **清理 Docker 资源**:
   ```bash
   docker system prune -a -f
   docker builder prune -f
   ```
3. **使用安全构建脚本重新构建**

## 最佳实践

1. **生产环境**: 使用远程构建方案（方案 3）
2. **开发/测试环境**: 使用安全构建脚本（方案 1）
3. **频繁更新**: 使用更新脚本（方案 4），避免不必要的构建

## 性能对比

| 方案 | 构建时间 | 服务器负载 | 推荐场景 |
|------|---------|-----------|---------|
| 标准构建 | 5-10分钟 | 高 | 本地开发 |
| 安全构建 | 8-15分钟 | 中 | 服务器构建 |
| 远程构建 | 本地 5-10分钟<br>拉取 1-2分钟 | 低 | 生产环境 |

---

**建议**: 生产环境优先使用远程构建方案，避免在服务器上直接构建。

