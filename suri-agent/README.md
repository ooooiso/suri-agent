# suri-agent / 微服务化重构

## 架构蓝图（V4.0 Microservices）

本目录正在从单体架构向微服务化演进。原有目录保留作为参考，新目录为服务化目标架构。

```
suri-agent/
│
├── 【新架构】微服务目录
│
│   common/                  ← 共享基础设施
│   │   service_base.py      ← 所有服务的基类（生命周期、优雅重启、健康检查）
│   │   grpc_client.py       ← gRPC 客户端工厂
│   │   nats_client.py       ← NATS 消息总线客户端
│   │   constants.py         ← 常量定义
│   │
│   supervisor/              ← 进程管理器（元层）
│   │   service.py           ← 启动/停止/重启所有子进程
│   │   reload_handler.py    ← 热升级协议（SIGUSR1、状态迁移）
│   │   health_checker.py    ← 健康检查与自动恢复
│   │
│   gateway/                 ← 接入网关（替代原 access/）
│   │   service.py           ← CLI / Telegram Bot / Web UI / JSON-RPC 统一入口
│   │   cli_server.py        ← 终端交互
│   │   telegram_bot.py      ← Telegram Bot 连接
│   │   web_server.py        ← Web UI + SSE
│   │   rpc_server.py        ← JSON-RPC 服务
│   │   output_router.py     ← 输出路由（Terminal/File/Memory/Logger/Telegram）
│   │
│   scheduler/               ← 调度编排（替代原 core/ 调度部分）
│   │   service.py           ← 任务全生命周期管理
│   │   task_dispatcher.py   ← 任务接收、部门匹配、分派
│   │   task_planner.py      ← 任务分解、单/多角色规划
│   │   agent_registry.py    ← Agent 生命周期、独立上下文
│   │   department_registry.py ← 部门扫描、能力匹配
│   │   interrupt_handler.py ← 受阻分类、升级、取消
│   │   approval_service.py  ← 审批状态机
│   │   state_card.py        ← 任务看板渲染
│   │
│   role_engine/             ← 角色引擎（替代原 role/）
│   │   service.py           ← 角色运行时框架
│   │   runtime.py           ← 角色实例管理（suri/suri_dev/suri_hr/...）
│   │   messenger.py         ← 角色间通信（跨部门权限、投影触发）
│   │   builder.py           ← 角色创建、Soul 模板生成
│   │   coordinator.py       ← 任务分配、跨部门协作协调
│   │   context_manager.py   ← 角色对话上下文（替代 AgentContext）
│   │
│   tool_host/               ← 工具运行时（替代原 tools/ + mcp/）
│   │   service.py           ← 工具注册、动态加载、权限检查
│   │   executor.py          ← 工具执行器（沙箱隔离）
│   │   sandbox.py           ← 子进程/WASM 沙箱
│   │   registry.py          ← 工具注册表管理
│   │   mcp_host.py          ← MCP 框架宿主
│   │
│   memory/                  ← 记忆中心（替代原 infrastructure/memory + memory/）
│   │   service.py           ← 数据存取统一接口
│   │   memory_service.py    ← 角色级 SQLite 管理
│   │   context_service.py   ← 系统提示组装（Soul + 规则 + 经验注入）
│   │   schema.py            ← 数据库 Schema 定义
│   │   migrations/          ← 数据库迁移脚本
│   │
│   model/                   ← 模型中心（替代原 model/）
│   │   service.py           ← LLM 调用统一入口
│   │   manager.py           ← ModelManager（配置、API Key、流式输出）
│   │   router.py            ← ModelRouter（智能选择、降级告警）
│   │   providers/           ← 各厂商适配器
│   │       openai.py
│   │       anthropic.py
│   │       base.py
│   │
│   security/                ← 安全与文件（替代原 infrastructure/security + filesystem + rules/安全相关）
│   │   service.py           ← 权限校验、审批管理
│   │   security_service.py  ← SecurityService（权限委托、Soul 保护、令牌验证）
│   │   file_service.py      ← FileService（统一文件读写、安全钩子）
│   │   ownership_rule.py    ← FileOwnershipRule（类型化所有权、前缀匹配）
│   │   code_commit_rule.py  ← CodeCommitRule（变更报告、紧急修复）
│   │
│   logger/                  ← 日志中心（替代原 infrastructure/logger + logs/）
│   │   service.py           ← 日志接收、分类、结构化
│   │   logger_service.py    ← LoggerService（按天轮转、JSON 日志、Token 统计）
│   │   handlers/            ← 各类日志处理器
│   │
│   learning/                ← 进化引擎（保留原 learning/）
│   │   service.py           ← 自学习异步调度
│   │   feedback_collector.py
│   │   experience_extractor.py
│   │   role_learner.py
│   │   platform_learner.py
│   │
│   config/                  ← 配置中心（替代原 infrastructure/config）
│   │   service.py           ← 配置扫描、Soul 索引、服务发现
│   │   config_service.py    ← ConfigService（别名解析、部门管理、工具注册表）
│   │   service_registry.py  ← 本地服务发现（轻量级，替代 Consul）
│   │
│   contracts/               ← 接口契约（Protobuf）
│       supervisor.proto
│       scheduler.proto
│       role_engine.proto
│       tool_host.proto
│       memory.proto
│       model.proto
│       security.proto
│       logger.proto
│       learning.proto
│       config.proto
│       common.proto
│
│
├── 【参考保留】原有单体架构目录（逐步迁移）
│
│   access/                  ← 接入层 → 迁移到 gateway/
│   core/                    ← 核心调度 → 迁移到 scheduler/
│   infrastructure/          ← 基础设施 → 拆分至 memory/security/logger/config/
│   role/                    ← 角色逻辑 → 迁移到 role_engine/
│   tools/                   ← 工具集 → 迁移到 tool_host/
│   mcp/                     ← MCP 框架 → 迁移到 tool_host/mcp_host.py
│   model/                   ← 模型管理 → 迁移到 model/
│   learning/                ← 自学习 → 保留，逐步迁移到 learning/
│   rules/                   ← 规则引擎 → 拆分至各服务
│   tests/                   ← 测试 → 保留，逐步增加服务级测试
│
```

