"""Session Hub — 会话控制中枢（PRD 对齐版）。

符合 prd/plugins/access/session-hub.md 规范：
- 三层上下文隔离：adhoc / project / global
- 会话状态流转：active → idle → suspended → expired
- 通道注册/发现机制
- 统一事件路由（输入 → user.input，输出 → 通道 send）
- 能力协商与降级

PRD 引用：prd/plugins/access/session-hub.md
"""

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

from agent_framework.shared.utils.event_types import Event, Priority

# ── 会话状态（PRD: active / idle / suspended / expired）──
SESSION_ACTIVE = "active"
SESSION_IDLE = "idle"
SESSION_SUSPENDED = "suspended"
SESSION_EXPIRED = "expired"

# ── 三层隔离层（PRD: adhoc / project / global）──
ISOLATION_ADHOC = "adhoc"
ISOLATION_PROJECT = "project"
ISOLATION_GLOBAL = "global"

# ── 超时配置 ──
IDLE_TIMEOUT = 600        # 10 分钟后 idle → expired
ABSOLUTE_TIMEOUT = 86400  # 24 小时后强制过期
ADHOC_EXPIRE_DAYS = 7     # Ad-hoc 层 7 天过期

# ── 能力降级链（PRD: channel-capabilities.md）──
DEFAULT_DEGRADE_CHAIN = {
    "rich": ["markdown", "text"],
    "video": ["image", "text"],
    "file": ["text"],
    "html": ["markdown", "text"],
    "image": ["text"],
    "audio": ["file", "text"],
}

MAX_CONCURRENT_SESSIONS = 100


@dataclass
class ChannelCapabilities:
    """通道能力矩阵（PRD: channel-capabilities.md）。"""
    # core
    text: bool = True
    markdown: bool = False
    html: bool = False
    commands: bool = True
    # media
    images: bool = False
    video: bool = False
    audio: bool = False
    files: bool = False
    file_max_size_mb: int = 0
    # interaction
    buttons: bool = False
    forms: bool = False
    sliders: bool = False
    # streaming
    text_stream: bool = False
    file_stream: bool = False
    # ui
    rich_ui: bool = False
    notifications: bool = False
    dynamic_content: bool = False
    offline_mode: bool = False
    local_storage: bool = False
    # extras
    clipboard: bool = False
    voice: bool = False
    location: bool = False
    identity: bool = False
    # 降级链
    degrade_chain: Dict[str, List[str]] = field(default_factory=lambda: dict(DEFAULT_DEGRADE_CHAIN))


@dataclass
class SessionMessage:
    """统一会话消息（PRD: session-protocol.md）。"""
    session_id: str
    channel_type: str
    channel_id: str
    msg_type: str               # text / command / file / image / video / audio / location
    content: str
    attachments: List[Dict] = field(default_factory=list)
    timestamp: float = 0.0
    reply_to: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class SessionOutput:
    """统一输出消息（PRD: session-protocol.md）。"""
    channel_type: str
    channel_id: str
    content_type: str           # text / markdown / html / image / file / video / rich
    content: str
    attachments: List[Dict] = field(default_factory=list)
    options: List[str] = field(default_factory=list)
    streaming: bool = False
    stream_channel: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class Session:
    """会话数据模型（PRD: session-hub.md 三层隔离）。"""
    session_id: str
    channel_type: str
    channel_id: str
    state: str = SESSION_ACTIVE
    created_at: float = 0.0
    last_active_at: float = 0.0
    capabilities: Optional[ChannelCapabilities] = None
    context: Dict = field(default_factory=dict)
    # ★ 三层上下文隔离
    isolation_layer: str = ISOLATION_ADHOC
    project_id: Optional[str] = None
    adhoc_expire_at: Optional[float] = None


class RegisteredChannel:
    """已注册的通道插件。"""
    def __init__(self, name: str, channel_type: str,
                 capabilities: ChannelCapabilities,
                 handler: Any,
                 manifest: Dict = None):
        self.name = name
        self.channel_type = channel_type
        self.capabilities = capabilities
        self.handler = handler
        self.manifest = manifest or {}


