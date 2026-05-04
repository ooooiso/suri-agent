# session-hub — 会话控制中枢

> access 体系的核心插件。管理会话生命周期、统一输入输出、路由事件、通道注册发现。

---

## 一、定位

session-hub 是 access 体系的主插件，负责：

| 职责 | 说明 |
|------|------|
| **会话管理** | 会话的创建、切换、销毁、超时 |
| **统一协议适配** | 所有通道的输入转换为标准事件，标准输出按通道能力适配 |
| **事件路由** | 输入 → `user.input` / `user.command`，输出 → 通道特定格式 |
| **通道注册/发现** | 通道插件在 session-hub 注册，声明能力矩阵 |
| **能力协商** | 根据通道能力矩阵，调整输出格式和内容类型 |

---

## 二、会话管理

### 会话生命周期

```
用户连接（新通道 / 新终端）
    │
    ▼
创建会话 Session
  ├── session_id: uuid
  ├── channel_type: cli / tg / web / desktop
  ├── channel_id: 通道侧用户标识
  ├── created_at
  └── state: active
    │
    ▼
用户交互 → 更新 session.last_active_at
    │
    ▼
用户断开 / 超时 → 销毁会话
    │
    ▼
会话状态: expired
```

### 会话状态

| 状态 | 说明 | 触发 |
|------|------|------|
| `active` | 会话活跃中 | 用户连接/消息 |
| `idle` | 会话空闲 | 用户离开（桌面端） |
| `suspended` | 会话挂起 | 用户切走（Telegram 临时消息） |
| `expired` | 会话过期 | 超时（默认 30 分钟） |

### 会话上下文（三层隔离）

每个 session 维护上下文，并感知三层隔离层级：

```python
@dataclass
class Session:
    session_id: str
    channel_type: str
    channel_id: str          # 通道侧用户标识（如 chat_id / client_id）
    state: str               # active / idle / suspended / expired
    created_at: float
    last_active_at: float
    capabilities: ChannelCapabilities  # 该通道的能力矩阵
    context: dict            # 当前会话关联的角色、任务等
    
    # ★ 三层上下文隔离感知
    isolation_layer: str = "adhoc"      # adhoc / project / global
    project_id: Optional[str] = None    # 仅在 project 层有效
    adhoc_expire_at: Optional[float] = None  # Ad-hoc 层过期时间（创建+7天）
```

### 三层隔离的会话管理

```
用户发起会话
    │
    ├── 默认：Ad-hoc 层会话
    │   ├── session.isolation_layer = "adhoc"
    │   ├── 7天自动过期清理
    │   ├── 仅使用临时记忆
    │   └── 不关联任何项目
    │
    ├── 加入项目后 → Project 层会话
    │   ├── session.isolation_layer = "project"
    │   ├── session.project_id = "ecommerce_app"
    │   ├── 使用项目专属记忆/知识/wiki
    │   └── 切换项目时 session 自动切换
    │
    └── 全局配置 → Global 层会话
        ├── session.isolation_layer = "global"
        ├── 跨项目通用设置
        └── 共享全局记忆

会话切换流程：
  Ad-hoc → Project:  用户选择项目 → session.project_id 设定
  Project → Ad-hoc:  用户退出项目 → session.project_id 清空
  Project → Project: 用户切换项目 → session.project_id 更新（记忆隔离）
```

会话的 `project_id` 和 `isolation_layer` 将传递给：
1. `_meta` 中的 `project_id` 字段（工具调用上下文中）
2. memory_service 的 DB 选择（ad-hoc.db / project.db / global.db）
3. 所有事件中的 context 信息（用于过滤和隔离）

---

## 三、事件路由

### 输入流（用户 → 系统）

```
通道插件收到用户消息
    │
    ├── 转换为标准 SessionMessage
    │   ├── session_id
    │   ├── channel_type
    │   ├── content (text / command / file / image / ...)
    │   └── attachments (可选)
    │
    ▼
session-hub 解析消息类型
    │
    ├── 纯文本 → user.input 事件
    │   └── 发布到 role_manager
    │
    ├── 命令（/开头）→ user.command 事件
    │   └── 普通命令 → 对应插件
    │   └── 会话命令 → 本地处理
    │       ├── /session 查看会话
    │       ├── /switch 切换会话通道
    │       └── /history 查看历史
    │
    └── 附件（图片/文件等）→ user.attachment 事件
        └── 携带通道能力信息，便于系统决定是否处理
```

### 输出流（系统 → 用户）

```
系统产生响应
    │
    ├── llm.response → session-hub 收到
    ├── tool.result → session-hub 收到
    ├── system.notification → session-hub 收到
    ├── role.message → session-hub 收到
    └── ...
    │
    ▼
session-hub 查找目标 session
    │
    ▼
session-hub 根据 session.capabilities 格式化输出
    │
    ├── 纯文本 → 所有通道支持
    ├── Markdown → 通道支持程度不同
    │   ├── CLI: 基本 Markdown（无自动格式化问题）
    │   ├── Telegram: MarkdownV2（需严格转义）
    │   ├── Web: 完整 HTML/Markdown 渲染
    │   └── Desktop: 原生富文本渲染
    │
    ├── 图片 → 通道支持程度不同
    │   ├── CLI: 显示图片路径/URL
    │   ├── Telegram: 直接发送图片消息
    │   ├── Web: img 标签渲染
    │   └── Desktop: 原生图片嵌入
    │
    ├── 文件 → 通道支持程度不同
    │   ├── CLI: 显示下载链接
    │   ├── Telegram: 直接发送文件
    │   ├── Web: 下载链接 / Blob
    │   └── Desktop: 本地保存或下载
    │
    └── 视频/动态 → 仅高级通道
        ├── Web: 视频嵌入
        └── Desktop: 原生视频播放
    │
    ▼
session-hub 调用对应通道插件的 send()
    │
    ▼
用户看到适配后的输出
```

