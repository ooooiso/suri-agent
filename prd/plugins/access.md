# access 插件 PRD

## 定位

统一接入层，接收用户输入，转换为事件发送到 event_bus。支持多通道（CLI、Telegram、WebSocket 等），所有通道统一通过事件总线与系统交互。

---

## 功能需求

### 1. 多通道接入

| 通道 | 状态 | 说明 |
|------|------|------|
| CLI | ✅ 已实现 | 终端交互，默认接入方式 |
| Telegram | ✅ 已实现 | Telegram 机器人 |
| WebSocket | 📋 规划中 | 浏览器端交互 |
| API | 📋 规划中 | 第三方系统 HTTP 接入 |

### 2. 消息路由

- 接收各通道输入，统一转换为 `user.input` 事件
- 支持命令前缀（如 `/model`、`/role`）
- 命令转换为 `user.command` 事件

### 3. 消息格式化

- 统一输出格式（Markdown）
- 通道适配（CLI 纯文本、Telegram MarkdownV2）
- 长消息分页

---

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `llm.response` | llm_gateway | 向用户显示 LLM 回复 |
| `llm.stream_chunk` | llm_gateway | 流式输出 |
| `interrupt.user_decision_needed` | interrupt_handler | 向用户呈现决策选项 |
| `system.notification` | 任意插件 | 系统通知 |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `user.input` | role_manager | 用户消息 |
| `user.command` | 对应插件 | 用户命令 |

---

## 热更新与解耦

### 1. 通道路由外部化

当前通道选择逻辑硬编码在代码中，新增通道需改代码。

**优化方案**：
- 创建 `~/.suri/data/configs/channel_routes.yaml` 作为外部路由配置
- 通道选择逻辑从代码中分离

### 2. 通道与逻辑分离

- 每个通道（CLI/Telegram）独立文件
- 通道注册通过事件机制
- 新增通道只需添加 YAML 配置 + 实现通道类

### 3. 外部路由配置格式

```yaml
# ~/.suri/data/configs/channel_routes.yaml
channels:
  cli:
    enabled: true
    module: "plugins.access.cli"
    description: "命令行交互"
  telegram:
    enabled: true
    module: "plugins.access.telegram"
    description: "Telegram 机器人"
    config:
      bot_token_env: "TELEGRAM_BOT_TOKEN"
```

---

## 配置项

```yaml
access:
  default_channel: "cli"
  channels:
    cli:
      enabled: true
    telegram:
      enabled: true
      bot_token_env: "TELEGRAM_BOT_TOKEN"
  output:
    format: "markdown"
    max_message_length: 4096
```

---

## 依赖关系

- 上游：suri_core（EventBus）
- 下游：role_manager（处理用户输入）
- 下游：llm_gateway（接收 LLM 响应）

---

## 生命周期

1. `init()` → 加载通道配置
2. `start()` → 启动各通道
3. `stop()` → 关闭各通道
4. `cleanup()` → 清理资源
