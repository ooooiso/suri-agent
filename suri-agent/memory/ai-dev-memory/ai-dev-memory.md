# ai-dev-memory/

AI 开发记忆：面向 AI 开发助手的核心上下文库。

## 定位

本目录是 suri 平台 **AI 开发上下文的唯一权威源**。无论使用哪个编辑器或 AI 助手开发本项目，都应该优先读取这里的文档。

## 文件说明

| 文件 | 用途 |
|------|------|
| `architecture.md` | 架构决策记录（ADR），记录重大设计选择和原因 |
| `development-log.md` | 按时间线记录每次开发的内容、影响、待办 |
| `module-index.md` | 模块索引：所有目录/文件的功能、接口、所有权、变更记录 |

## 更新流程

```
开发完成 → 调用大模型生成更新摘要 → document-review 审核 → 用户确认 → 写入 ai-dev-memory/
```

## 读取建议

AI 开发助手在开始任何开发任务前，应依次读取：
1. `module-index.md` — 了解当前模块全貌
2. `architecture.md` — 了解架构约束和决策
3. `development-log.md` — 了解最近的变更和待办

## 事件记录

- 初始创建
