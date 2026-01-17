# 服务器更新步骤（v9.1）

## 🚀 快速更新（推荐）

### 方式 1: 使用镜像仓库更新脚本（最简单）

```bash
# SSH 登录服务器
ssh your-server

# 进入项目目录
cd /opt/ojo

# 运行更新脚本（会自动处理所有步骤）
chmod +x scripts/update-from-registry.sh
./scripts/update-from-registry.sh
```

**脚本会自动：**
1. ✅ 加载 `.env` 文件
2. ✅ 登录镜像仓库
3. ✅ 备份数据（可选）
4. ✅ 停止服务
5. ✅ 拉取最新镜像
6. ✅ 标记镜像
7. ✅ 启动服务
8. ✅ 检查服务状态

---

## 📋 手动更新步骤

如果脚本有问题，可以手动执行：

### 步骤 1: 检查 GitHub Actions 构建状态

1. 访问：https://github.com/Inkotake/ojo/actions
2. 查看 "Build and Push Docker Image" 工作流
3. 确认构建成功（绿色 ✓）

**如果没有构建，手动触发：**
- 点击 "Build and Push Docker Image"
- 点击 "Run workflow" → "Run workflow"

### 步骤 2: 登录服务器

```bash
ssh your-server
cd /opt/ojo
```

### 步骤 3: 检查环境变量

```bash
# 查看 .env 文件
cat .env | grep DOCKER

# 确保有以下配置：
# DOCKER_REGISTRY=ghcr.io
# DOCKER_NAMESPACE=inkotake/ojo
# DOCKER_IMAGE_TAG=latest
# DOCKER_USERNAME=inkotake
# DOCKER_PASSWORD=ghp_your_token
```

### 步骤 4: 登录镜像仓库

```bash
# 登录 GitHub Container Registry
docker login ghcr.io -u inkotake
# 输入你的 GitHub Token 作为密码
```

### 步骤 5: 拉取最新镜像

```bash
# 拉取最新镜像
docker pull ghcr.io/inkotake/ojo:latest

# 标记镜像
docker tag ghcr.io/inkotake/ojo:latest ojo:v9.0
```

### 步骤 6: 重启服务

```bash
# 停止服务
docker-compose down

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f ojo-api
```

### 步骤 7: 验证更新

```bash
# 检查服务状态
docker-compose ps

# 健康检查
curl http://localhost:8000/api/health

# 访问前端，检查：
# - LLM配置页面是否已移除"任务Provider分配"
# - 任务页面是否有统一的LLM选择器
```

---

## 🔍 验证更新是否成功

### 检查前端

1. 访问：`http://your-server:7355/llm-config`
2. **应该看到**：
   - ✅ API Keys 配置
   - ✅ API 地址配置
   - ✅ 模型名称配置
   - ✅ 生成参数配置
   - ✅ 网络配置
   - ❌ **不应该看到**："任务Provider分配"部分

3. 访问：`http://your-server:7355/tasks`
4. **应该看到**：
   - ✅ "2. LLM (生成+求解)" 选择器
   - ✅ 说明文字："数据生成和代码求解统一使用此LLM"

### 检查后端

```bash
# 查看API返回
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/admin/llm-config

# 应该不包含 llm_provider_generation 和 llm_provider_solution 字段
```

---

## 🐛 常见问题

### 问题 1: 镜像拉取失败 "denied"

**原因**: GitHub Token 权限不足

**解决**:
1. 检查 Token 是否有 `read:packages` 权限
2. 更新 `.env` 中的 `DOCKER_PASSWORD`
3. 重新登录：`docker login ghcr.io -u inkotake`

### 问题 2: 服务启动失败

**检查日志**:
```bash
docker-compose logs ojo-api
```

**常见原因**:
- 环境变量未配置
- 端口被占用
- 数据库文件权限问题

### 问题 3: 前端还是显示旧界面

**解决**:
1. **清除浏览器缓存**：
   - Chrome: Ctrl+Shift+Delete → 清除缓存
   - 或使用无痕模式访问

2. **强制刷新**：
   - Windows: Ctrl+F5
   - Mac: Cmd+Shift+R

3. **检查镜像是否更新**：
   ```bash
   docker images | grep ojo
   # 查看镜像的创建时间
   ```

---

## 📝 更新检查清单

- [ ] GitHub Actions 构建成功
- [ ] 服务器 `.env` 配置正确
- [ ] Docker 登录成功
- [ ] 镜像拉取成功
- [ ] 服务启动成功
- [ ] 前端显示新界面（无"任务Provider分配"）
- [ ] 任务页面有统一LLM选择器

---

## 🔗 相关文档

- [代码同步指南](SYNC_TO_SERVER.md)
- [GitHub Actions 设置](GITHUB_ACTIONS_SETUP.md)
- [GHCR 访问问题](GHCR_ACCESS_FIX.md)

