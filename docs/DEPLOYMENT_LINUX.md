# OJO v9.0 Linux 生产环境部署指南

> **重要提示**: 
> - 重新构建镜像**不会**丢失数据（数据存储在 Docker 卷中）
> - 使用提供的安全脚本可以防止构建时服务器卡住
> - 建议定期备份数据（见 [数据安全指南](DATA_SAFETY.md)）

## 一、系统要求

- **操作系统**: Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)
- **Python**: 3.9+ (推荐 3.11)
- **编译器**: g++ (用于本地验题)
- **内存**: 至少 2GB
- **磁盘**: 至少 10GB 可用空间

## 二、环境变量配置

创建 `.env` 文件（或通过系统环境变量设置）：

```bash
# 服务器配置
OJO_HOST=0.0.0.0
OJO_PORT=8000
OJO_DEBUG=false

# 路径配置（可选，Docker 环境会自动使用 /app 目录）
OJO_WORKSPACE=/app/workspace    # 工作区目录
OJO_LOGS_DIR=/app/logs          # 日志目录
OJO_DB_PATH=/app/data/ojo.db    # 数据库路径

# 安全配置（必须设置）
JWT_SECRET_KEY=your-secret-key-here
OJO_ENCRYPTION_KEY=your-encryption-key-here

# CORS 配置（生产环境建议限制）
CORS_ORIGINS=https://your-domain.com
```

## 三、Docker 部署（推荐）

### ⚠️ 重要：防止构建时服务器卡住

**不要直接使用 `docker build` 或 `docker-compose build`**，这可能导致服务器资源耗尽。

### 方式 1: 安全构建脚本（推荐）✅

```bash
# 使用安全构建脚本（自动限制资源、备份数据）
chmod +x scripts/build-docker-safe.sh
./scripts/build-docker-safe.sh
```

**特点**:
- 自动检查系统资源
- 限制构建资源使用（内存 2GB，CPU 2核）
- 自动备份数据
- 构建前清理缓存
- 自动重启服务

### 方式 2: 智能更新脚本（推荐用于更新）✅

```bash
# 自动检测是否需要重新构建
chmod +x scripts/update-remote.sh
./scripts/update-remote.sh
```

**特点**:
- 自动检测 Dockerfile/requirements.txt 是否变更
- 只更新代码时跳过构建
- 自动备份数据
- 安全重启服务

### 方式 3: 直接启动（镜像已存在时）✅

```bash
# 如果镜像已存在，直接启动
docker-compose up -d
```

### 方式 4: 远程构建（最佳实践，避免服务器构建）✅

```bash
# 在本地或 CI/CD 环境构建并推送
chmod +x scripts/build-docker-remote.sh
./scripts/build-docker-remote.sh

# 在服务器上拉取
docker pull <your-registry>/ojo:v9.0
docker-compose up -d
```

### 查看日志

```bash
docker-compose logs -f ojo-api
```

### 健康检查

```bash
curl http://localhost:8000/api/health
```

### 数据备份

```bash
# 手动备份数据
chmod +x scripts/backup-data.sh
./scripts/backup-data.sh
```

**相关文档**:
- [何时需要重新构建](WHEN_TO_REBUILD.md)
- [数据安全指南](DATA_SAFETY.md)
- [构建安全指南](BUILD_SAFETY.md)

## 四、直接部署（不使用 Docker）

### 1. 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv g++ gcc libffi-dev curl

# CentOS/RHEL
sudo yum install -y python3 python3-pip gcc-c++ libffi-devel curl
```

### 2. 克隆项目

```bash
git clone <repository-url>
cd ojo
```

### 3. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 5. 配置环境变量

```bash
# 创建 .env 文件
cp .env.example .env
# 编辑 .env 文件，设置必要的配置
```

### 6. 创建必要目录

```bash
mkdir -p workspace logs data
chmod 755 workspace logs data
```

### 7. 启动服务

```bash
# 使用启动脚本
chmod +x scripts/start.sh
./scripts/start.sh

# 或直接启动
cd src
python api_server.py
```

### 8. 使用 systemd 管理（可选）

创建 `/etc/systemd/system/ojo.service`:

```ini
[Unit]
Description=OJO v9.0 API Server
After=network.target

