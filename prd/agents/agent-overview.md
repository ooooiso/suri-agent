# 角色（Agent）体系

> 定义 suri-agent 中的角色（Agent）完整体系：概念、类型、职责边界、生命周期、能力和协作方式。

---

## 一、核心概念

### 什么是角色（Agent）

```
角色 = 独立智能体
  ├── 有 Soul（自我定义、职责、人格）
  ├── 有技能（能力原子单元，可自学自增）
  ├── 有记忆（SQLite 持久化，经验积累）
  ├── 有学习能力（通过 role_learner 持续进化）
  ├── 有工具调用能力（插件/MCP）
  ├── 有通信能力（通过 role_comm 协作）
  └── 有升级机制（通过 upgrade_manager 管理版本）
```

### suri 与普通角色的区别

| 维度 | suri（主人 Agent） | 普通角色（worker/project_director/admin） |
|------|-------------------|----------------------------------------|
| 数量 | 唯一 | 多个 |
| 可删除 | ❌ 不可删除 | ✅ 可删除 |
| 角色类型 | `core` | `worker` / `project_director` / `admin` |
| 角色 ID | 固定为 `suri` | 自动生成 |
| 核心职责 | 处理业务 + 自我进化 + 调度 + 维护 | 执行专职任务 |
| 特殊权限 | 创建/删除角色、管理插件、更新其他角色的 Soul | 无特殊权限 |
| 技能范围 | 通用 + 持续扩展 | 专职技能 |
| 升级方式 | 自我升级 + 用户确认 | 角色自学 + suri 评估 + 用户确认 |

---

## 二、角色类型

| 类型 | `role_type` | 数量限制 | 可删除 | 典型示例 | 核心职责 |
|------|-------------|---------|-------|---------|---------|
| **核心调度** | `core` | 唯一（suri） | ❌ | suri | 主人 Agent，处理业务 + 自我进化 + 调度 |
| **工作角色** | `worker` | 不限 | ✅ | 前端开发、文档撰写员 | 执行具体业务任务 |
| **项目总监** | `project_director` | 不限 | ✅ | 电商总监 | 项目内多角色调度协作 |
| **管理角色** | `admin` | 不限 | ✅ | 系统管理员 | 角色管理、配置管理、审计 |

### 角色类型选择决策树

```
创建角色时
├─ 系统调度需求？ → core（仅 suri）
├─ 项目协调需求？ → project_director
│   （管理多个 worker 协作）
├─ 系统管理需求？ → admin
│   （查看日志、管理配置、审计）
└─ 业务执行需求？ → worker
    （写文档、写代码、数据分析等）
```

---

## 三、角色能力来源

角色通过以下方式获得能力：

```
角色能力 = Soul（定义做什么） + Skill（怎么做） + Tool（用什么做）

Soul ← 创建时 suri 生成，后续可被 suri 更新
  ├── 决定角色的职责边界
  ├── 决定角色的行为偏好
  └── 决定角色的工作方法论

Skill ← 自学 + 用户确认激活
  ├── role_learner 检测重复模式（≥3次）
  ├── 技能建议 → suri 评估 → 用户确认
  └── 写入 skill 文件，下次任务生效

Tool ← suri 开发 / MCP 注册
  ├── suri 为角色开发专门的 MCP 工具
  ├── 插件暴露的能力
  └── 系统内置工具
```

---

## 四、角色生命周期

```
角色创建（suri 提案 → 用户确认 → role_manager.create_role()）
    │
    ▼
角色就绪（等待任务分配）
    │
    ▼
角色执行任务（循环：分析→执行→学习→进化）
    │
    ├── 分析任务（理解需求，检查技能匹配）
    ├── 执行步骤（调用插件/MCP/工具）
    ├── 返回结果（task.completed）
    ├── 异步学习（role_learner 分析经验）
    └── 技能进化（检测模式 → 建议 → 确认 → 激活）
    │
    ├── 角色升级（技能优化 / Soul 更新 / 工具扩展）
    │
    └── 角色删除（suri 或用户发起）
        │
        ▼
    数据归档（_archived/{role_id}/，30天后自动清理）
```

### 状态定义

| 状态 | 说明 | 能否接收任务 | 能否自学 |
|------|------|------------|---------|
| `created` | 刚创建，正在初始化 | ❌ | ❌ |
| `ready` | 就绪，等待任务 | ✅ | ✅ |
| `busy` | 正在执行任务 | ❌ | ❌ |
| `blocked` | 被中断/受阻 | ❌ | ❌ |
| `upgrading` | 正在升级（Soul 更新/技能变更） | ❌ | ✅ |
| `archived` | 已归档 | ❌ | ❌ |
| `deleted` | 已删除 | ❌ | ❌ |

### 状态转换

```
created → ready  （初始化完成）
ready   → busy   （收到任务）
busy    → ready  （任务完成）
busy    → blocked（执行中中断/超时）
blocked → ready  （中断解决）
ready   → upgrading（Soul 更新/技能变更中）
upgrading → ready（变更完成）
ready   → archived（被删除）
archived → deleted（30天后自动清理）
```

---

## 五、角色工作流

详见 [workflow.md](workflow.md)。

角色标准工作流包含：
1. 接收任务（suri分配 / 其他角色协作 / 用户直接请求 / cron触发）
2. 分析分解（匹配技能 → 调用 task_planner → 创建执行实例）
3. 按步骤执行（调用 LLM / 工具 / 技能 / 记忆）
4. 返回结果（task.completed → 触发学习）
5. 自学提升（role_learner 异步分析 → 技能检测）
6. 通信协作（role_comm 与其他角色交换信息）

---

## 六、角色在项目中的角色

详见 [project-workflow.md](../collaboration/project-workflow.md)。

| 项目阶段 | 涉及角色 | 活动 |
|---------|---------|------|
| 创建项目 | suri | 分析需求，创建项目目录 + 项目总监 + 群组 |
| 项目运行 | 项目总监 + worker | 总监调度，worker 执行 |
| 缺少角色 | 项目总监 → suri → 用户 | 请求创建新角色 |
| 角色升级 | worker + role_learner | 项目中自学新技能 |
| 项目归档 | 项目总监 + worker | 汇总交付，归档角色 |

---

## 七、角色间协作

详见 [collab-patterns.md](../collaboration/collab-patterns.md)。

| 协作模式 | 说明 | 适用场景 |
|---------|------|---------|
| 主从模式 | 项目总监 → 分配 → worker | 项目内多角色协作 |
| 点对点 | role_comm.send | 角色间信息交换 |
| 广播 | role_comm.broadcast | 通知所有角色 |
| 求助 | role_comm → suri | 角色遇到困难 |

---

## 八、角色存储

```yaml
~/.suri/runtime/roles/
├── suri/                 # 核心角色（不可删除，纳入 Git）
│   ├── soul.md
│   ├── skills/
│   │   └── task_dispatch_v1.0.json
│   ├── memories/
│   │   ├── role.db
│   │   └── insights/
│   └── meta.json
├── doc_writer/           # 工作角色
│   ├── soul.md
│   ├── skills/
│   ├── memories/
│   ├── reference/
│   └── output/
├── ecommerce_director/   # 项目总监（项目附带的角色）
│   ├── soul.md
│   ├── skills/
│   └── memories/
└── _archived/            # 已删除角色的归档
    └── old_role_01/
```

**核心角色 suri** 的运行时数据位于 `~/.suri/runtime/roles/suri/`，代码仓库中 `roles/suri/soul.md` 作为初始模板。