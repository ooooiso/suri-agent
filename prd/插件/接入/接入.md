# access 接入体系

> **此文件已被替代** — access 不再是单个插件，而是**会话中枢 + 多通道插件体系**。

---

## 此文档已拆分

原 access.md 的内容已拆分为以下独立文档：

| 原章节 | 新位置 |
|--------|--------|
| 体系总览 | [README.md](README.md) |
| 会话+路由+生命周期 | [session-hub.md](session-hub.md) |
| 消息格式+协议 | [session-protocol.md](session-protocol.md) |
| 能力模型+适配规则 | [channel-capabilities.md](channel-capabilities.md) |
| CLI 通道 | [channels/cli.md](channels/cli.md) |
| Telegram 通道 | [channels/telegram.md](channels/telegram.md) |
| Web 通道 | [channels/web.md](channels/web.md) |
| 桌面端通道 | [channels/desktop.md](channels/desktop.md) |
| 引导式配置 | [wizard.md](wizard.md) |
| 配置编辑器 | [config_editor.md](config_editor.md) |

---

## 核心变化

```
之前：access 是一个插件，通道是它的内部功能
现在：access = session-hub（会话中枢）+ 4+ 个独立通道插件

之前：所有通道输出格式相同
现在：每个通道声明能力矩阵，按能力适配输出

之前：新增通道需改 access 代码
现在：新增通道 = 新目录 + manifest.json + channel.py
