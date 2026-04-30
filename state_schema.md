---
description: 角色级独立 SQLite 数据库结构说明
version: "1.0.0"
owner: suri
---

# 角色级独立数据库结构

## 说明

Suri 平台采用**角色级独立存储**架构。每个角色拥有独立的 SQLite 数据库：

```
group/<department>/<role>/memories/role.db
```

不再使用全局的 `state.db`。每个 `role.db` 的表结构相同，数据按角色隔离。

## 表结构

### 1. sessions — 会话记录

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | TEXT PRIMARY KEY | 会话唯一 ID |
| user_id | TEXT | 用户标识 |
| start_time | TIMESTAMP | 会话开始时间 |
| end_time | TIMESTAMP | 会话结束时间 |
| status | TEXT | active / closed / stalled |

### 2. tasks — 任务记录

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | TEXT PRIMARY KEY | 任务唯一 ID |
| session_id | TEXT | 所属会话 |
| requester_role | TEXT | 请求角色 |
| target_department | TEXT | 目标部门 |
| target_director | TEXT | 目标总监 |
| status | TEXT | pending / in_progress / completed / failed / cancelled |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| retry_count | INTEGER | 已重试次数 |

### 3. messages — 消息记录

| 字段 | 类型 | 说明 |
|------|------|------|
| message_id | TEXT PRIMARY KEY | 消息唯一 ID |
| task_id | TEXT | 关联任务 |
| sender_role | TEXT | 发送者 |
| receiver_role | TEXT | 接收者 |
| body | TEXT | 消息内容（JSON） |
| timestamp | TIMESTAMP | 发送时间 |

### 4. approvals — 审批记录

| 字段 | 类型 | 说明 |
|------|------|------|
| approval_id | TEXT PRIMARY KEY | 审批唯一 ID |
| report_id | TEXT | 关联变更报告 |
| requester | TEXT | 请求角色 |
| status | TEXT | pending / approved / rejected / timeout |
| approval_token | TEXT | 审批令牌 |
| user_response | TEXT | 用户原始回复 |
| created_at | TIMESTAMP | 创建时间 |
| resolved_at | TIMESTAMP | 解决时间 |

### 5. changelogs — 配置变更日志

| 字段 | 类型 | 说明 |
|------|------|------|
| log_id | INTEGER PRIMARY KEY AUTOINCREMENT | 自增 ID |
| commit_id | TEXT | 变更标识 |
| author_role | TEXT | 作者 |
| changed_files | TEXT | 文件清单（JSON） |
| reason | TEXT | 变更原因 |
| approver | TEXT | 审批人 |
| timestamp | TIMESTAMP | 记录时间 |

## 初始化

角色首次创建或首次访问记忆时，`MemoryService` 自动检查并初始化对应角色的 `role.db` 表结构。

## 迁移说明

- 旧架构：`state.db`（全局数据库，所有角色共用）
- 新架构：`group/<role>/memories/role.db`（角色级独立存储）
- 迁移日期：2026-04-30
- 原因：权限边界模糊、数据混乱 → 角色隔离、安全性提升
