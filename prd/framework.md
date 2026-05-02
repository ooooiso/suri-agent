# 框架核心说明

## 架构概述

- 单进程插件化架构
- 核心（core）+ 插件（plugins）
- 插件通过事件总线通信
- 本地运行，零依赖，mac 优先

## 数据存储

### 存储分层

| 层级 | 位置 | 用途 |
|------|------|------|
| 用户数据 | `~/.suri/data/` | SQLite 数据库、配置文件 |
| 运行时数据 | `~/.suri/runtime/` | 角色实例、动态插件、会话缓存 |
| 临时数据 | `/tmp/suri-agent/` | 解压文件、临时缓存 |
| 备份数据 | `~/.suri/backup/` | 代码变更快照 |

### SQLite 表结构

- `plugins` — 插件注册表（名称、版本、路径、状态、类型）
- `roles` — 角色注册表（ID、名称、能力清单、状态）
- `events` — 事件日志（时间、来源、目标、事件类型、内容）
- `messages` — 通信记录（会话 ID、角色、消息内容、时间）
- `changes` — 代码变更审计（变更者、文件路径、变更前、变更后、时间）
- `config` — 用户配置（键、值、更新时间）

### 文件存储

- 角色配置：`~/.suri/runtime/roles/{role_id}.json`
- 角色技能：`~/.suri/runtime/roles/{role_id}/skills/{skill_name}.json`
- 动态插件：`~/.suri/runtime/plugins/{plugin_name}/`
- 日志文件：`~/.suri/runtime/logs/{YYYYMMDD}.log`
- 会话历史：`~/.suri/runtime/sessions/{session_id}.jsonl`

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
- 错误事件：异常转为事件广播，suri_core 决定处理策略
- 重试机制：可配置重试次数和退避策略
- 降级策略：服务失败时切换到备用方案

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
  - `user.input` — 用户输入
  - `role.*` — 角色事件（创建、调用、销毁）
  - `tool.call` — 工具调用
  - `tool.result` — 工具返回结果
  - `llm.request` — 大模型请求
  - `llm.response` — 大模型响应
  - `error.*` — 错误事件

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
3. 启动 core/ 核心层（plugin_manager、event_bus、scheduler）
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

## .kimi/

> AI 开发规范

- 描述 Kimi 开发规则，会话启动时强制读取

## core/

> 核心层

- 系统核心，不依赖任何插件
- 负责插件管理、事件调度、任务协调

## /core/plugin_manager

> 插件管理器

- 与 event_bus、scheduler 协同
- 职责：扫描、加载、初始化、注册、卸载插件
- 说明：读取 plugins/ 和 ~/.suri/runtime/plugins/，按依赖顺序管理插件生命周期

## /core/event_bus

> 事件总线

- 与 plugin_manager、scheduler 协同
- 职责：插件间异步事件通信
- 说明：基于 asyncio.Queue，发布订阅模式，所有插件通过事件总线交互

## /core/scheduler

> 任务调度

- 与 plugin_manager、event_bus 协同
- 职责：角色任务调度、优先级管理、超时控制
- 说明：协调多个角色同时执行任务，避免资源冲突

## plugins/

> 插件层

- 所有功能模块以插件形式存在
- 核心插件启动时加载，动态插件运行时加载

## /plugins/llm_gateway

> 大模型网关插件

- 与 core/event_bus 协同
- 职责：大模型调用、上下文管理、结果分发
- 说明：唯一对外模型调用出口，管理对话历史和 token 消耗

## /plugins/log_service

> 日志服务插件

- 与 core/event_bus 协同
- 职责：日志记录、归档、查询
- 说明：全系统日志集中存储，包含通信记录和代码变更审计

## /plugins/access

> 统一接入插件

- 与 core/event_bus 协同
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

## /plugins/role_manager

> 角色管理插件

- 与 core/event_bus 协同
- 职责：角色创建、销毁、配置管理
- 说明：管理角色生命周期，维护角色能力清单和技能模板

## /plugins/mcp

> MCP 插件

- 与 core/event_bus 协同
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

## /role/role_instances

> 角色实例

- 具体角色实例的存储目录

## /role/role_instances/memory

> 角色记忆

- 角色的对话历史和记忆数据

## /role/role_instances/skills

> 角色技能

- 角色可执行的技能定义

## works/

> 工作区

- 用户项目工作目录，可在下方创建项目

## tests/

> 测试

- 单元测试、集成测试、插件测试

---
核心改动：
目前只设立一个核心角色ruri，在主程序中建立rusi文件夹，作为核心角色目录，根目录新增角色文件夹存放其他角色。不在有部门功能。

不需要通知我。先根据分析完成所有改造。
