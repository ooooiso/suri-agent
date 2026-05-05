# log_service 插件 PRD

## 定位

全系统日志集中存储插件，提供分级日志记录、分类归档、结构化查询能力。中文日志输出，按天轮转，保留 30 天。

## 功能需求

### 1. 分级日志
- 级别：DEBUG / INFO / WARN / ERROR
- 输出：终端（可选）+ 文件（`logs/{category}/suri-{YYYY-MM-DD}.log`）
- 同时输出结构化 JSONL（`suri-{YYYY-MM-DD}.jsonl`）

### 2. 分类管理
- 支持分类配置化（`logs/categories.yaml`）
- 默认分类：runtime / error / schedule / role / system / tool_calls
- 每个分类独立目录，自动创建

### 3. 日志轮转与归档
- 按日期分割文件
- 超过 30 天的日志自动归档到 `backup/{category}/`
- 归档时保持目录结构

### 4. 日志查询
- 按分类、日期、插件名、级别筛选
- 按时间倒序返回
- 支持 JSONL 结构化字段查询

### 5. 插件独立日志
- 每个插件可拥有独立日志文件（通过 PluginLogger 代理）

## 接口定义

### 订阅事件
- `*`（通配符）→ 记录关键系统事件到 system/schedule 分类
- `tool.call` → 记录工具调用到 tool_calls 分类
- `llm.request` → 记录模型请求到 runtime 分类
- `task.created` / `task.completed` / `task.failed` → 记录到 schedule 分类

### 三清单变更日志（新增）

订阅三清单相关事件，记录所有注册表变更：

| 事件 | 分类 | 说明 |
|------|------|------|
| `role.registered` / `role.updated` / `role.deprecated` | system | 角色清单变更日志 |
| `plugin.registered` / `plugin.updated` / `plugin.deprecated` | system | 插件清单变更日志 |
| `tool.registered` / `tool.updated` / `tool.deprecated` | system | 工具清单变更日志 |
| `triple.registry.synced` | system | 三清单同步完成日志 |
| `role.skill_added` / `role.skill_removed` | role | 技能变更日志 |

每个三清单变更事件记录内容包括：
- 变更类型（registered / updated / deprecated / removed）
- 变更对象信息（ID、名称、版本）
- 变更前后对比（关键字段 diff）
- 触发源（插件/用户/自动）

### 发布事件
- 不发布事件（纯消费者）

## 配置项

```yaml
log_service:
  log_base: "logs/"
  backup_base: "backup/"
  retention_days: 30
  categories:
    runtime: "程序运行"
    error: "错误"
    schedule: "调度"
    role: "角色通信"
    system: "系统"
    tool_calls: "工具调用"
```

## 事件 Payload Schema

### 订阅事件

#### `error.*`（通配符）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `error_code` | integer | 是 | 错误码 |
| `error_type` | string | 是 | 错误类型 |
| `message` | string | 是 | 错误描述 |
| `source` | string | 是 | 错误来源插件/角色 |
| `timestamp` | string | 是 | 错误时间 |
| `context` | object | 否 | 上下文信息 |

### 发布事件

本插件不发布业务事件，仅写入日志文件。

## 依赖关系

- 上游：suri_core
- 下游：所有需要记录日志的插件

## 数据模型

### 文件存储
- `logs/{category}/suri-{date}.log` — 人类可读文本日志
- `logs/{category}/suri-{date}.jsonl` — 结构化机器日志
- `backup/{category}/` — 归档日志

### 日志条目结构
```json
{
  "timestamp": "2026-05-02T16:00:00",
  "level": "INFO",
  "plugin": "llm_gateway",
  "message": "请求模型: glm-4",
  "category": "runtime"
}
```

## 生命周期

1. `init()` → 加载分类配置、确保目录、执行归档清理
2. `register_events()` → 订阅关键系统事件
3. `start()` → 标记就绪
4. `stop()` → 刷新缓冲区
5. `cleanup()` → 关闭文件句柄

## 安全边界

- 日志中敏感信息（API Key）必须脱敏处理
- 错误分类自动复制到 error 目录