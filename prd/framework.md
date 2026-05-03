# 框架核心说明

## 架构概述

- 单进程插件化架构
- **所有功能实体均为插件**，suri_core 是"内核插件"而非特殊框架
- **21 个插件**分 5 层：内核层(1) + 基础服务层(3) + 执行层(5) + 能力层(6) + 接入层(1) + 扩展层(4) + 工具层(1: code_tool)
- 插件通过事件总线通信
- 本地运行，零依赖，mac 优先

## 系统支持

- 目前仅需要支持macos系统

## 数据存储

### 存储分层

| 层级 | 位置 | 用途 |
|------|------|------|
| 用户数据 | `~/.suri/data/` | SQLite 数据库、配置文件、升级报告 |
| 运行时数据 | `~/.suri/runtime/` | 角色实例、动态插件、会话缓存 |
| 临时数据 | `/tmp/suri-agent/` | 解压文件、临时缓存 |
| 备份数据 | `~/.suri/backup/` | 代码变更快照 |

### SQLite 表结构

- `plugins` — 插件注册表（名称、版本、路径、状态、类型），归属：suri_core
- `events` — 事件日志（时间、来源、目标、事件类型、内容），归属：suri_core
- `messages` — 通信记录（会话 ID、角色、消息内容、时间），归属：role_comm
- `changes` — 代码变更审计（变更者、文件路径、变更前、变更后、时间），归属：security_service
- `agents` — Agent 注册表（agent_id、任务、状态、父子关系），归属：agent_registry
- `agent_steps` — Agent 步骤（步骤 ID、Agent、状态、依赖），归属：agent_registry

### 文件存储

- 角色 Soul：`~/.suri/runtime/roles/{role_id}/soul.md`
- 角色技能：`~/.suri/runtime/roles/{role_id}/skills/{skill_name}.json`
- 角色记忆：`~/.suri/runtime/roles/{role_id}/memories/role.db`
- 角色洞察：`~/.suri/runtime/roles/{role_id}/insights/`
- 动态插件：`~/.suri/runtime/plugins/{plugin_name}/`
- 日志文件：`~/.suri/runtime/logs/{YYYYMMDD}.log`
- 会话历史：`~/.suri/runtime/sessions/{session_id}.jsonl`
- 升级报告：`~/.suri/data/upgrade_reports/`

## 启动流程

```
main.py（极简入口，非插件，<20 行）
    │
    ▼
实例化 SuriCorePlugin（内核插件）
    │
    ▼
bootstrap()：
  ├─ 创建 EventBus（含内部分发逻辑）
  ├─ 创建 PluginManager
  ├─ 自注册：suri_core 注册为第一个插件
  └─ 扫描并加载其他插件
    │
    ▼
系统就绪，等待事件
```

```python
# main.py
import asyncio
from suri_core import SuriCorePlugin

async def main():
    core = SuriCorePlugin()
    await core.bootstrap()
    await core.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## 热更新机制

详见 `prd/hot_reload_rules.md`。

核心原则：
1. **零硬编码** — 所有可变数据必须外部化到文件/数据库/配置中
2. **事件驱动热更新** — 数据变更后通过 EventBus 发布事件，相关插件自动刷新
3. **版本协商** — 插件间通过 manifest.json 声明兼容版本，启动时校验
4. **统一升级通道** — 所有运行时自修改通过 upgrade_manager 统一管理

### 当前硬编码问题清单

| # | 位置 | 硬编码内容 | 应外部化到 | 优先级 |
|---|------|-----------|-----------|--------|
| 1 | `plugins/role_manager/plugin.py` | `SOUL_TEMPLATE` 字符串 | `~/.suri/data/templates/soul_template.md` | 🔴 高 |
| 2 | `plugins/role_manager/plugin.py` | `_get_system_prompt()` 中的工具调用说明 | `~/.suri/data/templates/tool_descriptions.yaml` | 🔴 高 |
| 3 | `plugins/task_planner/plugin.py` | `_load_builtin_templates()` 中的内置模板 | `~/.suri/data/templates/task_templates.yaml` | 🔴 高 |
| 4 | `plugins/interrupt_handler/plugin.py` | `_classify_reason()` 中的关键词列表 | `~/.suri/data/configs/interrupt_keywords.yaml` | 🟡 中 |
| 5 | `plugins/access/plugin.py` | 通道路由逻辑 | `~/.suri/data/configs/channel_routes.yaml` | 🟡 中 |

### 热更新事件流

```
配置变更 → config_service 发布 config.updated 事件
    │
    ▼
