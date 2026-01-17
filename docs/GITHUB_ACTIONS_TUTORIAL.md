# GitHub Actions 使用教程（详细步骤）

> 手把手教你配置 GitHub Actions 自动构建 Docker 镜像

## 🎯 方案说明

**工作流程**:
1. 本地开发 → 推送代码到 GitHub
2. GitHub Actions → 自动构建 Docker 镜像
3. 推送到镜像仓库（GitHub Container Registry 或阿里云）
4. 服务器 → 直接拉取镜像，无需构建

## 📋 第一步：选择镜像仓库

### 选项 1: GitHub Container Registry (ghcr.io) - 推荐

**优点**:
- ✅ 完全免费
- ✅ 与 GitHub 集成，无需额外配置
- ✅ 支持私有仓库

**缺点**:
- ⚠️ 国内访问可能较慢

### 选项 2: 阿里云容器镜像服务 - 推荐国内服务器

**优点**:
- ✅ 国内访问速度快
- ✅ 稳定可靠

**缺点**:
- ⚠️ 需要阿里云账户

## 🚀 第二步：配置 GitHub Actions

### 方式 A: 使用 GitHub Container Registry（最简单）

#### 1. 检查工作流文件

工作流文件已创建在 `.github/workflows/docker-build.yml`，无需修改。

#### 2. 推送代码触发构建

```bash
# 在本地
git add .
git commit -m "触发构建"
git push origin main
```

#### 3. 查看构建状态

1. 访问你的 GitHub 仓库
2. 点击 "Actions" 标签
3. 查看构建进度

构建完成后，镜像会自动推送到 `ghcr.io/your-username/ojo:latest`

### 方式 B: 使用阿里云容器镜像服务

#### 1. 创建镜像仓库

