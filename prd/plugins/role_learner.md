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
