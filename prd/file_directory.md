# Suri Agent 项目目录结构

> 本文档描述 suri-agent 的完整目录结构。
> - 无标记的目录：代码仓库中的静态文件
> - `[运行时]`：程序首次运行或动态创建，不纳入版本控制
> - `[预留]`：角色/插件学习过程中可能自动创建的目录，运行时按需生成

---

## 代码仓库目录

```
suri-agent/                        # 项目根目录
  - .kimi/                         # AI 开发规范，会话启动时强制读取
  - agent_framework/               # 核心层（内核插件 suri_core）
    - plugin_manager/              # 插件管理器：扫描、加载、生命周期管理
    - event_bus/                   # 事件总线：asyncio.Queue + 发布订阅
    - suri_core_plugin/            # 内核插件实现：自举注册、协调
    - migrations/                  # 数据库迁移脚本（按版本号排序）
  - plugins/                       # 插件层（20 个插件）
    - access/                      # 统一接入层（CLI / Web / Telegram / Lark / API）
      - cli.py
      - web.py
      - telegram.py
      - lark.py
      - api.py
    - config_service/              # 配置管理
    - log_service/                 # 日志与审计
    - security_service/            # 安全沙箱与权限
    - task_scheduler/              # 任务调度引擎
    - task_planner/                # 任务分解与规划
    - agent_registry/              # Agent 生命周期管理
    - role_comm/                   # 角色间通信
    - interrupt_handler/           # 中断与用户决策
    - llm_gateway/                 # LLM 网关
    - memory_service/              # 记忆存储与检索
    - role_manager/                # 角色全生命周期管理
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
      - plugin.py
      - reader.py
      - explorer.py
      - search.py
      - stats.py
      - writer.py                  # [迭代 2 解锁]
      - test_runner.py             # [迭代 2 解锁]
      - executor.py                # [迭代 2 解锁]
    - suri_core/                   # 内核插件（与 agent_framework/ 协同）
  - shared/                        # 公共层（禁止包含业务逻辑）
    - interfaces/                  # 插件接口定义（PluginInterface 等）
    - utils/                       # 通用工具（日志、配置、事件类型等）
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
    - plugins/                     # 20 个插件的详细 PRD
  - roles/                         # 角色模板目录（首次运行时复制到 ~/.suri/runtime/roles/）
    - suri/                        # 核心角色模板
      - soul.md                    # 核心角色 Soul
      - memories/                  # [预留] 运行时生成 role.db + insights/
      - skills/                    # [预留] 运行时生成技能文件
    - {role_id}/                   # [预留] 其他角色模板（由 role_manager 创建时生成）
      - soul.md
      - memories/
      - skills/
  - works/                         # [预留] 项目工作区（运行时按 project_id 创建）
    - {project_id}/                # 单个项目目录
      - .meta.json                 # 项目元数据
      - prd.md                     # 项目需求
      - plan/                      # 任务规划
      - output/                    # 角色输出成果
      - logs/                      # 项目级日志
  - tests/                         # 测试代码
    - framework/                   # 测试框架基类（TestBase、fixtures、utils、harness）
    - unit/                        # 单元测试
    - integration/                 # 集成测试
    - plugin/                      # 插件测试
    - fullforce/                   # 压力测试
  - resources/                     # [预留] 资源文件（运行时生成）
    - test_reports/                # [运行时] 测试报告输出目录
  - main.py                        # 入口文件（<20 行）
  - requirements.txt               # Python 依赖（尽量保持为零依赖）
  - .env.example                   # 环境变量示例
  - README.md                      # 项目说明
```

---

## 运行时目录（`~/.suri/`）

> 以下目录在首次运行 `python main.py` 时自动创建，不纳入代码版本控制。

```
~/.suri/                           # [运行时] 系统运行时根目录
  - config.json                    # [运行时] 用户配置（模型、通道、偏好）
  - runtime/                       # [运行时] 运行时数据
    - suri.db                      # [运行时] 中央 SQLite 数据库（插件/事件/消息/审计）
    - roles/                       # [运行时] 角色运行时数据（从 roles/ 模板复制）
      - suri/                      # [运行时] 核心角色运行时数据
        - soul.md
        - memories/
          - role.db                # [运行时] 角色级 SQLite 数据库
          - insights/              # [运行时] RoleLearner 生成的洞察文件
        - skills/                  # [运行时] 技能模板文件
        - scripts/                 # [预留] 角色学习后自定义脚本
        - reference/               # [预留] 角色学习后收集的参考资料
        - output/                  # [运行时] 角色输出文件
      - {role_id}/                 # [运行时] 其他角色运行时数据
        - soul.md
        - memories/
          - role.db
          - insights/
        - skills/
        - scripts/                 # [预留]
        - reference/               # [预留]
        - output/
    - plugins/                     # [运行时] 动态插件运行时数据
      - {plugin_id}/               # [运行时] 各插件私有运行时目录
    - logs/                        # [运行时] 系统日志
      - {plugin_name}/             # [运行时] 按插件分目录
    - sessions/                    # [运行时] 会话历史
  - data/                          # [运行时] 持久化数据
    - upgrade_reports/             # [运行时] 升级报告存储
  - backup/                        # [运行时] 自动备份
```

---

## 运行时目录创建时机

| 目录 | 创建时机 | 创建者 |
|------|----------|--------|
| `~/.suri/` | 首次运行 `main.py` | main.py |
| `~/.suri/config.json` | 首次运行向导 | access / 用户 |
| `~/.suri/runtime/` | 首次运行 | suri_core |
| `~/.suri/runtime/suri.db` | 首次运行 | suri_core（含迁移） |
| `~/.suri/runtime/roles/suri/` | 首次运行 | role_manager |
| `~/.suri/runtime/roles/{role_id}/` | 创建角色时 | role_manager |
| `~/.suri/runtime/plugins/{plugin_id}/` | 加载动态插件时 | plugin_manager |
| `~/.suri/runtime/logs/` | 首次运行 | log_service |
| `~/.suri/runtime/sessions/` | 首次会话时 | access |
| `~/.suri/data/upgrade_reports/` | 首次生成升级报告时 | upgrade_manager |
| `~/.suri/backup/` | 首次备份时 | 运维脚本 |
| `works/{project_id}/` | 创建项目时 | work_flow / Project Director |
| `roles/{role_id}/scripts/` | 角色学习生成脚本时 | role_learner |
| `roles/{role_id}/reference/` | 角色收集参考资料时 | 角色自身 |

---

## 设计原则

1. **代码与数据分离**：代码仓库中只保留静态模板（`role/suri/`），运行时数据全部放在 `~/.suri/runtime/`
2. **角色隔离**：每个角色的数据在独立目录中，禁止跨角色直接访问
3. **插件自治**：每个插件的运行时数据在 `~/.suri/runtime/plugins/{plugin_id}/` 中，由插件自行管理
4. **预留最小化**：`[预留]` 目录按需创建，不预先生成空目录
