# suri-agent PRD 文档

> suri-agent — 基于多 Agent 智能体架构的可进化 AI 代理系统。suri 是主人 Agent，按自己的 Soul 处理业务、自我进化、调度角色、维护系统。

---

## 文档一览

```
prd/
├── README.md                           ← 本文档（总入口）
│
├── overview/                           ← ① 概览：先从这里开始
│   ├── architecture.md                 ← 架构全景（suri 定位）
│   ├── design-principles.md            ← 核心设计原则
│   └── terminology.md                  ← 术语表
│
├── agents/                             ← ② 角色（Agent）体系
│   ├── agent-overview.md               ← 角色体系全貌
│   ├── soul-spec.md                    ← Soul 文件格式
│   ├── skill-spec.md                   ← Skill 文件格式
│   ├── workflow.md                     ← 角色工作流
│   ├── skill-development.md            ← 技能开发指南
│   ├── skill-composition.md            ← 技能组合
│   └── skills-overview.md              ← 技能概述
│
├── collaboration/                      ← ③ 多角色协作
│   ├── collab-patterns.md              ← 协作模式细节（事件驱动 + 自然语言）
│   ├── conflict-resolution.md          ← 冲突解决
│   ├── project-workflow.md             ← 项目工作流（含项目总监）
│   └── workspace.md                    ← 工作区结构
│
├── security/                           ← ④ 安全体系
│   ├── security-spec.md                ← 安全规范
│   ├── permission-model.md             ← 权限模型
│   └── audit-trail.md                  ← 审计日志
│
├── schema/                             ← ⑤ 规范定义
│   ├── database.md                     ← 数据库定义
│   ├── event-registry.md               ← 事件注册
│   ├── template-spec.md                ← 模板格式
│   └── template-auto-update.md         ← 模板自动更新
│
├── operations/                         ← ⑥ 运行与开发
│   ├── startup.md                      ← ★ 启动流程（main.py + suri_core）
│   ├── framework-rules.md              ← 框架核心规则
│   ├── directory-structure.md          ← 目录结构
│   ├── system-flow.md                  ← 系统整体流程
│   ├── program-flow.md                 ← 程序运行流程
│   ├── plugin-development.md           ← 插件开发指南
│   ├── hot-reload.md                   ← 热更新机制
│   └── deployment.md                   ← 部署指南
│
├── evolution/                          ← ⑦ 进化协同（★核心新增）
│   ├── coevolution.md                  ← 四维协同进化总览
│   ├── skill-evolution.md              ← 技能进化
│   ├── soul-evolution.md               ← Soul 进化
│   ├── plugin-evolution.md             ← 插件进化
│   └── tool-evolution.md               ← MCP 工具进化
│
└── plugins/                            ← 插件详细设计
    ├── README.md                       ← 插件全景 + 可扫码表
    ├── core/                           ← 内核插件
    ├── capability/                     ← 能力层插件
    ├── execution/                      ← 执行层插件
    ├── service/                        ← 基础服务插件
    ├── extension/                      ← 扩展能力插件
    └── access/                         ← 接入层插件
```

---

## 阅读路径

```
第一次接触 →
  1. overview/architecture.md        ← 理解 suri 定位和整体架构
  2. overview/design-principles.md   ← 理解核心设计哲学
  3. agents/agent-overview.md           ← 理解角色（Agent）体系
  4. evolution/coevolution.md           ← 理解四维协同进化
  5. agents/workflow.md                 ← 理解角色怎么工作
  6. collaboration/collab-patterns.md   ← 理解角色协作模式
  7. collaboration/project-workflow.md  ← 理解项目工作流

开始开发 →
  1. operations/startup.md              ← ★ 启动流程（主入口）
  2. operations/plugin-development.md   ← 理解插件开发
  3. operations/hot-reload.md           ← 理解热更新
  4. schema/event-registry.md           ← 理解事件注册
  5. operations/directory-structure.md  ← 理解目录结构

理解迁移 →
  1. operations/deployment.md           ← 迁移与部署
  2. operations/startup.md              ← 启动自检
  3. overview/design-principles.md      ← 解耦原则

理解进化 →
  1. evolution/coevolution.md          ← 总览
  2. evolution/skill-evolution.md      ← 技能进化
  3. evolution/plugin-evolution.md     ← 插件进化
  4. evolution/soul-evolution.md       ← Soul 进化
  5. evolution/tool-evolution.md       ← 工具进化
```

