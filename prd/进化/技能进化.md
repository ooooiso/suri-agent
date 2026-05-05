# 技能进化（Skill Evolution）

> 定义 suri-agent 中角色技能的进化机制。技能进化是由 role_learner 检测模式、suri 评估、用户确认的闭环流程。

---

## 一、技能进化的触发条件

| 触发条件 | 检测者 | 说明 |
|---------|--------|------|
| 模式检测 | role_learner | 检测到角色执行重复任务 ≥3 次 |
| 用户主动 | 用户直接要求 | 用户通过 CLI/Telegram 提出 skill 需求 |
| suri 建议 | suri 角色 | suri 发现任务可抽象为 skill |
| 迁移复用 | 角色导入 | 从其他角色导入 skill |

## 二、技能生成流程

```
role_learner 检测到重复模式
    │
    ▼
提取任务特征（触发词、步骤、产出物）
    │
    ▼
生成 skill v0.1 草案（LLM 辅助）
    │
    ▼
发布 role.skill_suggested 事件
    │
    ▼
suri 收到通知 → 评估 skill 质量
    │
    ├── 质量达标 → 呈现给用户确认
    │   ├── 用户确认 → 激活 skill
    │   └── 用户拒绝 → 记录到 rejected_skills
    │
    └── 质量不达标 → 丢弃，记录到 failed_attempts
```

## 三、skill 版本管理

```
skill 文件路径：{role_id}/skills/{skill_name}_v{major}.{minor}.json

版本规则：
  major 递增：接口/参数变更，不向后兼容
  minor 递增：功能增强，向后兼容

升级流程：
  1. 生成新版本 skill 文件
  2. 保留旧版本（可回滚）
  3. 发布 role.skill_updated 事件
  4. 通知所有使用此 skill 的角色

回滚：
  1. 恢复旧版本 skill 文件
  2. 发布 role.skill_rolled_back 事件
  3. 使用旧版本继续执行
```

## 四、技能生命周期

```
DRAFT ──→ ACTIVE ──→ DEPRECATED ──→ REMOVED
  │          │            │
  │          ├── 正常使用   └── 不再使用
  │          ├── 可升级
  │          └── 可回滚
  │
  └── 用户确认前 → 若被拒绝 → DISCARDED

DRAFT:    角色已生成但未激活
ACTIVE:   用户已确认，可使用
DEPRECATED: 有新版本替代
REMOVED:  已删除（但仍可恢复）
DISCARDED: 用户拒绝