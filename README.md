<div align="center">

# 🔨 OJForge - 智能OJ题目处理工坊

> **AI驱动的Online Judge题目全流程自动化平台**  
> 让题目迁移、数据生成、批量上传变得简单高效

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61dafb.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[功能特性](#-核心功能) • [快速开始](#-快速开始) • [使用指南](#-使用指南) • [API文档](#-api文档) • [部署指南](#-部署指南)

</div>

---

## ✨ 项目简介

**OJForge** (原名 OJO) 是一个强大的OJ题目批处理平台，通过AI大语言模型自动化完成题目的全生命周期管理。无论你是需要批量迁移题目、自动生成测试数据，还是构建自己的OJ平台，OJForge都能帮你显著提升效率。

### 🎯 核心价值

- **⚡ 全流程自动化** - 从题目拉取到数据生成再到上传验证，一键完成
- **🤖 AI智能生成** - 使用DeepSeek、Gemini等LLM自动生成高质量测试数据和题解
- **🔌 多平台支持** - 支持7+主流OJ平台，轻松实现题目迁移
- **🎨 现代化界面** - 美观的React前端，实时任务进度展示
- **👥 多用户协作** - 完善的用户隔离和权限管理
- **📊 实时监控** - WebSocket实时推送任务状态，清晰了解每个任务进展

---

## 🌟 核心功能

### 📥 题目拉取（Fetch）
从多个OJ平台智能拉取题目，支持：
- **平台支持**：SHSOJ、Codeforces、AtCoder、洛谷(Luogu)、Aicoders、HydroOJ
- **批量获取**：支持按标签、按ID范围批量拉取
- **智能解析**：自动识别题目ID、URL，支持多种输入格式
- **题面粘贴**：直接粘贴题面内容，系统自动解析

### ⚙️ 数据生成（Generate）
使用AI大语言模型生成测试数据：
- **多种LLM支持**：DeepSeek、Gemini、OpenAI、SiliconFlow
- **智能生成**：根据题目描述自动生成gen.py测试数据生成脚本
- **灵活配置**：可自定义温度、top_p等参数，控制生成质量
- **批量处理**：支持高并发生成，大幅提升效率

### 📤 数据上传（Upload）
将生成的测试数据上传到目标OJ平台：
- **多平台适配**：支持SHSOJ、HydroOJ等平台的数据上传
- **智能格式转换**：自动适配不同OJ的数据格式要求
- **配置自动更新**：上传后自动更新题目配置信息
- **上传验证**：上传完成后自动验证数据完整性

### 🔍 代码求解（Solve）
AI自动生成题解并验证：
- **智能求解**：使用LLM分析题目并生成解题代码
- **自动提交**：生成代码后自动提交到OJ平台验证
- **结果追踪**：实时追踪判题状态，获取判题结果
- **多语言支持**：支持C++、Python、Java等多种编程语言

### 📋 题单管理（Training）
管理员专属功能，批量管理题目集合：
- **题单创建**：创建题单，批量添加题目
- **权限管理**：支持公开、私有、密码保护等多种权限设置
- **智能排序**：支持按难度、标签等多种方式排序
- **批量操作**：一键添加/删除题目，快速构建题单

### 🔧 其他功能

- **文本清洗（Wash）**：自动清洗敏感信息，保护隐私
- **适配器配置**：灵活的OJ平台适配器配置系统
- **并发控制**：可自定义LLM和OJ的并发数量
- **实时日志**：每个任务都有详细的执行日志，方便调试
- **工作区管理**：每个任务都有独立的工作区，支持下载和清理

---

## 🚀 快速开始

### 前置要求

- **Python**: 3.8 或更高版本
- **Node.js**: 18 或更高版本（用于前端开发）
- **Docker** (可选): 用于容器化部署
- **LLM API Key**: 至少需要一个LLM提供商的API密钥（DeepSeek/Gemini/OpenAI）

### 方式一：Docker部署（推荐）⭐

Docker部署是最简单快速的方式，推荐用于生产环境。

#### 1. 克隆项目

```bash
git clone <repository-url>
cd ojo
```

#### 2. 配置环境变量

```bash
# 复制配置示例文件
cp .env.example .env

# 编辑 .env 文件，设置必要的配置
# 至少需要设置LLM API密钥
```

#### 3. 启动服务

```bash
# 使用Docker Compose一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 4. 访问界面

打开浏览器访问 `http://localhost:8000`

**默认账号**：
- 用户名：`admin`
- 密码：`admin123`

> ⚠️ **重要提示**：首次登录后请立即修改管理员密码！

### 方式二：手动部署

适合本地开发和测试环境。

#### 1. 克隆并进入项目目录

```bash
git clone <repository-url>
cd ojo
```

#### 2. 创建Python虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
pip install -r requirements_api.txt
```

#### 4. 配置数据库

```bash
# 数据库会在首次运行时自动创建
# 确保有写入权限
```

#### 5. 启动后端服务

```bash
# 开发模式（自动重载）
cd src
python api_server.py

# 或使用uvicorn直接启动
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

#### 6. 启动前端服务（可选）

如果需要修改前端，需要单独启动：

```bash
cd frontend
npm install
npm run dev
```

### 方式三：GitHub Actions自动构建（生产推荐）🔥

适合需要频繁更新的生产环境。

#### 1. 配置GitHub Actions

详细步骤请参考 [docs/GITHUB_ACTIONS_SETUP.md](docs/GITHUB_ACTIONS_SETUP.md)

#### 2. 推送代码自动构建

```bash
git push origin main
# GitHub Actions会自动构建Docker镜像并推送到镜像仓库
```

#### 3. 在服务器上拉取更新

```bash
cd /opt/ojo
chmod +x scripts/update-from-registry.sh
./scripts/update-from-registry.sh
```

**优势**：
- ✅ 服务器零构建，避免卡顿
- ✅ 自动构建，无需手动操作
- ✅ 快速更新，几秒钟完成

---

## 📖 使用指南

### 基础使用流程

#### 1. 配置LLM API密钥

首次使用前，需要在Web界面配置LLM API密钥：

1. 登录系统
2. 进入「LLM配置」页面
3. 填入你的API密钥（DeepSeek/Gemini/OpenAI等）
4. 保存配置

> 💡 **提示**：不同的任务可以选择不同的LLM。数据生成和代码求解可以分别使用不同的模型。

#### 2. 配置OJ适配器

在「适配器」页面配置各个OJ平台的账号信息：

- **SHSOJ**：需要用户名和密码
- **HydroOJ**：需要Cookie或Token
- **Codeforces/AtCoder/Luogu**：通常无需配置（公开平台）

#### 3. 创建任务

在「任务中心」页面创建新任务：

**方式一：手动输入**
```
1001
1002
2000-2005
https://oj.aicoders.cn/problem/2772
```

**方式二：批量添加**
- 按标签获取（SHSOJ）
- 按ID范围获取
- 粘贴多个URL

**方式三：粘贴题面**
直接粘贴题目内容，系统自动解析

#### 4. 选择处理模块

根据需要选择处理模块：

| 模块 | 说明 | 使用场景 |
|------|------|----------|
| 📥 **拉取** | 从源OJ获取题面 | 题目迁移、备份 |
| ⚙️ **生成** | LLM生成测试数据 | 新建题目、补充数据 |
| 📤 **上传** | 上传到目标OJ | 题目迁移、部署 |
| 🔍 **求解** | 生成题解并验证 | 验证题目、生成题解 |

**预设模式**：
- **完整流程**：拉取 → 生成 → 上传 → 求解（适合题目迁移）
- **只生成**：仅生成测试数据（适合补充已有题目）
- **只上传**：仅上传已生成的数据（适合重新上传）

#### 5. 执行任务

- 选择LLM提供商和模型
- 配置生成参数（可选）
- 点击「开始处理」
- 实时查看任务进度和日志

#### 6. 查看结果

- **任务列表**：查看所有任务的状态
- **任务详情**：查看详细日志和执行结果
- **下载工作区**：下载题目文件和数据
- **复制题目ID**：快速获取标准化题目ID

### 高级功能

#### 并发控制

在「并发控制」页面可以配置：

- **LLM并发数**：控制同时调用LLM API的数量（默认40）
- **OJ并发数**：控制同时访问OJ平台的数量（默认1，避免被封）

> 💡 **建议**：根据API限制和服务器性能调整。LLM并发可以较高，但OJ并发建议保持较低。

#### 题单管理（管理员）

管理员可以创建和管理题单：

1. 进入「题单管理」页面
2. 创建新题单，设置名称、权限等
3. 从任务结果中添加题目到题单
4. 配置题单的排序和分类

#### 文本清洗

「文本清洗」功能可以自动清洗题目中的敏感信息：

- 自动识别和替换敏感词汇
- 保护隐私信息
- 支持自定义清洗规则

---

## 🛠️ 技术架构

### 技术栈

**后端**
- **框架**：FastAPI（高性能异步Web框架）
- **数据库**：SQLite（轻量级，适合中小规模使用）
- **认证**：JWT（JSON Web Token）
- **实时通信**：WebSocket
- **并发处理**：asyncio + ThreadPoolExecutor

**前端**
- **框架**：React 18 + TypeScript
- **UI库**：Ant Design
- **状态管理**：React Hooks
- **实时通信**：WebSocket Client

**AI/LLM**
- **DeepSeek**：数据生成和代码求解
- **Gemini**：OCR、总结和推理
- **OpenAI**：兼容OpenAI API的模型
- **SiliconFlow**：OCR和多模态处理

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    表现层 (Presentation)                      │
│  React前端 + FastAPI REST API + WebSocket                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                     服务层 (Service Layer)                    │
│  AuthService | TaskService | SecretService | ConfigService   │
│                      PipelineRunner                          │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                  基础设施层 (Infrastructure)                  │
│  Database | LLMClient | OJAdapter | EventBus                 │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

- **适配器系统**：统一的OJ平台适配接口，支持7+平台
- **Pipeline引擎**：可配置的任务处理流水线
- **用户隔离**：多用户支持，独立配置和数据
- **加密服务**：敏感信息加密存储
- **事件总线**：解耦的服务间通信

---

## 📚 API文档

OJForge提供完整的REST API，支持程序化集成。

### 认证

所有API（除登录外）都需要Bearer Token认证：

```http
Authorization: Bearer <your-jwt-token>
```

### 主要接口

#### 认证相关

```http
POST /api/auth/login          # 用户登录
GET  /api/auth/check          # 检查认证状态
POST /api/auth/logout         # 用户登出
```

#### 任务管理

```http
POST /api/tasks               # 创建任务
GET  /api/tasks               # 查询任务列表
GET  /api/tasks/{task_id}     # 获取任务详情
DELETE /api/tasks/{task_id}   # 删除任务
POST /api/tasks/{task_id}/retry  # 重试任务
```

#### 适配器

```http
GET  /api/adapters            # 获取适配器列表
GET  /api/adapters/{name}     # 获取适配器详情
PUT  /api/adapters/{name}     # 更新适配器配置
```

#### 配置管理

```http
GET  /api/config              # 获取用户配置
PUT  /api/config              # 更新用户配置
GET  /api/config/llm          # 获取LLM配置
PUT  /api/config/llm          # 更新LLM配置
```

### WebSocket

实时通信通过WebSocket实现：

```
ws://localhost:8000/ws
```

消息格式：
```json
{
  "type": "task_update",
  "task_id": "xxx",
  "status": "running",
  "progress": 50
}
```

### 完整API文档

启动服务后，访问以下地址查看交互式API文档：

- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`

更多API详情请参考 [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

---

## 🐳 部署指南

### Docker部署

#### 标准部署

```bash
# 1. 克隆项目
git clone <repository-url>
cd ojo

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 停止服务
docker-compose down
```

#### 安全构建（防止服务器卡住）

```bash
# 使用安全构建脚本（带资源限制）
chmod +x scripts/build-docker-safe.sh
./scripts/build-docker-safe.sh
```

#### 自定义镜像构建

```bash
# 构建镜像
docker build -t ojforge:latest .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/workspace:/app/workspace \
  --name ojforge \
  ojforge:latest
```

### 生产环境部署

#### 使用Nginx反向代理

参考 [config/nginx.conf](config/nginx.conf) 配置Nginx：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 使用systemd管理服务

创建 `/etc/systemd/system/ojforge.service`：

```ini
[Unit]
Description=OJForge API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ojo
Environment="PATH=/opt/ojo/venv/bin"
ExecStart=/opt/ojo/venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl enable ojforge
sudo systemctl start ojforge
sudo systemctl status ojforge
```

### 备份和恢复

#### 数据备份

```bash
# 使用备份脚本
chmod +x scripts/backup-data.sh
./scripts/backup-data.sh
```

#### 数据恢复

```bash
# 使用恢复脚本
chmod +x scripts/restore-data.sh
./scripts/restore-data.sh <backup-file>
```

更多部署详情请参考：
- [docs/DEPLOYMENT_LINUX.md](docs/DEPLOYMENT_LINUX.md) - Linux部署指南
- [docs/DOCKER_BUILD.md](docs/DOCKER_BUILD.md) - Docker构建指南
- [docs/SERVER_UPDATE_GUIDE.md](docs/SERVER_UPDATE_GUIDE.md) - 服务器更新指南

---

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OJO_HOST` | API服务器监听地址 | `0.0.0.0` |
| `OJO_PORT` | API服务器监听端口 | `8000` |
| `OJO_DEBUG` | 调试模式 | `false` |
| `OJO_WORKSPACE` | 工作区目录 | `workspace` (Docker: `/app/workspace`) |
| `OJO_LOGS_DIR` | 日志目录 | `logs` (Docker: `/app/logs`) |
| `OJO_DB_PATH` | 数据库路径 | `ojo.db` (Docker: `/app/data/ojo.db`) |
| `JWT_SECRET_KEY` | JWT密钥（自动生成） | - |
| `OJO_ENCRYPTION_KEY` | 加密密钥（自动生成） | - |

### LLM配置

在Web界面的「LLM配置」中配置：

- **DeepSeek API Key**：用于数据生成和代码求解
- **Gemini API Key**：用于OCR、总结和推理
- **OpenAI API Key**：支持GPT-4等模型
- **SiliconFlow API Key**：用于OCR和多模态处理

### OJ适配器配置

每个用户可以为不同的OJ平台配置独立的账号信息：

- **SHSOJ**：base_url, username, password
- **HydroOJ**：base_url, domain, sid, sid_sig
- **Aicoders**：base_url
- 其他平台：base_url（如需要）

配置会自动加密存储，保护账号安全。

### 并发控制配置

- **LLM并发数**：同时调用LLM API的数量（建议：20-40）
- **OJ并发数**：同时访问OJ平台的数量（建议：1-3，避免被封）
- **请求超时**：LLM请求超时时间（分钟）
- **代码执行超时**：代码执行超时时间（分钟）

---

## 🔍 常见问题

### Q: 如何重置管理员密码？

A: 使用提供的脚本：

```bash
python scripts/reset-admin-password.py
```

### Q: 支持哪些OJ平台？

A: 目前支持：
- SHSOJ
- HydroOJ
- Codeforces
- AtCoder
- 洛谷(Luogu)
- Aicoders
- Manual（手动题面）

更多平台正在开发中。

### Q: 如何添加新的OJ平台适配器？

A: 参考现有适配器的实现：

1. 在 `src/services/oj/adapters/` 下创建新目录
2. 实现 `OJAdapter` 接口
3. 在 `registry.py` 中注册适配器

详细文档请参考适配器开发指南。

### Q: 任务执行失败怎么办？

A: 
1. 查看任务详情页面的日志
2. 检查LLM API配置是否正确
3. 检查OJ平台账号是否有权限
4. 尝试重试任务（支持自动重试）

### Q: 如何提高生成质量？

A: 
1. 调整LLM的温度参数（较低的温度更稳定）
2. 选择更强的模型（如deepseek-reasoner）
3. 提供更详细的题目描述
4. 使用多次生成取最佳结果

### Q: 数据存储在哪里？

A: 
- **数据库**：`ojo.db`（用户、任务、配置等）
- **工作区**：`workspace/`（题目文件、生成的数据）
- **日志**：`logs/`（运行日志）

Docker部署时，这些目录映射到宿主机的 `data/` 目录。

### Q: 如何迁移到新服务器？

A: 
1. 备份 `ojo.db` 和 `workspace/` 目录
2. 在新服务器上部署OJForge
3. 恢复数据库和工作区文件
4. 更新OJ适配器配置

更多问题请查看 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)

