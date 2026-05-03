# suri-agent 项目全目录结构

> 基于多 Agent 智能体架构的可进化 AI 代理系统。
> 最后更新: 2026-05-04

```
suri-agent/
│
├── main.py                          # ★ 应用入口（<20 行极简启动）
├── requirements.txt                 # Python 依赖
├── .env.example                     # 环境变量模板
├── .gitignore
├── README.md
│
├── agent_framework/                 # ★ 框架核心（系统层代码）
│   ├── core/suri_core/              #   内核：自举注册，协调 EventBus + PluginManager
│   ├── event_bus/                   #   异步事件总线（发布/订阅）
│   ├── plugin_manager/              #   插件管理器（扫描/加载/生命周期）
│   ├── migrations/                  #   SQLite 数据库迁移脚本
│   ├── access/                      #   接入层（预留）
│   ├── capability/                  #   能力层（预留子目录结构）
│   ├── execution/                   #   执行层（预留子目录结构）
│   ├── extension/                   #   扩展层（预留子目录结构）
│   ├── service/                     #   基础服务层（预留子目录结构）
│   └── suri_core_plugin/            #   旧版内核插件（过渡用）
│
├── plugins/                         # ★ 插件实现（运行时代码）
│   ├── access/                      #   接入层：CLI、Telegram、配置编辑器
│   ├── agent_registry/              #   执行层：Agent 生命周期管理
│   ├── code_tool/                   #   执行层：文件读写、搜索、统计
│   ├── config_service/              #   服务层：配置管理
│   ├── interrupt_handler/           #   执行层：中断分类、自动重试
│   ├── llm_gateway/                 #   能力层：LLM 路由、模型切换
│   ├── log_service/                 #   服务层：日志记录
│   ├── role_manager/                #   能力层：角色 CRUD、Soul 解析
│   ├── security_service/            #   服务层：权限校验、审计
│   ├── task_planner/                #   执行层：任务分解
│   ├── task_scheduler/              #   执行层：任务调度
│   └── test_framework/              #   扩展层：测试基础设施
│
├── prd/                             # ★ 产品需求文档（完整设计说明）
│   ├── README.md                    #   PRD 入口和阅读路径
│   ├── overview/                    #   ① 架构概览
│   │   ├── architecture.md          #     架构全景（suri 定位）
│   │   ├── design-principles.md     #     核心设计原则（含迁移解耦）
│   │   └── terminology.md           #     术语表
│   ├── agents/                      #   ② 角色体系
│   │   ├── agent-overview.md        #     角色体系全貌
│   │   ├── soul-spec.md             #     Soul 文件格式
│   │   ├── skill-spec.md            #     Skill 文件格式
│   │   ├── workflow.md              #     角色工作流
│   │   ├── skill-development.md     #     技能开发指南
│   │   ├── skill-composition.md     #     技能组合
│   │   └── skills-overview.md       #     技能概述
│   ├── collaboration/               #   ③ 多角色协作
│   │   ├── collab-patterns.md       #     协作模式细节
│   │   ├── conflict-resolution.md   #     冲突解决
│   │   ├── project-workflow.md      #     项目工作流
│   │   └── workspace.md             #     工作区结构（含并发锁）
│   ├── security/                    #   ④ 安全体系
│   │   ├── security-spec.md         #     安全规范
│   │   ├── permission-model.md      #     权限模型
│   │   └── audit-trail.md           #     审计日志
│   ├── schema/                      #   ⑤ 规范定义
│   │   ├── database.md              #     数据库定义
│   │   ├── event-registry.md        #     事件注册（含 role.message 链）
│   │   ├── template-spec.md         #     模板格式
│   │   └── template-auto-update.md  #     模板自动更新
│   ├── operations/                  #   ⑥ 运行与开发
│   │   ├── startup.md               #     启动流程（含启动自检）
│   │   ├── framework-rules.md       #     框架核心规则
│   │   ├── directory-structure.md   #     目录结构
│   │   ├── system-flow.md           #     系统整体流程
│   │   ├── program-flow.md          #     程序运行流程
│   │   ├── plugin-development.md    #     插件开发指南
│   │   ├── hot-reload.md            #     热更新机制
│   │   └── deployment.md            #     部署指南（含迁移场景）
│   ├── evolution/                   #   ⑦ 进化协同
│   │   ├── coevolution.md           #     四维协同进化总览
│   │   ├── skill-evolution.md       #     技能进化
│   │   ├── soul-evolution.md        #     Soul 进化
│   │   ├── plugin-evolution.md      #     插件进化
│   │   └── tool-evolution.md        #     MCP 工具进化
│   └── plugins/                     #   ⑧ 插件详细设计
│       ├── README.md                #     插件全景 + 可扫码表
│       ├── core/suri_core.md        #     内核插件
│       ├── capability/              #     能力层（LLM/记忆/角色/学习等）
│       ├── execution/               #     执行层（任务/通信/代码工具等）
│       ├── service/                 #     基础服务（配置/日志/安全）
│       ├── extension/               #     扩展（测试/定时/钩子/同步）
│       └── access/                  #     接入层（CLI/Web/Telegram/桌面）
│
├── roles/                           # ★ 角色模板（代码仓库）
│   ├── README.md                    #   角色说明
│   └── suri/                        #   suri 主人角色
│       ├── meta.json                #     元数据
│       └── soul.md                  #     Soul 定义
│
├── shared/                          # ★ 共享代码
│   ├── interfaces/                  #   接口定义
│   │   └── plugin.py                #     插件基类接口
│   └── utils/                       #   工具函数
│       └── event_types.py           #     事件类型常量
│
├── tests/                           # ★ 测试
│   ├── framework/base.py            #   测试基类
│   ├── plugin/                      #   插件单元测试（10 个测试文件）
│   ├── unit/                        #   模块单元测试（3 个测试文件）
│   └── integration/                 #   集成测试（预留）
│
└── works/                           # 工作区模板（首次运行复制到 ~/.suri/runtime/）
    └── README.md
```

---

## 核心架构概念速览

| 概念 | 说明 |
|------|------|
| **suri** | 主人 Agent，按自己 Soul 处理业务、自我进化、调度角色 |
| **角色 (Agent)** | 拥有独立 Soul/技能/记忆/学习能力的智能体 |
| **插件 (Plugin)** | 被动能力提供者，自身也是 Agent，可学习更新 |
| **技能 (Skill)** | 能力原子单元，可被 role_learner 检测、自学自增 |
| **四维协同进化** | Skill / Soul / Plugin / Tool 独立进化，事件广播感知 |
| **事件总线** | 异步发布/订阅，所有实体仅通过事件通信 |
| **项目总监** | 项目内多 worker 角色调度协作的角色类型 |
| **热更新** | 运行时无需重启即可更新插件/Soul/技能 |
| **运行时数据** | `~/.suri/` 下存储角色/项目/配置，与代码仓库解耦 |

## 目录设计原则

```
agent_framework/   ← 框架核心（系统级代码，可独立升级）
plugins/           ← 插件实现（运行时代码，热加载）
prd/               ← 产品需求文档（设计说明）
roles/             ← 角色模板（首次运行复制到 ~/.suri/runtime/roles/）
shared/            ← 共享代码（接口定义、工具函数）
tests/             ← 测试
works/             ← 工作区模板（首次运行复制到 ~/.suri/runtime/works/）
```

**关键解耦**：项目数据（`~/.suri/runtime/works/`）和角色数据（`~/.suri/runtime/roles/`）在运行时目录，与代码仓库分离，支持平滑迁移。