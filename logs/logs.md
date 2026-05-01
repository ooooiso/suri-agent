# logs/

日志总目录：存放 suri 平台各类运行日志，按模块分类存储，按天轮转文件。

## 子目录

| 目录 | 用途 | 记录内容 | 文件格式 |
|------|------|---------|---------|
| `runtime/` | 程序运行日志 | 用户交互、模型调用、命令执行 | 文本 `.log` |
| `error/` | 错误日志 | 异常、崩溃、API 调用失败 | 文本 `.log` |
| `schedule/` | 调度日志 | 任务创建、角色间调度、任务状态变更 | 文本 `.log` |
| `role/` | 角色通信日志 | 角色间消息、任务关联通信 | 文本 `.log` |
| `system/` | 系统日志 | 启动、关闭、代码变更、服务重载 | 文本 `.log` |
| `statistics/` | 统计日志 | Token 消耗、文件创建、任务完成等结构化数据 | JSONL `.jsonl` |
| `tool_calls/` | 工具调用日志 | 各角色调用工具的参数、结果、成功率 | 文本 `.log` |

## 配置文件

| 文件 | 用途 |
|------|------|
| `categories.yaml` | 日志分类单一来源配置，`LoggerService` 初始化时加载。新增分类只需修改此文件。 |

## 文件命名规则

- 文本日志：`suri-YYYY-MM-DD.log`
- JSONL 日志：`suri-YYYY-MM-DD.jsonl`

每个子目录下按天创建文件，自动轮转。

## 日志格式

**文本日志**：
```
[YYYY-MM-DD HH:MM:SS] [级别] [模块] 消息内容
```
级别：信息 / 警告 / 错误 / 调试

**JSONL 日志**（statistics/）：
```json
{"event": "token_usage", "timestamp": "...", "model_id": "...", "role_id": "...", ...}
```

## 写入来源

| 目录 | 写入代码 | 说明 |
|------|---------|------|
| `runtime/` | `LoggerService._write()` | 通用运行时事件 |
| `error/` | `LoggerService._write()` | 错误与异常 |
| `schedule/` | `LoggerService._write()` | 任务调度事件 |
| `role/` | `LoggerService._write()` | 角色间通信 |
| `system/` | `LoggerService._write()` | 系统级事件 |
| `statistics/` | `LoggerService._write_json_log()` | 结构化统计事件（Token、文件、任务） |
| `tool_calls/` | `LoggerService.log_tool_call()` | 工具调用记录（统一入口） |

## 事件记录

- 初始创建，从 resources/logs/ 迁移至此
- 新增分类子目录：runtime、error、schedule、role、system
- 2026-05-01: 新增 `statistics/` JSONL 结构化日志（Token 用量、文件创建、任务完成）
- 2026-05-01: 新增 `tool_calls/` 工具调用日志（原由 ToolService 独立管理，现统一纳入 LoggerService）
