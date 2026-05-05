# 桌面端通道

> 桌面端原生应用接入通道。全能力通道：富文本、图片/视频/文件、原生通知、离线模式、本地缓存。

---

## 一、定位

桌面端通道是 suri-agent 的原生桌面客户端接入方式。

**特点**：
- 全能力通道，无能力限制
- 原生系统通知
- 离线缓存和队列
- 本地文件系统深度集成
- 多窗口/多会话管理

---

## 二、能力清单

```json
{
  "name": "channel.desktop",
  "channel_type": "desktop",
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
      "file_max_size_mb": 500
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
      "offline_mode": true,
      "local_storage": true
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
原生桌面客户端 (Electron / Tauri / Flutter)
    │
    ├── WebSocket ↔ session-hub (实时双向)
    ├── 本地 IPC 通道 ↔ session-hub (高性能)
    ├── 本地 SQLite (离线缓存)
    ├── 文件系统 API (本地文件读写)
    └── 系统通知 API
```

---

## 四、实现要点

### 框架选择
- Electron (跨平台桌面应用)
- Tauri (更轻量的 Rust 后端 + Web 前端)
- Flutter Desktop (原生体验)

### 本地缓存
- SQLite 存储会话历史（离线可读）
- 文件缓存（图片、附件）
- 离线任务队列

### 原生集成
- macOS: Notification Center
- Windows: Toast Notifications
- Linux: D-Bus Notifications
- 系统文件选择对话框

---

> **📋 占位文档** — 具体实现时补充细节。
