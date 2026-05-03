# CLI 通道

> 终端交互通道。最轻量级的接入方式，纯文本 + Markdown 基础渲染。

---

## 一、定位

CLI 通道是 suri-agent 默认的接入方式，也是最基础的通道实现。

**特点**：
- 零依赖，终端天然可用
- 纯文本交互，无富 UI
- 适合开发调试场景
- 作为 session-hub 的默认 fallback

---

## 二、能力清单

```json
{
  "name": "channel.cli",
  "channel_type": "cli",
  "version": "1.0.0",
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
    "html": ["text"],
    "image": ["text"]
  }
}
```

---

## 三、启动方式

```bash
# 默认启动（main.py 自动启动 CLI）
python main.py

# 显式指定通道
python main.py --channel cli
```

启动后进入交互模式：

```
suri-agent v1.0.0 — CLI 通道已就绪
输入 /help 查看可用命令
输入 /exit 退出

suri> 
```

---

## 四、消息格式

```python
# 输入：用户在 suri> 提示符后输入文本
# 纯文本 → user.input
# /命令  → user.command

# 输出：直接打印到终端
# 纯文本 → print()
# Markdown → ANSI 渲染
# 图片 → "📷 [图片名称.png] (宽度x高度)"
# 文件 → "📎 [文件名.pdf] (2.3MB)"
```

---

## 五、流式输出

CLI 天然支持流式输出：

```
suri> 写个故事
suri (writing)...... 
从前有一个...

# 流式输出实时逐字符打印
# 终端显示 streaming 状态指示器
```

---

## 六、长消息分页

超过终端高度的消息自动分页：

```
# 输出末尾显示
-- 更多 (回车继续, q 退出) --
```

---

## 七、特殊命令（会话级）

| 命令 | 作用 | 示例 |
|------|------|------|
| `/exit` | 退出会话 | `/exit` |
| `/help` | 帮助 | `/help` |
| `/history` | 查看历史 | `/history 20` |
| `/session` | 查看会话信息 | `/session` |
| `/clear` | 清屏 | `/clear` |

---

## 八、实现参考

CLI 通道插件接口：

```python
class CliChannel(ChannelPlugin):
    async def start(self):
        """启动 CLI 读取循环"""
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, input, "suri> ")
            msg = SessionMessage(
                session_id=self.session_id,
                channel_type="cli",
                channel_id=self.channel_id,
                msg_type="command" if line.startswith("/") else "text",
                content=line,
            )
            await self.hub.handle_input(msg)

    async def send(self, output: SessionOutput):
        """输出到终端"""
        if output.streaming:
            await self._stream_output(output.content)
        else:
            rendered = self._render(output)
            print(rendered)
            if output.options:
                self._show_options(output.options)
    
    def _render(self, output: SessionOutput) -> str:
        """根据 content_type 格式化输出"""
        if output.content_type == "markdown":
            return self._ansi_markdown(output.content)
        elif output.content_type == "text":
            return output.content
        elif output.content_type == "image":
            return f"📷 [{output.attachments[0].name}]"
        else:
            return output.content
