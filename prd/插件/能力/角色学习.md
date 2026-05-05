# role_learner 插件 PRD

## 定位

角色自学习插件，专注于**单个角色**的记忆读取、经验提取、技能形成检测。不分析框架全局，不生成程序级报告。只服务角色成长，和程序无关。

同时提供 **ProgramLearner** 模块——全局分析能力，由 suri 角色调用，不独立运行。

## 功能需求

### 1. 经验提取（ExperienceExtractor）
- 从角色的 `experiences` 表读取任务反馈
- LLM 分析任务记录，生成结构化洞察（insight）
- 洞察类别：success_pattern / improvement / pitfall / preference
- 保存到 `roles/{role_id}/memories/insights/*.md`

### 2. 技能形成检测
- 监控角色重复使用的工具组合
- 检测到重复模式（≥3 次）→ 生成技能建议
- 技能建议上报 role_manager，可选创建为正式技能

### 3. 上下文注入
- `get_recent_insights_for_context(role_id, task_hint)`
- 按时间（30 天内）+ confidence 排序
- 关键词粗排匹配 task_hint
- 总字符不超过 2000，直接注入角色系统提示

### 4. 学习触发
- 任务完成后异步触发（不阻塞主流程）
- `/learn role {role_id}` 手动触发
- 定时模式：记忆积累达到阈值自动触发（预留）

## ProgramLearner（全局分析模块）

> 非独立插件，不独立运行。由 **suri 角色**在需要全局分析时调用。

### 职责边界

| 维度 | RoleLearner | ProgramLearner |
|------|------------|----------------|
| 分析对象 | 单个角色的记忆、行为 | 全局插件调用模式、系统性能、角色协作效率 |
| 触发者 | 角色任务完成事件 | suri 角色主动调用 |
| 输出 | 角色洞察、技能建议 | 系统优化建议、架构调整方案 |
| 数据范围 | `roles/{role_id}/` 下数据 | 全局事件日志、插件注册表、角色协作记录 |

### 调用方式
suri 角色通过事件调用：
```
suri 角色发布事件：task.created
  └─ target: role_learner
  └─ payload: {mode: "program_analysis", scope: "global", focus: "plugin_efficiency"}

role_learner 返回：
  └─ event: task.completed
  └─ payload: {report: "...", suggestions: [...]}
```

### 输出示例
- 插件调用热点分析：哪些插件被频繁调用，是否存在冗余
- 角色协作效率：任务分配是否合理，是否存在瓶颈角色
- 系统资源建议：基于事件日志推断性能优化点
- **注意**：ProgramLearner 只生成建议报告，不直接修改任何代码或配置

## 接口定义

### 订阅事件
- `task.completed` / `task.failed` → 异步触发对应角色学习（RoleLearner 模式）
- `user.command`（/learn role）→ 手动触发角色学习
- `task.created`（mode=program_analysis）→ 触发全局分析（ProgramLearner 模式，仅 suri 角色可调用）

### 发布事件
- `role.skill_suggested` — 发现新技能模式，上报 role_manager
- `learning.report_generated` — ProgramLearner 生成系统优化报告，上报 upgrade_manager
- `task.completed` — ProgramLearner 分析完成，返回报告给 suri 角色

## 配置项

```yaml
role_learner:
  auto_trigger_threshold: 20
  analysis_days: 7
  insight_ttl_days: 90
  min_skill_pattern_count: 3
  context_injection_limit: 2000
  program_learner:
    enabled: true
    min_events_for_analysis: 100
    analysis_focus: ["plugin_efficiency", "role_collaboration", "resource_usage"]
```

## 事件 Payload Schema

### 订阅事件

#### `task.completed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `role_id` | string | 是 | 完成任务的角色 ID |
| `result` | string | 是 | 执行结果 |
| `duration_ms` | integer | 否 | 耗时 |

#### `task.failed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `role_id` | string | 是 | 角色 ID |
| `error_message` | string | 是 | 失败原因 |

#### `user.command`（command=/learn role）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `command` | string | 是 | "/learn" |
| `args` | object | 是 | 参数，含 `role_id` |

#### `task.created`（mode=program_analysis）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | string | 是 | "program_analysis" |
| `scope` | string | 是 | 分析范围 |
| `focus` | array | 否 | 关注维度 |

### 发布事件

#### `role.skill_suggested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role_id` | string | 是 | 目标角色 ID |
| `skill_name` | string | 是 | 建议技能名称 |
| `skill_description` | string | 是 | 技能描述 |
| `trigger_count` | integer | 是 | 触发模式检测的次数 |
| `confidence` | float | 是 | 置信度 0.0-1.0 |

## 学习与升级流程

角色学习是"分析→建议→确认→执行"的闭环。所有变更须经用户确认。

### 触发条件

| 触发方式 | 来源 | 说明 |
|----------|------|------|
| 事件触发 | `task.completed` / `task.failed` | 任务完成后异步触发，不阻塞主流程 |
| 手动触发 | `user.command`（/learn role {role_id}） | 用户或角色主动发起 |
| 阈值触发 | 记忆积累达到阈值 | 预留机制，自动触发学习 |

### 执行流程

