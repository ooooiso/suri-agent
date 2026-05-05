# Suri Agent 项目目录结构

> 本文档描述 suri-agent 的完整目录结构。
> - 无标记的目录：代码仓库中的静态文件，纳入 Git 版本控制
> - `[运行时]`：程序运行过程中自动生成，不纳入版本控制
> - `[预留]`：角色/插件学习过程中可能自动创建的目录，运行时按需生成

---

## 核心设计原则

### 三层数据分离

| 层级 | 目录 | Git 管理 | 说明 |
|------|------|---------|------|
| **角色定义** | `roles/{role_id}/` | ✅ 是 | soul.md（角色定义）、skills/（技能定义）、meta.json（元数据） |
| **运行时数据** | `~/.suri/runtime/roles/{role_id}/` | ❌ 否 | adhoc/（临时会话，7天清理）、projects/（项目工作数据）、global/role.db（运行时库） |
| **系统配置** | `~/.suri/` | ❌ 否 | API Key、模型选择、日志、缓存 |

**关键规则**：
- `roles/` 只存储**角色定义和结构化数据**（Soul、技能、洞察），这些数据是"代码般的资产"
- `~/.suri/runtime/roles/` 存储**运行时数据**（会话、项目工作记忆、DB），这些数据量大、不适合 Git 管理
- 换设备时：`git clone` 获取角色定义 → 首次启动自动重建运行时目录
- 迁移指南见文档底部

### 插件目录统一

所有插件代码统一放在 `agent_framework/plugins/{type}/{name}/` 下：
- `agent_framework/plugins/access/` — 接入层
- `agent_framework/plugins/service/` — 基础服务层
- `agent_framework/plugins/execution/` — 执行层
- `agent_framework/plugins/capability/` — 能力层
- `agent_framework/plugins/extension/` — 扩展层

`plugins/`（顶层目录）已废弃，作为旧代码过渡。新插件全部创建在 `agent_framework/plugins/` 下。

---

## 代码仓库目录

