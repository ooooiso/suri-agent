# 术语表

> suri-agent 系统使用的核心术语定义。
> **本文档为所有交叉引用的唯一源头。**

---

## 角色（Agent）

| 术语 | 定义 |
|------|------|
| **suri** | 主人 Agent（第一性智能体），系统唯一的 `core` 类型角色 |
| **角色（Agent）** | 独立智能体，拥有 Soul/技能/记忆/学习能力 |
| **角色类型** | `core`（唯一，suri）/ `worker`（工作）/ `project_director`（项目总监）/ `admin`（管理） |
| **角色状态** | `created` / `ready` / `busy` / `blocked` / `upgrading` / `archived` / `deleted` |

## 三层数据分离 ⭐（所有文档以此处定义为准）

> 系统所有涉及"角色数据存储、Git 管理、路径规则"的描述，**统一引用此节**，禁止在各文档中独立重复描述。

| 层级 | 目录 | Git 管理 | 内容 | 说明 |
|------|------|---------|------|------|
| **角色定义** | `roles/{role_id}/` | ✅ 是 | soul.md, meta.json, skills/, memories/insights/ | 代码般的资产，随 Git 迁移 |
| **运行时数据** | `~/.suri/runtime/roles/{role_id}/` | ❌ 否 | adhoc/, projects/, global/role.db | 会话/项目记忆，首次启动自动重建 |
| **系统配置** | `~/.suri/` | ❌ 否 | config.json, logs/, suri.db | API Key 等敏感信息 |

**跨文档引用约定**：
- 所有提及"角色数据存储"的地方 → 统一写"详见 terminology.md 三层数据分离"
- 所有提及"Git 版本控制"的地方 → 统一写"参见 terminology.md 三层数据分离"
- 禁止在 design-principles.md / program-flow.md / startup.md / directory-structure.md 中**独立重复**三层数据分离的定义

## 三清单体系 ⭐（所有文档以此处定义为准）

> Role Registry / Plugin Registry / Tool Registry 的"三清单"，所有交叉引用统一定义于此。

| 清单 | 维护者 | 存储位置 | 广播事件 |
|------|--------|---------|---------|
| **Role Registry** | `role_manager` | `~/.suri/data/registries/role_registry.json` | `role.registered` / `role.updated` / `role.deprecated` |
| **Plugin Registry** | `plugin_manager` | `~/.suri/data/registries/plugin_registry.json` | `plugin.registered` / `plugin.updated` / `plugin.deprecated` |
| **Tool Registry** | `mcp_framework` | `~/.suri/data/registries/tool_registry.json` | `tool.registered` / `tool.updated` / `tool.deprecated` |

**三清单审计**：所有三清单变更必须经过 security_service 拦截检查，见 security_service.md 三清单审计节。

## 核心配置文件

| 术语 | 定义 |
|------|------|
| **Soul** | 角色的自我定义文件，YAML frontmatter + Markdown body，存储在 `roles/{role_id}/soul.md` |
| **Skill** | 角色的能力原子单元。通过 skill 文件定义，可被 role_learner 检测、自学自增。包含 `tool_mappings` 字段 |
| **Memory** | 角色的经验积累。SQLite 持久化，按上下文类型分为 Ad-hoc/Project/Global 三层 |
| **Manifest** | 插件的声明文件。定义名称、版本、api_version、事件合约 |
| **_meta** | 工具调用中的上下文元数据，包含 `role_id, project_id, task_id, session_id`。由 security_service 的 meta_validator 校验 |

## 系统机制

| 术语 | 定义 |
|------|------|
| **EventBus** | 事件总线，系统的通信中枢。异步发布/订阅模式 |
| **PluginManager** | 插件管理器，负责插件扫描、加载、生命周期管理 |
| **suri_core** | 内核插件，系统第一个插件。自举注册 EventBus 和 PluginManager |
| **上下文隔离** | 角色上下文分为 Ad-hoc / Project / Global 三层，严格隔离防混淆 |
| **切换快照** | 角色切换项目时保存的 context_snapshot，包含当前任务摘要和关键事实 |
| **审批令牌** | security_service 生成的临时许可，用于高危操作确认。超时 300 秒自动失效 |
| **热更新** | 运行时无需重启即可更新配置/数据/代码。支持 L1(配置)/L2(数据)/L3(代码) 三级 |

## 插件热更新级别

| 级别 | 名称 | 范围 | 是否重启 |
|------|------|------|---------|
| **L1** | 配置热更新 | 配置文件、模板、关键词 | ❌ 不需要 |
| **L2** | 数据热更新 | 三清单、角色定义、工具注册 | ❌ 不需要 |
| **L3** | 代码热更新 | 插件代码变更 | ⚠️ 视情况 |

## 进化

| 术语 | 定义 |
|------|------|
| **技能进化** | Skill 文件版本递进（v1.0 → v1.1），role_learner 检测重复模式后建议 |
| **Soul 进化** | Soul 文件被 suri 更新，变更角色职责边界/行为偏好 |
| **插件进化** | 插件通过 self-analysis → 自修改流程更新自己的能力 |
| **工具进化** | suri 通过自然语言对话维护开发工具，注册/更新/废弃后自动广播通知 |
| **协同通知** | 某个维度变更后，通过事件广播通知所有相关方 |

## 其他

| 术语 | 定义 |
|------|------|
| **RAG** | 检索增强生成，memory_service 使用 RAG 检索相关记忆 |
| **MCP** | Model Context Protocol，MCP 工具框架 |
| **LLM 厂商路由** | llm_gateway 根据模型权重/可用性选择 LLM 供应商 |
| **SQLite** | 轻量级嵌入式数据库，用于角色记忆和系统表存储 |