[Service]
Type=simple
User=ojo
WorkingDirectory=/opt/ojo
Environment="PATH=/opt/ojo/venv/bin"
Environment="OJO_WORKSPACE=/opt/ojo/workspace"
Environment="OJO_LOGS_DIR=/opt/ojo/logs"
Environment="OJO_DB_PATH=/opt/ojo/data/ojo.db"
ExecStart=/opt/ojo/venv/bin/python /opt/ojo/src/api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable ojo
sudo systemctl start ojo
sudo systemctl status ojo
```

## 五、路径配置说明

### 环境变量优先级

1. **OJO_WORKSPACE**: 工作区目录（存储题目数据、测试用例等）
   - 默认: `workspace` (当前目录)
   - Docker: `/app/workspace`

2. **OJO_LOGS_DIR**: 日志目录
   - 默认: `logs` (当前目录)
   - Docker: `/app/logs`

3. **OJO_DB_PATH**: 数据库文件路径
   - 默认: `ojo.db` (当前目录)
   - Docker: `/app/data/ojo.db`

### 自动检测逻辑

代码会自动检测：
- 如果设置了环境变量，使用环境变量
- 如果 `/app/workspace` 或 `/app/logs` 存在（Docker 环境），使用这些路径
- 否则使用当前目录的相对路径

## 六、验证部署

### 1. 检查服务状态

```bash
curl http://localhost:8000/api/health
```

预期响应：
```json
{"status": "ok", "version": "9.0.0"}
```

### 2. 检查 API 文档

访问: http://localhost:8000/docs

### 3. 检查日志

```bash
# Docker
docker-compose logs ojo-api

# 直接部署
tail -f logs/app.log
```

## 七、常见问题

### 1. 编译错误：找不到 g++

**问题**: 本地验题时提示找不到编译器

**解决**:
```bash
# Ubuntu/Debian
sudo apt-get install g++

# CentOS/RHEL
sudo yum install gcc-c++
```

### 2. 权限错误

**问题**: 无法创建目录或写入文件

**解决**:
```bash
# 确保目录权限正确
chmod 755 workspace logs data
chown -R ojo:ojo workspace logs data
```

### 3. 数据库路径错误

**问题**: 数据库文件无法创建或访问

**解决**:
- 检查 `OJO_DB_PATH` 环境变量
- 确保数据库目录存在且有写权限
- Docker 环境确保数据卷已挂载

### 4. 端口被占用

**问题**: 端口 8000 已被占用

**解决**:
```bash
# 修改环境变量
export OJO_PORT=8001

# 或修改 docker-compose.yml
ports:
  - "8001:8000"
```

## 八、性能优化

### 1. 并发控制

通过 `/api/concurrency` 接口调整并发限制：
- `max_compile_concurrent`: 本地编译验题并发数（默认 2）
- `max_llm_concurrent`: LLM 请求并发数
- `max_global_tasks`: 全局任务并发数

### 2. 日志轮转

日志文件自动轮转（5MB），保留最近 5 个文件。

### 3. 数据库优化

SQLite 数据库会自动创建索引，无需手动优化。

## 九、安全建议

1. **生产环境必须设置**:
   - `JWT_SECRET_KEY`: 使用强随机字符串
   - `OJO_ENCRYPTION_KEY`: 使用 Fernet 密钥（32 字节 base64）

2. **限制 CORS**:
   - 设置 `CORS_ORIGINS` 为实际域名
   - 不要使用 `*` 允许所有来源

3. **防火墙**:
   - 只开放必要的端口（80/443/8000）
   - 使用 Nginx 反向代理

4. **定期备份**:
   - 数据库文件: `/app/data/ojo.db`
   - 配置文件: 环境变量或 `.env`

## 十、更新升级

### Docker 环境

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

### 直接部署

```bash
# 拉取最新代码
git pull

# 更新依赖
pip install -r requirements.txt

# 重启服务
sudo systemctl restart ojo
```

---

**注意**: 首次部署后，请访问 `/api/admin/llm-config` 配置 LLM API 密钥。

