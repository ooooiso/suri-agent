# Web 通道

> Web 端接入通道。支持富文本、图片、视频、动态 UI 组件、WebSocket 实时流。

---

## 一、定位

Web 通道是 suri-agent 的浏览器端接入方式。

**特点**：
- 完整的富文本渲染（HTML/Markdown/CSS）
- 图片/视频嵌入渲染
- 自定义 UI 组件（卡片、图表、表格）
- WebSocket 实时流式输出
- 浏览器通知

---

## 二、能力清单

```json
{
  "name": "channel.web",
  "channel_type": "web",
  "version": "0.0.0",
  "capabilities": {
    "core": {
      "text": true,
      "markdown": true,
      "commands": true
    },
    "media": {
      "images": true,
      "video": true,
      "audio": true,
      "files": true,
      "file_max_size_mb": 100
    },
    "interaction": {
      "buttons": true,
      "forms": true
    },
    "streaming": {
      "text_stream": true,
      "file_stream": true
    },
    "ui": {
      "rich_ui": true,
      "notifications": true,
      "dynamic_content": true,
      "offline_mode": false,
      "local_storage": false
    },
    "extras": {
      "clipboard": true,
      "voice": true,
      "location": true,
      "identity": true
    }
  }
}
```

---

## 三、架构

```
浏览器 (React/Vue)
    │
    ├── WebSocket ↔ session-hub (实时双向)
    ├── HTTP/REST ↔ session-hub (文件上传/下载)
    └── Service Worker (浏览器通知)
```

---

## 四、实现要点

### 前端框架
- React 或 Vue SPA
- WebSocket 客户端管理连接
- Markdown 渲染：marked.js / react-markdown
- UI 组件库

### 后端
- WebSocket 服务器（与 session-hub 集成）
- 文件上传/下载端点
- CORS 配置

---

> **📋 占位文档** — 具体实现时补充细节。
