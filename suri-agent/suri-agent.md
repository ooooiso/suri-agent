# suri-agent.md — Suri Agent 项目框架定义

> 本文档是项目的核心指导文件，描述完整的架构、结构、规则和约定。任何变更均需同步更新本文档。

---

## 1. 项目定位

**Suri Agent** 是一个基于角色驱动的多 Agent 协作平台。

- **核心调度**：suri 作为唯一用户交互入口，负责需求解析、任务分派、进度跟踪。
- **角色自治**：每个角色拥有独立的记忆、会话、技能和工作流程，自行学习，自行决策。
- **中枢协调**：跨角色协作通过中枢部门（central）统一协调，不直接跨部门通信。
- **规则代码化**：所有业务规则从 Markdown 迁移为 Python 代码，运行时直接执行。
- **流程代码化**：平台级流程从 Markdown 迁移为 Python 代码，运行时直接执行。

---

## 2. 目录结构总览

```
suri/                               # 项目根目录
│
│  【源代码/配置模板 — 程序运行前已存在】
├── requirements.txt                # Python 依赖清单（源代码）
├── suri                            # 客户端命令（源代码，终端唯一入口）
├── .env.example                    # 环境变量模板（配置模板）
│
├── scripts/                        # 辅助脚本（源代码）
│   ├── run.sh                      # 多模式启动脚本
│   ├── install.sh                  # 系统安装脚本
│   └── suri-daemon                 # 后台管理命令
│
├── wiki/                           # 知识库（用户面向，可编辑）
│   ├── state_schema.md             # 数据库表结构说明文档
│   ├── models/model_pool.md        # 模型池配置
│   ├── communication/telegram.md   # 通信配置
│   └── memory/memory_config.md     # 记忆策略配置
│
│  【运行时生成 — 程序运行后自动创建/修改】
├── .env                            # 环境变量（首次运行引导写入）
├── config.yaml                     # 运行时参数（首次运行写入，可热重载）
├── model_config.json               # 模型配置（/model add 写入）
├── .doc_sync_rule_state.json       # 文档同步规则状态（自动持久化）
│
│  【角色定义 — 源代码（运行前）+ 运行时记忆（运行后生成）】
├── group/                          # 角色组
│   ├── central/                    # 中枢部门
│   │   ├── suri/                   # 核心调度角色（源代码：suri.md）
│   │   ├── suri-hr/                # 角色管理员（源代码：suri-hr.md + 技能模板）
│   │   ├── suri-dev/               # 主程序维护（源代码：suri-dev.md）
│   │   └── document-review/        # 文档审核员（源代码：document-review.md）
│   ├── _archived/                  # 已归档角色（保留30天）
│   └── group_function.md           # 部门职能索引与角色能力速查（源代码）
│
│  ⚠️ 注意：group/<role>/memories/role.db 为运行时生成，运行前不应存在
│
├── skills/                         # suri 专属技能库（源代码）
│   ├── task_dispatch/              # 需求解析、部门匹配、任务下发
│   ├── escalation/                 # 任务升级、重试耗尽、用户回流
│   ├── user_approval/              # 安全审批流程中向用户请求确认
│   ├── exception_handler/          # 通用异常捕获与分类处理
│   └── cross_department_sync/      # 跨部门协作进度同步
│
│  【日志目录 — 运行前仅有 .md 说明，.log 文件为运行时生成】
├── logs/                           # 运行日志（按模块分类，按天轮转）
│   ├── runtime/                    # 程序运行日志
│   ├── error/                      # 错误日志
│   ├── schedule/                   # 调度日志
│   ├── role/                       # 角色通信日志
│   └── system/                     # 系统日志
│
│  【运行时资源 — 运行前为空目录，运行后自动填充】
├── resources/                      # 运行时资源
│   ├── cache/                      # 运行时缓存
│   ├── sessions/                   # 会话记录
│   └── temp/                       # 临时文件
│
│  【主程序 — 全部源代码，运行前已存在】
└── suri-agent/                     # 主程序
    ├── main.py                     # 主程序入口
    ├── suri-agent.md               # 本文档（核心框架定义）
    │
    ├── access/                     # 接入层
    │   ├── access.md               # 接入层说明
    │   ├── base.py
    │   ├── tui/                    # 终端交互
    │   │   ├── cli.py              # 命令行客户端
    │   │   ├── server.py           # JSON-RPC 服务端
    │   │   ├── rpc_methods.py
    │   │   ├── middleware.py
    │   │   └── README.md
    │   ├── telegram/
    │   │   └── bot.py              # Telegram 机器人
    │   └── feishu/
    │       └── bot.py              # 飞书机器人
    │
    ├── core/                       # 核心调度层
    │   ├── core.md                 # 核心调度层说明
    │   ├── task_dispatcher.py      # 任务调度器
    │   ├── model_router.py         # 模型路由
    │   ├── context.py              # 上下文管理
    │   ├── approval.py             # 审批引擎
    │   ├── tool_executor.py        # 工具执行器
    │   └── doc_sync.py             # 文档同步服务
    │
    ├── model/                      # 模型管理
    │   ├── model.md                # 模型管理说明
    │   ├── __init__.py             # 入口
    │   └── manager.py              # 模型配置与调用管理
    │
    ├── memory/                     # 记忆总目录
    │   ├── memory.md               # 记忆总目录说明
    │   └── ai-dev-memory/          # AI 开发记忆
    │       ├── ai-dev-memory.md    # AI 开发记忆总览
    │       ├── architecture.md     # 架构决策记录
    │       ├── development-log.md  # 开发日志
    │       └── module-index.md     # 模块索引
    │
    ├── infrastructure/             # 基础设施层
    │   ├── infrastructure.md       # 基础设施层说明
    │   ├── config.py               # 配置加载器
    │   ├── memory.py               # 记忆服务（角色级独立存储）
    │   ├── security.py             # 安全服务
    │   ├── filesystem.py           # 文件服务
    │   ├── logger.py               # 日志服务（中文日志、按天轮转）
    │   └── utils.py                # 通用工具函数
    │
    ├── mcp/                        # MCP 扩展框架
    │   ├── mcp.md                  # MCP 框架说明
    │   ├── base.py                 # MCP 服务基类
    │   ├── registry.py             # MCP 注册中心
    │   └── services/               # 具体 MCP 服务（可自增长）
    │       ├── code_execution/
    │       ├── filesystem/
    │       └── web_search/
    │
    ├── role/                       # 角色管理层
    │   ├── role.md                 # 角色管理层说明
    │   ├── coordinator.py          # 角色协同调度器
    │   ├── messenger.py            # 角色通信管理器
    │   └── builder.py              # 角色搭建规则执行器
    │
    ├── rules/                      # 业务规则执行代码
    │   ├── rules.md                # 规则总览
    │   ├── __init__.py             # RuleEngine 入口
    │   ├── base.py                 # 规则基类
    │   ├── scheduling.py           # 调度规则
    │   ├── security.py             # 安全审批规则
    │   ├── file_ownership.py       # 文件所有权
    │   ├── model_routing.py        # 模型路由
    │   ├── communication.py        # 通信协议
    │   ├── role_management.py      # 角色生命周期
    │   └── code_commit.py          # 代码提交规范
    │
    ├── process/                    # 平台流程执行代码
    │   ├── process.md              # 流程总览
    │   ├── __init__.py             # ProcessEngine 入口
    │   ├── base.py                 # 流程基类
    │   ├── workflow.py             # 工作流执行器
    │   └── change_approval.py      # 变更审批执行器
    │
    ├── tools/                      # 公共工具库（可选调用）
    │   ├── tools.md                # 工具库说明
    │   ├── tool_registry.md        # 工具注册索引
    │   ├── data_converter/         # 数据转换
    │   ├── file_compressor/        # 文件压缩
    │   └── image_processor/        # 图像处理
    │
    ├── hooks/                      # 事件钩子
    │   ├── hooks.md                # 钩子说明
    │   └── README.md
    │
    └── cron/                       # 定时任务
        └── cron.md                 # 定时任务说明
```