```
suri-agent/                        # 项目根目录（Git 管理全部）
  - .kimi/                         # AI 开发规范，会话启动时强制读取
  - agent_framework/               # 核心层（内核插件 suri_core）
    - __init__.py
    - plugin_manager/              # 插件管理器：扫描、加载、生命周期管理
      - __init__.py
      - manager.py                 # PluginManager 实现（AST扫描、拓扑排序、热加载）
    - event_bus/                   # 事件总线：asyncio.Queue + 发布订阅
      - __init__.py
      - bus.py                     # EventBus 实现（优先级队列、SQLite持久化）
    - core/                        # 核心层子模块
      - suri_core/                 # 内核插件实现：自举注册、协调
        - __init__.py
        - plugin.py                # SuriCorePlugin 实现
        - manifest.json            # 内核插件清单
    - migrations/                  # 数据库迁移脚本（按版本号排序）
      - 001_initial.sql            # 初始 schema
      - 002_agents.sql             # Agent 注册表
      - runner.py                  # 迁移执行器
    - plugins/                     # ⭐ 插件层（按类型分子目录）
      - access/                    # 统一接入层（CLI / Telegram）
        - __init__.py
        - manifest.json
        - plugin.py                # 插件主入口（共用路由层）
        - cli.py                   # CLI 通道（线程分离异步输入 + 状态面板 + 恢复菜单）
        - wizard.py                # 首次运行配置向导
        - config_editor.py         # 运行时配置编辑器（/reconfig 菜单 + /setkey）
        - telegram.py              # Telegram 通道
        - telegram_bot.py          # Bot API 封装
        - base.py                  # 接入通道基类 ✅
        - formatter.py             # 共用格式化器 ✅
        - session_hub.py           # 会话 Hub ✅（迭代 1 新增）
        - channels/                # 通道路由层 ✅（迭代 1 新增）
          - __init__.py
          - ...                    # 各通道具体实现
      - service/                   # 基础服务层（无业务逻辑）
        - config_service/
          - __init__.py
          - manifest.json
          - plugin.py              # 配置读写、热重载（文件监听+变更通知+子树隔离）
        - log_service/
          - __init__.py
          - manifest.json
          - plugin.py              # 分级日志、分类归档
        - security_service/
          - __init__.py
          - manifest.json
          - plugin.py              # AST 扫描 + 沙箱权限校验
      - execution/                 # 执行层（任务调度、Agent管理）
        - task_scheduler/
          - __init__.py
          - manifest.json
          - plugin.py              # 任务调度引擎
        - task_planner/
          - __init__.py
          - manifest.json
          - plugin.py              # 任务分解与规划（模板匹配+LLM规划）
        - agent_registry/
          - __init__.py
          - manifest.json
          - plugin.py              # Agent 生命周期管理
        - role_comm/
          - __init__.py
          - manifest.json
          - plugin.py              # 角色间通信
        - interrupt_handler/
          - __init__.py
          - manifest.json
          - plugin.py              # 中断与用户决策
        - code_tool/
          - __init__.py
          - manifest.json
          - plugin.py              # 事件路由（只读 + 写入）
          - reader.py              # read_file（迭代 1）
          - explorer.py            # list_dir（迭代 1）
          - search.py              # grep（迭代 1）
          - stats.py               # stat_project（迭代 1）
          - writer.py              # write_file / append_file / create_file ✅
      - capability/                # 能力层（AI 核心能力）
        - llm_gateway/
          - __init__.py
          - manifest.json
          - plugin.py              # 网关主逻辑（含客户端、路由、切换）
        - memory_service/
          - __init__.py
          - manifest.json
          - plugin.py              # 记忆存储与检索（向量记忆+类型分类+重要性评分）
        - role_manager/
          - __init__.py
          - manifest.json
          - plugin.py              # 角色全生命周期管理（Soul管理+上下文管理+工具说明注入）
          - soul_parser.py         # Soul.md YAML frontmatter 解析器
        - mcp_framework/
          - __init__.py
          - manifest.json
          - plugin.py              # MCP 工具服务框架
      - extension/                 # 扩展层（测试、文档、钩子）
        - test_framework/
          - __init__.py
          - manifest.json
          - plugin.py              # 测试框架（EventBusFixture、TestBase、PluginTestHarness）
        - upgrade_manager/
          - __init__.py
          - manifest.json
          - plugin.py              # 插件自升级管理
  - agent_framework/shared/          # 公共层（禁止包含业务逻辑）
    - __init__.py
    - interfaces/                  # 插件接口定义
      - __init__.py
      - plugin.py                  # PluginInterface
    - utils/                       # 通用工具
      - __init__.py
      - event_types.py             # Event / Priority 定义（不含 EventType，使用字符串事件类型）
  - prd/                           # 产品文档（AI 开发前读取）
    - README.md                    # PRD 总索引
    - overview/                    # 总览文档
      - architecture.md            # 架构设计
      - design-principles.md       # 设计原则
      - terminology.md             # 术语表
    - operations/                  # 运维文档
      - deployment.md              # 部署指南
      - directory-structure.md     # 本文档
      - framework-rules.md         # 框架运行规则
      - hot-reload.md              # 热更新机制
      - plugin-development.md      # 插件开发规范
      - program-flow.md            # 程序级主流程
      - startup.md                 # 启动流程
      - system-flow.md             # 系统级流程
    - agents/                      # 角色/Agent 文档
      - agent-overview.md          # Agent 总览
      - skill-spec.md              # 技能规范
      - skills-overview.md         # 技能总览
      - soul-spec.md               # Soul 规范
      - workflow.md                # 角色工作流
      - skill-composition.md       # 技能组合
      - skill-development.md       # 技能开发
    - collaboration/               # 协作文档
      - collab-patterns.md         # 协作模式
      - conflict-resolution.md     # 冲突解决
      - project-workflow.md        # 项目工作流
      - workspace.md               # 工作区
    - evolution/                   # 进化文档
      - coevolution.md             # 协同进化
      - plugin-evolution.md        # 插件进化
      - skill-evolution.md         # 技能进化
      - soul-evolution.md          # Soul 进化
      - tool-evolution.md          # 工具进化
    - schema/                      # Schema 文档
      - database.md                # 数据库 Schema
      - event-registry.md          # 事件注册表
      - template-spec.md           # 模板规范
      - template-auto-update.md    # 模板自动更新
    - security/                    # 安全文档
      - audit-trail.md             # 审计日志
      - permission-model.md        # 权限模型
      - security-spec.md           # 安全规范
    - plugins/                     # 各插件详细 PRD
      - README.md
      - access/                    # access 插件 PRD
        - access.md
        - channel-capabilities.md
        - session-hub.md
        - session-protocol.md
        - channels/                # 各通道 PRD
      - capability/                # 能力插件 PRD
        - llm_gateway.md
        - memory_service.md
        - role_manager.md
        - mcp_framework.md
        - mcp_protocol.md
        - knowledge_base.md
        - role_learner.md
        - tool_development.md
        - upgrade_manager.md
        - wiki_service.md
        - builtin_services.md
      - core/                      # 内核插件 PRD
        - suri_core.md
      - execution/                 # 执行插件 PRD
        - agent_registry.md
        - code_tool.md
      - service/                   # 服务插件 PRD
      - extension/                 # 扩展插件 PRD
  - roles/                         # ⭐ 所有角色数据（Git 管理，换设备 git clone 全回来）
    - suri/                        # 核心角色
      - soul.md                    # 角色人格定义（YAML frontmatter + Markdown）
      - meta.json                  # 角色元数据（type / created_at）
      - memories/                  # 角色记忆
        - insights/                # 角色学习洞察
      - skills/                    # 角色技能（学习进化出的能力）
    - {role_id}/                   # 其他角色（由 role_manager 创建）
      - soul.md
      - meta.json
      - memories/
      - skills/
  - works/                         # [预留] 项目工作区（运行时按 project_id 创建）
    - README.md
  - tests/                         # 测试代码
    - __init__.py
    - framework/                   # 测试框架基类
      - __init__.py
      - base.py                    # AsyncTestCase + EventCollector ✅
    - unit/                        # 单元测试
      - __init__.py
      - test_event_bus.py
      - test_plugin_manager.py
      - test_code_tool_modules.py
      - test_healthcheck.py        # 健康检查测试
    - plugin/                      # 插件测试
      - __init__.py
      - test_code_tool.py
      - test_security_service.py
      - test_access.py
      - test_access_events.py
      - test_code_tool_events.py
      - test_llm_gateway.py
      - test_role_manager.py
      - test_role_comm.py
      - test_memory_service.py
      - test_interrupt_handler.py
      - test_task_planner.py
  - main.py                        # 入口文件（<20 行）
  - requirements.txt               # Python 依赖（尽量保持为零依赖）
  - .env.example                   # 环境变量示例
  - README.md                      # 项目说明
  - DEV-PLAN.md                    # 开发计划
  - AUDIT-REPORT.md                # 审计报告
  - PROJECT_STRUCTURE.md           # 项目结构说明
  - .gitignore
```