---

## 四、通道注册/发现

### 通道插件注册 API

每个通道插件在 init 时向 session-hub 注册：

```python
class ChannelPlugin(PluginInterface):
    async def register(self, hub: SessionHub):
        await hub.register_channel(
            name="channel.cli",
            channel_type="cli",
            capabilities=ChannelCapabilities(
                text=True,
                markdown=True,
                images=False,
                files=False,
                streaming=True,
                rich_ui=False,
                native_notifications=False,
            ),
            handler=self,  # ChannelPlugin 实例
        )
```

### 发现机制

通道插件放入 `plugins/access/` 目录，session-hub 启动时扫描所有 `channel.*.md` 对应的实现文件，通过 manifest.json 的 `channel_type` 字段识别：

```json
// channels/cli/manifest.json
{
  "name": "channel.cli",
  "channel_type": "cli",
  "version": "1.0.0",
  "entry": "channel.py",
  "capabilities": {
    "text": true,
    "markdown": true,
    "images": false,
    "files": false,
    "streaming": true,
    "rich_ui": false
  }
}
```

---

## 五、订阅/发布事件

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `llm.response` | llm_gateway | 格式化 LLM 回复并发送到对应通道 |
| `llm.stream_chunk` | llm_gateway | 流式输出 |
| `interrupt.user_decision_needed` | interrupt_handler | 呈现决策选项 |
| `system.notification` | 任意插件 | 系统通知 |
| `tool.result` | code_tool / mcp_framework | 工具执行结果 |
| `role.message_received` | role_comm | 角色间消息（抄送用户） |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `user.input` | role_manager | 用户普通消息 |
| `user.command` | 对应插件 | 用户命令 |
| `user.attachment` | role_manager | 用户上传的附件（图片/文件） |
| `session.created` | log_service | 会话创建 |
| `session.expired` | log_service | 会话过期 |
| `channel.registered` | log_service | 通道插件注册 |
| `channel.unregistered` | log_service | 通道插件注销 |

---

## 六、配置项

```yaml
session_hub:
  enabled: true
  default_channel: "cli"
  session_timeout_minutes: 30
  max_concurrent_sessions: 100
  channels:
    cli:
      enabled: true
    telegram:
      enabled: true
      bot_token_env: "TELEGRAM_BOT_TOKEN"
    web:
      enabled: false
    desktop:
      enabled: false
```

---

## 七、统计接口（迭代 2）

> `/sessions` 命令的数据来源。SessionHub 提供 `get_stats()` 方法返回会话统计信息。

### 7.1 返回结构

```python
@dataclass
class SessionStats:
    total_sessions: int                    # 历史累计会话数
    active_sessions: int                   # 当前活跃（active + idle）会话数
    sessions_by_channel: Dict[str, int]    # 按通道类型统计: {"cli": 5, "tg": 2}
    sessions_by_state: Dict[str, int]      # 按状态统计: {"active": 3, "idle": 2, "expired": 10}
    avg_session_duration_min: float        # 平均会话持续时长（分钟）
    messages_total: int                    # 历史总消息数
    messages_today: int                    # 今日消息数
    top_channels: List[str]                # 最活跃的通道排行
    hot_reload_status: Dict[str, Any]      # 热更新系统状态
        - running: bool                    # FileWatcher 是否在运行
        - watch_dirs: List[str]            # 监听目录
        - interval: float                  # 轮询间隔
        - changed_files: List[str]         # 最近检测到的变更文件
        - last_reload_time: float          # 最近一次热更新时间戳
    plugin_stats: Dict[str, Any]           # 插件汇总统计
        - total: int                       # 总插件数
        - running: int                     # 运行中
        - stopped: int                     # 已暂停
        - failed: int                      # 加载失败
        - upgrading: int                   # 升级中
        - by_type: Dict[str, int]          # 按类型分类
```

### 7.2 数据来源

| 字段 | 来源 |
|------|------|
| `sessions` 相关 | SessionHub 内部 `_sessions` 字典 |
| `messages` 相关 | log_service 统计 |
| `hot_reload_status` | HotReloadManager 实时状态 |
| `plugin_stats` | PluginManager 遍历计算 |

### 7.3 终端渲染

```
> /sessions

┌────────────────────────────────────────────────┐
│  Suri Session 会话统计                          │
├────────────────────────────────────────────────┤
│  当前会话: active (CLI)                        │
│  ─────────────────────────────────────         │
│  历史累计会话:        28                       │
│  今日消息:            156                      │
│  插件总数:            15 / 15 运行中           │
│  热更新状态:          ✅ 运行中 (2s 轮询)     │
│  最近重载:            formatter.py (12s前)    │
└────────────────────────────────────────────────┘
```

---

## 八、替换了原来的 access.md

原 `access.md` 中关于：
- 多通道接入 → 迁移到各通道独立文档 + session-hub 通道注册
- 消息路由 → 迁移到 session-hub 事件路由
- 消息格式化 → 迁移到 channel-capabilities.md
- 通道路由外部化 → 迁移到 session-hub 配置 + 通道 manifest
- 配置项 → 保留在 session-hub 配置
- 依赖关系 → 保留
- 生命周期 → 保留并扩展

**旧的 access.md 被本文件 + session-protocol.md + channel-capabilities.md 替代**。