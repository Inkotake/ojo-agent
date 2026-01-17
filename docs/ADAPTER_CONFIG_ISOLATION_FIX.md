# 适配器配置隔离问题修复

## 问题

**根本原因**：配置存储与读取位置不匹配
- 配置保存：`user_adapter_configs` 表（用户级别）
- 配置读取：`cfg.adapter_configs`（系统级别）
- **结果**：读取不到用户配置 → 报错"账号未配置"

**并发问题**：
- 适配器实例全局共享，配置缓存在实例中 → 多用户配置互相覆盖
- `TaskService` 覆盖全局配置 → 并发时配置混乱

## 修复方案

**核心原则**：
1. 适配器无状态：不在共享实例中缓存用户配置
2. 动态读取：每次从 `context.user_id` → 数据库读取用户配置
3. 严格隔离：用户未配置则报错，不回退系统配置

## 修改清单

### 1. SHSOJAdapter (`src/services/oj/adapters/shsoj/adapter.py`)

**新增方法**：
- `_get_user_config(user_id)` - 从数据库读取用户配置
- `_get_user_id_from_context()` - 从 context 获取 user_id

**修改方法**：
- `_ensure_config()` - 改为从用户配置读取，移除配置缓存

```python
def _get_user_config(self, user_id: int) -> Dict[str, Any]:
    """从数据库读取用户配置（严格隔离）"""
    db = get_database()
    config = db.get_user_adapter_config(user_id, 'shsoj')
    if not config or not config.get('username') or not config.get('password'):
        raise RuntimeError("SHSOJ账号未配置，请在GUI中填写用户名和密码后再试")
    return config

def _ensure_config(self):
    """从用户配置读取，不缓存"""
    user_id = self._get_user_id_from_context()
    user_config = self._get_user_config(user_id)
    # 应用配置，但不设置 _config_loaded = True
```

### 2. HydroOJAdapter (`src/services/oj/adapters/hydrooj/adapter.py`)

**同 SHSOJAdapter 改造**：
- 新增 `_get_user_config(user_id)` 和 `_get_user_id_from_context()`
- 修改 `_ensure_config()` 从用户配置读取

### 3. TaskService (`src/services/task_service.py`)

**删除代码**（第 382-384 行）：
```python
# 删除：不再覆盖全局配置
user_adapter_configs = self.db.get_all_user_adapter_configs(user_id)
if user_adapter_configs:
    cfg_mgr.cfg.adapter_configs = user_adapter_configs
```

### 4. Pipeline (`src/services/pipeline.py`)

**修改 `_initialize_adapters()`**：
```python
adapter.initialize({
    'config_manager': self.cfg_mgr,
    'user_id': self.user_id  # 传递 user_id
})
```

**修改 `_get_upload_adapter()` 和 `_get_submit_adapter()`**：
```python
def _get_upload_adapter(self):
    adapter = self.registry.get_adapter(name)
    if adapter:
        # 每次使用时更新 user_id（适配器是共享的）
        adapter._context = adapter._context or {}
        adapter._context['user_id'] = self.user_id
    return adapter
```

**修改 URL 构建**（第 922-928 行）：
```python
# 从数据库读取用户配置
from core.database import get_database
db = get_database()
adapter_config = db.get_user_adapter_config(self.user_id, upload_adapter.name)
base_url = adapter_config.get("base_url", "")
domain = adapter_config.get("domain", "")
```

## 测试验证

1. ✅ 用户A配置 SHSOJ 后上传 → 使用用户A的配置
2. ✅ 用户B配置不同的 HydroOJ 后上传 → 使用用户B的配置
3. ✅ 用户A和B并发上传 → 各自配置互不干扰
4. ✅ 用户未配置 → 明确报错"账号未配置"
5. ✅ 上传后打开链接 → 指向正确的OJ和题目

## 注意事项

- **LLM 配置**：保持系统级别（API Key 全局共享，用户只选择 provider）
- **不向后兼容**：不再支持系统级适配器配置（安全隔离需求）
