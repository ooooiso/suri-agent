# telegram/

Telegram 机器人接入层。

## 功能

- 接收 Telegram 消息
- 将用户消息转发至 suri 核心调度
- 将角色回复返回至 Telegram 聊天

## 配置

业务配置：`groups.yaml`

| 字段 | 说明 |
|------|------|
| `telegram.enabled` | 是否启用 Telegram 集成 |
| `telegram.bot_username` | Bot 用户名 |
| `telegram.central_group_id` | 中枢群 ID |
| `groups.<dept>` | 部门绑定的 Telegram 群组 ID |

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `TELEGRAM_BOT_TOKEN` | Bot Token（从 @BotFather 获取） |
| `TELEGRAM_BOT_USERNAME` | Bot 用户名 |
| `TELEGRAM_CENTRAL_GROUP_ID` | 中枢群 ID |

## 命令列表

| 命令 | 说明 | 使用场景 |
|------|------|---------|
| `/start` | 开始使用 | 私聊 |
| `/help` | 显示帮助 | 私聊/群组 |
| `/status` | 查看系统状态 | 私聊/群组 |
| `/bind_group <部门>` | 绑定群到部门 | 群组（管理员） |
| `/create_role <角色ID> [部门]` | 创建新角色 | 私聊 |

## 投影规则

- 同部门通信 → 投影到该部门群
- 跨部门通信 → 投影到双方部门群 + 中枢群
- 投影是单向展示，不参与通信路由

## 事件记录

- 初始预留
- 2026-05-01: 实现真连接、命令处理、投影服务
