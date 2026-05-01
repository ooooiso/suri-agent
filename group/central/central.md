# central/


## 部门负责人

- `suri` — 中枢调度总监（director / scheduler）

## 成员角色

| 角色 | 类型 | 职责 |
|------|------|------|
| `suri` | scheduler | 中枢调度：需求解析、任务分发、跨部门协调、异常处理 |
| `suri_dev` | maintainer | 程序维护：核心代码维护、Bug 修复、框架升级、工具开发 |
| `suri_hr` | admin | 人力资源：角色创建、部门管理、技能模板维护、能力清单同步 |
| `suri_review` | reviewer | 文档审核：文档一致性审查、变更确认、质量把关 |
| `suri_stats` | specialist | 统计分析：数据统计、项目指标、Token 用量监控 |

## 别名兼容

| 旧名称 | canonical 名称 |
|--------|---------------|
| `suri-dev` | `suri_dev` |
| `suri-hr` | `suri_hr` |
| `document-review` | `suri_review` |
| `analyst` | `suri_stats` |

## 事件记录

- 2026-05-01: V2.0 重构 — 角色重命名为下划线命名法（suri_dev, suri_hr, suri_review, suri_stats），保留别名兼容
