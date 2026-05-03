# Soul 进化

> 定义 Soul 维度的进化机制 —— suri 更新角色 Soul 的触发条件、流程和影响。

---

## 一、Soul 的定义

Soul 是角色的自我定义文件（`soul.md`），决定角色的：
- **职责边界** — 能做什么、不能做什么
- **行为偏好** — 处理风格、优先级、决策准则
- **工作方法论** — 角色如何完成通用任务
- **协作规则** — 与其他角色交互的约守

详见 [agents/soul-spec.md](../agents/soul-spec.md)。

---

## 二、Soul 更新触发条件

| 触发条件 | 发起方 | 说明 |
|---------|-------|------|
| 角色职责调整 | suri | 用户需求变化导致角色职责范围改变 |
| 技能变更导致 Soul 不适配 | role_learner → suri | 角色学到新技能，原 Soul 能力边界描述落后 |
| 用户主动要求 | 用户 | 用户直接要求调整角色的行为方式 |
| 项目总监反馈 | 项目总监 | 项目运行中发现角色职责边界不合理 |
| 协作冲突 | suri | 角色间频繁冲突，需要明确权责边界 |

---

## 三、Soul 更新流程

```
更新触发（suri / 用户 / 角色反馈）
    │
    ▼
suri 分析当前 Soul 与目标状态的差距
    ├── 职责边界是否需要调整
    ├── 行为偏好是否需要更新
    └── 协作规则是否需要修改
    │
    ▼
suri 生成 Soul 更新方案（增量 diff）
    │
    ▼
用户确认更新方案
    │
    ▼
执行 Soul 更新
    ├── 写入 soul.md 新版本
    ├── 保留旧版本备份 ~/.suri/runtime/roles/{role_id}/soul_v{old}.md
    └── 更新 meta.json 中的 soul_version
    │
    ▼
广播 soul.updated 事件
    ├── 该角色 → 刷新 system prompt
    ├── 项目总监 → 评估项目影响
    ├── 项目组 → 检查协作是否需要调整
    └── 能力索引刷新
    │
    ▼
角色以新 Soul 继续运行
    ├── 当前任务：继续使用旧 Soul（运行时 context 切换策略）
    └── 新任务：使用新 Soul
```

---

## 四、运行时 context 切换策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| **继续旧 Context**（默认） | 当前正在执行的任务继续使用旧 Soul，新任务使用新 Soul | 大部分场景 |
| **切换新 Context** | 立即刷新 system prompt 和上下文 | Soul 变更影响安全/核心决策 |
| **等待完成** | 等待当前任务完成后再生效 | Soul 变更不影响当前工作 |

**实现方式**：
- system prompt 在每次 `llm.request` 前从最新的 soul.md 刷新
- 当前任务的 context 中的旧 system prompt 继续使用到任务完成
- 新任务/新步骤开始时读取最新的 soul.md

---

## 五、Soul 版本

Soul 使用独立于 Skill 的版本体系：

```
~/.suri/runtime/roles/{role_id}/
  ├── soul.md          ← 当前版本（软链接）
  ├── soul_v1.md       ← v1 备份
  ├── soul_v2.md       ← v2 备份
  └── meta.json        ← 含 soul_version: 2
```

**回滚操作**：
1. suri 检查旧版本 soul.md 备份是否存在
2. 将当前 soul.md 替换为旧版本
3. 通知用户当前 Soul 已回滚到 v{old}
4. 广播 soul.rollback 事件