---

## 3. 角色体系

### 3.1 角色存储模型

每个角色拥有完全独立的存储：

| 存储位置 | 用途 | 格式 |
|----------|------|------|
| `group/<dept>/<role>/memories/role.db` | 会话、任务、消息、审批 | SQLite |
| `group/<dept>/<role>/memories/*.md` | 私人长期记忆 | Markdown |
| `group/<dept>/<role>/skills/` | 技能库 | Markdown + YAML |
| `group/<dept>/<role>/reference/files_i_use.md` | 文件权限地图 | Markdown |
| `group/<dept>/<role>/<role>.md` | Soul 文件（人格定义） | Markdown + YAML |

### 3.2 核心角色定义

| 角色 ID | 类型 | 核心能力 | 调度匹配关键词 | 必要性 |
|---------|------|---------|---------------|--------|
| **suri** | 调度总监 | 需求解析、任务分发、跨部门协调、异常处理、汇总交付 | 任何用户需求的第一入口 | ** mandatory（缺失则程序无法启动）** |
| **suri-hr** | 角色管理 | 角色创建、能力分析、流程模板、组织架构维护 | 新建/修改/注销角色 | 可选（删除不影响终端对话） |
| **suri-dev** | 程序维护 | Bug修复、代码升级、性能优化、框架维护 | 平台技术问题、升级需求 | 可选（删除不影响终端对话） |
| **document-review** | 文档审核 | 文档一致性审查、变更确认、更新汇报 | 新增/修改模块后需要更新文档时 | 可选（删除不影响终端对话） |

