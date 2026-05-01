# 输出框架 (Output Framework)

**关联代码文件:**
- `suri-agent/access/output/__init__.py`
- `suri-agent/access/output/output_types.py`
- `suri-agent/access/output/output_channel.py`
- `suri-agent/access/output/output_router.py`
- `suri-agent/access/tui/cli.py` (OutputRouter 消费者)

---

## 1. 设计目标

统一管理所有角色的**输出形式**、**输出目标**、**投递方式**，实现：

- **多平台适配**: 终端、Telegram、飞书、Webhook 统一接口
- **多类型支持**: 文本、代码、文件、图片、视频、报告、告警
- **自动路由**: 根据角色和类型自动选择投递通道
- **格式协商**: 根据平台能力降级或转换输出格式
- **投递确认**: 记录投递状态，支持重试和审计

---

## 2. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     OutputRouter                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  route()    │  │  deliver_*()│  │  register_channel() │ │
│  │  路由决策    │  │  便捷方法    │  │  通道注册            │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴───────┬──────────────┬──────────────┐
       ▼               ▼              ▼              ▼
┌─────────────┐ ┌──────────┐ ┌────────────┐ ┌────────────┐
│  Terminal   │ │  File    │ │  Memory    │ │  Logger    │
│  Channel    │ │  Channel │ │  Channel   │ │  Channel   │
│ (终端输出)   │ │(文件写入) │ │(记忆存储)  │ │(日志记录)  │
└─────────────┘ └──────────┘ └────────────┘ └────────────┘
       │               │              │              │
       ▼               ▼              ▼              ▼
┌─────────────┐ ┌──────────┐ ┌────────────┐ ┌────────────┐
│  Telegram   │ │ Webhook  │ │            │ │            │
│  Channel    │ │ Channel  │ │            │ │            │
│ (预留接口)   │ │(预留接口) │ │            │ │            │
└─────────────┘ └──────────┘ └────────────┘ └────────────┘
```

---

## 3. 核心类型

### OutputType（输出类型枚举）

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| `TEXT` | 纯文本 | 日常对话、说明 |
| `CODE` | 代码片段 | 程序代码、配置文件 |
| `MARKDOWN` | Markdown 文档 | 格式化说明、文档 |
| `FILE` | 文件引用 | 生成的文件、附件 |
| `IMAGE` | 图片（URL/路径） | 截图、图表、生成图片 |
| `VIDEO` | 视频（URL/路径） | 录屏、演示视频 |
| `AUDIO` | 音频（URL/路径） | 语音消息、录音 |
| `REPORT` | 结构化报告 | 审计报告、分析报告 |
| `ALERT` | 告警通知 | 异常、错误、紧急通知 |
| `STATUS` | 状态更新 | 进度、心跳 |

### OutputChannel（输出通道枚举）

| 通道 | 说明 | 状态 |
|------|------|------|
| `TERMINAL` | 终端彩色文本输出 | ✅ 已实现 |
| `FILE` | 文件系统写入 | ✅ 已实现 |
| `MEMORY` | 角色记忆数据库存储 | ✅ 已实现 |
| `LOGGER` | 日志系统记录 | ✅ 已实现 |
| `TELEGRAM` | Telegram Bot API | ⏳ 预留接口 |
| `WEBHOOK` | HTTP POST 回调 | ⏳ 预留接口 |
| `FEISHU` | 飞书/ Lark API | ⏳ 预留接口 |

---

## 4. 路由规则

### 4.1 默认路由（按角色）

| 角色 | 默认通道 |
|------|----------|
| `suri` | TERMINAL + LOGGER + MEMORY |
| `suri-dev` | TERMINAL + FILE + LOGGER + MEMORY |
| `suri-hr` | TERMINAL + FILE + LOGGER + MEMORY |
| `document-review` | TERMINAL + FILE + LOGGER + MEMORY |

### 4.2 类型覆盖（按输出类型）

| 类型 | 追加通道 |
|------|----------|
| `ALERT` | + TELEGRAM（高优先级时） |
| `CODE` | + FILE（自动保存） |
| `REPORT` | + FILE（自动保存） |

### 4.3 优先级提升

| 优先级 | 行为 |
|--------|------|
| `urgent` | 追加 TELEGRAM + LOGGER(error) |
| `high` | 追加 LOGGER(error) |
| `normal` | 标准路由 |
| `low` | 标准路由 |

---

## 5. 文件输出路径

`FileChannel` 根据角色 Soul 中的 `output_path` 字段自动选择保存目录（与 `file_ownership` 权限系统对齐）：

| 角色 | 默认目录 | 配置来源 |
|------|----------|----------|
| `suri_dev` | `group/central/suri_dev/output/` | Soul `output_path` |
| `suri-hr` | `group/suri-hr/output/` | Soul `output_path` |
| `document-review` | `group/document-review/reports/` | Soul `output_path` |
| `suri` | `resources/sessions/output/` | Soul `output_path` |
| *(新增角色)* | `resources/temp/` | 未声明时回退 |

**动态解析**：`FileChannel` 优先从 ConfigService 读取角色 Soul 中的 `output_path` 字段，无需修改代码即可支持新角色。

所有文件写入前经过 `SecurityService` 权限校验。

---

## 6. 使用方式

### 6.1 在 CLI 中初始化

```python
from access.output import OutputRouter, OutputChannel

