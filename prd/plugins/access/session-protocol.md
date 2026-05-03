# 统一会话协议

> 定义 access 体系下所有通道插件的输入输出消息格式、事件类型和能力协商机制。

---

## 一、消息格式（统一协议）

所有通道插件向 session-hub 发送的消息必须遵循此格式：

### SessionMessage

```python
@dataclass
class SessionMessage:
    """统一会话消息"""
    session_id: str           # 会话 ID
    channel_type: str         # 通道类型：cli / tg / web / desktop
    channel_id: str           # 通道侧用户标识
    msg_type: str             # text / command / file / image / video / audio / location
    content: str              # 消息内容
    attachments: list[Attachment] = []  # 附件列表（可选）
    timestamp: float          # 时间戳
    reply_to: str = None      # 回复的消息 ID（可选）
    metadata: dict = None     # 通道特定元数据（可选）

@dataclass
class Attachment:
    """附件"""
    type: str                 # image / file / video / audio / location
    url: str                  # 附件的 URL 或本地路径
    name: str                 # 附件名称
    mime_type: str            # MIME 类型
    size: int                 # 大小（字节）
    preview_url: str = None   # 预览链接（可选，仅图片/视频）
```

---

## 二、输出消息格式

session-hub 向通道插件发送的输出消息：

### SessionOutput

```python
@dataclass
class SessionOutput:
    """统一输出消息"""
    channel_type: str         # 目标通道
    channel_id: str           # 目标用户
    content_type: str         # text / markdown / html / image / file / video / rich
    content: str              # 文本/HTML/Markdown 内容
    attachments: list[Attachment] = []  # 附件（图片/文件/视频）
    options: list[str] = None          # 按钮选项（交互式，如中断决策）
    streaming: bool = False            # 是否流式输出
    stream_channel: str = None         # 流式通道 ID（用于流式输出）
    metadata: dict = None              # 额外元数据
```

---

## 三、消息类型定义

### 输入消息类型（用户 → 系统）

| msg_type | 说明 | 示例 |
|----------|------|------|
| `text` | 纯文本 | "帮我写个文档" |
| `command` | 系统命令 | `/help` |
| `image` | 图片 | 上传的截图 |
| `file` | 文件 | 上传的 PDF |
| `video` | 视频 | 上传的演示视频 |
| `audio` | 音频 | 语音消息 |
| `location` | 位置信息 | GPS 坐标 |
| `sticker` | 贴纸/表情 | Telegram sticker |

### 输出消息类型（系统 → 用户）

| content_type | 说明 | 通道能力要求 |
|-------------|------|-------------|
| `text` | 纯文本 | 所有通道 |
| `markdown` | Markdown 文本 | CLI/Telegram/Web/Desktop |
| `html` | HTML 富文本 | Web/Desktop |
| `image` | 图片 | Telegram/Web/Desktop |
| `file` | 文件 | Telegram/Web/Desktop |
| `video` | 视频 | Web/Desktop |
| `rich` | 富交互（按钮/组件/卡片） | Web/Desktop |
| `stream` | 流式文本 | CLI/Web/Desktop |

---

## 四、事件类型

### 通道 → session-hub 事件

| 事件 | 触发条件 | payload |
|------|---------|---------|
| `channel.message` | 用户发送消息 | SessionMessage |
| `channel.connected` | 用户建立连接 | session_id, channel_type, channel_id |
| `channel.disconnected` | 用户断开连接 | session_id, channel_type |
| `channel.typing` | 用户正在输入 | session_id |
| `channel.file_uploading` | 用户正在上传文件 | session_id, file_name, progress |
| `channel.command` | 用户发送命令 | session_id, command, args |

### session-hub → 通道事件

| 事件 | 触发条件 | payload |
|------|---------|---------|
| `channel.send` | 系统需要向用户发送消息 | SessionOutput |
| `channel.stream_start` | 开始流式输出 | session_id, stream_id |
| `channel.stream_chunk` | 流式输出数据块 | session_id, stream_id, chunk |
| `channel.stream_end` | 流式输出结束 | session_id, stream_id, complete_text |
| `channel.typing_notify` | 系统正在处理 | session_id |
| `channel.option_prompt` | 系统需要用户选择 | session_id, options, context |
| `channel.notification` | 系统通知 | session_id, title, body, level |

---

## 五、能力协商

每条通道在注册时声明能力矩阵。session-hub 在输出时参考能力矩阵适配。

```yaml
# 标准能力清单
capabilities:
  core:                          # 基础能力
    text: true                   # 纯文本
    markdown: true               # Markdown 渲染
    commands: true               # 命令前缀

  media:                         # 媒体能力
    images: false                # 图片
    video: false                 # 视频
    audio: false                 # 音频
    files: false                 # 文件传输
    file_max_size_mb: 0         # 文件大小限制（0=不支持）

  interaction:                   # 交互能力
    buttons: false               # 按钮/选项
    forms: false                 # 表单输入
    sliders: false               # 滑块/选择器

  streaming:                     # 流能力
    text_stream: false           # 文本流式输出
    file_stream: false           # 文件流式传输

  ui:                            # UI 能力
    rich_ui: false               # 富 UI（组件/卡片）
    notifications: false         # 原生通知
    dynamic_content: false       # 动态内容更新
    offline_mode: false          # 离线模式
    local_storage: false         # 本地缓存

  extras:                        # 扩展能力
    clipboard: false             # 剪贴板
    voice: false                 # 语音输入
    location: false              # 位置信息
    identity: false              # 身份认证
```

**能力协商流程**：
1. 通道注册时上传能力清单
2. session-hub 存储到 session.capabilities
3. 输出时，session-hub 检查每种 content_type 是否在能力矩阵中
4. 若不支持，降级：video → image → markdown → text
5. 降级链：每个通道自主定义
