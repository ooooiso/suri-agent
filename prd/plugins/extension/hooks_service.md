# hooks_service 插件 PRD

## 定位

事件钩子插件，提供文件操作拦截、文档监控、代码变更回调等扩展点。允许其他插件注册钩子函数，在关键操作前后执行自定义逻辑。

## 功能需求

### 1. 文件操作钩子
- `pre_read(path)` / `post_read(path, content)`
- `pre_write(path, content)` / `post_write(path)`
- `pre_delete(path)` / `post_delete(path)`
- 钩子可拦截操作（返回 False 阻止）

### 2. 文档监控钩子
- `on_doc_created(path)` — 文档创建
- `on_doc_modified(path)` — 文档修改
- `on_doc_deleted(path)` — 文档删除
- 触发 doc_sync 检查

### 3. 任务生命周期钩子
- `pre_task_dispatch(task)` — 任务分派前
- `post_task_complete(task, result)` — 任务完成后
- `on_task_fail(task, error)` — 任务失败

### 4. 插件扩展钩子
- `pre_plugin_load(manifest)` — 插件加载前
- `post_plugin_start(plugin)` — 插件启动后
- `pre_plugin_unload(plugin)` — 插件卸载前

### 5. 钩子注册
- 支持优先级（高/中/低）
- 支持异步钩子
- 支持一次性钩子（执行后自动注销）

## 接口定义

### 订阅事件
- 所有系统事件（作为底层拦截层）

### 发布事件
- 不发布新事件（只拦截和回调）

## 配置项

```yaml
hooks_service:
  enable_file_hooks: true
  enable_doc_hooks: true
  enable_task_hooks: true
  max_hook_execution_time: 5.0
```

## 事件 Payload Schema

### 订阅事件

本插件订阅所有系统事件（通配符），但不修改事件内容。

拦截后可能发布的事件：

#### `hooks.file_changed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | 是 | 变更文件路径 |
| `change_type` | string | 是 | created / modified / deleted |
| `diff` | string | 否 | 变更内容 diff |
| `timestamp` | string | 是 | 变更时间 |

#### `hooks.pre_task_dispatch`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `task_text` | string | 是 | 任务描述 |
| `matched_roles` | array | 是 | 匹配的角色列表 |

#### `hooks.post_task_complete`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `status` | string | 是 | completed / failed |
| `duration_ms` | integer | 否 | 耗时 |

## 依赖关系

- 上游：suri_core
- 下游：doc_sync、security_service 等使用钩子的插件

## 生命周期

1. `init()` → 初始化钩子注册表
2. `start()` → 标记就绪，开始接收注册
3. `stop()` → 拒绝新注册，等待正在执行的钩子
4. `cleanup()` → 清空所有钩子

## 安全边界

- 钩子超时强制终止（防死锁）
- 异常钩子不影响主流程
- 钩子执行顺序优先级严格
