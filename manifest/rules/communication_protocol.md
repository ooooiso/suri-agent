---
rule_id: communication_protocol
name: 角色通信协议
version: "0.1.0"
owner: suri
last_updated: 2026-04-30
---

# 角色通信协议

## 1. 寻址方式

- 角色间通过 `role_id` 寻址。
- Telegram/飞书账号映射见 `function_index.md` 中的角色黄页。
- 群组 ID 见 `communication/telegram.md`。

## 2. 消息格式（必填字段）

每条任务相关消息必须包含：

```yaml
message_id: "msg_xxx"          # 全局唯一消息 ID
sender_role: "role_id"         # 发送者角色 ID
receiver_role: "role_id"       # 接收者角色 ID（或群组 ID）
timestamp: "2026-04-30T08:36:00Z"
priority: high | normal | low
task_ref: "task_xxx"           # 关联任务 ID
body:
  type: task | approval | notify | escalation
  content: "消息正文"
  attachments: []              # 附件列表（可选）
```

## 3. 通信通道纪律

| 场景 | 通道 | 说明 |
|------|------|------|
| 部门内部沟通 | 部门群 | 如设计部使用 `@shushi_design_group` |
| 总监→suri 汇报 | 私聊 | 总监直接向 suri 汇报任务状态 |
| 跨部门协作 | 总监对总监（私聊）+ 抄送调度群 | 必须双方总监对接，抄送 `@shushi_central_group` |
| 广播通知 | 中台调度群 | suri 向全平台广播重大事项 |
| 审批消息 | security_admin → suri → 用户 | 按 `security.md` 规定的流向 |

## 4. 跨部门协作强制规则

- **禁止**普通成员跨部门直接通信。
- 跨部门需求必须由**需求方总监**向**提供方总监**发起（私聊）。
- 私聊内容必须抄送中台调度群，供 suri 跟踪。
- 违规跨部门直连将被安全钩子拦截并警告。

## 5. 消息留存

- 所有任务相关消息由 suri 记录到 `sessions/` 和 `state.db`。
- 审批消息留存期限：90 天。
- 普通任务消息留存期限：30 天。
