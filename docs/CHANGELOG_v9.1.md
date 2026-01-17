# OJO v9.1 更新日志

## 功能优化与配置精简 (2024-12-25)

### ✅ 已完成的功能

#### 1. 联网搜索功能禁用
- **状态**: ✅ 已完成
- **说明**: 暂时禁用题解联网搜索功能，跳过此环节
- **修改文件**:
  - `src/services/solution_searcher.py` - `_search_from_web` 方法返回空列表

#### 2. LLM Provider 统一
- **状态**: ✅ 已完成
- **说明**: 用户在任务界面选择一个 LLM，数据生成和代码求解统一使用该 LLM
- **修改文件**:
  - `src/api/schemas.py` - `TaskCreateRequest` 添加 `llm_provider` 字段
  - `src/services/task_service.py` - 设置统一的 `llm_provider` 到生成和求解
  - `frontend/src/pages/TasksPage.tsx` - 添加统一 LLM 选择器

#### 3. 移除任务 Provider 分配
- **状态**: ✅ 已完成
- **说明**: LLM 配置页面移除管理员分配，由用户在任务界面决定
- **修改文件**:
  - `frontend/src/pages/LLMConfigPage.tsx` - 移除任务 Provider 分配 UI
  - `src/api/routes/admin.py` - 更新接口文档说明
  - `src/api/server.py` - 移除废弃字段返回

#### 4. 移除并发控制
- **状态**: ✅ 已完成
- **说明**: 并发控制移至「并发管理」页面统一配置
- **修改文件**:
  - `frontend/src/pages/LLMConfigPage.tsx` - 移除并发控制 UI
  - `frontend/src/pages/SettingsPage.tsx` - 移除并发控制，添加迁移提示
  - `src/api/server.py` - 移除 `llm_max_concurrency` 字段返回

#### 5. 配置字段清理
- **状态**: ✅ 已完成
- **说明**: 标记废弃字段，保留以兼容旧数据
- **修改文件**:
  - `src/services/unified_config.py` - 标记 `llm_provider_generation/solution` 为废弃
  - `src/services/llm/factory.py` - 添加废弃字段使用说明
  - `src/services/llm/task_config.py` - 添加废弃字段使用说明

#### 6. 单元测试完善
- **状态**: ✅ 已完成
- **说明**: 更新测试用例，确保所有功能正常
- **修改文件**:
  - `tests/unit/test_llm_config.py` - 更新测试用例

#### 7. 文档更新
- **状态**: ✅ 已完成
- **说明**: 更新 README 和 REFACTORING_PROPOSAL 文档
- **修改文件**:
  - `README.md` - 更新功能说明
  - `REFACTORING_PROPOSAL.md` - 更新完成状态

### 🔧 技术细节

#### 废弃字段处理策略
- **保留字段**: `llm_provider_generation` 和 `llm_provider_solution` 保留在 `AppConfig` 中
- **原因**: 兼容旧数据库配置，避免迁移问题
- **使用方式**: `task_service.py` 在任务执行时统一设置这两个字段为相同的 `llm_provider`

#### API 接口变更
- `/api/config` - 不再返回 `llm_provider_generation`、`llm_provider_solution`、`llm_max_concurrency`
- `/api/admin/llm-config` - 不再返回 Provider 分配相关字段
- `/api/concurrency/config` - 新增并发管理接口（独立页面）

#### 前端页面变更
- **LLM 配置页面**: 仅保留 API Key、模型名称、参数配置
- **任务页面**: 添加统一的 LLM 选择器
- **设置页面**: 移除 LLM provider 选择器，添加迁移提示
- **并发管理页面**: 独立的并发控制配置

### 📝 迁移指南

#### 对于用户
1. **LLM 选择**: 现在在创建任务时选择，而不是在配置页面
2. **并发控制**: 移至「并发管理」页面统一配置
3. **旧配置**: 自动兼容，无需手动迁移

#### 对于开发者
1. **API 调用**: 使用 `llm_provider` 字段而不是 `llm_provider_generation/solution`
2. **配置读取**: 废弃字段仍可读取，但不应写入新值
3. **测试**: 运行 `pytest tests/unit/test_llm_config.py` 验证功能

### 🐛 已知问题
无

### 🔮 未来计划
- 考虑完全移除废弃字段（需要数据迁移）
- 优化 LLM 选择器的用户体验
- 添加更多并发控制预设

---

**版本**: v9.1.0  
**发布日期**: 2024-12-25  
**兼容性**: 向后兼容 v9.0.0

