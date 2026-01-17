# 已废弃代码 (Deprecated Code)

此目录包含已废弃但暂时保留的前端代码文件。

## 封存日期
2024-12-22

## 封存文件

| 文件 | 原路径 | 废弃原因 |
|------|--------|----------|
| `taskStore.ts` | `stores/taskStore.ts` | 定义了完整的 Zustand store，但项目中无任何组件使用 |

## 注意事项

- 这些代码可能在未来版本中被完全删除
- 如需恢复，请将文件移回原路径
- 项目当前使用 React Query 管理服务端状态，Zustand 仅用于 `authStore`
