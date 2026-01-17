# LLM 配置模块改进报告

## 问题诊断

### 1. 任务适配器混乱问题
**现象**: 用户选择洛谷添加任务后，切换到批量添加时，之前的洛谷任务被认为是 aicoders。

**根因**: `pendingQueue` 中的任务在添加时使用当时的 `fetchAdapter` 状态，但批量添加对话框完成后会使用对话框内选择的适配器覆盖所有新任务。问题在于批量导入时没有为每个任务独立保存其适配器。

### 2. GEN 阶段错误使用硅基流动
**现象**: 用户选择 DeepSeek，但 GEN 阶段报错 "硅基流动API密钥未配置"。

**根因**: `pipeline.py` 中的 `create_generator()` 方法无条件传入 `self.llm_ocr`：
```python
def create_generator(self) -> GeneratorService:
    return GeneratorService(
        None, self.llm_gen, self.llm_ocr, ...  # llm_ocr 在这里被强制创建
    )
```
即使用户不需要 OCR 功能，`llm_ocr` 属性访问会触发 `create_for_task("ocr")`，进而创建 `SiliconFlowClient`。如果未配置硅基流动 API Key，就会抛出异常。

### 3. LLM 配置保存逻辑分散
**现象**: 配置修改后需要手动点击保存，测试需要单独点击，体验不佳。

**根因**: 前端配置页面是传统的"填写-保存"模式，没有实现自动保存和即时测试。

### 4. 架构混乱 - 代码分散多处
**现状**:
- `unified_config.py`: 存储配置定义（`AppConfig` dataclass）
- `factory.py`: LLM 客户端创建逻辑
- `task_config.py`: 任务级别的 LLM 配置
- `provider_registry.py`: 新增的 Provider 注册表
- `admin.py`, `server.py`: API 端点

**问题**:
- `create_for_task()` 使用废弃字段 `llm_provider_generation`
- Provider 定义和客户端创建逻辑分离，不够内聚
- 错误处理不一致（有的抛异常，有的返回 None）

---

## 改进方案

### 1. 任务适配器修复
- 每个待提交任务在添加时立即绑定当时的适配器
- 使用任务对象的 `adapter` 字段存储，不再依赖全局状态
- 批量添加对话框的适配器选择只影响新添加的任务

### 2. LLM 懒加载 + 可选 OCR
- `llm_ocr` 改为真正的懒加载，只在实际需要 OCR 时才创建
- `GeneratorService` 构造函数的 `ocr_client` 参数改为可选
- 如果 OCR 未配置但不需要使用，不报错

### 3. LLM 配置页面优化
- API Key 直接明文显示在输入框（管理员权限）
- 每次编辑字段失焦后自动保存
- 保存成功后自动触发测试
- 显示每个 Provider 的配置状态（已配置/未配置/测试结果）

### 4. 架构重构
**核心原则**: Provider Registry 作为唯一定义源

```
┌─────────────────────────────────────────────────────────────┐
│                    Provider Registry                         │
│  - 定义所有 Provider（id, name, api_key_field, etc.）        │
│  - 定义能力（generation, solution, ocr, summary）            │
│  - 前后端共享定义                                             │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   LLMFactory          ConfigService       Frontend
   (创建客户端)         (读写配置)          (动态渲染UI)
```

---

## 具体修改清单

### 后端
1. `pipeline.py`: `llm_ocr` 真正懒加载，`create_generator()` OCR 可选
2. `factory.py`: `create_for_task()` 改用 Provider Registry
3. `provider_registry.py`: 完善 Provider 定义
4. `admin.py`: 使用 Registry 动态返回配置
5. `server.py`: 测试接口增强

### 前端
1. `TasksPage.tsx`: 每个任务固定适配器和 LLM 选择
2. `LLMConfigPage.tsx`: 自动保存 + 即时测试 + 明文显示

### 测试
1. 更新单元测试覆盖新逻辑
2. 添加集成测试验证 Provider 配置流程

---

## 实施优先级

| 优先级 | 任务 | 影响 |
|-------|------|-----|
| P0 | 修复 GEN 阶段 OCR 强依赖 | 阻塞用户使用 |
| P0 | 修复任务适配器混乱 | 阻塞用户使用 |
| P1 | LLM 配置页面优化 | 体验改善 |
| P2 | 架构重构完善 | 可维护性 |

