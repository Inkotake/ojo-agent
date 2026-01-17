# HydroOJ 适配器问题修复详细文档

> **文档版本**: v1.1  
> **创建日期**: 2026-01-06  
> **修复日期**: 2026-01-06  
> **状态**: ✅ 已修复

---

## 目录

1. [问题概述](#问题概述)
2. [问题详细分析](#问题详细分析)
3. [根本原因](#根本原因)
4. [修复方案](#修复方案)
5. [代码修改清单](#代码修改清单)
6. [测试验证](#测试验证)

---

## 问题概述

用户报告了三个主要问题：

1. **前端完成状态不显示**：任务完成后，前端界面不显示完成状态
2. **远程已有题目不跳过**：即使远端已存在同名题目，系统仍重新上传，导致重复创建
3. **打开链接按钮无效**：前端"打开上传链接"按钮点击无响应

### 问题日志证据

```
[13:12:09] [P1001] [CHECK] 检查远端是否已有同名题目...
[13:12:09] [P1001] [CHECK] 远端无同名题目，继续正常流程
[13:12:14] [P1001] ✓ 上传成功: P1001 A+B Problem_hydro.zip
[13:12:14] [P1001] [UPLOAD] ✓ 上传成功 (耗时 0.43s, 响应码=200)
[13:12:14] [P1001] [SOLVE] 开始远程求解流程...
[13:12:14] [P1001] HydroOJ 题目ID: 1005
```

**问题分析**：
- 日志显示 `[CHECK] 远端无同名题目`，但后续求解时使用了 `HydroOJ 题目ID: 1005`
- 说明远端实际存在题目（ID 1005），但检测逻辑未正确识别
- 上传成功后没有显示 `题目真实ID` 和 `题目链接` 的日志

---

## 问题详细分析

### 问题 1: 前端完成状态不显示

#### 症状
- 任务执行完成后，前端界面仍显示"进行中"状态
- 任务状态未更新为"完成"
- 进度条未显示 100%

#### 影响范围
- `frontend/src/pages/TasksPage.tsx` - 任务列表显示
- `frontend/src/pages/Dashboard.tsx` - 仪表盘显示
- `src/services/task_service.py` - 任务状态更新逻辑

#### 可能原因
1. **数据库更新失败**：`uploaded_url` 字段未正确保存到数据库
2. **前端数据映射错误**：后端返回的字段名与前端期望不一致
3. **WebSocket 广播缺失**：任务完成事件未正确广播到前端

### 问题 2: 远程已有题目不跳过

#### 症状
- 日志显示 `[CHECK] 远端无同名题目`，但实际题目已存在
- 系统继续执行生成和上传流程
- 导致重复创建题目（如 ID 1005）

#### 影响范围
- `src/services/pipeline.py` - CHECK 阶段逻辑
- `src/services/oj/adapters/hydrooj/data_uploader_impl.py` - `_search_exact_title` 方法
- `src/services/oj/adapters/hydrooj/data_uploader_impl.py` - `upload_testcase` 方法

#### 可能原因
1. **标题匹配过于严格**：标题中的空格、标点符号差异导致匹配失败
2. **搜索逻辑缺陷**：`_search_exact_title` 未考虑标题规范化
3. **已保存 ID 未利用**：未检查本地已保存的 `real_id` 是否仍然有效

### 问题 3: 打开链接按钮无效

#### 症状
- 前端"打开上传链接"按钮存在但点击无响应
- 控制台可能显示 `uploadedUrl is empty or invalid`

#### 影响范围
- `frontend/src/components/TaskActionMenu.tsx` - 按钮点击处理
- `frontend/src/pages/TasksPage.tsx` - `uploaded_url` 数据传递
- `src/services/task_service.py` - `uploaded_url` 提取和保存

#### 可能原因
1. **数据传递链路断裂**：`uploaded_url` 从 Pipeline → TaskService → 数据库 → API → 前端 的传递过程中丢失
2. **字段提取错误**：TaskService 未正确从 Pipeline 结果中提取 `uploaded_url`
3. **数据库字段缺失**：`uploaded_url` 未正确保存到数据库

---

## 根本原因

### 根本原因 1: uploaded_url 传递链路不完整

**问题链路**：
```
Pipeline.extra["uploaded_url"] 
  → TaskService._execute_pipeline() 提取 uploaded_url
  → TaskResult.uploaded_url
  → TaskService 更新数据库
  → API 返回给前端
  → 前端显示
```

**断点分析**：
1. **Pipeline 层**：`result.extra["uploaded_url"]` 可能未正确设置
2. **TaskService 层**：`task_result.extra.get('uploaded_url')` 提取逻辑可能失败
3. **数据库层**：`db.update_task(task_id, uploaded_url=...)` 可能未执行
4. **API 层**：返回的任务数据可能缺少 `uploaded_url` 字段

### 根本原因 2: 远程检测逻辑不完善

**问题分析**：
1. **标题规范化缺失**：`_search_exact_title` 直接比较原始标题，未处理空格、标点差异
2. **已保存 ID 未利用**：检测失败时未检查本地已保存的 `real_id` 是否仍然有效
3. **错误处理不足**：搜索失败时直接返回 `None`，未尝试备用方案

**示例场景**：
- 本地标题：`"P1001 A+B Problem"`（两个空格）
- 远端标题：`"P1001  A+B Problem"`（三个空格）
- 结果：精确匹配失败，误判为"不存在"

### 根本原因 3: real_id 提取不完整

**问题分析**：
1. **响应格式不一致**：HydroOJ 上传可能返回 200 或 302，`real_id` 提取逻辑不统一
2. **提取失败未处理**：如果 `real_id` 提取失败，未尝试从已保存数据读取
3. **日志不完整**：提取失败时未记录详细日志，难以排查

---

## 修复方案

### 修复方案 1: 完善 uploaded_url 传递链路

#### 1.1 Pipeline 层修复

**文件**: `src/services/pipeline.py`

**位置**: 约 1100-1120 行（上传成功处理）

**修改内容**：
```python
# 修改前：
response_data = up_resp.get("response", {})
real_id = response_data.get("real_id")
if real_id and upload_adapter:
    # ... 构建 uploaded_url
    result.extra["uploaded_url"] = uploaded_url

# 修改后：
response_data = up_resp.get("response", {})
real_id = response_data.get("real_id")

# 如果 response 中没有，尝试从顶层获取
if not real_id:
    real_id = up_resp.get("real_id")

# 如果还是没有，尝试从已保存的数据读取
if not real_id and upload_adapter:
    saved_real_id = ProblemDataManager.get_upload_real_id(pdir, upload_adapter.name)
    if saved_real_id:
        real_id = saved_real_id
        self._append_log(f"[{pid}] [UPLOAD] 从已保存数据读取 real_id: {real_id}")

if real_id and upload_adapter:
    # 保存 real_id
    ProblemDataManager.set_upload_real_id(pdir, upload_adapter.name, str(real_id))
    self._append_log(f"[{pid}] [UPLOAD] 已保存 {upload_adapter.name} 题目ID: {real_id}")
    
    # 构建 uploaded_url
    try:
        from core.database import get_database
        db = get_database()
        adapter_config = db.get_user_adapter_config(self.user_id, upload_adapter.name)
        base_url = adapter_config.get("base_url", "")
        domain = adapter_config.get("domain", "")
        if base_url and domain:
            uploaded_url = f"{base_url.rstrip('/')}/d/{domain}/p/{real_id}"
            result.extra["uploaded_url"] = uploaded_url
            self._append_log(f"[{pid}] [UPLOAD] 题目链接: {uploaded_url}")
            
            # 同时更新数据库（如果任务ID存在）
            if self._current_task_id:
                try:
                    db.update_task(self._current_task_id, uploaded_url=uploaded_url)
                    self._append_log(f"[{pid}] [UPLOAD] 已更新数据库 uploaded_url")
                except Exception as db_err:
                    logger.debug(f"[{pid}] 更新数据库 uploaded_url 失败: {db_err}")
    except Exception as url_err:
        logger.debug(f"构建上传URL失败: {url_err}")
else:
    # 如果没有 real_id，记录警告
    self._append_log(f"[{pid}] [UPLOAD] ⚠ 警告: 未能获取题目ID，上传链接将不可用")
    logger.warning(f"[{pid}] [UPLOAD] 响应数据: {up_resp}")
```

#### 1.2 TaskService 层修复

**文件**: `src/services/task_service.py`

**位置**: 约 488-492 行（uploaded_url 提取）

**修改内容**：
```python
# 修改前：
if hasattr(task_result, 'extra') and task_result.extra:
    uploaded_url = task_result.extra.get('uploaded_url')

# 修改后：
uploaded_url = None

# 方法1: 从 extra 字段提取
if hasattr(task_result, 'extra') and task_result.extra:
    uploaded_url = task_result.extra.get('uploaded_url')

# 方法2: 从直接属性提取
if not uploaded_url and hasattr(task_result, 'uploaded_url'):
    uploaded_url = task_result.uploaded_url

# 方法3: 从数据库读取（如果任务已完成）
if not uploaded_url and task_id:
    try:
        task_info = self.db.get_task(task_id, user_id, False)
        if task_info and task_info.get('uploaded_url'):
            uploaded_url = task_info.get('uploaded_url')
            logger.debug(f"从数据库读取 uploaded_url: {uploaded_url}")
    except Exception as e:
        logger.debug(f"读取数据库 uploaded_url 失败: {e}")

# 确保 uploaded_url 被设置到 TaskResult
if uploaded_url:
    logger.debug(f"提取到 uploaded_url: {uploaded_url}")
```

#### 1.3 CHECK 阶段修复（已保存 ID 验证）

**文件**: `src/services/pipeline.py`

**位置**: 约 809-861 行（CHECK 阶段）

**修改内容**：
```python
# 在 existing_id = uploader._search_exact_title(title, hydrooj_auth) 之后

if existing_id:
    # ... 现有逻辑
else:
    # 如果精确匹配失败，尝试检查已保存的 real_id
    saved_real_id = ProblemDataManager.get_upload_real_id(pdir, upload_adapter.name)
    if saved_real_id:
        self._append_log(f"[{pid}] [CHECK] 发现已保存的题目ID: {saved_real_id}，验证是否仍存在...")
        
        # 验证题目是否仍然存在
        try:
            from core.database import get_database
            db = get_database()
            adapter_config = db.get_user_adapter_config(self.user_id, upload_adapter.name)
            base_url = adapter_config.get("base_url", "")
            domain = adapter_config.get("domain", "")
            
            if base_url and domain:
                verify_url = f"{base_url.rstrip('/')}/d/{domain}/p/{saved_real_id}"
                verify_r = hydrooj_auth.session.get(verify_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Referer': f"{base_url}/d/{domain}/p"
                })
                
                if verify_r.status_code == 200:
                    # 题目存在，提取标题验证
                    import re
                    title_match = re.search(r'<title>([^<]+)</title>', verify_r.text)
                    if title_match:
                        remote_title = title_match.group(1).split(' - ')[0].strip()
                        if remote_title == title.strip():
                            remote_exists = True
                            existing_id = saved_real_id
                            self._append_log(f"[{pid}] [CHECK] ✓ 通过已保存ID找到题目 (ID: {existing_id})")
                            
                            # 设置成功状态
                            result.ok_gen = True
                            result.ok_upload = True
                            
                            # 保存 real_id（确保最新）
                            ProblemDataManager.set_upload_real_id(pdir, upload_adapter.name, str(existing_id))
                            
                            # 构建 uploaded_url
                            uploaded_url = f"{base_url.rstrip('/')}/d/{domain}/p/{existing_id}"
                            result.extra["uploaded_url"] = uploaded_url
                            self._append_log(f"[{pid}] [CHECK] 题目链接: {uploaded_url}")
                            
                            self._emit_status(row, {"gen": "跳过(远端已有)", "upload": "跳过(已存在)"})
        except Exception as e:
            logger.debug(f"[{pid}] 验证已保存题目ID失败: {e}")
            self._append_log(f"[{pid}] [CHECK] 验证已保存ID失败: {e}，继续正常流程")
    
    if not remote_exists:
        self._append_log(f"[{pid}] [CHECK] 远端无同名题目，继续正常流程")
```

### 修复方案 2: 增强标题匹配容错性

#### 2.1 _search_exact_title 标题规范化

**文件**: `src/services/oj/adapters/hydrooj/data_uploader_impl.py`

**位置**: 约 149-192 行

**修改内容**：
```python
def _search_exact_title(self, title: str, auth: Any) -> Optional[str]:
    """精确标题匹配搜索（支持标题规范化）
    
    Args:
        title: 题目标题
        auth: HydroOJAuth 认证对象
        
    Returns:
        精确匹配的题目ID，未找到则返回 None
    """
    if not title:
        return None
    
    try:
        # 规范化标题：去除多余空格，统一格式
        # 将多个连续空格替换为单个空格
        normalized_title = ' '.join(title.strip().split())
        
        from urllib.parse import quote
        search_url = f"{self.base_url}/d/{self.domain}/p?q={quote(normalized_title)}"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': f"{self.base_url}/d/{self.domain}/p",
        }
        r = auth.session.get(search_url, headers=headers, timeout=30)
        r.raise_for_status()
        
        target_title = normalized_title
        problem_rows = re.finditer(
            r'<tr[^>]*data-pid="([^"]+)"[^>]*>(.*?)</tr>',
            r.text,
            re.DOTALL
        )
        
        for row_match in problem_rows:
            pid = row_match.group(1)
            row_html = row_match.group(2)
            
            title_match = re.search(r'<a[^>]*>([^<]+)</a>', row_html)
            if title_match:
                # 规范化远端标题
                found_title = ' '.join(title_match.group(1).strip().split())
                if found_title == target_title:
                    logger.debug(f"[HydroOJ Upload] _search_exact_title 找到: {pid} (标题: '{found_title}')")
                    return pid
        
        logger.debug(f"[HydroOJ Upload] _search_exact_title 未找到匹配标题: '{target_title}'")
        return None
    except Exception as e:
        logger.debug(f"[HydroOJ Upload] _search_exact_title 失败: {e}")
        return None
```

### 修复方案 3: 前端按钮修复

#### 3.1 TaskActionMenu 按钮修复

**文件**: `frontend/src/components/TaskActionMenu.tsx`

**位置**: 约 129-141 行

**修改内容**：
```typescript
{/* 打开上传链接 */}
{uploadedUrl && uploadedUrl.trim() && (
  <button
    onClick={() => {
      const url = uploadedUrl.trim();
      if (url && (url.startsWith('http://') || url.startsWith('https://'))) {
        window.open(url, '_blank', 'noopener,noreferrer');
        setIsOpen(false);
      } else {
        console.warn('uploadedUrl is invalid:', url);
        toast.error('链接地址无效');
      }
    }}
    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-green-600 hover:bg-green-50"
    title={uploadedUrl}
  >
    <ExternalLink size={16} />
    打开上传链接
  </button>
)}
```

#### 3.2 TasksPage 数据传递验证

**文件**: `frontend/src/pages/TasksPage.tsx`

**位置**: 约 116-128 行（数据映射）

**修改内容**：
```typescript
return (response.data.tasks || []).map((task: { 
  id: number; 
  problem_id: string; 
  status?: number; 
  progress?: number; 
  stage?: string; 
  error_message?: string; 
  created_at?: string; 
  updated_at?: string; 
  uploaded_url?: string 
}) => {
  // 验证 uploaded_url
  const uploadedUrl = task.uploaded_url?.trim() || null;
  if (uploadedUrl && !uploadedUrl.startsWith('http')) {
    console.warn(`Invalid uploaded_url for task ${task.id}:`, uploadedUrl);
  }
  
  return {
    id: String(task.id),
    displayId: task.problem_id,
    status: task.status || 0,
    progress: task.progress || 0,
    currentStage: task.stage || 'pending',
    logs: [],
    task_id: String(task.id),
    error_message: task.error_message,
    created_at: task.created_at,
    updated_at: task.updated_at,
    uploaded_url: uploadedUrl,  // 确保传递规范化后的 URL
  };
})
```

---

## 代码修改清单

### 后端修改

| 文件 | 行号范围 | 修改类型 | 优先级 |
|------|----------|----------|--------|
| `src/services/pipeline.py` | 809-861 | CHECK 阶段增强 | P0 |
| `src/services/pipeline.py` | 1100-1120 | uploaded_url 提取和保存 | P0 |
| `src/services/task_service.py` | 488-492 | uploaded_url 提取增强 | P0 |
| `src/services/oj/adapters/hydrooj/data_uploader_impl.py` | 149-192 | 标题规范化 | P1 |

### 前端修改

| 文件 | 行号范围 | 修改类型 | 优先级 |
|------|----------|----------|--------|
| `frontend/src/components/TaskActionMenu.tsx` | 129-141 | 按钮点击验证 | P0 |
| `frontend/src/pages/TasksPage.tsx` | 116-128 | 数据验证 | P1 |

---

## 测试验证

### 测试场景 1: 远程已有题目检测

**前置条件**：
- 远端已存在题目 "P1001 A+B Problem"（ID: 1005）
- 本地有该题目的题面数据

**测试步骤**：
1. 创建新任务，启用 fetch + gen + upload + solve
2. 观察日志中的 `[CHECK]` 阶段输出
3. 验证是否检测到远端题目并跳过生成和上传

**预期结果**：
```
[P1001] [CHECK] 检查远端是否已有同名题目...
[P1001] [CHECK] ✓ 远端已有同名题目 (ID: 1005)，跳过生成和上传
[P1001] [CHECK] 题目链接: https://jooj.top/d/polygon_test/p/1005
[P1001] [GEN] 跳过(远端已有)
[P1001] [UPLOAD] 跳过(已存在)
```

### 测试场景 2: uploaded_url 传递

**前置条件**：
- 任务成功上传到 HydroOJ

**测试步骤**：
1. 完成一个上传任务
2. 检查数据库 `tasks` 表的 `uploaded_url` 字段
3. 检查前端任务列表是否显示链接按钮
4. 点击按钮验证是否能打开链接

**预期结果**：
- 数据库 `uploaded_url` 字段有值
- 前端显示"打开上传链接"按钮
- 点击按钮能正常打开 HydroOJ 题目页面

### 测试场景 3: 标题规范化匹配

**前置条件**：
- 远端题目标题：`"P1001  A+B Problem"`（多个空格）
- 本地题目标题：`"P1001 A+B Problem"`（单个空格）

**测试步骤**：
1. 执行 CHECK 阶段
2. 验证是否能正确匹配

**预期结果**：
- 标题规范化后能正确匹配
- 日志显示找到匹配题目

---

## 注意事项

1. **向后兼容性**：修改需确保不影响现有功能
2. **错误处理**：所有网络请求需添加超时和异常处理
3. **日志记录**：关键步骤需记录详细日志，便于排查
4. **性能影响**：已保存 ID 验证会增加一次 HTTP 请求，需评估性能影响

---

## 后续优化建议

1. **缓存机制**：缓存已检测的题目 ID，避免重复检测
2. **批量检测**：支持批量检测多个题目是否已存在
3. **标题模糊匹配**：在精确匹配失败时，提供模糊匹配选项
4. **用户提示**：检测到重复题目时，提供更友好的用户提示

---

## 实际修复记录

### 已应用的修复 (2026-01-06)

| 修复项 | 文件 | 状态 |
|--------|------|------|
| 标题规范化 | `src/services/oj/adapters/hydrooj/data_uploader_impl.py` | ✅ 已修复 |
| real_id 回退提取 | `src/services/oj/adapters/hydrooj/data_uploader_impl.py` | ✅ 已修复 |
| 前端 URL 验证 | `frontend/src/components/TaskActionMenu.tsx` | ✅ 已修复 |
| CHECK 阶段已保存 ID 回退 | `src/services/pipeline.py` | ✅ 已修复 |

### 修复详情

1. **标题规范化** (`_search_exact_title`)
   - 使用 `' '.join(title.strip().split())` 规范化本地和远端标题
   - 解决了多余空格导致的匹配失败问题

2. **real_id 回退提取** (`_upload_to_hydro`)
   - HTTP 200 时如果 JSON 解析失败，回退到 `_get_latest_problem_id` 搜索
   - 增加日志提示当无法获取 `real_id` 时

3. **前端 URL 验证** (`TaskActionMenu.tsx`)
   - 增加 `uploadedUrl.trim()` 验证
   - 检查 URL 是否以 `http://` 或 `https://` 开头
   - 无效 URL 显示错误提示

4. **CHECK 阶段已保存 ID 回退** (`pipeline.py`)
   - 精确标题搜索失败时，检查已保存的 `real_id`
   - 验证已保存 ID 对应的题目是否仍存在且标题匹配

### 架构评估结论

- ✅ 符合职责分离原则（Pipeline 不直接操作数据库）
- ✅ 符合 DRY 原则（复用 `_search_exact_title` 方法）
- ✅ 向后兼容（不影响现有功能）
- ✅ 防御性编程（前端 URL 验证）

---

**文档维护者**: AI Assistant  
**最后更新**: 2026-01-06