### 3.3 角色能力边界

**suri**（central 部门负责人，所有部门的中枢）
- can：接收并解析用户需求、匹配责任部门并下发任务给总监、跟踪任务全生命周期、协调跨部门协作、处理异常回流与用户决策、汇总交付物并呈现给用户
- cannot：直接生成业务内容（代码、图像、文章等）、替用户做决策、越权操作受保护文件
- **mandatory**：`group/central/suri/suri.md` 必须存在，缺失则程序无法启动
- **调度链**：用户 → suri → 部门总监 → 成员 → 结果回流 suri → 用户。任何角色无法解决的问题最终回流到 suri，由 suri 返回给用户决策。

**suri-hr**
- can：创建新角色并初始化目录结构、分析角色应具备的能力、维护角色基本信息与索引、提供工作流程模板、执行角色注销与归档
- cannot：处理业务任务、干涉角色的具体工作方式、强制角色使用特定工具、修改主程序代码

**suri-dev**
- can：维护 suri-agent/ 核心代码、修复平台运行中的 Bug、升级框架版本、优化性能与稳定性、确保核心流程正常运行
- cannot：处理业务需求、修改角色配置、操作受保护的外部配置、介入业务角色的具体任务

**document-review**
- can：审核角色提交的文档更新、检查文档与代码一致性、生成审核报告、向用户汇报请求确认、审核通过后执行文档写入
- cannot：直接修改代码或配置文件、替用户做决策、跳过审核直接写入文档

### 3.4 角色文件夹标准结构

```
group/<department>/<role_id>/
├── <role_id>.md              # Soul 文件（人格、职责、边界、独立存储声明）
├── memories/
│   ├── role.db               # SQLite：会话、任务、消息、审批
│   └── *.md                  # 文本记忆
├── reference/
│   └── files_i_use.md        # 文件权限地图
└── skills/
    ├── skills.md             # 技能索引
    └── <skill_name>/         # 具体技能包
        ├── skill             # 技能主定义
        ├── assets/           # 静态资源
        ├── references/       # 参考文档
        └── scripts/          # 可执行脚本
```

---

## 4. 主程序架构（suri-agent/）

### 4.1 四大模块分离

| 模块 | 目录 | 职责 | 属性 |
|------|------|------|------|
| **主程序** | `suri-agent/` | 运行时框架、初期调度、接入层、基础设施 | 源代码（受保护） |
| **角色** | `group/` | 部门、总监、成员的定义与自治 | 源代码 + 运行时记忆 |
| **知识库** | `wiki/` | 用户面向的可编辑知识 | 可编辑 |
| **资源库** | `resources/` | 运行时缓存、会话、临时文件 | 运行时生成 |

### 4.2 分层架构

