# 架构决策记录 (Architecture Decision Records)

> 记录 suri 平台的重大架构决策及其原因。每条记录包含：决策日期、背景、决策内容、后果。

---

## ADR-001: 目录命名使用连字符

- **日期**: 2026-04-30
- **背景**: Python 包名不能使用连字符，但项目目录使用连字符更符合 shell/URL 惯例
- **决策**: 目录使用连字符（如 `suri-agent/`），Python import 时通过 PYTHONPATH 解决，import 不加 `suri_agent.` 前缀
- **后果**: 所有内部 import 直接使用 `from model.manager import ...`

## ADR-002: 角色独立存储

- **日期**: 2026-04-30
- **背景**: 多个角色共用 state.db 导致数据混乱、权限边界模糊
- **决策**: 每个角色的记忆/会话/任务存放到 `group/<role>/memories/role.db`，不再共用根目录 state.db
- **后果**: MemoryService 按 role_id 隔离存储，安全性提升

## ADR-003: 规则与流程代码化

- **日期**: 2026-04-30
- **背景**: manifest/rules/ 和 manifest/process/ 中的 Markdown 规则需要运行时解析，效率低且易出错
- **决策**: 所有业务规则和平台级流程从 Markdown 迁移为 Python 代码，运行时直接 import 执行
- **后果**: rules/ 和 process/ 目录下为 Python 模块，不再解析 Markdown

## ADR-004: 模型管理独立模块

- **日期**: 2026-04-30
- **背景**: 需要对接多个外部大模型，管理模型配置和 API Key
- **决策**: 在 `suri-agent/model/` 下建立独立的模型管理模块，负责配置管理和 API 调用
- **后果**: ModelManager 管理 model_config.json，支持 OpenAI 兼容格式和 Anthropic API，cli.py 在首次运行时引导配置

## ADR-005: AI 开发记忆独立维护

- **日期**: 2026-04-30
- **背景**: 开发过程中架构决策、模块变更频繁，需要集中记录作为 AI 开发上下文；原 wiki/ 目录面向用户，不适合存放 AI 内部记忆
- **决策**: 在 `suri-agent/memory/ai-dev-memory/` 下建立 AI 开发记忆库，包含架构决策、开发日志、模块索引；wiki/ 仅保留用户面向内容
- **后果**: AI 开发助手统一从 `suri-agent/memory/ai-dev-memory/` 读取上下文；每次开发后必须同步更新
