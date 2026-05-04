"""role_comm 插件 — 角色间消息通信服务。

纯事件驱动架构：
  1. 订阅 role.message 事件 → 存储到 SQLite
  2. 发布 role.message_received 事件 → 通知接收方
  3. 按 session_id 隔离对话上下文
"""

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework.shared.utils.event_types import Event
from agent_framework.shared.interfaces.plugin import PluginInterface


@dataclass
class RoleMessage:
    """角色消息数据类。"""
    msg_id: str
    from_role: str
    to_role: str
    session_id: str
    content: str
    summary: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    consumed: bool = False
    reply_to: Optional[str] = None


class RoleCommPlugin(PluginInterface):
    """角色间消息通信插件。
    
    提供：
    - 点对点自然语言消息投递
    - session_id 隔离对话上下文
    - 消息摘要（长消息自动）
    - 批量处理（batch_window_ms 攒消息）
    - 留存策略（活跃/非活跃/已完成）
    """

    def __init__(self):
        self._event_bus = None
        self._config = {}
        self._runtime_root: Optional[Path] = None
        self._db_path: Optional[Path] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._status = "stopped"
        # 批处理缓存: {session_id: [messages]}
        self._batch_buffer: Dict[str, List[RoleMessage]] = {}
        self._batch_timer = None

    # ── 生命周期 ──

    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config.get("role_comm", {})

        # 确定运行时目录
        if self._runtime_root is None:
            default_root = Path.cwd() / ".suri" / "runtime"
            self._runtime_root = Path(self._config.get("runtime_root", default_root))

        self._db_path = self._runtime_root / "role_comm" / "messages.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._connect()
        self._create_tables()
        self._register_events()
        self._status = "initialized"

    async def start(self) -> None:
        self._status = "running"

    async def pause(self) -> None:
        self._status = "paused"

    async def resume(self) -> None:
        self._status = "running"

    async def stop(self) -> None:
        self._status = "stopped"

    async def cleanup(self) -> None:
        self._status = "stopped"
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── 数据库 ──

    def _connect(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                msg_id TEXT PRIMARY KEY,
                from_role TEXT NOT NULL,
                to_role TEXT NOT NULL,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                timestamp REAL NOT NULL,
                consumed INTEGER DEFAULT 0,
                reply_to TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON messages(session_id, consumed, timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_receiver 
                ON messages(to_role, consumed, timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_from 
                ON messages(from_role, timestamp);
        """)
        self._conn.commit()

    def _dict_from_row(self, row: sqlite3.Row) -> dict:
        return dict(row)

    # ── 事件注册 ──

    def _register_events(self) -> None:
        if not self._event_bus:
            return

        # 订阅角色发消息事件
        self._event_bus.subscribe("role.message", self._handle_role_message)

        # 订阅查询事件
        self._event_bus.subscribe("role.messages_query", self._handle_query)
        self._event_bus.subscribe("role.messages_consume", self._handle_consume)
        self._event_bus.subscribe("role.messages_summary", self._handle_summary)

    # ── 事件处理 ──

    async def _handle_role_message(self, event) -> None:
        """处理 role.message 事件 → 存储并通知接收方。"""
        if self._status != "running":
            return

        payload = event.payload if hasattr(event, 'payload') else event
        msg = RoleMessage(
            msg_id=payload.get("msg_id", str(uuid.uuid4())),
            from_role=payload["from_role"],
            to_role=payload["to_role"],
            session_id=payload["session_id"],
            content=payload["content"],
            timestamp=payload.get("timestamp", time.time()),
            reply_to=payload.get("reply_to"),
        )

        # 长消息自动摘要
        threshold = self._config.get("summary", {}).get("threshold_chars", 500)
        if len(msg.content) > threshold:
            msg.summary = msg.content[:self._config.get("summary", {}).get("max_summary_chars", 100)]

        # 存储到 SQLite
        self._store_message(msg)

        # 发布通知事件
        await self._event_bus.publish(Event(
            event_type="role.message_received",
            source="role_comm",
            payload={
                "receiver": msg.to_role,
                "session_id": msg.session_id,
                "unread_count": self._get_unread_count(msg.to_role, msg.session_id),
                "msg_id": msg.msg_id,
            },
        ))

        # 批处理逻辑
        if self._config.get("process_mode") == "event_driven":
            self._batch_push(msg.session_id, msg)

    def _store_message(self, msg: RoleMessage) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO messages 
               (msg_id, from_role, to_role, session_id, content, summary, timestamp, consumed, reply_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg.msg_id, msg.from_role, msg.to_role, msg.session_id,
             msg.content, msg.summary, msg.timestamp, int(msg.consumed), msg.reply_to),
        )
        self._conn.commit()

    def _get_unread_count(self, role: str, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE to_role=? AND session_id=? AND consumed=0",
            (role, session_id),
        ).fetchone()
        return row["cnt"] if row else 0

    async def _batch_push(self, session_id: str, msg: RoleMessage) -> None:
        """批处理缓存：按 session 攒消息。"""
        if session_id not in self._batch_buffer:
            self._batch_buffer[session_id] = []
        self._batch_buffer[session_id].append(msg)

        max_batch = self._config.get("max_batch_size", 5)
        if len(self._batch_buffer[session_id]) >= max_batch:
            await self._flush_batch(session_id)

    async def _flush_batch(self, session_id: str) -> None:
        """刷新批处理缓存。"""
        if session_id not in self._batch_buffer or not self._batch_buffer[session_id]:
            return

        msgs = self._batch_buffer.pop(session_id)
        if self._event_bus and msgs:
            await self._event_bus.publish(Event(
                event_type="role.messages_batch",
                source="role_comm",
                payload={
                    "receiver": msgs[0].to_role,
                    "sessions": {session_id: [asdict(m) for m in msgs]},
                },
            ))

    async def _handle_query(self, event) -> None:
        """处理 role.messages_query 事件 → 返回未读消息。"""
        payload = event.payload if hasattr(event, 'payload') else event
        role = payload.get("role")
        session_id = payload.get("session_id")

        if session_id:
            rows = self._conn.execute(
                """SELECT * FROM messages WHERE to_role=? AND session_id=? AND consumed=0 
                   ORDER BY timestamp""",
                (role, session_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM messages WHERE to_role=? AND consumed=0 
                   ORDER BY timestamp""",
                (role,),
            ).fetchall()

        # 按 session 分组
        sessions = {}
        for row in rows:
            d = self._dict_from_row(row)
            sid = d["session_id"]
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(d)

        if self._event_bus:
            await self._event_bus.publish(Event(
                event_type="role.messages_result",
                source="role_comm",
                payload={
                    "receiver": role,
                    "sessions": sessions,
                },
            ))

    async def _handle_consume(self, event) -> None:
        """处理 role.messages_consume 事件 → 标记已读。"""
        payload = event.payload if hasattr(event, 'payload') else event
        role = payload.get("role")
        session_id = payload.get("session_id")

        self._conn.execute(
            "UPDATE messages SET consumed=1 WHERE to_role=? AND session_id=? AND consumed=0",
            (role, session_id),
        )
        self._conn.commit()

        if self._event_bus:
            await self._event_bus.publish(Event(
                event_type="role.messages_consumed",
                source="role_comm",
                payload={
                    "receiver": role,
                    "session_id": session_id,
                },
            ))

    async def _handle_summary(self, event) -> None:
        """处理 role.messages_summary 事件 → 返回消息摘要列表。"""
        payload = event.payload if hasattr(event, 'payload') else event
        role = payload.get("role")
        session_id = payload.get("session_id")

        rows = self._conn.execute(
            """SELECT msg_id, from_role, session_id, summary, timestamp, consumed 
               FROM messages WHERE to_role=? AND session_id=? 
               ORDER BY timestamp DESC LIMIT 50""",
            (role, session_id),
        ).fetchall()

        summaries = [self._dict_from_row(r) for r in rows]

        if self._event_bus:
            await self._event_bus.publish(Event(
                event_type="role.messages_summary_result",
                source="role_comm",
                payload={
                    "receiver": role,
                    "session_id": session_id,
                    "summaries": summaries,
                },
            ))

    # ── 公开 API（内部使用，不通过事件） ──

    def send_message(self, from_role: str, to_role: str, session_id: str,
                     content: str, reply_to: Optional[str] = None) -> str:
        """直接发送消息（非事件路径，供测试用）。"""
        msg = RoleMessage(
            msg_id=str(uuid.uuid4()),
            from_role=from_role,
            to_role=to_role,
            session_id=session_id,
            content=content,
            reply_to=reply_to,
        )
        self._store_message(msg)
        return msg.msg_id

    def get_messages(self, role: str, session_id: Optional[str] = None,
                     limit: int = 50) -> List[dict]:
        """查询消息。"""
        if session_id:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE to_role=? AND session_id=? ORDER BY timestamp LIMIT ?",
                (role, session_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE to_role=? ORDER BY timestamp LIMIT ?",
                (role, limit),
            ).fetchall()
        return [self._dict_from_row(r) for r in rows]

    def get_unread_count(self, role: str, session_id: Optional[str] = None) -> int:
        """获取未读消息数。"""
        if session_id:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE to_role=? AND session_id=? AND consumed=0",
                (role, session_id),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE to_role=? AND consumed=0",
                (role,),
            ).fetchone()
        return row["cnt"] if row else 0

    def mark_consumed(self, role: str, session_id: str) -> int:
        """标记 session 消息为已读。返回影响的记录数。"""
        self._conn.execute(
            "UPDATE messages SET consumed=1 WHERE to_role=? AND session_id=? AND consumed=0",
            (role, session_id),
        )
        self._conn.commit()
        return self._conn.total_changes

    def delete_old_messages(self, retention_days: int = 30) -> dict:
        """删除过期消息。返回删除统计。"""
        cutoff = time.time() - retention_days * 86400
        deleted = self._conn.execute(
            "DELETE FROM messages WHERE timestamp < ?",
            (cutoff,),
        ).rowcount
        self._conn.commit()
        return {"deleted": deleted, "retention_days": retention_days}

    def health_check(self) -> dict:
        """健康检查。"""
        try:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()
            total = row["cnt"] if row else 0
            return {
                "status": "pass",
                "total_messages": total,
                "db_path": str(self._db_path),
                "db_size_bytes": self._db_path.stat().st_size if self._db_path.exists() else 0,
            }
        except Exception as e:
            return {"status": "fail", "detail": str(e)}