相关插件订阅 config.updated
    ├── 重新加载配置
    ├── 更新内存状态
    └── 继续处理新请求（不影响正在进行的任务）
```

## 解耦设计原则

详见 `prd/decoupling_principles.md`。

核心原则：
1. **插件间仅通过 EventBus 通信** — 禁止直接调用其他插件的方法
2. **数据与逻辑分离** — 配置/模板/关键词等数据外部化，逻辑只处理数据
3. **每个插件可独立迭代** — 通过 manifest.json 版本声明 + 事件契约保证兼容
4. **迭代通知机制** — 插件升级后发布 `plugin.upgraded` 事件，框架自动协调

### 角色与插件解耦

```
角色 (Role) = 数据（Soul 文件、技能、记忆）
插件 (Plugin) = 逻辑（处理事件、调用 LLM、操作文件）

角色不包含逻辑，插件不包含角色数据
```

- 插件不绑定特定角色
- 角色切换只影响 system prompt 和上下文，不影响插件运行
- 新增角色不需要修改任何插件代码

### 插件版本协商

```json
{
  "name": "task_planner",
  "version": "1.2.0",
  "api_version": "1.0",
  "provides_interfaces": ["TaskPlanner"],
  "requires_interfaces": {
    "llm_gateway": ">=1.0.0",
    "role_manager": ">=1.0.0"
  },
  "event_contract": {
    "publishes": ["task.planned", "task.plan_updated"],
    "subscribes": ["task.plan_requested", "task.replan_requested"]
  }
}
```

## 基础框架需求

### 配置管理

- 配置优先级：环境变量 > `~/.suri/config.json` > 默认值
- 配置热更新：运行时修改无需重启
- 配置校验：启动时检查必填项

### 日志系统

- 分级：DEBUG / INFO / WARN / ERROR
- 输出：终端 + 文件（`~/.suri/runtime/logs/`）
- 轮转：按日期分割，保留 30 天
- 插件日志：每个插件独立日志文件

### 错误处理

- 插件崩溃隔离：单个插件异常不影响核心
- 错误事件：异常转为事件广播，由对应插件处理
- 重试机制：task_scheduler 统一控制重试次数和退避策略
- 降级策略：服务失败时切换到备用方案

### 错误码规范

全局错误码体系，所有插件统一使用：

| 错误码段 | 类别 | 说明 |
|----------|------|------|
| `1000-1099` | 系统级 | suri_core / EventBus / PluginManager |
| `1100-1199` | 基础服务 | config_service / log_service / security_service |
| `1101` | `security.read_denied` | security_service 读权限拒绝 |
| `1102` | `security.write_denied` | security_service 写权限拒绝 |
| `2000-2099` | 任务调度 | task_scheduler / task_planner |
| `2100-2199` | Agent | agent_registry / interrupt_handler |
| `2200-2299` | 通信 | role_comm |
| `3000-3099` | LLM | llm_gateway |
| `3100-3199` | 工具 | mcp_framework / code_tool |
| `4000-4099` | 角色 | role_manager / role_learner |
| `4100-4199` | 元学习 | upgrade_manager |
| `5000-5099` | 接入 | access |
| `5100-5199` | 扩展 | cron_service / hooks_service / test_framework / doc_sync |
| `9000-9099` | 通用 | 跨插件通用错误 |

**错误响应格式标准**：

```json
{
  "error_code": 1001,
  "error_type": "system.plugin_load_failed",
  "message": "插件加载失败：AST 扫描未通过",
  "plugin_id": "xxx_plugin",
  "retryable": false,
  "timestamp": "2026-05-02T15:51:00+08:00"
}
```

**通用错误码（9000 段）**：

| 错误码 | 错误类型 | 说明 | 重试建议 |
|--------|---------|------|---------|
| `9000` | `general.unknown` | 未知错误 | 否 |
| `9001` | `general.timeout` | 操作超时 | 是 |
| `9002` | `general.invalid_param` | 参数无效 | 否 |
| `9003` | `general.unauthorized` | 未授权 | 否 |
| `9004` | `general.not_found` | 资源不存在 | 否 |
| `9005` | `general.duplicate` | 资源重复 | 否 |
| `9006` | `general.busy` | 系统繁忙 | 是（退避）|
| `9007` | `general.insufficient_resource` | 资源不足 | 否 |
| `9008` | `general.dependency_failed` | 依赖服务失败 | 是 |
| `9009` | `general.cancelled` | 操作被取消 | 否 |

各插件 PRD 中定义本插件特有的错误码。

### 插件生命周期

```
扫描 → 加载 → 初始化 → 注册 → 运行 → 暂停 → 卸载 → 清理
```

- 扫描：plugin_manager 读取 plugins/ 和 ~/.suri/runtime/plugins/
- 加载：import 插件模块
- 初始化：调用插件 init()，传入 event_bus 和配置
- 注册：插件声明订阅的事件类型
- 运行：开始接收和处理事件
- 暂停：暂停事件处理（保留状态）
- 卸载：停止事件处理，调用 cleanup()
- 清理：移除注册，释放资源

### 插件自修改流程

**所有插件（包括 suri_core）运行时修改代码，必须遵循**：

1. **自分析**：插件通过 PluginSelfLearning 分析自身性能/错误/调用模式
2. **生成方案**：产出升级方案（变更原因、具体变更、回滚策略、风险评估）
3. **suri 呈现**：suri 角色汇总方案，向用户说明升级理由和影响
4. **用户确认**：用户批准后方可执行
5. **执行变更**：IDE 模式生成变更文件，或代码补丁方式应用
6. **验证**：
   - 普通插件：健康检查、基础功能测试
   - suri_core：必须通过冒烟测试（EventBus + PluginManager 基础功能验证）
7. **生效**：热更新或重启

**关键约束**：
- 无插件可私自修改代码
- 所有升级方案必须包含回滚策略
- suri_core 涉及核心逻辑的变更可能需要重启

### 安全沙箱

- 代码审查：动态插件加载前静态扫描（禁止网络请求、系统删除等危险操作）
- 权限控制：每个插件声明所需权限，suri_core 审批
- 资源限制：CPU 时间、内存使用上限
- 文件隔离：插件只能访问声明的目录

### 事件总线

- 异步：基于 asyncio.Queue
- 模式：发布/订阅
- 事件类型：
  - `system.*` — 系统事件（启动、关闭、插件变更）
  - `user.input` / `user.command` — 用户输入
  - `role.*` — 角色事件（创建、调用、销毁）
  - `task.*` — 任务事件（创建、规划、调度、完成、失败、超时、取消）
  - `agent.*` — Agent 事件（创建、状态变更、完成、受阻）
  - `llm.request` / `llm.response` — 大模型请求/响应
  - `tool.call` / `tool.result` — 工具调用/结果
  - `error.*` — 错误事件
  - `plugin.*` — 插件事件（加载、卸载、升级）
  - `upgrade.*` — 升级报告事件
  - `interrupt.*` — 中断处理事件
  - `doc_sync.*` — 文档同步事件

**已知问题**：EventBus 的 `subscribe` 方法是异步 coroutine，但所有插件的 `register_events()` 中调用 `self.event_bus.subscribe(...)` 时未加 `await`，产生大量 `RuntimeWarning: coroutine was never awaited` 警告（当前 222 个）。建议修复方案：
- 方案 A：让 `register_events()` 变成 async 方法，插件中 `await self.event_bus.subscribe(...)`
- 方案 B：让 `subscribe` 支持同步调用（如内部使用 `asyncio.create_task` 或同步队列）
- 方案 C：EventBus 提供同步的 `subscribe_sync` 方法供 `register_events()` 使用
- 方案 D：在 PluginManager 加载插件时自动 await register_events 的 coroutine

### 服务注册发现

- 注册表：SQLite `plugins` 表 + 内存字典
- 注册时机：插件初始化时自动注册
- 发现方式：按名称查询、按类型查询、按能力查询
- 心跳检测：核心插件 5 秒一次，普通插件 30 秒一次

## 角色学习机制

1. 角色发现现有工具/插件不满足需求
2. 生成新插件代码（Python 模块 + manifest.json）
3. 向 suri_core 申请注册（提交代码 + 权限声明）
4. suri_core 安全审查（代码扫描 + 权限评估）
5. 审批通过后存入 `~/.suri/runtime/plugins/`
6. plugin_manager 动态加载
7. 新插件通过 event_bus 与其他插件协同

## 运行规则

1. 用户执行 `suri-agent` 二进制文件
2. 程序解压运行时文件到 `/tmp/suri-agent/`
3. 启动 suri_core 内核插件（自举注册）
4. plugin_manager 扫描 plugins/ 和 `~/.suri/runtime/plugins/`
5. 按依赖顺序加载核心插件
6. 加载接入插件，等待用户输入
7. 用户退出时，按依赖反向卸载插件
8. 归档会话日志，清理临时文件


---

目录说明

## prd/

> 产品文档服务

- 描述产品需求，AI 开发前读取
- [`README.md`](README.md) — PRD 文档总索引

## .kimi/

> AI 开发规范

- 描述 Kimi 开发规则，会话启动时强制读取

## agent_framework/

> 核心层（内核插件 suri_core）

- 内核插件，启动时自举注册
- 负责插件管理、事件调度
- 注意：不是传统意义上的"框架"，而是插件体系中的一个特殊插件

## /agent_framework/plugin_manager

> 插件管理器

- 与 event_bus 协同
- 职责：扫描、加载、初始化、注册、卸载插件
- 说明：读取 plugins/ 和 ~/.suri/runtime/plugins/，按依赖顺序管理插件生命周期

## /agent_framework/event_bus

> 事件总线

- 与 plugin_manager 协同
- 职责：插件间异步事件通信
- 说明：基于 asyncio.Queue，发布订阅模式，所有插件通过事件总线交互

## /agent_framework/suri_core_plugin

> 内核插件实现

- SuriCorePlugin 类实现
- 职责：自举注册、EventBus 和 PluginManager 的协调
- 说明：启动时由 main.py 实例化，自行注册到 PluginManager

## plugins/

> 插件层

- 所有功能模块以插件形式存在
- 核心插件启动时加载，动态插件运行时加载

## /plugins/llm_gateway

> 大模型网关插件

- 与 suri_core/event_bus 协同
- 职责：大模型调用、上下文管理、结果分发
- 说明：唯一对外模型调用出口，管理对话历史和 token 消耗

## /plugins/log_service

> 日志服务插件

- 与 suri_core/event_bus 协同
- 职责：日志记录、归档、查询
- 说明：全系统日志集中存储，包含通信记录和代码变更审计

## /plugins/access

> 统一接入插件

- 与 suri_core/event_bus 协同
- 职责：接收用户输入，转换为事件发送到 event_bus
- 说明：CLI、Web、UI、Telegram、飞书、API 的统一入口

## /plugins/access/cli

> 终端接入

- 与 access 协同
- 职责：命令行交互
- 说明：终端用户输入输出，默认接入方式

## /plugins/access/web

> 网页接入

- 与 access 协同
- 职责：浏览器端交互
- 说明：Web 页面访问入口

## /plugins/access/ui

> 桌面 UI 接入

- 与 access 协同
- 职责：桌面应用交互
- 说明：原生桌面程序入口

## /plugins/access/telegram

> Telegram 接入

- 与 access 协同
- 职责：Telegram 机器人交互
- 说明：Telegram 平台入口

## /plugins/access/lark

> 飞书接入

- 与 access 协同
- 职责：飞书机器人交互
- 说明：飞书平台入口

## /plugins/access/api

> API 接入

- 与 access 协同
- 职责：第三方系统通过 HTTP API 接入
- 说明：外部系统调用 suri-agent 的接口入口

## /plugins/task_scheduler

> 任务调度器插件

- 与 suri_core/event_bus、llm_gateway、agent_registry 协同
- 职责：任务优先级队列、并发控制、超时重试、LLM 响应等待
- 说明：被角色或 task_planner 调用，负责任务的执行调度

## /plugins/task_planner

> 任务规划器插件

- 与 suri_core/event_bus、llm_gateway、role_manager 协同
- 职责：任务分解、DAG 依赖管理、预设模板、LLM 辅助规划
- 说明：被角色调用，将复杂任务分解为可执行步骤序列

## /plugins/agent_registry

> Agent 注册表插件

- 与 suri_core/event_bus、memory_service 协同
- 职责：Agent 生命周期、子 Agent、状态跟踪、进度查询
- 说明：创建/销毁/跟踪 Agent，支持父子关系

## /plugins/role_comm

> 角色通信插件

- 与 suri_core/event_bus 协同
- 职责：角色间点对点/广播消息、权限规则、持久化队列
- 说明：提供结构化角色通信服务

## /plugins/interrupt_handler

> 中断处理器插件

- 与 suri_core/event_bus、role_comm、agent_registry 协同
- 职责：受阻原因分类、用户建议生成、升级通道
- 说明：任务执行受阻时的系统级处理

## /plugins/upgrade_manager

> 升级报告管理器插件

- 与 suri_core/event_bus、role_learner 协同
- 职责：升级报告状态机、闭环检查、Finding/UpgradeReport 模型
- 说明：管理升级报告的完整生命周期

## /plugins/doc_sync

> 文档同步插件

- 与 suri_core/event_bus、hooks_service、llm_gateway 协同
- 职责：文件变更监控、LLM 生成文档更新建议、用户确认写入
- 说明：保持代码与文档一致性

## /plugins/role_manager

> 角色管理插件

- 与 suri_core/event_bus 协同
- 职责：角色创建、销毁、配置管理
- 说明：管理角色生命周期，维护角色能力清单和技能模板

## /plugins/role_learner

> 角色学习插件

- 与 suri_core/event_bus 协同
- 职责：角色自学习（经验提取、技能形成）+ ProgramLearner 全局分析
- 说明：RoleLearner 分析单个角色；ProgramLearner 由 suri 角色调用进行全局分析

## /plugins/mcp

> MCP 插件

- 与 suri_core/event_bus 协同
- 职责：工具协议支持、注册发现、调用执行
- 说明：托管工具，提供 MCP 协议支持

## /plugins/mcp/client

> MCP Client

- 与 mcp_server、mcp_registry 协同
- 职责：协议客户端，发起工具调用
- 说明：向 mcp_server 发送工具调用请求

## /plugins/mcp/server

> MCP Server

- 与 mcp_client、mcp_registry 协同
- 职责：工具服务统一接口规范
- 说明：接收调用请求，路由到具体工具执行

## /plugins/mcp/registry

> 注册发现

- 与 mcp_server 协同
- 职责：维护可用工具清单
- 说明：扫描内置工具和运行时工具，提供发现能力

## /plugins/mcp/tools

> 工具实现

- 与 mcp_server 协同
- 说明：具体工具实现，被 mcp_server 统一托管

## /plugins/mcp/tools/file_system

> 文件操作工具

- 与 mcp_server 协同
- 职责：读写本地文件
- 说明：提供文件增删改查能力

## /plugins/mcp/tools/web_search

> 网络搜索工具

- 与 mcp_server 协同
- 职责：检索互联网信息
- 说明：提供网页搜索能力

## /plugins/mcp/tools/shell_exec

> 命令执行工具

- 与 mcp_server 协同
- 职责：执行系统命令
- 说明：提供 shell 命令执行能力

## shared/

> 公共层

- 核心和插件共享的接口定义和工具函数
- 禁止包含业务逻辑

## /shared/interfaces

> 插件接口定义

- 说明：所有插件必须实现的接口协议（PluginInterface、ToolInterface 等）

## /shared/utils

> 公共工具函数

- 说明：日志、配置、文件操作等通用工具

## role/

> 角色运行时数据

- 运行时动态创建的角色数据存储

## /roles/registry.md

> 统一角色清单

- 由 role_manager 维护
- 记录所有角色元信息、能力、权限

## /roles/{role_id}/

> 角色目录

- `soul.md` — 角色自我定义（YAML frontmatter + Markdown body）
- `memories/` — 角色记忆
- `skills/` — 角色技能
- `insights/` — 学习洞察

### Soul Schema

`soul.md` 采用 YAML frontmatter + Markdown body 格式：

```yaml
---
role_id: "frontend_dev"           # 角色唯一标识
nickname: "前端开发"               # 显示名称
role_type: "worker"               # core / worker / admin / project_director
version: "1.0.0"                  # Soul 版本
created_at: "2024-01-15T10:00:00Z"
updated_at: "2024-06-01T08:30:00Z"
capabilities:
  - "react_development"
  - "ui_design"
  - "api_integration"
