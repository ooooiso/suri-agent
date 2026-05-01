# memory/

> 关联代码: suri-agent/infrastructure/memory.py, suri-agent/core/context.py

记忆总目录：存放 suri 平台所有类型的记忆，是整个程序未来的记忆中枢。

## 定位

本目录是 suri 平台各类记忆的统一存储中心，不仅服务于 AI 开发，也服务于程序运行时的状态记录、角色交互历史、会话存档等。任何需要长期保留、供后续检索或供 AI 读取的上下文，都应归入此处。

## 设计原则

1. **分类隔离**：不同类型的记忆存放在独立的子目录中，避免混杂。
2. **AI 可读**：记忆格式优先选择 AI 易于解析的结构（Markdown、JSON、SQLite），方便外部 AI（包括其他编辑器的 AI）直接读取作为上下文。
3. **每次变更后同步**：新增、修改、删除模块时，必须同步更新本目录中对应的记忆文件。
4. **大模型辅助整理**：调用外部大模型生成更新摘要，由 document-review 审核后写入。

## 记忆策略配置

业务配置：`config.yaml`

| 字段 | 说明 |
|------|------|
| `memory_config.retention_days` | 消息保留天数（默认 90 天） |
| `memory_config.archive_threshold` | 单角色消息归档阈值（默认 1000 条） |

- 超过保留期的消息自动归档到 `_archived/` 目录
- 单角色消息超过阈值时触发归档

## 子目录

| 目录 | 用途 | 面向对象 |
|------|------|---------|
| `ai-dev-memory/` | AI 开发记忆：架构决策、开发日志、模块索引 | AI 开发助手 |

## 角色经验日志（V2.0）

每个角色的 SQLite 数据库（`group/<role>/memories/role.db`）新增 `experiences` 表：

| 字段 | 说明 |
|------|------|
| `task_id` | 关联任务 ID |
| `action` | 采取的动作摘要 |
| `result` | 结果描述 |
| `feedback` | 用户/系统反馈 |
| `reflection` | 反思（可由 LLM 后续生成） |
| `tags` | 标签（逗号分隔） |
| `created_at` | 记录时间 |

API：`MemoryService.save_experience()` / `get_experiences()` / `get_experience_stats()`

## 未来扩展

随着平台发展，本目录下可新增其他记忆类型，例如：
- `session-history/` — 用户会话历史存档
- `task-memory/` — 任务执行记录与复盘
- `role-interactions/` — 角色间交互日志

## 事件记录

- 初始创建，从 wiki/core-memory/ 迁移至此处
- 2026-05-01: **1000轮压力测试通过**（500轮生活对话 + 500轮任务对话，48/48测试项全通过）
- 2026-05-01: 修复 `get_role_messages()` JSON解析异常处理（添加 try/except，防止损坏body导致整个查询崩溃）
- 2026-05-01: 数据库连接管理优化 — 所有 SQLite 操作改用 `with` 上下文管理器，消除连接泄漏风险
- 2026-05-01: 修复 `update_insight_trigger()` — 从正则硬替换改为 frontmatter 解析+重建，消除格式脆弱性
- 2026-05-01: 修复 cli.py 消息ID冲突 — `_execute_dispatch()` 使用纳秒时间戳后缀确保消息ID唯一性
- 2026-05-01: suri 角色上下文升级 — `suri_process()` 改用 `ContextService.build_context()` 构建系统提示，注入学习经验和历史记忆
- 2026-05-01: **多用户并发隔离** — SQLite 启用 WAL 模式；新增 `get_session_messages()` 按 session 过滤消息；`build_context()` 支持 `session_id` 参数；`suri_process()` 支持 `user_id` 参数和 `_get_or_create_session()` 自动会话管理
