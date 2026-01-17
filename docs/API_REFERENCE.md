# OJO API Reference

## 概述

OJO API 基于 FastAPI 构建，所有API返回JSON格式数据。

- **Base URL**: `http://localhost:8000/api`
- **认证方式**: JWT Bearer Token

---

## 认证

### 登录
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

**响应:**
```json
{
  "status": "success",
  "token": "eyJhbG...",
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin"
  }
}
```

### 检查认证状态
```http
GET /api/auth/check
Authorization: Bearer <token>
```

### 登出
```http
POST /api/auth/logout
Authorization: Bearer <token>
```

---

## 任务管理

### 创建任务
```http
POST /api/tasks
Authorization: Bearer <token>
Content-Type: application/json

{
  "problem_ids": ["1001", "1002", "1003"],
  "enable_fetch": true,
  "enable_generation": true,
  "enable_upload": true,
  "enable_solve": false,
  "source_adapter": "shsoj",
  "target_adapter": "shsoj"
}
```

**响应:**
```json
{
  "task_id": "task_20241222_123456",
  "status": "pending",
  "problem_ids": ["1001", "1002", "1003"]
}
```

### 获取任务列表
```http
GET /api/tasks
Authorization: Bearer <token>
```

**响应:**
```json
{
  "tasks": [
    {
      "task_id": "task_20241222_123456",
      "problem_id": "1001",
      "status": 1,
      "progress": 50,
      "stage": "Generating",
      "created_at": "2024-12-22T12:00:00Z"
    }
  ]
}
```

### 获取任务详情
```http
GET /api/tasks/{task_id}
Authorization: Bearer <token>
```

### 重试任务模块
```http
POST /api/v2/tasks/{task_id}/retry
Authorization: Bearer <token>
Content-Type: application/json

{
  "module": "gen"  // fetch, gen, upload, solve
}
```

### 取消任务
```http
DELETE /api/tasks/{task_id}
Authorization: Bearer <token>
```

---

## 题目管理

### 按标签获取题目
```http
GET /api/problems/by-tag?tag=模拟&limit=50
Authorization: Bearer <token>
```

**响应:**
```json
{
  "total": 25,
  "problems": [
    {
      "id": "1001",
      "title": "题目标题",
      "source": "shsoj"
    }
  ]
}
```

### 按范围获取题目
```http
GET /api/problems/by-range?start=1001&end=1010
Authorization: Bearer <token>
```

### 识别题目来源
```http
GET /api/problems/identify?url=https://oj.aicoders.cn/problem/1234
Authorization: Bearer <token>
```

**响应:**
```json
{
  "url": "https://oj.aicoders.cn/problem/1234",
  "source": "shsoj",
  "source_display": "SHSOJ",
  "parsed_id": "1234"
}
```

### 手动创建题目
```http
POST /api/problems/create-manual
Authorization: Bearer <token>
Content-Type: application/json

{
  "custom_id": "manual_001",
  "title": "题目标题",
  "description": "题目描述...",
  "input_format": "输入格式...",
  "output_format": "输出格式...",
  "samples": "样例输入输出...",
  "time_limit": 1000,
  "memory_limit": 256
}
```

---

## 题单管理

### 创建题单
```http
POST /api/training/create
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "题单标题",
  "description": "题单描述",
  "problem_ids": ["1001", "1002"]
}
```

### 添加题目到题单
```http
POST /api/training/{training_id}/add
Authorization: Bearer <token>
Content-Type: application/json

{
  "problem_ids": ["1003", "1004", "1005"]
}
```

### 获取题单列表
```http
GET /api/training/list
Authorization: Bearer <token>
```

### 删除题单
```http
DELETE /api/training/{training_id}
Authorization: Bearer <token>
```

---

## 清洗工具

### 预览清洗结果
```http
POST /api/wash/preview
Authorization: Bearer <token>
Content-Type: application/json

{
  "problem_ids": ["1001", "1002"],
  "fields": ["description", "input", "output"],
  "sensitive_words": ["上海市", "学校"]
}
```

**响应:**
```json
{
  "success": true,
  "message": "预览完成，共发现 5 处需要清洗",
  "results": [
    {
      "problem_id": "1001",
      "field": "description",
      "original": "上海市某中学...",
      "cleaned": "***某***...",
      "changes": 2
    }
  ],
  "total_changes": 5
}
```

### 执行清洗
```http
POST /api/wash/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "problem_ids": ["1001", "1002"],
  "fields": ["description", "input", "output"],
  "dry_run": false
}
```

### 获取默认敏感词
```http
GET /api/wash/sensitive-words
```

---

## 适配器管理

### 获取适配器列表
```http
GET /api/adapters
Authorization: Bearer <token>
```

**响应:**
```json
{
  "adapters": [
    {
      "name": "shsoj",
      "display_name": "SHSOJ",
      "capabilities": ["fetch_problem", "upload_data"],
      "has_config": true,
      "health": {
        "healthy": true,
        "status": "connected"
      }
    }
  ]
}
```

### 获取适配器配置
```http
GET /api/adapters/{adapter_name}/config
Authorization: Bearer <token>
```

### 保存适配器配置
```http
POST /api/adapters/{adapter_name}/config
Authorization: Bearer <token>
Content-Type: application/json

{
  "cookie": "session=xxx...",
  "base_url": "https://oj.example.com"
}
```

---

## 系统统计

### 获取系统状态
```http
GET /api/system/stats
Authorization: Bearer <token>
```

### 获取API使用统计
```http
GET /api/stats/usage
Authorization: Bearer <token>
```

---

## 管理员API

### 获取全局任务列表
```http
GET /api/admin/tasks/global
Authorization: Bearer <admin_token>
```

### 获取用户列表
```http
GET /api/admin/users
Authorization: Bearer <admin_token>
```

### 获取管理员系统统计
```http
GET /api/admin/system/stats
Authorization: Bearer <admin_token>
```

---

## WebSocket

### 连接
```javascript
const ws = new WebSocket('ws://localhost:8000/ws')
```

### 消息类型

**任务进度更新:**
```json
{
  "type": "task.progress",
  "task_id": "task_xxx",
  "problem_id": "1001",
  "progress": 50,
  "stage": "Generating"
}
```

**任务完成:**
```json
{
  "type": "task.completed",
  "task_id": "task_xxx"
}
```

**任务失败:**
```json
{
  "type": "task.failed",
  "task_id": "task_xxx",
  "error": "Error message"
}
```

**心跳:**
```json
// 发送
{"type": "ping", "timestamp": 1703232000000}

// 接收
{"type": "pong", "timestamp": 1703232000000}
```

---

## 错误码

| 状态码 | 说明 |
|-------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 限流

- 普通API: 100次/分钟
- LLM相关: 10次/分钟
- 登录: 5次/分钟

---

*最后更新: 2024-12-22*
