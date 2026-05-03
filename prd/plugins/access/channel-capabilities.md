# 通道能力模型

> 每个通道插件声明能力矩阵，session-hub 根据能力差异适配输出。

---

## 一、能力矩阵总览

| 能力 | CLI | Telegram | Web | 桌面端 |
|------|:---:|:--------:|:---:|:------:|
| **纯文本** | ✅ | ✅ | ✅ | ✅ |
| **Markdown 渲染** | ✅基础 | ✅MarkdownV2 | ✅完整 | ✅原生 |
| **HTML 渲染** | ❌ | ❌ | ✅ | ✅部分 |
| **命令前缀** | ✅ | ✅ | ✅ | ✅ |
| **图片** | 📎链接 | ✅直接发送 | ✅img标签 | ✅原生嵌入 |
| **视频** | ❌ | ❌ | ✅ | ✅原生 |
| **音频** | ❌ | ✅语音消息 | ✅ | ✅原生 |
| **文件** | 📎链接 | ✅直接发送 | ✅下载/Blob | ✅本地保存 |
| **按钮/选项** | ❌ | ✅内联键盘 | ✅原生按钮 | ✅原生组件 |
| **表单** | ❌ | ❌ | ✅ | ✅ |
| **流式输出** | ✅实时 | ✅实时 | ✅实时 | ✅实时 |
| **富 UI(卡片/组件)** | ❌ | ❌ | ✅ | ✅ |
| **原生通知** | ❌ | ✅ | ✅浏览器 | ✅系统通知 |
| **动态内容更新** | ❌ | ✅编辑消息 | ✅WebSocket | ✅本地刷新 |
| **离线模式** | ❌ | ❌ | ❌ | ✅ |
| **本地缓存** | ❌ | ❌ | ❌ | ✅ |
| **剪贴板** | ❌ | ✅ | ✅ | ✅ |
| **语音输入** | ❌ | ❌ | ✅WebRTC | ✅系统API |
| **身份认证** | ❌ | ❌ | ✅OAuth | ✅系统账户 |

---

## 二、能力协商工作原理

```
系统产生响应
    │
    ├── content_type: "video" (系统想发视频)
    │
    ▼
session-hub 查 session.capabilities
    │
    ├── CLI: video=false → 降级链: video → link → text
    │   └── 发文本 "{视频文件: demo.mp4, 大小: 15MB}"
    │
    ├── Telegram: video=false → 降级链: video → file → link
    │   └── 发文件 demo.mp4
    │
    ├── Web: video=true → 直接发
    │   └── <video src="..." controls>
    │
    └── Desktop: video=true → 直接发
        └── 原生视频播放器嵌入
```

### 降级链

每个通道定义自己的降级链：

| 通道 | 降级链 |
|------|--------|
| CLI | `rich → markdown → text`, `video → image → text`, `file → text` |
| Telegram | `html → markdown → text`, `video → file → text`, `image → file → text` |
| Web | 无降级（全能力） |
| Desktop | 无降级（全能力） |

---

## 三、通道能力声明格式

每个通道插件的 manifest.json 中声明能力矩阵：

```json
{
  "name": "channel.cli",
  "channel_type": "cli",
  "version": "1.0.0",
  "entry": "channel.py",
  "capabilities": {
    "core": {
      "text": true,
      "markdown": true,
      "commands": true
    },
    "media": {
      "images": false,
      "video": false,
      "audio": false,
      "files": false,
      "file_max_size_mb": 0
    },
    "interaction": {
      "buttons": false,
      "forms": false
    },
    "streaming": {
      "text_stream": true,
      "file_stream": false
    },
    "ui": {
      "rich_ui": false,
      "notifications": false,
      "dynamic_content": false,
      "offline_mode": false,
      "local_storage": false
    },
    "extras": {
      "clipboard": false,
      "voice": false,
      "location": false,
      "identity": false
    }
  },
  "degrade_chain": {
    "rich": ["markdown", "text"],
    "video": ["image", "text"],
    "file": ["text"],
    "html": ["markdown", "text"],
    "image": ["text"]
  }
}
```

---

## 四、各通道输出适配规则

### CLI

```
规则:
  - 纯文本 → 直接打印
  - Markdown → 基本 ANSI 渲染（**粗体** → 粗体，`代码` → 颜色高亮）
  - 图片 → 显示路径/URL + 图片尺寸
  - 文件 → 显示文件名 + 大小 + 路径
  - 流式 → 实时逐字符输出
  - 过长输出 → 自动分页（q 退出，回车继续）
```

### Telegram

```
规则:
  - 纯文本 → 发送文本消息
  - Markdown → 转换为 MarkdownV2（严格转义特殊字符）
  - 图片 → 发送 Photo 消息（支持预览）
  - 文件 → 发送 Document 消息
  - 按钮 → 发送内联键盘 InlineKeyboardMarkup
  - 流式 → 编辑单条消息实时更新
  - 长消息 → 自动分段（max 4096 字符）
```

### Web

```
规则:
  - 纯文本 → p 标签
  - Markdown → 完整 Markdown 渲染（marked.js / react-markdown）
  - HTML → 直接插入 DOM
  - 图片 → img 标签，懒加载
  - 视频 → video 标签
  - 文件 → 下载链接 / Blob URL
  - 富 UI → 自定义组件（卡片/图表/表格）
  - 流式 → WebSocket 实时推送
  - 按钮 → HTML button / 表单
```

### 桌面端

```
规则:
  - 与 Web 一致，但利用原生能力
  - 图片 → 原生图片组件，支持放大/保存
  - 视频 → 原生视频播放器
  - 文件 → 本地保存对话框
  - 通知 → 系统原生通知（macOS Notification Center / Windows Toast）
  - 离线 → 本地 SQLite 缓存 + 离线队列
```

---

## 五、通道路由配置

```yaml
# ~/.suri/data/configs/channel_routes.yaml
session_hub:
  default_channel: "cli"

  channels:
    cli:
      enabled: true
      description: "终端交互"
      entry: "plugins.access.channels.cli.channel"

    telegram:
      enabled: true
      description: "Telegram 机器人"
      entry: "plugins.access.channels.telegram.channel"
      config:
        bot_token_env: "TELEGRAM_BOT_TOKEN"
        webhook_url: "https://example.com/webhook"

    web:
      enabled: false
      description: "Web 端交互"
      entry: "plugins.access.channels.web.channel"
      config:
        websocket_port: 8765
        cors_origins: ["http://localhost:3000"]

    desktop:
      enabled: false
      description: "桌面端客户端"
      entry: "plugins.access.channels.desktop.channel"
      config:
        local_db_path: "~/.suri/runtime/access/desktop.db"
        auto_start: false
