# access 接入体系总览

> access 不是"一个接入插件"，而是**会话控制中枢 + 多通道插件体系**。

---

## 一、核心思想

```
access 体系 = 会话中枢(SessionHub) + N 个通道插件(Channel Plugins)
                  │
                  ▼
          会话控制中枢（session-hub）
         ┌────────────────────────────┐
         │ • 会话创建/切换/销毁        │
         │ • 统一输入输出协议           │
         │ • 事件路由                  │
         │ • 通道注册/发现             │
         │ • 能力协商                  │
         └────┬───────┬───────┬───────┘
              │       │       │
      ┌───────┘       │       └───────┐
      ▼               ▼               ▼
  CLI 通道       Telegram 通道     Web 通道
  (channel.cli)  (channel.tg)    (channel.web)
      │               │               │
      ▼               ▼               ▼
  纯文本+Markdown  MarkdownV2+    富文本+图片+
                  图片/文件      视频+动态UI
```

**每个通道是独立插件**，注册到 access 会话中枢：

| 通道 | 注册名 | 能力级别 |
|------|--------|---------|
| CLI | `channel.cli` | 文本 + Markdown |
| Telegram | `channel.tg` | 文本 + MarkdownV2 + 图片 + 文件 |
| Web | `channel.web` | 富文本 + 图片 + 视频 + 动态组件 + 实时流 |
| 桌面端 | `channel.desktop` | 富文本 + 图片/视频/文件 + 原生通知 + 本地缓存 |
| API | `channel.api` | 纯 JSON 结构化输出 |

---

## 二、access 体系文档结构

```
prd/plugins/access/
├── README.md                 ← 本文档（体系总览）
├── session-hub.md            ← ★ 会话中枢（核心插件）
├── session-protocol.md       ← ★ 统一会话协议
├── channel-capabilities.md   ← ★ 通道能力模型
├── wizard.md                 ← 引导式配置器
├── config_editor.md          ← 配置编辑器
└── channels/
    ├── cli.md                ← CLI 通道
    ├── telegram.md           ← Telegram 通道
    ├── web.md                ← Web 通道（占位）
    └── desktop.md            ← 桌面端通道（占位）
```

---

## 三、阅读路径

```
先理解整体 →
  1. README.md                  ← 体系总览
  2. session-hub.md             ← 会话中枢核心
  3. session-protocol.md        ← 统一协议

再理解通道 →
  4. channel-capabilities.md    ← 能力模型
  5. channels/cli.md            ← CLI 细节
  6. channels/telegram.md       ← Telegram 细节

扩展时 →
  7. channels/web.md            ← Web 实现参考
  8. channels/desktop.md        ← 桌面端实现参考
```

---

## 四、通道与角色的关系

```
                    access 会话中枢
                         │
               ┌─────────┴──────────┐
               │                    │
         用户输入事件         系统输出事件
          (user.input)      (llm.response等)
               │                    │
               ▼                    │
          EventBus                  │
               │                    │
               ▼                    │
          role_manager              │
          (代理角色处理)              │
               │                    │
               └─────────┬──────────┘
                         │
               ┌─────────▼──────────┐
               │   能力协商          │
               │   access 根据通道    │
               │   能力调整输出格式   │
               └────────────────────┘
```

- 通道不直接与角色交互，全部通过 EventBus
- access 根据通道能力矩阵自动适配输出格式
- 同一个响应，不同通道可能得到不同的呈现（通道自主选择）
