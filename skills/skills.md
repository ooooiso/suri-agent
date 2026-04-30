---
owner: suri
name: suri 技能索引
version: "0.1.0"
---

# suri 技能索引

本文件列出 suri 专属技能库中的所有技能包。这些技能仅供 suri 自身使用，用于调度、审批、异常处理等核心职能。

| 技能 ID | 路径 | 功能概述 | 状态 |
|---------|------|---------|------|
| task_dispatch | skills/task_dispatch/ | 解析需求、匹配部门、下发总监 | active |
| escalation | skills/escalation/ | 任务升级、重试耗尽、用户回流 | active |
| user_approval | skills/user_approval/ | 安全审批流程中向用户请求确认 | active |
| exception_handler | skills/exception_handler/ | 通用异常捕获与分类处理 | active |
| cross_department_sync | skills/cross_department_sync/ | 跨部门协作的进度同步与汇总 | active |

> 新增或修改技能后，需更新本索引并通知 config_admin。
