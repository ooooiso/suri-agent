# Suri Agent 项目目录结构

> 本文档描述 suri-agent 的完整目录结构。
> - 无标记的目录：代码仓库中的静态文件，纳入 Git 版本控制
> - `[运行时]`：程序运行过程中自动生成，不纳入版本控制
> - `[预留]`：角色/插件学习过程中可能自动创建的目录，运行时按需生成

---

## 核心设计原则

**所有角色数据保存在项目根目录 `roles/` 下**，纳入 Git 版本控制。
这样换设备时 `git clone` + `git pull`，角色的所有记忆、技能、学习成果都在。

`~/.suri/` 只放系统级配置（API Key 等敏感信息）和日志，不纳入 Git。

---

## 代码仓库目录

```
suri-agent/                        # 项目根目录（Git 管理全部）
  - .kimi/                         # AI 开发规范，会话启动时强制读取
  - agent_framework/               # 核心层（内核插件 suri_core）
    - __init__.py
    - plugin_manager/              # 插件管理器：扫描、加载、生命周期管理
      - __init__.py
      - manager.py                 # PluginManager 实现
    - event_bus/                   # 事件总线：asyncio.Queue + 发布订阅
      - __init__.py
      - bus.py                     # EventBus 实现
    - core/                        # 核心层子模块
      - suri_core/                 # 内核插件实现：自举注册、协调
        - __init__.py
        - plugin.py                # SuriCorePlugin 实现
        - manifest.json            # 内核插件清单
    - migrations/                  # 数据库迁移脚本（按版本号排序）
      - 001_initial.sql            # 初始 schema
  - agent_framework/plugins/                       # 插件层（20 个插件）
    - access/                      # 统一接入层（CLI / Web / Telegram / Lark / API）
      - __init__.py
      - manifest.json
      - plugin.py                  # 插件主入口（共用路由层）
      - cli.py                     # CLI 通道（线程分离异步输入 + 状态面板 + 恢复菜单）
      - wizard.py                  # 首次运行配置向导
      - config_editor.py           # 运行时配置编辑器（/reconfig 菜单 + /setkey）
      - telegram.py                # Telegram 通道
      - telegram_bot.py            # Bot API 封装
      - base.py                    # 接入通道基类 ✅（迭代 1 已实现）
      - formatter.py               # 共用格式化器 ✅（迭代 1 新增）
      - web.py                     # [迭代 2]
      - lark.py                    # [迭代 2]
      - api.py                     # [迭代 2]
    - config_service/              # 配置管理
      - __init__.py
      - manifest.json
      - plugin.py                  # 配置读写、热重载
      - store.py                   # [迭代 2] 配置存储拆分
    - log_service/                 # 日志与审计
      - __init__.py
      - manifest.json
      - plugin.py                  # 分级日志、分类归档
      - logger.py                  # [迭代 2] 日志器拆分
    - security_service/            # 安全沙箱与权限
      - __init__.py
      - manifest.json
      - plugin.py                  # AST 扫描 + 沙箱逻辑
    - task_scheduler/              # 任务调度引擎
    - task_planner/                # 任务分解与规划
    - agent_registry/              # Agent 生命周期管理
    - role_comm/                   # 角色间通信
    - interrupt_handler/           # 中断与用户决策
    - llm_gateway/                 # LLM 网关
      - __init__.py
      - manifest.json
      - plugin.py                  # 网关主逻辑（含客户端、路由、切换）
      - client/                    # [迭代 2] 各厂商客户端拆分
      - router.py                  # [迭代 2] 模型路由
      - cache.py                   # [迭代 2] 响应缓存
      - retry.py                   # [迭代 2] 重试逻辑
    - memory_service/              # 记忆存储与检索
    - role_manager/                # 角色全生命周期管理
      - __init__.py
      - manifest.json
      - plugin.py                  # 角色管理主逻辑
      - soul_parser.py             # Soul.md YAML frontmatter 解析器
      - creator.py                 # [迭代 2] 角色创建逻辑拆分
    - role_learner/                # 角色自主学习
    - mcp_framework/               # MCP 工具服务框架
      - services/                  # 内置工具服务
    - upgrade_manager/             # 插件自升级管理
    - cron_service/                # 定时任务
    - hooks_service/               # 事件钩子
    - test_framework/              # 测试框架
    - doc_sync/                    # 文档同步
    - code_tool/                   # 代码工具：安全文件读写
      - manifest.json
      - plugin.py                  # 事件路由（只读 + 写入）
      - reader.py                  # read_file（迭代 1）
      - explorer.py                # list_dir（迭代 1）
      - search.py                  # grep（迭代 1）
      - stats.py                   # stat_project（迭代 1）
      - writer.py                  # write_file / append_file / create_file ✅（迭代 1 已实现）
      - test_runner.py             # [迭代 2 解锁]
      - executor.py                # [迭代 2 解锁]
  - agent_framework/shared/          # 公共层（禁止包含业务逻辑）
    - __init__.py
    - interfaces/                  # 插件接口定义
      - __init__.py
      - plugin.py                  # PluginInterface
    - utils/                       # 通用工具
      - __init__.py
      - event_types.py             # Event / Priority / EventType 定义
      - log.py                     # [迭代 2] 日志工具
      - db.py                      # [迭代 2] 数据库工具
  - prd/                           # 产品文档（AI 开发前读取）
    - README.md                    # PRD 总索引
    - framework.md                 # 框架核心
    - rules.md                     # 系统运行铁律
    - process.md                   # 标准业务流程
    - program_flow.md              # 程序级主流程
    - role_workflow.md             # 单角色工作流
    - work_flow.md                 # 项目级工作流
    - learning_flow.md             # 学习机制
    - deployment.md                # 部署指南
    - plugin_development.md        # 插件开发规范
    - database_schema.md           # 数据库 Schema
    - event_registry.md            # 事件注册表
    - security_spec.md             # 安全规范
    - file_directory.md            # 本文档
    - agent_framework/plugins/                     # 20 个插件的详细 PRD
  - roles/                         # ⭐ 所有角色数据（Git 管理，换设备 git clone 全回来）
    - suri/                        # 核心角色
      - soul.md                    # 角色人格定义（YAML frontmatter + Markdown）
      - memories/                  # 角色记忆
        - role.db                  # 角色级 SQLite 数据库
        - insights/                # 角色学习洞察（从对话中提取的知识）
      - skills/                    # 角色技能（学习进化出的能力）
      - scripts/                   # 角色自定义脚本
      - reference/                 # 角色参考资料
      - output/                    # 角色输出文件（生成的代码、文档等）
    - {role_id}/                   # 其他角色（由 role_manager 创建）
      - soul.md
      - memories/
        - role.db
        - insights/
      - skills/
      - scripts/
      - reference/
      - output/
  - works/                         # [预留] 项目工作区（运行时按 project_id 创建）
    - {project_id}/                # 单个项目目录
      - .meta.json                 # 项目元数据
      - prd.md                     # 项目需求
      - plan/                      # 任务规划
      - output/                    # 角色输出成果
      - logs/                      # 项目级日志
  - tests/                         # 测试代码
    - __init__.py
    - framework/                   # 测试框架基类
      - __init__.py
      - base.py                    # AsyncTestCase + EventCollector ✅（迭代 1 已实现）
      - fixtures.py                # [迭代 2] 测试夹具
    - unit/                        # 单元测试
      - __init__.py
      - test_event_bus.py          # EventBus 测试
      - test_plugin_manager.py     # PluginManager 测试
      - test_code_tool_modules.py  # code_tool 模块测试
    - integration/                 # 集成测试
      - __init__.py
    - plugin/                      # 插件测试
      - __init__.py
      - test_code_tool.py          # code_tool 插件测试
      - test_security_service.py   # security_service 插件测试
      - test_access.py             # access 插件测试（CLISession、ConfigEditor、ConfigWizard）
      - test_access_events.py      # access 事件处理测试 ✅（迭代 1 新增）
      - test_code_tool_events.py   # code_tool 事件处理 + writer 测试 ✅（迭代 1 新增）
      - test_llm_gateway.py        # llm_gateway 插件测试（初始化、切换、聊天、事件处理）
      - test_role_manager.py       # role_manager 插件测试（角色 CRUD、事件处理、命令）
    - fullforce/                   # 压力测试
      - __init__.py
  - resources/                     # [预留] 资源文件（运行时生成）
    - test_reports/                # [运行时] 测试报告输出目录
  - main.py                        # 入口文件（<20 行）
  - requirements.txt               # Python 依赖（尽量保持为零依赖）
  - .env.example                   # 环境变量示例
  - README.md                      # 项目说明
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
    - agent_framework/plugins/                     # 动态插件运行时数据
      - {plugin_id}/
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
| `~/.suri/runtime/agent_framework/plugins/{plugin_id}/` | 加载动态插件时 | plugin_manager |
| `~/.suri/runtime/backup/` | 首次备份时 | 运维脚本 |
| `roles/suri/memories/` | 首次运行 | role_manager |
| `roles/suri/skills/` | 角色学习进化时 | role_learner |
| `roles/suri/scripts/` | 角色生成脚本时 | role_learner |
| `roles/suri/reference/` | 角色收集资料时 | 角色自身 |
| `roles/suri/output/` | 角色输出文件时 | 角色自身 |
| `roles/{role_id}/` | 创建角色时 | role_manager |
| `works/{project_id}/` | 创建项目时 | work_flow / Project Director |

---

## 设计原则

1. **角色数据在 Git 中**：所有角色的记忆、技能、学习成果保存在 `roles/` 下，`git commit` 版本控制，换设备 `git clone` 全回来
2. **系统配置在 `~/.suri/`**：API Key 等敏感信息不纳入 Git，防止误提交
3. **角色隔离**：每个角色的数据在独立目录中，禁止跨角色直接访问
4. **插件自治**：每个插件的运行时数据在 `~/.suri/runtime/agent_framework/plugins/{plugin_id}/` 中，由插件自行管理
5. **预留最小化**：`[预留]` 目录按需创建，不预先生成空目录