---

## 系统配置目录（`~/.suri/`）

> 只放系统级配置和日志，**不包含角色数据**。
> 不纳入 Git 版本控制。

```
~/.suri/                           # 系统运行时根目录
  - config.json                    # 用户配置（API Key、模型选择、通道配置）
  - runtime/
    - suri.db                      # 中央 SQLite 数据库（事件记录、审计日志）
    - logs/                        # 系统日志
      - {plugin_name}/             # 按插件分目录
    - sessions/                    # 会话历史
    - backup/                      # 自动备份
```

---

## 迁移指南

```bash
# 换设备时，只需要两步：

# 1. 克隆代码仓库（角色数据全在里面）
git clone https://github.com/ooooiso/suri-agent.git

# 2. 复制系统配置（API Key 等）
cp -r ~/.suri/ 新电脑的 ~/.suri/
```

**角色的所有记忆、技能、学习成果都在 `suri-agent/roles/` 下，随 Git 一起迁移。**

---

## 目录创建时机

| 目录 | 创建时机 | 创建者 |
|------|----------|--------|
| `~/.suri/` | 首次运行 `main.py` | main.py |
| `~/.suri/config.json` | 首次运行向导 | ConfigWizard（access 插件） |
| `~/.suri/runtime/` | 首次运行 | suri_core |
| `~/.suri/runtime/suri.db` | 首次运行 | suri_core（含迁移） |
| `~/.suri/runtime/logs/` | 首次运行 | log_service |
| `~/.suri/runtime/sessions/` | 首次会话时 | access |
| `~/.suri/runtime/backup/` | 首次备份时 | 运维脚本 |
| `roles/suri/memories/` | 首次运行 | role_manager |
| `roles/suri/skills/` | 角色学习进化时 | role_learner |
| `roles/{role_id}/` | 创建角色时 | role_manager |
| `works/{project_id}/` | 创建项目时 | project-workflow |

---

## 设计原则

1. **角色数据在 Git 中**：所有角色的记忆、技能、学习成果保存在 `roles/` 下，`git commit` 版本控制，换设备 `git clone` 全回来
2. **系统配置在 `~/.suri/`**：API Key 等敏感信息不纳入 Git，防止误提交
3. **角色隔离**：每个角色的数据在独立目录中，禁止跨角色直接访问
4. **插件自治**：每个插件的运行时数据在 `~/.suri/runtime/plugins/{plugin_id}/` 中，由插件自行管理
5. **预留最小化**：`[预留]` 目录按需创建，不预先生成空目录