1. 登录 [阿里云容器镜像服务](https://cr.console.aliyun.com/)
2. 点击左侧 "命名空间" → "创建命名空间"
   - 命名空间名称：如 `ojo` 或 `your-username`
   - 类型：选择 "公开" 或 "私有"
3. 点击左侧 "镜像仓库" → "创建镜像仓库"
   - 命名空间：选择刚创建的
   - 仓库名称：如 `ojo-api`
   - 仓库类型：选择 "私有"
   - 代码源：选择 "不绑定"

#### 2. 获取访问凭证

1. 在镜像仓库页面，点击 "访问凭证"
2. 设置固定密码（用于 GitHub Actions）
3. 记录：
   - 用户名：通常是你的阿里云账号
   - 密码：你设置的固定密码
   - 命名空间：如 `your-namespace`
   - 仓库名：如 `ojo-api`

#### 3. 配置 GitHub Secrets

1. 访问你的 GitHub 仓库
2. 点击 "Settings"（设置）
3. 左侧菜单选择 "Secrets and variables" → "Actions"
4. 点击 "New repository secret" 添加以下 Secrets：

**Secret 1: ACR_USERNAME**
```
Name: ACR_USERNAME
Value: 你的阿里云用户名（通常是邮箱或手机号）
```

**Secret 2: ACR_PASSWORD**
```
Name: ACR_PASSWORD
Value: 你在镜像仓库设置的固定密码
```

**Secret 3: ACR_NAMESPACE**
```
Name: ACR_NAMESPACE
Value: 命名空间/仓库名（如：your-namespace/ojo-api）
```

#### 4. 启用工作流

工作流文件已创建在 `.github/workflows/docker-build-aliyun.yml`。

#### 5. 触发构建

```bash
# 在本地
git add .
git commit -m "触发构建"
git push origin main
```

#### 6. 查看构建状态

1. 访问 GitHub 仓库 → "Actions" 标签
2. 查看构建进度
3. 构建完成后，镜像会推送到：`registry.cn-hangzhou.aliyuncs.com/your-namespace/ojo-api:v9.0`

## 🖥️ 第三步：服务器端配置

### 1. 拉取最新代码

```bash
cd /opt/ojo
git pull origin main
```

### 2. 创建 .env 文件

#### 如果使用 GitHub Container Registry

```bash
cat > .env << 'EOF'
# 镜像仓库配置
DOCKER_REGISTRY=ghcr.io
DOCKER_NAMESPACE=your-github-username/ojo
DOCKER_IMAGE_TAG=latest

# GitHub Container Registry 需要登录
# 使用 Personal Access Token (PAT)
DOCKER_USERNAME=your-github-username
DOCKER_PASSWORD=ghp_your_personal_access_token

# 应用配置
JWT_SECRET_KEY=your-secret-key-here
OJO_ENCRYPTION_KEY=your-encryption-key-here
OJO_HOST=0.0.0.0
OJO_PORT=8000
EOF
```

**获取 GitHub Personal Access Token**:
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 点击 "Generate new token (classic)"
3. 勾选 `read:packages` 和 `write:packages`
4. 生成并复制 Token

#### 如果使用阿里云容器镜像服务

```bash
cat > .env << 'EOF'
# 镜像仓库配置
DOCKER_REGISTRY=registry.cn-hangzhou.aliyuncs.com
DOCKER_NAMESPACE=your-namespace/ojo-api
DOCKER_IMAGE_TAG=v9.0

# 登录凭证
DOCKER_USERNAME=your-aliyun-username
DOCKER_PASSWORD=your-aliyun-password

# 应用配置
JWT_SECRET_KEY=your-secret-key-here
OJO_ENCRYPTION_KEY=your-encryption-key-here
OJO_HOST=0.0.0.0
OJO_PORT=8000
EOF
```

### 3. 修改 docker-compose.yml（可选）

如果使用镜像仓库，可以修改 `docker-compose.yml` 直接使用镜像：

```yaml
services:
  ojo-api:
    # 使用镜像仓库的镜像
    image: ${DOCKER_REGISTRY}/${DOCKER_NAMESPACE}:${DOCKER_IMAGE_TAG:-v9.0}
    # 注释掉 build 部分
    # build:
    #   context: .
    #   dockerfile: Dockerfile
```

### 4. 首次部署

```bash
# 给脚本添加执行权限
chmod +x scripts/*.sh

# 从镜像仓库拉取并启动
./scripts/update-from-registry.sh
```

## 🔄 日常更新流程

### 开发流程

```bash
# 1. 本地开发
# 修改代码...

# 2. 提交并推送
git add .
git commit -m "更新功能"
git push origin main

# 3. GitHub Actions 自动构建（等待 5-10 分钟）
# 访问 GitHub → Actions 查看构建进度
```

### 服务器更新

```bash
# 在服务器上执行
cd /opt/ojo
./scripts/update-from-registry.sh
```

**就这么简单！** 脚本会自动：
- ✅ 从镜像仓库拉取最新镜像
- ✅ 备份数据
- ✅ 重启服务

## ✅ 验证配置

### 1. 检查 GitHub Actions 构建

```bash
# 访问 GitHub 仓库
# 点击 "Actions" 标签
# 查看最新的构建任务
# 应该显示 "绿色勾" 表示成功
```

### 2. 检查镜像是否推送

#### GitHub Container Registry

```bash
# 在服务器上测试拉取
docker pull ghcr.io/your-username/ojo:latest
```

#### 阿里云容器镜像服务

```bash
# 登录阿里云控制台
# 进入容器镜像服务 → 镜像仓库
# 查看是否有新推送的镜像
```

### 3. 检查服务器服务

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f ojo-api

# 健康检查
curl http://localhost:8000/api/health
```

## 🐛 常见问题

### 问题 1: GitHub Actions 构建失败

**检查**:
1. 查看 Actions 日志，找到错误信息
2. 检查 Secrets 是否正确配置
3. 检查 Dockerfile 是否有语法错误

**解决**:
```bash
# 在本地测试构建
docker build -t test .
```

### 问题 2: 无法拉取镜像

**检查**:
```bash
# 检查环境变量
cat .env | grep DOCKER

# 测试登录
docker login ${DOCKER_REGISTRY} -u ${DOCKER_USERNAME}

# 测试拉取
docker pull ${DOCKER_REGISTRY}/${DOCKER_NAMESPACE}:v9.0
```

### 问题 3: 镜像标签不对

**检查**:
- GitHub Container Registry: 使用 `latest` 或 `main-<sha>`
- 阿里云: 使用 `v9.0` 或 `latest`

**修改 .env**:
```bash
# 查看可用的标签
# GitHub: 访问 ghcr.io/your-username/ojo
# 阿里云: 在控制台查看镜像版本
```

## 📊 工作流状态监控

### 查看构建历史

1. 访问 GitHub 仓库
2. 点击 "Actions" 标签
3. 查看所有构建历史

### 设置通知

1. GitHub → Settings → Notifications
2. 启用 "Actions" 通知
3. 构建完成或失败时会收到邮件

## 🔐 安全建议

### 1. Secrets 安全

- ✅ 不要在代码中硬编码密码
- ✅ 定期轮换密码
- ✅ 使用最小权限原则

### 2. 镜像安全

- ✅ 使用私有仓库存储敏感镜像
- ✅ 定期更新基础镜像
- ✅ 扫描镜像漏洞（GitHub 自动扫描）

## 📚 相关文档

- [服务器快速指南](SERVER_QUICK_GUIDE.md) - 最简单的操作
- [服务器更新指南](SERVER_UPDATE_GUIDE.md) - 详细操作说明
- [GitHub Actions 配置](GITHUB_ACTIONS_SETUP.md) - 技术细节

---

## 🎉 完成！

配置完成后，你的工作流程将是：

1. **开发** → 修改代码
2. **推送** → `git push origin main`
3. **自动构建** → GitHub Actions 自动构建镜像
4. **服务器更新** → `./scripts/update-from-registry.sh`

**再也不用担心服务器卡住了！** 🚀