## 服务通信协议

| 协议 | 用途 | 地址 |
|------|------|------|
| gRPC | 服务间同步调用 | `unix:///tmp/suri-{service}.sock` |
| NATS | 事件广播、异步通知 | `localhost:4222` |
| UDP | 日志采集（不阻塞业务） | `localhost:514` |
| HTTP | Web UI、JSON-RPC | `localhost:8080` |

## 关键设计原则

1. **进程隔离** — 每个服务独立进程，崩溃互不影响
2. **状态外置** — 运行时状态写入数据库，进程无状态可任意重启
3. **接口通信** — 服务间禁止直接 import，只能通过 gRPC / NATS
4. **热升级** — supervisor 管理优雅重启，suri_dev 可修改代码后安全 reload
5. **本地优先** — 全部进程本地运行，数据本地存储

## 启动顺序

```
supervisor (PID 1)
  ├─ config       # 先启动，其他服务依赖配置
  ├─ memory       # 数据库服务
  ├─ logger       # 日志服务
  ├─ security     # 安全服务
  ├─ model        # 模型服务
  ├─ tool_host    # 工具服务
  ├─ learning     # 学习服务
  ├─ role_engine  # 角色引擎
  ├─ scheduler    # 调度中心（依赖以上所有）
  └─ gateway      # 接入网关（最后启动，对外暴露）
```

## 数据归属

| 数据 | 存储位置 | 管理方 |
|------|---------|--------|
| 平台任务/Agent/审批 | `data/platform.db` | scheduler + memory |
| 角色消息/经验/洞察 | `group/<dept>/<role>/memories/role.db` | memory |
| Insight Markdown | `group/<dept>/<role>/memories/insights/*.md` | memory |
| Soul 文件 | `group/<dept>/<role>/<role>.md` | config |
| 技能定义 | `group/<dept>/<role>/skills/<skill>/skill.md` | role_engine |
| 用户项目 | `workspace/<project>/` | security (file_service) |
| 日志 | `logs/<category>/suri-YYYY-MM-DD.log` | logger |
| 模型配置 | `model_config.json` | model |
