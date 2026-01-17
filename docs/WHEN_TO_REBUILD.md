# 何时需要重新构建 Docker 镜像

## 需要重新构建的情况

### 1. **Dockerfile 变更** ✅ 必须重建

当以下文件发生变更时，**必须**重新构建：

- `Dockerfile` - Docker 镜像构建配置
- `requirements.txt` - Python 依赖变更
- `.dockerignore` - 构建上下文变更

**检测方法**:
```bash
# 检查 Dockerfile 是否变更
git diff HEAD~1 HEAD --name-only | grep -E "(Dockerfile|requirements.txt|\.dockerignore)"
```

### 2. **系统依赖变更** ✅ 必须重建

如果 Dockerfile 中的系统包有变更：
- `apt-get install` 的包列表
- 基础镜像版本（`FROM python:3.11-slim`）

### 3. **Python 依赖变更** ✅ 必须重建

`requirements.txt` 中：
- 新增包
- 更新包版本
- 删除包

**示例**:
```diff
- fastapi==0.100.0
+ fastapi==0.104.0
```

### 4. **构建配置变更** ✅ 必须重建

- 环境变量（`ENV`）
- 工作目录（`WORKDIR`）
- 数据卷配置（`VOLUME`）

## 不需要重新构建的情况

### 1. **仅源代码变更** ❌ 不需要重建

以下文件的变更**不需要**重新构建，只需重启容器：

- `src/**/*.py` - Python 源代码
- `frontend/src/**` - 前端源代码（但需要重新构建前端）
- `config/**` - 配置文件（如果使用卷挂载）
- `docs/**` - 文档文件

**处理方式**:
```bash
# 方式 1: 使用更新脚本（自动检测）
./scripts/update-remote.sh

# 方式 2: 手动更新
git pull origin main
docker-compose restart ojo-api
```

### 2. **前端构建产物变更** ⚠️ 视情况而定

如果 `frontend/dist/` 目录变更：
- **如果使用卷挂载**: 不需要重建，直接重启
- **如果打包在镜像中**: 需要重建

**检查方式**:
```bash
# 查看 docker-compose.yml 中 frontend/dist 是否被挂载
grep -A 5 "volumes:" docker-compose.yml
```

### 3. **环境变量变更** ❌ 不需要重建

`.env` 文件或环境变量变更：
- 只需重启容器
- 不需要重建镜像

```bash
docker-compose down
docker-compose up -d
```

### 4. **配置文件变更** ❌ 不需要重建

如果配置文件通过卷挂载：
- `config/**` - 配置文件
- 数据库文件
- 日志文件

## 快速判断流程

```
代码更新后，检查：

1. 是否有 Dockerfile/requirements.txt 变更？
   ├─ 是 → 需要重建 ✅
   └─ 否 → 继续检查

2. 是否有系统依赖变更？
   ├─ 是 → 需要重建 ✅
   └─ 否 → 继续检查

3. 是否只有源代码变更？
   ├─ 是 → 不需要重建，只需重启 ❌
   └─ 否 → 需要重建 ✅
```

## 自动化检测

使用更新脚本会自动检测：

```bash
./scripts/update-remote.sh
```

脚本会：
1. 检查 `Dockerfile` 是否变更
2. 检查 `requirements.txt` 是否变更
3. 自动决定是否需要重建
4. 只更新代码时跳过构建

## 实际场景示例

### 场景 1: 修复 Bug（仅 Python 代码）

```bash
# 修改了 src/services/pipeline.py
git pull origin main
docker-compose restart ojo-api  # 只需重启
```

### 场景 2: 添加新依赖

```bash
# 修改了 requirements.txt，添加了新包
git pull origin main
./scripts/build-docker-safe.sh  # 需要重建
```

### 场景 3: 优化 Dockerfile

```bash
# 修改了 Dockerfile
git pull origin main
./scripts/build-docker-safe.sh  # 必须重建
```

### 场景 4: 更新配置

```bash
# 修改了 .env 或 config.json
git pull origin main
docker-compose down
docker-compose up -d  # 只需重启
```

## 最佳实践

1. **开发阶段**: 
   - 频繁代码变更 → 使用卷挂载，无需重建
   - 修改 `docker-compose.yml` 添加卷挂载源代码

2. **生产环境**:
   - 使用更新脚本自动检测
   - 避免不必要的构建，节省时间和资源

3. **CI/CD**:
   - 每次推送都构建镜像
   - 使用镜像标签区分版本

## 检查命令

```bash
# 检查是否需要重建
git diff HEAD~1 HEAD --name-only | grep -E "(Dockerfile|requirements\.txt)"

# 查看当前镜像
docker images | grep ojo

# 查看容器使用的镜像
docker-compose ps
docker inspect ojo-api | grep Image
```

---

**总结**: 
- **Dockerfile/依赖变更** → 必须重建
- **仅源代码变更** → 只需重启
- **不确定时** → 使用 `./scripts/update-remote.sh` 自动判断

