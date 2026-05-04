# API 接口文档模板

> 本文档为 suri-agent 所有插件的 API 接口提供统一模板。
> 每个插件必须按此模板补充完整的接口文档。

---

## 模板说明

每个插件需按以下结构提供接口文档：

1. **插件概述** — 插件的定位、职责和边界
2. **事件契约** — 发布/订阅的事件类型及 payload schema
3. **工具调用接口** — 暴露的工具方法、参数和返回值
4. **配置项** — 插件的配置字段和默认值
5. **示例与错误码** — 调用示例和对应错误码

---

## 模板正文

### 1. 插件概述

```markdown
# {PluginName} 插件接口文档

## 1.1 定位

{一句话描述插件职责}

## 1.2 依赖清单

| 依赖接口 | 最低版本 | 说明 |
|---------|---------|------|
| {interface_name} | {min_version} | {说明} |

## 1.3 边界声明

{插件不处理什么，不依赖什么}
```

### 2. 事件契约

```markdown
## 2.1 发布事件

### {event_type}

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| {field_name} | {type} | ✅/❌ | {说明} |

**示例 payload**：

```json
{
  "field_name": "field_value"
}
```

### 2.2 订阅事件

| 事件类型 | 最低版本 | 处理逻辑 |
|---------|---------|---------|
| {event_type} | {min_version} | {处理逻辑描述} |

### 2.3 事件响应超时

| 事件类型 | 超时时间(秒) | 超时行为 |
|---------|-------------|---------|
| {event_type} | {timeout}s | {超时后行为} |
```

### 3. 工具调用接口

```markdown
## 3.1 {tool_name}

### 接口描述

{一句话描述工具功能}

### 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| {param_name} | {type} | ✅/❌ | {default} | {说明} |

### 返回值

| 字段 | 类型 | 说明 |
|------|------|------|
| {field_name} | {type} | {说明} |

### 错误码

| 错误码 | 条件 |
|--------|------|
| {error_code} | {触发条件} |

### 调用示例

```python
# 通过 EventBus 调用
await event_bus.publish(Event(
    event_type="{tool.call}",
    source="caller_plugin",
    payload={
        "tool": "{tool_name}",
        "params": { ... }
    }
))
```
```

### 4. 配置项

```markdown
## 4.1 配置字段

配置文件位置：`~/.suri/data/configs/{plugin_name}.yaml`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| {field_name} | {type} | ✅/❌ | {default} | {说明} |

## 4.2 配置示例

```yaml
{field_name}: {example_value}
```

## 4.3 热更新支持

| 配置项 | 热更新级别 | 变更后行为 |
|--------|-----------|-----------|
| {field_name} | L1/L2/L3 | {变更后行为描述} |
```

### 5. 错误码

```markdown
## 5.1 错误码列表

| 错误码 | 名称 | 说明 | 可恢复 | 事件 |
|--------|------|------|--------|------|
| {code} | {name} | {说明} | ✅/❌ | {event_type} |

## 5.2 重试策略

| 错误码 | 是否自动重试 | 最大重试次数 | 重试间隔 |
|--------|-------------|-------------|---------|
| {code} | ✅/❌ | {n} | {interval}s |
```

### 6. 性能指标

```markdown
## 6.1 关键性能指标

| 指标 | 目标值 | 告警阈值 |
|------|--------|---------|
| {metric} | {target} | {threshold} |
```

---

## 具体插件接口文档索引

| 插件 | 文件 | 状态 |
|------|------|------|
| suri_core | `plugins/core/suri_core/api.md` | ⏳ 待补充 |
| config_service | `plugins/service/config_service/api.md` | ⏳ 待补充 |
| log_service | `plugins/service/log_service/api.md` | ⏳ 待补充 |
| security_service | `plugins/service/security_service/api.md` | ⏳ 待补充 |
| task_scheduler | `plugins/execution/task_scheduler/api.md` | ⏳ 待补充 |
| task_planner | `plugins/execution/task_planner/api.md` | ⏳ 待补充 |
| agent_registry | `plugins/execution/agent_registry/api.md` | ⏳ 待补充 |
| interrupt_handler | `plugins/execution/interrupt_handler/api.md` | ⏳ 待补充 |
| role_comm | `plugins/execution/role_comm/api.md` | ⏳ 待补充 |
| code_tool | `plugins/execution/code_tool/api.md` | ⏳ 待补充 |
| llm_gateway | `plugins/capability/llm_gateway/api.md` | ⏳ 待补充 |
| role_manager | `plugins/capability/role_manager/api.md` | ⏳ 待补充 |
| memory_service | `plugins/capability/memory_service/api.md` | ⏳ 待补充 |
| role_learner | `plugins/capability/role_learner/api.md` | ⏳ 待补充 |
| mcp_framework | `plugins/capability/mcp_framework/api.md` | ⏳ 待补充 |
| upgrade_manager | `plugins/capability/upgrade_manager/api.md` | ⏳ 待补充 |
| access | `plugins/access/api.md` | ⏳ 待补充 |
| test_framework | `plugins/extension/test_framework/api.md` | ⏳ 待补充 |
| cron_service | `plugins/extension/cron_service/api.md` | ⏳ 待补充 |
| hooks_service | `plugins/extension/hooks_service/api.md` | ⏳ 待补充 |
| doc_sync | `plugins/extension/doc_sync/api.md` | ⏳ 待补充 |
| monitor | `plugins/extension/monitor/api.md` | ⏳ 待补充 |

---

## 使用说明

1. **复制模板**：将本模板复制到 `prd/plugins/{category}/{plugin_name}/api.md`
2. **填写接口**：根据实际代码实现填写每个插件的事件、工具、配置
3. **维护版本**：API 变更时同步更新对应 api.md
4. **交叉引用**：在 plugin.md（插件主文档）中引用 api.md

> 本模板已覆盖所有 22 个插件，预计总工作量 5-7 天。