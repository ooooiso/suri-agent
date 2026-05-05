# Telegram 通道

> Telegram Bot 接入通道。支持文本/图片/文件/按钮交互，基于 python-telegram-bot。

---

## 一、定位

Telegram 通道是 suri-agent 的移动端主要接入方式。

**特点**：
- 移动端友好，随时随地交互
- 支持图片和文件直接发送
- MarkdownV2 富文本渲染
- 内联键盘按钮交互
- 支持消息编辑（流式更新）

---

## 二、能力清单

```json
{
  "name": "channel.tg",
  "channel_type": "tg",
  "version": "1.0.0",
  "capabilities": {
    "core": {
      "text": true,
      "markdown": true,
      "commands": true
    },
    "media": {
      "images": true,
      "video": false,
      "audio": true,
      "files": true,
      "file_max_size_mb": 50
    },
    "interaction": {
      "buttons": true,
      "forms": false
    },
    "streaming": {
      "text_stream": true,
      "file_stream": false
    },
    "ui": {
      "rich_ui": false,
      "notifications": true,
      "dynamic_content": true,
      "offline_mode": false,
      "local_storage": false
    },
    "extras": {
      "clipboard": true,
      "voice": false,
      "location": true,
      "identity": false
    }
  },
  "degrade_chain": {
    "rich": ["markdown", "text"],
    "video": ["file", "text"],
    "html": ["markdown", "text"],
    "image": ["file", "text"]
  }
}
```

---

## 三、启动方式

```bash
# 需要设置环境变量
export TELEGRAM_BOT_TOKEN="your_bot_token"

# 启动（自动加载已启用的通道）
python main.py

# 或通过命令启动
python main.py --channel telegram
```

---

## 四、Bot 命令

### 会话命令

| 命令 | 作用 | 说明 |
|------|------|------|
| `/start` | 开始会话 | 创建新 session |
| `/help` | 帮助 | 显示可用命令 |
| `/history` | 查看历史 | `/history 20` 最近 20 条 |
| `/session` | 查看会话信息 | session_id, channel, 角色 |
| `/workon` | 创建/切换项目 | `/workon 项目名` |

### 交互模式

```
用户发送:
  /start → bot 回复欢迎消息
  文本消息 → bot 代理 suri 处理
  图片 → bot 接收图片（user.attachment 事件）
  文件 → bot 接收文件（user.attachment 事件）
  
Bot 回复:
  文本 → MarkdownV2 渲染
  流式 → 编辑单条消息实时更新
  图片 → 直接发送 Photo
  文件 → 直接发送 Document
  选项 → 内联键盘 InlineKeyboardMarkup
```

---

## 五、流式输出实现

Telegram 流式输出通过编辑单条消息实现：

```
# 流程
1. bot 发送 "思考中..."
2. 收到流式 chunk → 编辑消息追加内容
3. 收到 stream_end → 最终消息完成

# 限制
- 编辑频率限制：每条消息最多编辑 20 次/分钟
- 消息长度限制：最多 4096 字符（超出分段）
- 编辑仅保留最新版本

# 优化策略
- 缓存最近 5 秒的 chunk 批量更新
- 超长消息自动分段发送
- 交互结束标记 [完成] ✓
```

---

## 六、Markdown 渲染

Telegram 使用 MarkdownV2 格式，需严格转义特殊字符：

```python
MARKDOWN_ESCAPE_CHARS = [
    '_', '*', '[', ']', '(', ')', '~', '`',
    '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
]

def escape_markdown_v2(text: str) -> str:
    """转义 MarkdownV2 特殊字符"""
    for char in MARKDOWN_ESCAPE_CHARS:
        text = text.replace(char, f'\\{char}')
    return text
```

**支持格式**：
```
*bold text*     → 粗体
_italic text_   → 斜体
`code`          → 代码
```code_block``` → 代码块
[link](url)     → 链接
```

---

## 七、权限与安全

- Bot Token 通过环境变量获取，不在配置文件中明文存储
- 每个 chat_id 对应一个 session
- 支持白名单模式（仅允许特定用户/群组）
- 所有消息通过 session-hub 统一路由

---

## 八、实现参考

```python
class TelegramChannel(ChannelPlugin):
    async def start(self):
        """初始化 Telegram Bot"""
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.app = Application.builder().token(token).build()
        self.app.add_handler(MessageHandler(filters.TEXT, self.handle_text))
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.app.add_handler(CommandHandler("start", self.handle_start))
        await self.app.initialize()
        await self.app.start()

    async def send(self, output: SessionOutput):
        """发送消息到 Telegram"""
        chat_id = output.channel_id
        if output.streaming:
            await self._send_streaming(chat_id, output.content)
        elif output.content_type == "image":
            await self._send_photo(chat_id, output.attachments[0])
        elif output.content_type == "file":
            await self._send_document(chat_id, output.attachments[0])
        elif output.options:
            await self._send_with_keyboard(chat_id, output)
        else:
            text = self._render_markdown(output.content)
            await self.app.bot.send_message(chat_id, text, parse_mode="MarkdownV2")
