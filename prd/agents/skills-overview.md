# 技能体系

> 定义角色的技能（Skill）体系：开发、注册、发现、组合和升级。
>
> **核心原则**：技能是角色的能力原子单元。技能可独立开发、跨角色共享。

---

## 技能全景

```
Skill 体系
├── 技能文件（JSON）— 定义技能的能力和触发条件
├── 技能注册 — 通过事件注册到 tool_descriptions.yaml
├── 技能发现 — 通过 template_updater 自动维护
├── 技能组合 — 角色可拥有多个技能，按需编排
├── 技能升级 — 角色通过 self-learning 增加或改进技能
└── 技能市场 — 跨角色共享技能（未来）
```

---

## 目录结构

| 文档 | 说明 |
|------|------|
| [`skill_development.md`](skill_development.md) | 技能开发指南 |
| [`skill_discovery.md`](skill_discovery.md) | 技能注册与发现 |
| [`skill_composition.md`](skill_composition.md) | 技能组合与编排 |

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [`skill_spec.md`](../skill_spec.md) | Skill 文件格式规范 |
| [`spec/template_spec.md`](../../spec/template_spec.md) | tool_descriptions.yaml 模板规范 |
| [`spec/template_auto.md`](../../spec/template_auto.md) | 模板自动更新机制 |