| 层级 | 目录 | 职责 |
|------|------|------|
| 接入层 | `access/` | 对接用户交互入口（TUI、Telegram、飞书），**只负责接收输入和显示输出** |
| 核心调度层 | `core/` | 任务调度、模型路由、审批、上下文、工具执行、文档同步 |
| 基础设施层 | `infrastructure/` | 配置加载、记忆（角色级独立存储）、安全、文件系统、日志 |
| 扩展框架 | `mcp/` | MCP 服务注册与调用，可动态扩展 |
| 角色管理 | `role/` | 角色协同调度、通信管理、搭建规则执行 |
| 模型管理 | `model/` | 模型配置、API Key 管理、首次运行引导、外部模型调用 |
| 记忆中枢 | `memory/` | 各类记忆统一存储：AI 开发记忆、未来可扩展会话/任务/交互记忆 |
| 规则执行 | `rules/` | 8 条核心业务规则，代码化执行 |
| 流程执行 | `process/` | 平台级流程，代码化执行 |
| 公共工具 | `tools/` | 跨角色可复用工具库，角色可选调用 |
| 事件钩子 | `hooks/` | 文件操作拦截器、文档监控 |
| 定时任务 | `cron/` | 定时执行脚本 |

### 4.2 模块职责详细定义

**access/** — 接入层
- `cli.py`：终端命令行客户端，**只负责接收用户输入和显示输出，不处理业务逻辑**。所有业务逻辑交给 suri 角色处理。
- `server.py`：JSON-RPC 服务端
- `rpc_methods.py`：RPC 方法定义
- `middleware.py`：请求中间件
- `telegram/bot.py`：Telegram 机器人
- `feishu/bot.py`：飞书机器人

**core/** — 核心调度层
- `task_dispatcher.py`：接收→解析→匹配部门→下发总监→跟踪→交付
- `model_router.py`：按任务类型选择模型，超时/报错时自动降级
- `context.py`：构建角色上下文，注入 Soul、技能、记忆
- `approval.py`：安全审批流程管理
- `tool_executor.py`：调用公共工具，执行角色技能中的脚本
- `doc_sync.py`：文档同步服务，检测代码变更→调用大模型生成摘要→用户确认→写入核心记忆库

**model/** — 模型管理
- `manager.py`：模型配置加载/保存、添加/删除/列出模型、设置默认模型、调用外部模型 API 生成回复
- 首次运行时引导用户配置模型参数（模型选择、API Key、端点地址）
- 支持 OpenAI 兼容格式和 Anthropic API
- 配置保存在 `model_config.json` 和 `.env` 中

**infrastructure/** — 基础设施层
- `config.py`：扫描并解析 group/、skills/、suri-agent/tools/ 中的 .md 配置
- `memory.py`：每个角色独立的 SQLite 存储 + 文本记忆文件管理
- `security.py`：调用 FileOwnershipRule 和 SecurityRule 执行权限校验
- `filesystem.py`：带安全钩子的文件操作
- `logger.py`：日志服务，中文输出，按天轮转存储于 `resources/logs/`，记录系统/调度/模型/通信等事件
- `utils.py`：通用工具函数

**mcp/** — MCP 扩展框架
- `base.py`：BaseMCPService、MCPTool 基类定义
- `registry.py`：动态加载 mcp/services/ 下的服务
- `services/`：具体服务（代码执行、文件系统、网页搜索），可自增长

**role/** — 角色管理层
- `coordinator.py`：任务分配、跨部门协作协调、依赖解析
- `messenger.py`：消息路由、格式校验、跨部门通信权限检查
- `builder.py`：角色创建、Soul 验证、目录初始化、能力分析

**rules/** — 业务规则执行代码
- `RuleEngine` 统一管理所有规则实例
- 规则直接实例化并调用，不再解析 .md 文件

**process/** — 平台流程执行代码
- `ProcessEngine` 统一管理所有流程实例
- 流程直接实例化并调用，不再解析 .md 文件

---

## 5. 规则体系（rules/）

所有规则已代码化，运行时直接执行。

| 规则 ID | 名称 | 控制角色 | 核心功能 |
|---------|------|---------|---------|
| scheduling | 调度规则 | suri | 任务入口唯一性、部门匹配、下发总监、重试升级 |
| security | 安全审批规则 | suri-dev | 监控范围、审批链、令牌验证、离线代理 |
| file_ownership | 文件所有权 | suri-dev | 路径→角色映射、权限校验、跨角色授权 |
| model_routing | 模型路由 | suri-dev | 按任务类型选模型、自动降级、连续降级告警 |
| communication_protocol | 通信协议 | suri | 消息格式校验、通道选择、跨部门权限、留存期限 |
| role_management | 角色生命周期 | suri-hr | ID验证、创建/修改/注销流程、归档清理 |
| code_commit | 代码提交规范 | suri-dev | 变更报告校验、紧急修复时限、审计追溯 |
| 文档同步规则 | 文档同步 | suri | suri-agent/ 下每个文件夹必须配有同名 .md 文件，事件发生时同步更新 |
| 核心记忆同步规则 | 核心记忆 | document-review | 每次开发完成后检测代码变更，调用大模型生成摘要，经审核、用户确认后写入 suri-agent/memory/ai-dev-memory/ |
| 文档同步自动化规则 | 文档同步 | document-review | DocSyncRule + DocWatcher 自动监控代码变更，检测缺失/过时文档，驱动大模型生成更新建议，经审核后自动写入 |

---

## 6. 流程体系（process/）

所有平台级流程已代码化，运行时直接执行。角色内部流程由角色自行定义。

| 流程 ID | 名称 | 适用场景 |
|---------|------|---------|
| workflow | 工作流与自优化 | 标准任务调度、跨部门协作、异常处理、用户决策回流、能力缺口处理、技能沉淀、自优化上报 |
| change_approval | 配置变更审批 | 变更报告准备→发起→security_admin审核→用户确认→执行→记录日志 |
| init_setup | 首次运行初始化 | 配置模型参数→可选连接 Telegram→写入 config.yaml / .env |

---

## 7. 文件所有权映射

| 路径 | 控制角色 | 说明 |
|------|---------|------|
| `group/<role>/` | role_self | 角色自身管理 Soul、技能、记忆 |
| `group/<role>/memories/` | role_self | 私人长期记忆，修改需审批 |
| `group/<role>/skills/` | role_self | 技能定义与脚本，修改需审批 |
| `group/<role>/reference/` | role_self | 个人文件权限地图 |
| `skills/` | suri | suri 专属技能库 |
| `suri-agent/tools/` | suri-dev | 公共工具库（维护） |
| `suri-agent/rules/` | suri-dev | 安全规则（代码化） |
| `suri-agent/process/` | suri-dev | 流程定义（代码化） |
| `suri-agent/` 代码目录 | suri-dev | 主程序（受保护） |
| `config.yaml` | suri-dev | 运行时参数配置 |
| `.env` | suri-dev | 环境变量与密钥 |
| `resources/` | role_self / suri | 运行时资源 |
| `wiki/` | suri-dev | 知识库（可编辑） |

---

## 8. 命名规范

### 8.1 角色 ID
- 格式：`[a-z][a-z0-9_]*`
- 示例：`suri`、`suri_hr`、`image_gen`
- 禁止：连字符 `-`、大写字母、数字开头

### 8.2 目录命名
- 项目根目录：`suri/`
- 主程序：`suri-agent/`（连字符，非 Python 包名）
- 角色目录：`group/<department>/<role_id>/`
- 技能目录：`skills/<skill_id>/` 或 `group/<role>/skills/<skill_id>/`

### 8.3 文件命名
- Soul 文件：`<role_id>.md`
- 技能主定义：`skill`（无扩展名）或 `README.md`
- 工具主定义：`tool.md`
- 规则/流程代码：`<name>.py`
- 文档文件：`<folder_name>.md`（文档同步规则）

### 8.4 版本号
- 统一格式：`x.y.z`
- 当前版本：`1.0.0`

---

## 9. 启动顺序

```
1. 加载环境变量 (.env)
2. 初始化 ConfigService（扫描 group/、skills/、tools/）
3. 初始化 MemoryService（角色级独立存储）
4. 初始化 SecurityService（规则代码执行）
5. 初始化 FileService（带安全钩子）
6. 初始化 ModelService（模型路由）
7. 初始化 ContextService（上下文构建）
8. 初始化 ModelManager（模型配置与调用）
9. 初始化 RoleManager（协同、通信、搭建）
10. 初始化 ApprovalService（审批引擎）
10. 初始化 ToolService（工具执行器）
11. 初始化 TaskService（调度引擎）
12. 初始化 MCPRegistry（MCP 扩展）
13. 启动消息监听循环
```

---

## 10. 安全边界

| 级别 | 说明 | 示例 |
|------|------|------|
| **可编辑（agent）** | agent 可按规则读写 | group/、skills/、wiki/、resources/ |
| **可编辑（需审批）** | 修改需走安全审批流程 | config.yaml、.env、suri-agent/rules/ |
| **受保护（不可编辑）** | 仅 IDE/终端修改 | suri-agent/ 核心代码（除 mcp/services/） |
| **可自增长** | 可外部扩展补充 | mcp/services/、tools/ |

---

## 11. 扩展机制

| 扩展点 | 方式 | 说明 |
|--------|------|------|
| 新增角色 | suri-hr 调用 builder.py | 按标准流程创建目录和 Soul |
| 新增技能 | 角色自行维护 | 在角色 skills/ 目录下创建 |
| 新增工具 | 开发后注册 | 放入 tools/，更新 tool_registry.md |
| 新增 MCP 服务 | 在 mcp/services/ 下创建 | 继承 BaseMCPService，自动加载 |
| 新增规则 | 修改 rules/ | 继承 BaseRule，注册到 RuleEngine |
| 新增流程 | 修改 process/ | 继承 BaseProcess，注册到 ProcessEngine |
| 核心记忆更新 | 调用 DocSyncService | 开发完成后自动检测变更，生成摘要，审核后写入 |
| 文档自动同步 | DocSyncRule + DocWatcher | 后台监控代码变更，自动检测违规项，驱动大模型更新 |

---

## 12. 变更日志

| 日期 | 变更内容 | 变更人 |
|------|---------|--------|
| 2026-04-30 | 初始化 suri-agent.md | suri |
| 2026-04-30 | 新增 model/ 模型管理模块 | suri |
| 2026-04-30 | 新增 suri-agent/memory/ai-dev-memory/ AI 开发记忆库 | suri |
| 2026-04-30 | 新增 document-review 文档审核角色 | suri |
| 2026-04-30 | 新增 core/doc_sync.py 文档同步服务 | suri |
| 2026-04-30 | 全面梳理文档同步规则：补充 16+ 个缺失的同名 .md 文档 | suri |
| 2026-04-30 | 重写 model/model.md，同步所有模块变更至 suri-agent.md | suri |
| 2026-04-30 | 新增 LoggerService 日志服务 | suri |
| 2026-04-30 | 新增 DocSyncRule 文档同步规则引擎 + DocWatcher 文件监控钩子 | suri |
| 2026-04-30 | 建立"代码变更即文档更新"自动化闭环规则 | suri |
| 2026-05-01 | 全面代码审查：修复 6 处致命错误（运行时必报错） | suri |
| 2026-05-01 | 修复 20+ 处未使用导入、5 处未使用变量、移除重复定义 | suri |
| 2026-05-01 | 修复 except Exception: pass 静默吞异常（添加日志输出） | suri |
| 2026-05-01 | 修复非 TTY 环境 input() 阻塞（setup_wizard、doc_sync） | suri |
| 2026-05-01 | 修复 model/manager.py API 响应防御性编程（KeyError/IndexError） | suri |
| 2026-05-01 | 修复 ConfigService 未扫描 wiki/ 目录、创建 3 个缺失知识库文档 | suri |
| 2026-05-01 | 补全缺失的 __init__.py（feishu、telegram、hooks） | suri |
| 2026-05-01 | 简化首次运行模型配置：提供商选择菜单 | suri |
| 2026-05-01 | 强制模型配置：无模型时程序不继续运行 | suri |
| 2026-05-01 | 两级模型选择菜单（品牌 → 型号），GLM-4 为推荐 | suri |
| 2026-05-01 | 模型自动降级：默认模型失败时自动切换备用模型 | suri |
| 2026-05-01 | 模型调用层升级：httpx + tenacity 重试 + SSE 流式输出 | suri |
| 2026-05-01 | 主循环跑通：asyncio.Queue 消息队列 + 消费者/生产者/超时检查 | suri |
| 2026-05-01 | 补单元测试：test_model_manager（14 项）+ test_task_dispatcher（10 项）| suri |
| 2026-05-01 | 调度智能化：三级部门匹配（关键词 → LLM 分类 → central 兜底）| suri |

---

## 13. 维护声明

- 本文档由 **suri** 维护。
- 任何对项目结构、角色定义、规则、流程的变更，必须同步更新本文档。
- 本文档位于 `suri-agent/suri-agent.md`，是项目的唯一权威框架定义源。