# 动态构建角色路由（从 Soul 文件）
role_routes = {}
for rid in config.list_roles():
    if rid == 'suri':
        continue
    channels_cfg = config.get_role_output_channels(rid)
    if channels_cfg:
        role_routes[rid] = [
            channel_map[c] for c in channels_cfg
            if c in channel_map
        ]

# SuriTerminal.__init__ 中
self.output_router = OutputRouter(
    project_root, memory_service, security_service, logger_service,
    role_routes=role_routes, config=config
)
```

### 6.2 投递文本输出

```python
# 自动路由到该角色的默认通道
self.output_router.deliver_text("你好，用户", role_id="suri")
```

### 6.3 投递代码输出

```python
# 自动保存到文件 + 终端显示 + 记忆存储
self.output_router.deliver_code(
    "def hello(): return 1",
    language="python",
    role_id="suri-dev",
    filename="hello.py"
)
```

### 6.4 投递告警

```python
# urgent 优先级触发 Telegram 通道
self.output_router.deliver_alert(
    "系统异常: 内存不足",
    priority="urgent",
    role_id="suri"
)
```

### 6.5 自定义 Payload

```python
from access.output import OutputPayload, OutputType, OutputChannel

payload = OutputPayload(
    type=OutputType.REPORT,
    content="# 审计报告\n\n通过",
    title="Q2安全审计",
    role_id="document-review",
    task_id="TASK_001",
    target_channels=[OutputChannel.TERMINAL, OutputChannel.FILE]
)
self.output_router.deliver(payload)
```

---

## 7. 终端输出格式

`TerminalChannel` 根据角色和类型渲染 ANSI 彩色输出：

| 角色 | 昵称 | 颜色 |
|------|------|------|
| `suri` | Suri | 青色 (\033[96m) |
| `suri_dev` | 码农老李 | 绿色 (\033[92m) |
| `suri_hr` | 人事大姐 | 黄色 (\033[93m) |
| `suri_review` | 审查员 | 紫色 (\033[95m) |
| `suri_stats` | 数据小能手 | 蓝色 (\033[94m) |
| *(新增角色)* | Soul `nickname` | 自动哈希分配 |

**动态颜色**：新增角色无需在 `ROLE_COLORS` 中注册，`TerminalChannel._get_role_color()` 会自动基于 `hash(role_id)` 分配确定性颜色。

**昵称系统**（V2.0）：`TerminalChannel` 优先显示 Soul frontmatter 中的 `nickname`，未设置时回退到 `name`，再回退到 `role_id`。旧别名（如 `suri-dev`）也会正确解析并显示对应昵称。

| 类型 | 颜色 |
|------|------|
| `ALERT` | 红色 (\033[91m) |

类型渲染：
- `CODE`: Markdown 代码块风格
- `ALERT`: 红色 ⚠️ 前缀
- `FILE`: 📄 文件路径提示
- `IMAGE`: 🖼️ 图片链接提示
- `REPORT`: 📊 标题 + 内容摘要

---

## 8. 测试

运行输出框架测试：

```bash
python3 tests/test_output_framework.py
```

覆盖：
- OutputPayload 创建与序列化 (7项)
- TerminalChannel 格式化 (4项)
- FileChannel 文件写入 (4项)
- MemoryChannel 记忆存储 (2项)
- OutputRouter 路由决策 (5项)
- OutputRouter 多通道投递 (2项)
- 角色-通道映射 (4项)

**总计 28 项，通过率 100%**

---

## 9. 扩展预留

### 9.1 Telegram 通道

```python
class TelegramChannel(BaseChannel):
    def __init__(self, bot_token: str, chat_id: str):
        # 接入 python-telegram-bot
        pass
    
    def deliver(self, payload):
        # send_message / send_photo / send_document
        pass
```

### 9.2 飞书通道

```python
class FeishuChannel(BaseChannel):
    def __init__(self, app_id: str, app_secret: str):
        # 接入 Lark Open API
        pass
```

### 9.3 Webhook 通道

```python
class WebhookChannel(BaseChannel):
    def deliver(self, payload):
        # requests.post(self.endpoint, json=payload.to_dict())
        pass
```

---

## 10. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-05-01 | 建立输出框架：OutputPayload, OutputType, OutputChannel, BaseChannel, TerminalChannel, FileChannel, MemoryChannel, LoggerChannel, TelegramChannel(Webhook), OutputRouter |
| 2026-05-01 | CLI 接入 OutputRouter，替换所有 print() 调用 |
| 2026-05-01 | FileChannel 路径与 file_ownership 权限系统对齐 |
| 2026-05-01 | **P0 动态路由改造**：OutputRouter 支持 `role_routes` 和 `config` 参数，角色路由从 Soul 文件动态生成 |
| 2026-05-01 | **P0 动态文件路径**：FileChannel 从 Soul `output_path` 动态解析，新增角色无需改代码 |
| 2026-05-01 | **P0 动态终端颜色**：TerminalChannel 新增角色自动哈希分配颜色，无需改代码 |
| 2026-05-01 | **V3.0 状态卡片集成**：`StateCardRenderer.render_terminal()` 自动追加任务看板到输出，支持 emoji 状态图标和进度显示 |
| 2026-05-01 | **V3.0 昵称显示链**：OutputRouter → `_resolve_role_display_name()` → ConfigService `get_role_nickname()` → Soul frontmatter `nickname` 字段 |
