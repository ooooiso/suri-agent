---
adapter_id: telegram
name: Telegram 通信配置
version: "0.1.0"
owner: config_admin
last_updated: 2026-04-30
status: active
---

# Telegram 通信配置

## 基础配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| Bot Token | （见 `.env` TELEGRAM_BOT_TOKEN） | 机器人凭证 |
| suri 用户名 | @shushi_hermesbot | 调度总监账号 |
| 中台调度群 | @shushi_central_group | 跨部门协调与广播 |

## 部门群组映射

| 部门 | 群组 ID | 成员 |
|------|---------|------|
| 设计部 | @shushi_design_group | art_director, image_gen, video_gen |
| 开发部 | @shushi_eng_group | dev_lead, script_dev, backend_dev, deploy_dev |
| 运维部 | @shushi_ops_group | ops_admin, security_admin, workflow_admin, config_admin, git_admin |
| 资源部 | @shushi_resource_group | file_admin |
| 人力资源部 | @shushi_hr_group | hr_admin |

## 消息格式

Telegram 消息由通信适配器自动封装为内部标准格式：

```yaml
message_id: "tg_msg_id"
sender_role: "resolved_from_tg_username"
receiver_role: "resolved_from_chat_id"
timestamp: "..."
priority: normal
task_ref: "..."
body: { type: ..., content: ... }
```

## 私聊 vs 群组

- **私聊**：用于 suri↔总监、总监↔总监 的直接通信。
- **群组**：用于部门内协作、中台调度群广播。
- **频道**：暂不启用。

## 状态

当前 Telegram 为**主通信通道**，飞书为预留备用。