```
task.completed 事件
    │
    ▼
1. 读取角色记忆（experiences 表，最近7天）
    │
    ▼
2. LLM 分析 → 生成结构化洞察
   · success_pattern — 成功模式
   · improvement — 改进方向
   · pitfall — 常见陷阱
   · preference — 偏好
    │
    ▼
3. 保存洞察到 roles/{id}/memories/insights/{timestamp}_{type}.md
    │
    ▼
4. 技能模式检测：重复工具组合≥3次 → 生成技能建议
    │
    ▼
5. 发布 role.skill_suggested 事件 → suri 汇总
    │
    ▼
6. 用户确认流程：suri 呈现 → 用户确认/修改/拒绝
    │
    ▼
7. 技能激活：写入角色 skill → 下次任务可用
```

### 上下文注入机制

```
角色接收新任务
    │
    ▼
role_learner.get_recent_insights_for_context(
    role_id={当前角色},
    task_hint={任务描述}
)
    │
    ▼
按时间(30天内) + confidence 排序
关键词粗排匹配 task_hint
    │
    ▼
选取 Top-N 洞察（总字符 ≤ 2000）
注入角色系统提示
```

### 角色自增技能流程

角色可主动申请增加新技能，无需等待被动分析：

**触发场景**：
1. 角色发现现有工具不满足需求
2. 角色重复执行同一流程≥3次，固化为技能
3. 角色被分配的新任务超出当前技能范围

**执行流程**：
```
角色发现技能缺口 → 分析缺口 → 生成技能方案（名称/触发条件/处理流程/所需工具）
    │
    ▼
提交申请 → upgrade_manager.save_report() → suri
    │
    ▼
suri 评估（是否重复/冲突/安全）
    │
    ▼
向用户呈现 → 用户确认/拒绝
    │
    ▼
确认 → 技能激活、热更新、tool_descriptions 更新
拒绝 → 记录原因
```

### suri 升级自身流程

suri 作为核心调度角色，当遇到无法处理的需求时，向用户申请增加新技能：

```
suri 接收需求 → 遍历技能 → 无法处理
    │
    ▼
suri 问用户："是否允许增加新技能？"
    │
    ├── 确认 → suri 生成新技能方案 → 用户确认 → 技能激活
    └── 拒绝 → 记录原因
```

suri 技能类型限制为：调度类、角色管理类、系统维护类、自身升级类。

### 升级方案标准格式

所有升级方案包含：

| 字段 | 说明 |
|------|------|
| source | role_learner / role / plugin / suri |
| type | skill_upgrade / behavior_adjust / tool_update |
| reason | 为什么需要升级 |
| changes | 具体变更内容（add/remove/modify） |
| rollback_strategy | 回滚方法（version_restore + backup_path） |
| risk_assessment | 风险评估（impact / failure_probability） |

### 状态机

```
PENDING → SUBMITTED → APPROVED → IMPLEMENTED → VERIFIED → COMPLETED
                            │                        │
                            ├── REJECTED             └── ROLLED_BACK
                            └── DEFERRED
```

### 统一约束

1. **无实体可私自修改代码或技能** — 所有变更须经用户确认
2. **所有方案必须包含回滚策略**
3. **suri 变更后需验证基础调度功能**
4. **所有角色都有升级机制**

## 技能注册与发现

### 技能注册

技能通过事件驱动注册到系统：

```
角色创建 / 技能新增
    │
    ▼
发布 role.skill_registered 事件
    │
    ├─ payload: { role_id, skills: [...], force: bool }
    │
    ▼
template_updater 处理
    ├─ 读取 tool_descriptions.yaml
    ├─ 按 skill_id 去重
    └─ 追加/覆盖 → 写回 YAML
```

**注册时机**：
| 时机 | 说明 |
|------|------|
| 角色创建时 | role_manager 自动注册角色初始技能 |
| 角色升级时 | upgrade_manager 注册新技能 |
| 手动触发 | suri 或角色主动发布注册事件 |

### 技能状态

| 状态 | 说明 |
|------|------|
| `active` | 可用，可被匹配 |
| `inactive` | 已停用，不可匹配 |
| `deprecated` | 已废弃，仅保留历史 |
| `beta` | 测试中，仅限指定角色使用 |

### 技能匹配策略

suri 如何找到匹配的技能：

```
用户输入 → suri 分析需求
    │
    ▼
读取 tool_descriptions.yaml 遍历 skills
    ├─ 用户输入匹配 triggers（关键词匹配）
    ├─ 用户输入匹配 description（语义匹配）
    └─ 多技能组合满足复杂需求（组合匹配）
```

## 依赖关系

- 上游：suri_core、memory_service、llm_gateway
- 下游：role_manager（接收技能建议）、upgrade_manager（保存 UpgradeReport）
- 特殊：ProgramLearner 模块仅响应 suri 角色的调用

## 生命周期

1. `init()` → 加载学习配置
2. `start()` → 标记就绪
3. `stop()` → 中断正在进行的分析
4. `cleanup()` → 保存待处理报告

## 安全边界

- 只读角色记忆，不修改运行时数据
- LLM 分析上下文脱敏
- 报告生成不阻塞主流程
- **核心原则**：RoleLearner 只分析单个角色，不跨角色全局分析；ProgramLearner 只生成建议，不直接修改系统
- **权限控制**：ProgramLearner 模式仅响应 suri 角色的调用事件，其他角色请求被拒绝