class SessionHub:
    """会话控制中枢。

    PRD 定位：
    - 会话管理（创建/切换/销毁/超时）
    - 统一协议适配（输入→user.input，输出→通道 send）
    - 事件路由
    - 通道注册/发现
    - 能力协商
    """

    def __init__(self, db_path: str = ""):
        self._db_path = db_path or str(Path.home() / ".suri" / "runtime" / "session_hub.db")
        self._channels: Dict[str, RegisteredChannel] = {}  # name -> channel
        self._sessions: Dict[str, Session] = {}             # session_id -> session
        self._event_bus = None
        # 对 :memory: 数据库保持单连接引用
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def set_event_bus(self, event_bus) -> None:
        """设置事件总线。"""
        self._event_bus = event_bus

    # ── 数据库初始化 ──

    def _init_db(self) -> None:
        """初始化会话数据库。"""
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                channel_type TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                state TEXT DEFAULT 'active',
                isolation_layer TEXT DEFAULT 'adhoc',
                project_id TEXT,
                context TEXT DEFAULT '{}',
                capabilities TEXT DEFAULT '{}',
                created_at REAL,
                last_active_at REAL,
                adhoc_expire_at REAL
            );

            CREATE TABLE IF NOT EXISTS registered_channels (
                name TEXT PRIMARY KEY,
                channel_type TEXT NOT NULL,
                capabilities TEXT DEFAULT '{}',
                manifest TEXT DEFAULT '{}',
                registered_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state);
            CREATE INDEX IF NOT EXISTS idx_sessions_layer ON sessions(isolation_layer);
            CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_channel ON sessions(channel_type, channel_id);
        """)
        conn.commit()
        # 对 :memory: 数据库保持单连接引用
        if self._db_path == ":memory:":
            self._mem_conn = conn
        else:
            self._close_conn(conn)

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接。

        对 :memory: 数据库返回持久连接（避免 in-memory 跨连接隔离），
        对文件数据库返回新连接。
        """
        if self._db_path == ":memory:" and self._mem_conn:
            self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        """关闭数据库连接。

        :memory: 数据库保持持久连接不关闭，
        文件数据库正常关闭。
        """
        if self._db_path != ":memory:":
            conn.close()

    def close(self) -> None:
        """关闭 SessionHub，释放资源。"""
        if self._mem_conn:
            self._mem_conn.close()
            self._mem_conn = None

    # ── 通道注册/发现（PRD: session-hub.md §四）──

    async def register_channel(self, name: str, channel_type: str,
                                capabilities: ChannelCapabilities,
                                handler: Any,
                                manifest: Dict = None) -> None:
        """注册通道插件。"""
        channel = RegisteredChannel(name, channel_type, capabilities, handler, manifest)
        self._channels[name] = channel

        # 持久化
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO registered_channels
                (name, channel_type, capabilities, manifest, registered_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, channel_type,
              json.dumps(asdict(capabilities)),
              json.dumps(manifest or {}),
              time.time()))
        conn.commit()
        self._close_conn(conn)

        # 发布事件
        if self._event_bus:
            await self._event_bus.publish(Event(
                event_type="channel.registered",
                source="session_hub",
                payload={"name": name, "channel_type": channel_type},
                priority=Priority.LOW,
            ))

    def get_channel(self, channel_type: str) -> Optional[RegisteredChannel]:
        """按通道类型查找已注册的通道。"""
        for ch in self._channels.values():
            if ch.channel_type == channel_type:
                return ch
        return None

    def get_channel_by_name(self, name: str) -> Optional[RegisteredChannel]:
        """按名称查找已注册的通道。"""
        return self._channels.get(name)

    def list_channels(self) -> List[Dict]:
        """列出所有已注册通道。"""
        return [
            {"name": ch.name, "channel_type": ch.channel_type,
             "capabilities": asdict(ch.capabilities)}
            for ch in self._channels.values()
        ]

    # ── 会话管理（PRD: session-hub.md §二）──

    def create_session(self, channel_type: str, channel_id: str,
                       capabilities: Optional[ChannelCapabilities] = None,
                       isolation_layer: str = ISOLATION_ADHOC,
                       project_id: Optional[str] = None) -> Session:
        """创建新会话（默认 Ad-hoc 层）。"""
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        now = time.time()
        adhoc_expire = now + ADHOC_EXPIRE_DAYS * 86400 if isolation_layer == ISOLATION_ADHOC else None

        session = Session(
            session_id=session_id,
            channel_type=channel_type,
            channel_id=channel_id,
            state=SESSION_ACTIVE,
            created_at=now,
            last_active_at=now,
            capabilities=capabilities,
            context={},
            isolation_layer=isolation_layer,
            project_id=project_id,
            adhoc_expire_at=adhoc_expire,
        )

        self._sessions[session_id] = session
        self._persist_session(session)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话（内存缓存优先）。"""
        if session_id in self._sessions:
            return self._sessions[session_id]

        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        self._close_conn(conn)

        if not row:
            return None

        session = self._row_to_session(row)
        self._sessions[session_id] = session
        return session

    def update_session_state(self, session_id: str, new_state: str) -> bool:
        """更新会话状态。"""
        session = self.get_session(session_id)
        if not session:
            return False

        session.state = new_state
        session.last_active_at = time.time()
        self._persist_session(session)
        return True

    def touch_session(self, session_id: str) -> None:
        """更新会话活跃时间。"""
        session = self.get_session(session_id)
        if session:
            session.last_active_at = time.time()
            if session.state == SESSION_IDLE:
                session.state = SESSION_ACTIVE
            self._persist_session(session)

    def close_session(self, session_id: str) -> bool:
        """关闭/过期会话。"""
        return self.update_session_state(session_id, SESSION_EXPIRED)

    def switch_layer(self, session_id: str, new_layer: str,
                     project_id: Optional[str] = None) -> bool:
        """切换会话隔离层（PRD: adhoc ↔ project ↔ global）。"""
        session = self.get_session(session_id)
        if not session:
            return False

        session.isolation_layer = new_layer
        session.project_id = project_id if new_layer == ISOLATION_PROJECT else None
        if new_layer == ISOLATION_ADHOC:
            session.adhoc_expire_at = time.time() + ADHOC_EXPIRE_DAYS * 86400
        else:
            session.adhoc_expire_at = None
        self._persist_session(session)
        return True

    def find_session_by_channel(self, channel_type: str,
                                 channel_id: str) -> Optional[Session]:
        """按通道标识查找活跃会话。"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE channel_type = ? AND channel_id = ? "
            "AND state IN (?, ?) ORDER BY last_active_at DESC LIMIT 1",
            (channel_type, channel_id, SESSION_ACTIVE, SESSION_IDLE)
        ).fetchone()
        self._close_conn(conn)

        if not row:
            return None
        return self._row_to_session(row)

    def list_sessions(self, state: Optional[str] = None,
                      isolation_layer: Optional[str] = None,
                      limit: int = 50) -> List[Session]:
        """列出会话。"""
        conditions = []
        params = []

        if state:
            conditions.append("state = ?")
            params.append(state)
        if isolation_layer:
            conditions.append("isolation_layer = ?")
            params.append(isolation_layer)

        where = " AND ".join(conditions) if conditions else "1=1"
        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM sessions WHERE {where} ORDER BY last_active_at DESC LIMIT ?",
            params + [limit]
        ).fetchall()
        self._close_conn(conn)
        return [self._row_to_session(r) for r in rows]

    def cleanup_stale_sessions(self) -> int:
        """清理过期会话。"""
        now = time.time()
        count = 0

        for session in list(self._sessions.values()):
            if session.state == SESSION_EXPIRED:
                continue
            # idle 超时 → expired
            if session.state == SESSION_IDLE and now - session.last_active_at > IDLE_TIMEOUT:
                session.state = SESSION_EXPIRED
                self._persist_session(session)
                count += 1
            # 绝对超时
            elif now - session.created_at > ABSOLUTE_TIMEOUT:
                session.state = SESSION_EXPIRED
                self._persist_session(session)
                count += 1
            # Ad-hoc 过期
            elif (session.isolation_layer == ISOLATION_ADHOC
                  and session.adhoc_expire_at
                  and now > session.adhoc_expire_at):
                session.state = SESSION_EXPIRED
                self._persist_session(session)
                count += 1

        # 从缓存中移除过期会话
        self._sessions = {k: v for k, v in self._sessions.items()
                          if v.state != SESSION_EXPIRED}
        return count

    def get_stats(self) -> Dict[str, Any]:
        """获取会话统计。"""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]
        active = conn.execute(
            "SELECT COUNT(*) as c FROM sessions WHERE state = ?", (SESSION_ACTIVE,)
        ).fetchone()["c"]
        by_layer = conn.execute(
            "SELECT isolation_layer, COUNT(*) as c FROM sessions GROUP BY isolation_layer"
        ).fetchall()
        by_channel = conn.execute(
            "SELECT channel_type, COUNT(*) as c FROM sessions GROUP BY channel_type"
        ).fetchall()
        self._close_conn(conn)
        return {
            "total_sessions": total,
            "active_sessions": active,
            "by_isolation_layer": {r["isolation_layer"]: r["c"] for r in by_layer},
            "by_channel": {r["channel_type"]: r["c"] for r in by_channel},
            "registered_channels": len(self._channels),
            "memory_cache": len(self._sessions),
        }

    # ── 能力协商（PRD: channel-capabilities.md §二）──

    def negotiate_output(self, session: Session,
                         desired_content_type: str,
                         content: str,
                         attachments: List[Dict] = None) -> SessionOutput:
        """根据通道能力协商输出格式（降级链）。"""
        caps = session.capabilities
        channel = self.get_channel(session.channel_type)

        # 检查通道是否直接支持该内容类型
        if self._capability_supports(caps, desired_content_type):
            return SessionOutput(
                channel_type=session.channel_type,
                channel_id=session.channel_id,
                content_type=desired_content_type,
                content=content,
                attachments=attachments or [],
            )

        # 降级链查找
        degrade_chain = (channel.capabilities.degrade_chain
                         if channel else DEFAULT_DEGRADE_CHAIN)
        chain = degrade_chain.get(desired_content_type, ["text"])

        for fallback_type in chain:
            if self._capability_supports(caps, fallback_type):
                # 执行降级转换
                converted = self._degrade_content(
                    desired_content_type, fallback_type, content
                )
                return SessionOutput(
                    channel_type=session.channel_type,
                    channel_id=session.channel_id,
                    content_type=fallback_type,
                    content=converted,
                    attachments=attachments or [],
                )

        # 最差情况：纯文本
        return SessionOutput(
            channel_type=session.channel_type,
            channel_id=session.channel_id,
            content_type="text",
            content=str(content),
            attachments=attachments or [],
        )

    def _capability_supports(self, caps: Optional[ChannelCapabilities],
                              content_type: str) -> bool:
        """检查能力是否支持某内容类型。"""
        if not caps:
            return content_type in ("text", "markdown")
        mapping = {
            "text": caps.text,
            "markdown": caps.markdown,
            "html": caps.html,
            "image": caps.images,
            "video": caps.video,
            "audio": caps.audio,
            "file": caps.files,
            "rich": caps.rich_ui,
            "stream": caps.text_stream,
        }
        return mapping.get(content_type, False)

    def _degrade_content(self, from_type: str, to_type: str,
                          content: str) -> str:
        """在不同内容类型间转换。"""
        if from_type == "video" and to_type == "text":
            return f"[视频文件: {content}]"
        elif from_type == "image" and to_type == "text":
            return f"[图片: {content}]"
        elif from_type == "file" and to_type == "text":
            return f"[文件: {content}]"
        elif from_type == "audio" and to_type == "file":
            return f"[音频文件: {content}]"
        elif from_type == "audio" and to_type == "text":
            return f"[音频消息: {content}]"
        elif from_type == "rich" and to_type == "markdown":
            return content  # 富文本→markdown 保持原样
        elif from_type == "rich" and to_type == "text":
            return content.split("\n")[0] if "\n" in content else content
        elif from_type == "html" and to_type == "markdown":
            return content  # 简化：保持原样
        elif from_type == "html" and to_type == "text":
            import re
            return re.sub(r"<[^>]+>", "", content)
        elif from_type == "markdown" and to_type == "text":
            import re
            return re.sub(r"[#*_~`>|-]", "", content)
        return content

    # ── 事件路由（PRD: session-hub.md §三）──

    async def route_user_input(self, msg: SessionMessage) -> None:
        """路由用户输入到系统内部事件。"""
        if not self._event_bus:
            return

        # 消息类型 → 事件类型
        event_type_map = {
            "text": "user.input",
            "command": "user.command",
            "image": "user.attachment",
            "file": "user.attachment",
            "video": "user.attachment",
            "audio": "user.attachment",
        }
        event_type = event_type_map.get(msg.msg_type, "user.input")

        payload = {
            "session_id": msg.session_id,
            "channel_type": msg.channel_type,
            "content": msg.content,
            "attachments": msg.attachments,
            "timestamp": msg.timestamp or time.time(),
            "metadata": msg.metadata,
        }

        # 注入会话上下文
        session = self.get_session(msg.session_id)
        if session:
            payload["isolation_layer"] = session.isolation_layer
            payload["project_id"] = session.project_id

        if msg.msg_type == "command":
            parts = msg.content.strip().split()
            payload["command"] = parts[0].lstrip("/") if parts else ""
            payload["args"] = parts[1:] if len(parts) > 1 else []

        await self._event_bus.publish(Event(
            event_type=event_type,
            source=f"session_hub.{msg.channel_type}",
            payload=payload,
            priority=Priority.NORMAL,
        ))

    async def route_system_output(self, event: Event) -> None:
        """路由系统输出到目标通道。"""
        payload = event.payload if hasattr(event, 'payload') else event
        session_id = payload.get("session_id", "")
        content = payload.get("content", "")
        content_type = payload.get("content_type", "text")
        attachments = payload.get("attachments", [])

        session = self.get_session(session_id)
        if not session:
            return

        channel = self.get_channel(session.channel_type)
        if not channel or not channel.handler:
            return

        # 能力协商
        output = self.negotiate_output(
            session, content_type, content, attachments
        )

        # 调用通道的 send 方法
        send_method = getattr(channel.handler, 'send', None)
        if send_method:
            await send_method(output)

    # ── 内部辅助 ──

    def _persist_session(self, session: Session) -> None:
        """持久化会话到数据库。"""
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO sessions
                (session_id, channel_type, channel_id, state,
                 isolation_layer, project_id, context,
                 capabilities, created_at, last_active_at, adhoc_expire_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.session_id,
            session.channel_type,
            session.channel_id,
            session.state,
            session.isolation_layer,
            session.project_id,
            json.dumps(session.context),
            json.dumps(asdict(session.capabilities)) if session.capabilities else "{}",
            session.created_at,
            session.last_active_at,
            session.adhoc_expire_at,
        ))
        conn.commit()
        self._close_conn(conn)

    def _row_to_session(self, row) -> Session:
        """数据库行转 Session 对象。"""
        caps_dict = json.loads(row["capabilities"]) if row["capabilities"] else {}
        caps = ChannelCapabilities(**caps_dict) if caps_dict else None

        return Session(
            session_id=row["session_id"],
            channel_type=row["channel_type"],
            channel_id=row["channel_id"],
            state=row["state"],
            isolation_layer=row["isolation_layer"],
            project_id=row["project_id"],
            context=json.loads(row["context"]) if row["context"] else {},
            capabilities=caps,
            created_at=row["created_at"],
            last_active_at=row["last_active_at"],
            adhoc_expire_at=row["adhoc_expire_at"],
        )