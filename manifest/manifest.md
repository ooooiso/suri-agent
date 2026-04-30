---
platform:
  name: Suri
  version: "1.0"
  description: |
    基于角色驱动的多 Agent 协作平台。
    以 suri 为调度核心，通过部门职能索引、强安全审批、流程自优化、
    全局模型热备和 MCP 能力扩展，实现可控、可演进的智能体协同。
  created_at: 2026-04-30

scheduler_role: suri
security_admin_role: security_admin
workflow_admin_role: workflow_admin
config_admin_role: config_admin
hr_admin_role: hr_admin

includes:
  function_index: function_index.md
  rules:
    - rules/scheduling.md
    - rules/security.md
    - rules/file_ownership.md
    - rules/model_routing.md
    - rules/communication_protocol.md
    - rules/role_management.md
    - rules/code_commit.md
  process:
    - process/workflow.md
    - process/change_approval.md
  communication:
    - communication/telegram.md
    - communication/feishu.md
  models: models/model_pool.md
  memory: memory/memory_config.md
  tools: tools/tool_registry.md
  templates: templates/
  docs: docs/
---

# Suri 多 Agent 协作平台

## 1. 平台定位

Suri 是一个角色驱动、强规则约束的多智能体协作系统。  
所有用户需求由调度核心 **suri** 统一入口，根据 `function_index.md` 分派至各部门总监，再由总监拆解并指派给执行角色。  
平台内置严格的文件安全审批、流程自优化上报、全局模型热备、MCP 能力扩展以及角色生命周期管理，确保协作有序、安全可控、可自我进化。

> 本文档仅描述平台**外部配置层面**的架构与规则。  
> 核心运行主程序、接入层、MCP 框架等实现细节不属于本文件范畴，由主程序维护者独立管理。

## 2. 核心角色

| 角色 ID | 昵称 | 职位 | 职责 |
|---------|------|------|------|
| `suri` | Suri | 调度总监 | 唯一用户交互入口，需求解析、任务分派、异常回流、审批转发 |
| `security_admin` | 瓦特 | 安全管理员 | 审核所有文件修改申请，执行安全审批规则 |
| `workflow_admin` | 泰勒 | 流程管理员 | 审核角色自优化上报，协调跨角色流程变更 |
| `config_admin` | 张衡 | 配置管理员 | 维护 `manifest/` 目录下所有配置文件，管理配置变更提审 |
| `hr_admin` | 玛丽安 | 角色管理员 | 负责角色创建、技能库与灵魂维护、部门归属调整 |

## 3. 平台配置架构

本文件及同目录下的所有文件构成平台的**配置层**，主程序运行时会读取此层。

```
manifest/                        # 【平台配置根目录】
├── manifest.md              # 本文件：平台主配置与模块引用
├── function_index.md        # 部门职能索引
├── rules/                   # 全局规则（7条核心规则）
│   ├── scheduling.md
│   ├── security.md
│   ├── file_ownership.md
│   ├── model_routing.md
│   ├── communication_protocol.md
│   ├── role_management.md
│   └── code_commit.md
├── process/                 # 标准流程
│   ├── workflow.md
│   └── change_approval.md
├── communication/           # 通信适配器配置
│   ├── telegram.md
│   └── feishu.md
├── models/                  # 模型池
│   └── model_pool.md
├── memory/                  # 记忆策略
│   └── memory_config.md
├── templates/               # 文件模板
│   ├── role_soul.md
│   ├── role_skills.md
│   ├── department_entry.md
│   ├── rule_file.md
│   ├── process_file.md
│   └── role_files_map.md
└── docs/                    # 文档
    ├── README.md
    ├── roles_mapping.md
    ├── changelog.md
    └── file_usage.md
```

## 4. 关键配置模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 部门职能索引 | `function_index.md` | suri 匹配任务归属、查找部门总监与群组 |
| 调度规则 | `rules/scheduling.md` | 任务分派策略、重试、异常回流 |
| 安全审批 | `rules/security.md` | 文件修改必须审批，用户确认 |
| 文件所有权 | `rules/file_ownership.md` | 每个目录/文件归属哪个角色 |
| 模型路由 | `rules/model_routing.md` | 模型优先级、自动降级、端点 |
| 通信协议 | `rules/communication_protocol.md` | 角色寻址、消息格式、通道规则 |
| 角色管理 | `rules/role_management.md` | 创建/修改/注销角色的强制流程 |
| 代码提交 | `rules/code_commit.md` | 变更报告字段、审批配合 |
| 工作流 | `process/workflow.md` | 任务下发、用户决策回路、技能沉淀 |
| 变更审批 | `process/change_approval.md` | 配置变更详细步骤 |
| 模型池 | `models/model_pool.md` | 全局模型清单及热备策略 |
| 工具注册 | `tools/tool_registry.md` | 公共工具索引、权限、开发者信息 |
| 记忆策略 | `memory/memory_config.md` | 保留期限、遗忘规则、跨角色共享 |

## 5. 角色文件与技能

每个角色实例位于 `profiles/<role_id>/`，标准结构：

```
<role_id>.md                # Soul 文件（角色灵魂）
skills/
    skills.md               # 技能索引
    <技能名称>/
        skill               # 技能主定义（Markdown+YAML）
        assets/             # 静态资源
        references/         # 参考文档
        scripts/            # 可执行脚本
memories/                   # 私人长期记忆
reference/
    files_i_use.md          # 个人文件权限地图
```

suri 的专属技能位于全局 `skills/` 目录，结构与其他角色技能包一致。

## 6. 运行原则

- **文件即真相**：关键规则和索引每次按需读取，不依赖对话记忆。
- **安全钩子**：文件操作拦截器实时校验所有权和审批状态。
- **变更必审批**：任何对业务文件的修改均需生成变更报告，经 `security_admin` 审核及用户确认。
- **用户决策回路**：开发人员遇难题时，经 suri 整理上下文与可选方案回流给用户，用户判断后决策。
- **技能沉淀**：用户确认的最终实现方案，经审批后写入角色技能库，成为可复用能力。
- **能力缺口识别**：当用户需求无法匹配现有部门时，suri 主动提示能力边界，询问是否需要组织扩展。
- **MCP 扩展**：角色可通过 MCP 服务动态补足能力，无需修改自身 skill 文件。
- **防遗忘机制**：核心规则注入角色 Soul 系统提示，关键路径上设置强制检查步骤。

## 7. 维护

本配置文件及 `manifest/` 目录由 **config_admin（张衡）** 拥有最终维护权。  

所有修改须遵循 `process/change_approval.md` 并记录在 `docs/changelog.md` 中。