keywords:
  - "frontend"
  - "react"
  - "typescript"
skills:
  - "component_design"
  - "state_management"
methodology: "组件优先，类型安全，移动优先设计"
context_window: 8000                # 角色上下文窗口偏好
temperature: 0.7                    # LLM 温度参数偏好
---

# 完整职责描述

## 职责范围
...

## 工作示例
...

## 禁忌
...
```

**字段约束**：

| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| `role_id` | string | 是 | 小写字母、数字、下划线，唯一 |
| `nickname` | string | 是 | 1-50 字符 |
| `role_type` | string | 是 | enum: core, worker, admin, project_director |
| `version` | string | 是 | 语义化版本 |
| `capabilities` | array[string] | 是 | 至少 1 项，每项 1-50 字符 |
| `keywords` | array[string] | 否 | 用于角色匹配和检索 |
| `skills` | array[string] | 否 | 已激活技能列表 |
| `methodology` | string | 否 | 工作方法论，≤2000 字符 |
| `context_window` | integer | 否 | 默认 8000 |
| `temperature` | float | 否 | 0.0-2.0，默认 0.7 |

**校验规则**：
- `role_id` 不能与现有角色重复
- `role_type=core` 只能有一个（suri）
- `role_type=project_director` 每个项目一个
- Soul 文件修改需 security_service 审批

## works/

> 工作区

- 用户项目工作目录，每个复杂项目对应一个子目录
- **项目目录结构**：
  ```
  works/{project_id}/
  ├── .meta.json          # 项目元数据（名称、状态、创建时间、关联角色、telegram_chat_id）
  ├── prd.md              # 项目需求文档
  ├── plan/               # 任务规划
  ├── output/             # 角色输出成果
  └── logs/               # 项目级日志
  ```
- **项目管理**：由项目总监角色负责调度，agent_registry 维护项目状态机
- **外部协作空间**：每个项目可绑定 Telegram 群组（框架预留飞书等扩展）

## tests/

> 测试

- 单元测试、集成测试、插件测试

---
核心改动：
目前只设立一个核心角色 suri，运行时数据存放于 `~/.suri/runtime/roles/suri/`，作为核心角色目录。其他角色运行时数据存放于 `~/.suri/runtime/roles/{role_id}/`。代码仓库中的 `roles/` 目录仅作为角色模板/初始数据，运行时复制到上述路径。

不需要通知我。先根据分析完成所有改造。