---

## 核心概念速览

| 概念 | 一句话 |
|------|--------|
| **suri** | 主人 Agent，按自己 Soul 处理业务、自我进化、调度角色 |
| **角色（Agent）** | 拥有独立 Soul/技能/记忆/学习能力的智能体 |
| **插件（Plugin）** | 被动能力提供者，响应事件或角色调用，自身也是 Agent |
| **技能（Skill）** | 能力原子单元，可被 role_learner 检测、自学自增 |
| **四维协同进化** | Skill/Soul/Plugin/Tool 独立进化，事件广播感知 |
| **事件总线** | 异步发布/订阅，万物皆事件，所有实体仅通过事件通信 |
| **项目总监** | 项目内多 worker 角色调度协作的角色类型 |
| **热更新** | 运行时无需重启即可更新插件/Soul/技能 |

---

## 迭代路线图

### V0.5 — 当前迭代（单通道验证版）

**目标**：验证核心链路可跑通，suri 能在 CLI 通道中完成基础对话和简单任务。

| 里程碑 | 状态 | 关键交付 |
|---------|------|---------|
| P0 功能验证 | ✅ 完成 | suri 对话循环、role_manager 角色管理、code_tool 文件操作 |
| 基础架构搭建 | ✅ 完成 | EventBus、PluginManager、系统启动流程 |
| 统一命名 & 文档修复 | ✅ 完成 | P0 审计修复（suri 定位、messages 表、事件注册） |
| 多角色通信验证 | 🔄 进行中 | role_comm 插件、消息传递链路 |
| 角色自学验证 | 📅 待启动 | role_learner 经验分析、skill 检测 |

**核心技术债**（V0.5 不解决）：
- Context 模型用字符串拼接（远期 V2.0 实现 5 层结构）
- 无多级缓存（Hot/Warm/Cold）
- no_messages_comm 表已合并到 messages
- no 独立 LLM 请求队列（当前简单 FIFO）

### V1.0 — MVP（多通道 + 基础协作）

**目标**：支持多通道接入、多角色协作、基础自学能力，达到可用状态。

| 里程碑 | 预期 | 交付物 |
|---------|------|--------|
| Telegram 通道 | V0.5-V1.0 之间 | 消息收发、会话管理、命令处理 |
| 多角色协作 | V1.0 | role_comm 完整链路、project_director 角色 |
| 角色自学 | V1.0 | role_learner 首次 skill 检测、skill 文件生成 |
| 升级管理 | V1.0 | upgrade_manager 报告闭环 |
| 配置热更新 | V1.0 | 外部化 tool_descriptions.yaml / soul_template.md |
| 错误处理完善 | V1.0 | interrupt_handler 完整链路 |
| 单元测试覆盖 | V1.0 | 核心插件 80%+ 覆盖率 |

### V2.0 — 成熟版（全功能 + 高性能）

**目标**：完整的 5 层 Context 模型、多级缓存、高级并发控制。

| 里程碑 | 预期 | 交付物 |
|---------|------|--------|
| 5 层 Context 模型 | V2.0 | system/session/task/history/memory 独立分层 |
| 三级上下文缓存 | V2.0 | Hot(内存)/Warm(SQLite)/Cold(磁盘) |
| 历史自动摘要压缩 | V2.0 | token 超限时 LLM 生成摘要 |
| 任务派生 Context.clone() | V2.0 | 子任务独立继承父 Context |
| LLM 请求队列 | V2.0 | 优先级排序、速率控制、预算控制 |
| MCP 工具框架 | V2.0 | 工具注册/发现/调用完整链路 |
| 插件热更新 | V2.0 | hot/warm/cold 三级热更新支持 |
| 监控系统 | V2.0 | monitor 插件、健康检查、告警 |
| 集成测试 | V2.0 | 端到端场景测试 |