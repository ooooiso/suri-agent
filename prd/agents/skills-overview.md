# 技能体系

> 定义角色的技能（Skill）体系：开发、注册、发现、组合和升级。
>
> **核心原则**：技能是角色的能力原子单元。技能可独立开发、跨角色共享。

---

## 技能全景

```
Skill 体系
├── 技能文件（JSON）— 定义技能的能力和触发条件
├── 技能注册 — 通过事件注册到 tool_descriptions.yaml（三清单联动）
├── 技能发现 — 通过 template_updater 自动维护（广播通知）
├── 技能组合 — 角色可拥有多个技能，按需编排
├── 技能升级 — 角色通过 self-learning 增加或改进技能
└── 技能市场 — 跨角色共享技能（未来）
```

---

## 技能与核心设计模式

### 三清单联动

技能注册、变更和废弃遵循三清单 + 广播模式：

```
技能变更（新增/升级/废弃）
    │
    ├─ 1. 更新 Role Registry（角色清单的技能列表）
    ├─ 2. 发布 role.skill_added / role.skill_updated / role.skill_removed 事件
    ├─ 3. suri 接收事件 → 评估影响
    ├─ 4. 所有角色接收事件 → 更新自身认知
    └─ 5. 广播通知完成（通过 access 层给用户可见通知）
```

### 三层上下文隔离

技能的执行受角色的三层上下文约束：

| 上下文层 | 对技能的影响 |
|---------|-------------|
| Ad-hoc 层 | 临时会话中技能仅使用会话内记忆，7天自动清理 |
| Project 层 | 项目工作中技能使用项目专属记忆+工具映射 |
| Global 层 | 通用技能在所有项目共享，跨项目复用 |

### tool_mappings

每个技能必须定义其使用的工具映射：

```json
{
  "skill_id": "file_analysis",
  "name": "文件分析",
  "tool_mappings": [
    "code_tool.read_file",
    "code_tool.search_files",
    "code_tool.stats"
  ],
  "created_at": "2026-05-01T08:00:00Z",
  "updated_at": "2026-05-03T10:00:00Z"
}
```

工具调用时自动携带 `_meta` 上下文元数据：
```python
_meta = {
    "role_id": "developer",
    "project_id": "ecommerce_app",  # 当前项目
    "task_id": "T-001",             # 当前任务
    "session_id": "dev_session_01"  # 当前会话
}
```

---

## 目录结构

| 文档 | 说明 |
|------|------|
| [`skill_development.md`](skill_development.md) | 技能开发指南 |
| [`skill-spec.md`](skill-spec.md) | 技能注册、发现与文件格式规范（含 tool_mappings） |
| [`skill_composition.md`](skill_composition.md) | 技能组合与编排（含三层上下文的技能组合策略） |

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [`skill_spec.md`](../skill_spec.md) | Skill 文件格式规范 |
| [`template-spec.md`](../schema/template-spec.md) | tool_descriptions.yaml 模板规范 |
| [`template-auto-update.md`](../schema/template-auto-update.md) | 模板自动更新机制 |
| [`triple-registry-spec.md`](../schema/triple-registry-spec.md) | 三清单体系规范 |
| [`context-isolation.md`](../schema/context-isolation.md) | 三层上下文隔离规范 |