# 技能进化

> 定义 Skill 维度的进化机制 —— 检测、建议、激活、兼容性。

---

## 一、技能进化流程

```
role_learner 检测到重复模式（≥3次）
    │
    ▼
生成技能建议（Skill 文件草案）
    │
    ▼
suri 评估技能质量、确定兼容性
    │
    ▼
用户确认（或拒绝）
    │
    ▼
写入 skill 文件至 ~/.suri/runtime/roles/{role_id}/skills/
    │
    ▼
广播 skill.activated 事件
    │
    ├── 项目总监收到 → 检查项目内角色技能变更
    ├── 其他角色收到 → 自主决策是否引用
    └── 能力索引增量重建
```

---

## 二、技能文件版本

```
~/.suri/runtime/roles/{role_id}/skills/
  └── {skill_name}_v{major}.{minor}.json
```

| 版本号变更 | 意义 | 示例 |
|-----------|------|------|
| `major` 递增 | 中断性变更 | `docs_writing_v1.0` → `docs_writing_v2.0` |
| `minor` 递增 | 增强性变更 | `docs_writing_v1.0` → `docs_writing_v1.1` |

**兼容性检查规则**：
| 场景 | 兼容性 | 操作 |
|------|--------|------|
| 仅增加可选参数 | 兼容 | 自动升级 |
| 修改参数格式 | 中断性变更 | 通知项目组验证 |
| 删除核心步骤 | 不兼容 | 回滚 / 用户决策 |

---

## 三、技能检测（role_learner）

role_learner 每次异步分析时，检查该角色近期的任务模式：

```
分析维度：
  ├── 任务类型（role_comm / code_tool / llm 调用）
  ├── 工作流步骤序列
  ├── 使用的工具链
  ├── 输入输出模式
  └── 频率 ≥ 3 次
```

**检测到新模式时**：
1. 对比现有 skill 列表，确认不重复
2. 生成 skill 文件草案（含步骤/参数/输出格式）
3. 通过 upgrade_manager 发起技能建议
4. suri 评估 → 用户确认 → 激活

**技能与技能的关联**：
- role_learner 也可检测技能之间是否存在耦合关系
- 如 `code_review_v1.0` 依赖 `python_linting_v1.0`，写入 `requires_skills` 字段

---

## 四、suri 评估技能建议

suri 评估技能时的检查清单：
1. 技能是否清晰定义了输入输出
2. 是否有明确的步骤序列
3. 新技能是否与现有技能重叠
4. 是否需要额外工具支持
5. 是否需要在 manifest.exposes 中新增工具暴露
6. 技能适用于哪些角色类型

---

## 五、技能变更通知

| 事件 | 触发 | 通知范围 |
|------|------|---------|
| `skill.activated` | 新技能激活 | 该角色 + suri |
| `skill.updated` | 技能版本升级 | 所有引用该技能的角色 + 项目总监 |
| `skill.compatibility_check_needed` | major 版本变更 | 项目总监 + 项目组 |

事件 payload 包含：
- role_id
- skill_name
- 新旧版本号
- 兼容性评估（兼容/中断性变更/不兼容）
- 变更摘要