---



查看完整更新日志：[docs/CHANGELOG_v9.1.md](docs/CHANGELOG_v9.1.md)

---

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. **Fork** 本仓库
2. **创建** 功能分支 (`git checkout -b feature/AmazingFeature`)
3. **提交** 更改 (`git commit -m 'Add some AmazingFeature'`)
4. **推送** 到分支 (`git push origin feature/AmazingFeature`)
5. **开启** Pull Request

### 开发规范

- 代码风格：遵循PEP 8（Python）和ESLint（TypeScript）
- 提交信息：使用清晰的提交信息，参考 [Conventional Commits](https://www.conventionalcommits.org/)
- 测试：新增功能需要添加相应的测试
- 文档：更新相关文档

### 报告问题

如果发现bug或有功能建议，请在 [Issues](https://github.com/your-repo/ojo/issues) 中提交。

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 许可证。

---

## 🙏 致谢

感谢以下项目和社区的支持：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的Python Web框架
- [React](https://reactjs.org/) - 用于构建用户界面的JavaScript库
- [Ant Design](https://ant.design/) - 企业级UI设计语言
- [DeepSeek](https://www.deepseek.com/) - 强大的AI大语言模型
- [Gemini](https://deepmind.google/technologies/gemini/) - Google的多模态AI模型





---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个Star！⭐**

Made with ❤️ by OJForge Team

</div>
