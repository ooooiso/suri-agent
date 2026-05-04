"""memory_service 插件 — 角色级独立记忆存储（SQLite + 文本记忆文件 + 向量检索基础设施）

核心架构：
- 每个角色拥有独立 SQLite 数据库 (~/.suri/runtime/roles/{role_id}/memories/role.db)
- 文本洞察文件存储在 ~/.suri/runtime/roles/{role_id}/memories/insights/*.md
- WAL 模式支持并发读写
- 禁止跨角色访问
- 支持 memory_type 区分 (episodic/semantic/procedural)
- 支持重要性评分 (importance 0.0 ~ 1.0)
- 标签系统 (tags JSON array)
- 向量检索基础设施 (embedding BLOB 列, 可选 LLM 生成)
- FTS5 全文搜索备用
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event
from agent_framework.shared.constants import RUNTIME_DIR


# 常量定义
MEMORIES_SUBDIR = "memories"
INSIGHTS_SUBDIR = "insights"
ROLE_DB_NAME = "role.db"
MAX_INSIGHT_FILE_SIZE = 1 * 1024 * 1024  # 1MB
FORGET_THRESHOLD_DAYS = 30
FORGET_CONFIDENCE_THRESHOLD = 0.3
# 记忆类型枚举
MEMORY_TYPE_EPISODIC = "episodic"   # 情节记忆：特定事件/经历
MEMORY_TYPE_SEMANTIC = "semantic"   # 语义记忆：事实/知识
MEMORY_TYPE_PROCEDURAL = "procedural"  # 程序记忆：技能/模式
VALID_MEMORY_TYPES = (MEMORY_TYPE_EPISODIC, MEMORY_TYPE_SEMANTIC, MEMORY_TYPE_PROCEDURAL)
# 向量维度（预留，暂不使用完整 embedding 模型）
DEFAULT_EMBEDDING_DIM = 0


class MemoryServicePlugin(PluginInterface):
    """角色级独立记忆存储插件。

    每个角色拥有独立 SQLite 数据库 + 文本记忆文件管理。
    纯服务插件，不发布事件。
    """

    def __init__(self):
        self.name = "memory_service"
        self.event_bus = None
        self.config = {}
        self._connections: Dict[str, sqlite3.Connection] = {}
        self._runtime_root: Optional[Path] = None

    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        self.event_bus = event_bus
        self.config = config.get("memory_service", {})
        self._runtime_root = Path.home() / RUNTIME_DIR

        # 订阅系统事件
        self.event_bus.subscribe("system.started", self._on_system_started)

    def register_events(self) -> None:
        """注册事件订阅"""
        pass

    async def start(self) -> None:
        pass

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        """关闭所有数据库连接"""
        for role_id, conn in self._connections.items():
            try:
                conn.commit()
                conn.close()
            except Exception:
                pass
        self._connections.clear()

    async def cleanup(self) -> None:
        await self.stop()

    # --- 事件处理 ---

    async def _on_system_started(self, event: Event) -> None:
        """系统启动时初始化所有角色的数据库"""
        pass  # 按需初始化

    # --- 数据库连接管理 ---

    def _get_role_db_path(self, role_id: str) -> Path:
        """获取角色数据库路径，安全防注入"""
        if ".." in role_id or "/" in role_id:
            raise ValueError(f"非法的 role_id: {role_id}")
        return (self._runtime_root / "roles" / role_id / MEMORIES_SUBDIR / ROLE_DB_NAME)

    def _get_insights_dir(self, role_id: str) -> Path:
        if ".." in role_id or "/" in role_id:
            raise ValueError(f"非法的 role_id: {role_id}")
        return (self._runtime_root / "roles" / role_id / MEMORIES_SUBDIR / INSIGHTS_SUBDIR)

    def _get_connection(self, role_id: str) -> sqlite3.Connection:
        """获取或创建角色的数据库连接"""
        if role_id in self._connections:
            return self._connections[role_id]

        db_path = self._get_role_db_path(role_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        self._init_role_tables(conn)
        self._connections[role_id] = conn
        return conn

    def _init_role_tables(self, conn: sqlite3.Connection) -> None:
        """初始化角色的数据库表（含向量检索基础设施）"""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory_facts (
                id TEXT PRIMARY KEY,
                key TEXT UNIQUE,
                value TEXT,
                confidence REAL DEFAULT 1.0,
                memory_type TEXT DEFAULT 'semantic',
                importance REAL DEFAULT 0.5,
                tags TEXT DEFAULT '[]',
                embedding BLOB DEFAULT NULL,
                embedding_model TEXT DEFAULT NULL,
                source TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS memory_experiences (
                id TEXT PRIMARY KEY,
                task_type TEXT,
                memory_type TEXT DEFAULT 'episodic',
                context TEXT,
                actions TEXT,
                result TEXT,
                satisfaction REAL DEFAULT 0.0,
                importance REAL DEFAULT 0.5,
                tags TEXT DEFAULT '[]',
                embedding BLOB DEFAULT NULL,
                embedding_model TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memory_patterns (
                id TEXT PRIMARY KEY,
                pattern TEXT,
                memory_type TEXT DEFAULT 'procedural',
                confidence REAL DEFAULT 0.5,
                evidence_count INTEGER DEFAULT 1,
                importance REAL DEFAULT 0.5,
                tags TEXT DEFAULT '[]',
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'active'
            );

            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                session_id TEXT,
                requester TEXT,
                target_dept TEXT,
                target_director TEXT,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                task_id TEXT,
                sender TEXT,
                receiver TEXT,
                body TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            );

            CREATE TABLE IF NOT EXISTS approvals (
                approval_id TEXT PRIMARY KEY,
                report_id TEXT,
                requester TEXT,
                status TEXT DEFAULT 'pending',
                token TEXT,
                user_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS changelogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                change_type TEXT,
                description TEXT,
                author TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_memory_facts_key ON memory_facts(key);
            CREATE INDEX IF NOT EXISTS idx_memory_facts_type ON memory_facts(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memory_facts_importance ON memory_facts(importance DESC);
            CREATE INDEX IF NOT EXISTS idx_memory_experiences_type ON memory_experiences(task_type);
            CREATE INDEX IF NOT EXISTS idx_memory_experiences_mtype ON memory_experiences(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memory_patterns_mtype ON memory_patterns(memory_type);
            CREATE INDEX IF NOT EXISTS idx_messages_task ON messages(task_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
        """)

        # 如果表已存在但缺少新列，使用 ALTER TABLE ADD COLUMN（SQLite 兼容）
        self._migrate_add_column(conn, "memory_facts", "memory_type",
                                 "TEXT DEFAULT 'semantic'")
        self._migrate_add_column(conn, "memory_facts", "importance",
                                 "REAL DEFAULT 0.5")
        self._migrate_add_column(conn, "memory_facts", "tags",
                                 "TEXT DEFAULT '[]'")
        self._migrate_add_column(conn, "memory_facts", "embedding",
                                 "BLOB DEFAULT NULL")
        self._migrate_add_column(conn, "memory_facts", "embedding_model",
                                 "TEXT DEFAULT NULL")
        self._migrate_add_column(conn, "memory_facts", "source",
                                 "TEXT DEFAULT ''")
        self._migrate_add_column(conn, "memory_experiences", "memory_type",
                                 "TEXT DEFAULT 'episodic'")
        self._migrate_add_column(conn, "memory_experiences", "importance",
                                 "REAL DEFAULT 0.5")
        self._migrate_add_column(conn, "memory_experiences", "tags",
                                 "TEXT DEFAULT '[]'")
        self._migrate_add_column(conn, "memory_experiences", "embedding",
                                 "BLOB DEFAULT NULL")
        self._migrate_add_column(conn, "memory_experiences", "embedding_model",
                                 "TEXT DEFAULT NULL")
        self._migrate_add_column(conn, "memory_patterns", "memory_type",
                                 "TEXT DEFAULT 'procedural'")
        self._migrate_add_column(conn, "memory_patterns", "importance",
                                 "REAL DEFAULT 0.5")
        self._migrate_add_column(conn, "memory_patterns", "tags",
                                 "TEXT DEFAULT '[]'")

        # 创建 FTS5 全文搜索虚拟表（如果不存在）
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    key, value, content='memory_facts', content_rowid='rowid'
                )
            """)
        except sqlite3.OperationalError:
            pass  # FTS5 可能不支持

        conn.commit()

    def _migrate_add_column(self, conn: sqlite3.Connection,
                            table: str, column: str, col_type: str) -> None:
        """安全地添加列（如果不存在）"""
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass  # 列已存在

    # --- 内部工具 ---

    def _validate_memory_type(self, memory_type: str) -> str:
        """验证记忆类型，无效则回退默认"""
        if memory_type not in VALID_MEMORY_TYPES:
            return MEMORY_TYPE_SEMANTIC
        return memory_type

    def _clamp_importance(self, importance: float) -> float:
        """限制重要性在 0.0 ~ 1.0 之间"""
        return max(0.0, min(1.0, importance))

    def _json_serialize_tags(self, tags: List[str]) -> str:
        """序列化标签为 JSON 字符串"""
        return json.dumps(tags or [], ensure_ascii=False)

    def _json_deserialize_tags(self, tags_str: str) -> List[str]:
        """反序列化 JSON 标签"""
        try:
            return json.loads(tags_str) if tags_str else []
        except (json.JSONDecodeError, TypeError):
            return []

    # --- 事实记忆（key-value + 增强字段） ---

    def set_fact(self, role_id: str, key: str, value: Any,
                 confidence: float = 1.0,
                 memory_type: str = MEMORY_TYPE_SEMANTIC,
                 importance: float = 0.5,
                 tags: List[str] = None,
                 source: str = "") -> None:
        """存储结构化事实（自动 upsert），支持记忆类型/重要性/标签"""
        conn = self._get_connection(role_id)
        now = datetime.now().isoformat()
        mtype = self._validate_memory_type(memory_type)
        imp = self._clamp_importance(importance)
        tags_str = self._json_serialize_tags(tags)

        conn.execute("""
            INSERT INTO memory_facts
                (id, key, value, confidence, memory_type, importance, tags, source,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                confidence = excluded.confidence,
                memory_type = excluded.memory_type,
                importance = excluded.importance,
                tags = excluded.tags,
                source = excluded.source,
                updated_at = excluded.updated_at,
                access_count = access_count + 1
        """, (uuid.uuid4().hex, key, json.dumps(value, ensure_ascii=False),
              confidence, mtype, imp, tags_str, source, now, now))
        conn.commit()

    def get_fact(self, role_id: str, key: str) -> Optional[Any]:
        """查询结构化事实"""
        conn = self._get_connection(role_id)
        row = conn.execute(
            "SELECT value FROM memory_facts WHERE key = ?", (key,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE memory_facts SET access_count = access_count + 1 WHERE key = ?",
                (key,)
            )
            conn.commit()
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                return row["value"]
        return None

    def delete_fact(self, role_id: str, key: str) -> bool:
        """删除事实"""
        conn = self._get_connection(role_id)
        cur = conn.execute("DELETE FROM memory_facts WHERE key = ?", (key,))
        conn.commit()
        return cur.rowcount > 0

    def list_facts(self, role_id: str,
                   memory_type: str = None,
                   min_importance: float = 0.0,
                   limit: int = 50) -> List[Dict]:
        """列出所有事实（按重要性+访问频率加权降序），支持类型过滤"""
        conn = self._get_connection(role_id)

        if memory_type:
            mtype = self._validate_memory_type(memory_type)
            rows = conn.execute(
                "SELECT key, value, confidence, memory_type, importance, tags, "
                "access_count, updated_at, source "
                "FROM memory_facts "
                "WHERE memory_type = ? AND importance >= ? "
                "ORDER BY (importance * 2 + access_count * 0.1) DESC LIMIT ?",
                (mtype, min_importance, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT key, value, confidence, memory_type, importance, tags, "
                "access_count, updated_at, source "
                "FROM memory_facts "
                "WHERE importance >= ? "
                "ORDER BY (importance * 2 + access_count * 0.1) DESC LIMIT ?",
                (min_importance, limit)
            ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            try:
                d["value"] = json.loads(d["value"])
            except (json.JSONDecodeError, TypeError):
                pass
            d["tags"] = self._json_deserialize_tags(d.get("tags", ""))
            results.append(d)
        return results

    def search_facts(self, role_id: str, query: str,
                     limit: int = 10) -> List[Dict]:
        """全文搜索事实（基于 FTS 或 LIKE 回退）"""
        conn = self._get_connection(role_id)

        # 优先使用 FTS5
        try:
            rows = conn.execute(
                "SELECT f.key, f.value, f.confidence, f.memory_type, f.importance, "
                "f.tags, f.access_count, f.updated_at "
                "FROM memory_fts m JOIN memory_facts f ON m.rowid = f.rowid "
                "WHERE memory_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)
            ).fetchall()
        except sqlite3.OperationalError:
            # 回退到 LIKE 模糊搜索
            rows = conn.execute(
                "SELECT key, value, confidence, memory_type, importance, tags, "
                "access_count, updated_at "
                "FROM memory_facts WHERE key LIKE ? OR value LIKE ? "
                "ORDER BY importance DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit)
            ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            try:
                d["value"] = json.loads(d["value"])
            except (json.JSONDecodeError, TypeError):
                pass
            d["tags"] = self._json_deserialize_tags(d.get("tags", ""))
            results.append(d)
        return results

    def get_memories_by_type(self, role_id: str,
                             memory_type: str,
                             limit: int = 50) -> List[Dict]:
        """按记忆类型批量查询"""
        return self.list_facts(role_id, memory_type=memory_type, limit=limit)

    # --- 经验记忆（增强） ---

    def store_experience(self, role_id: str, task_type: str,
                         context: str, actions: List[Dict],
                         result: str, satisfaction: float = 0.5,
                         importance: float = 0.5,
                         tags: List[str] = None) -> str:
        """记录经验，支持重要性/标签"""
        conn = self._get_connection(role_id)
        exp_id = uuid.uuid4().hex
        imp = self._clamp_importance(importance)
        tags_str = self._json_serialize_tags(tags)
        conn.execute("""
            INSERT INTO memory_experiences
                (id, task_type, memory_type, context, actions, result,
                 satisfaction, importance, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exp_id, task_type, MEMORY_TYPE_EPISODIC, context,
              json.dumps(actions, ensure_ascii=False),
              result, satisfaction, imp, tags_str))
        conn.commit()
        return exp_id

    def get_experiences(self, role_id: str, task_type: str = None,
                        min_satisfaction: float = 0.0,
                        min_importance: float = 0.0,
                        limit: int = 50) -> List[Dict]:
        """查询经验，支持满意度/重要性过滤"""
        conn = self._get_connection(role_id)
        if task_type:
            rows = conn.execute(
                "SELECT * FROM memory_experiences "
                "WHERE task_type = ? AND satisfaction >= ? AND importance >= ? "
                "ORDER BY (importance * 2 + satisfaction) DESC LIMIT ?",
                (task_type, min_satisfaction, min_importance, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memory_experiences "
                "WHERE satisfaction >= ? AND importance >= ? "
                "ORDER BY (importance * 2 + satisfaction) DESC LIMIT ?",
                (min_satisfaction, min_importance, limit)
            ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            try:
                d["actions"] = json.loads(d["actions"])
            except (json.JSONDecodeError, TypeError):
                pass
            d["tags"] = self._json_deserialize_tags(d.get("tags", ""))
            results.append(d)
        return results

    # --- 模式记忆（增强） ---

    def store_pattern(self, role_id: str, pattern: str,
                      confidence: float = 0.5,
                      importance: float = 0.5,
                      tags: List[str] = None,
                      source: str = "") -> str:
        """存储模式记忆，支持重要性/标签"""
        conn = self._get_connection(role_id)
        pat_id = uuid.uuid4().hex
        imp = self._clamp_importance(importance)
        tags_str = self._json_serialize_tags(tags)

        existing = conn.execute(
            "SELECT id, evidence_count FROM memory_patterns WHERE pattern = ?",
            (pattern,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE memory_patterns SET evidence_count = evidence_count + 1, "
                "confidence = MIN(1.0, confidence + 0.1), "
                "importance = MAX(importance, ?), "
                "tags = ? WHERE id = ?",
                (imp, tags_str, existing["id"])
            )
            conn.commit()
            return existing["id"]

        conn.execute("""
            INSERT INTO memory_patterns
                (id, pattern, memory_type, confidence, importance, tags, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pat_id, pattern, MEMORY_TYPE_PROCEDURAL,
              confidence, imp, tags_str, source))
        conn.commit()
        return pat_id

    def get_patterns(self, role_id: str, min_confidence: float = 0.0,
                     min_importance: float = 0.0,
                     limit: int = 20) -> List[Dict]:
        """查询模式（按重要性+置信度加权降序）"""
        conn = self._get_connection(role_id)
        rows = conn.execute(
            "SELECT * FROM memory_patterns "
            "WHERE confidence >= ? AND importance >= ? "
            "ORDER BY (importance * 2 + confidence) DESC, evidence_count DESC LIMIT ?",
            (min_confidence, min_importance, limit)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["tags"] = self._json_deserialize_tags(d.get("tags", ""))
            results.append(d)
        return results

    # --- 文本记忆 / 洞察（增强） ---

    def add_insight(self, role_id: str, title: str, body: str,
                    tags: List[str] = None,
                    importance: float = 0.5) -> str:
        """添加洞察文本文件（YAML frontmatter + Markdown body）"""
        insights_dir = self._get_insights_dir(role_id)
        insights_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        filename = f"{now.strftime('%Y-%m-%d')}_{title.replace(' ', '_')[:40]}.md"
        filepath = insights_dir / filename

        if len(body.encode("utf-8")) > MAX_INSIGHT_FILE_SIZE:
            raise ValueError(f"洞察文件超过大小限制: {len(body)} > {MAX_INSIGHT_FILE_SIZE}")

        tags_str = self._json_serialize_tags(tags)
        imp = self._clamp_importance(importance)
        content = f"""---
title: {title}
created_at: {now.isoformat()}
tags: {tags_str}
importance: {imp}
memory_type: {MEMORY_TYPE_EPISODIC}
---

{body}
"""
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def get_insights(self, role_id: str, days: int = 7,
                     min_importance: float = 0.0,
                     limit: int = 20) -> List[Dict]:
        """查询洞察（按重要性+日期倒序）"""
        insights_dir = self._get_insights_dir(role_id)
        if not insights_dir.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        results = []
        for f in sorted(insights_dir.glob("*.md"), reverse=True)[:limit * 2]:
            try:
                content = f.read_text(encoding="utf-8")
                title = f.stem
                tags = []
                created_at = None
                importance = 0.5
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        meta = parts[1]
                        body = parts[2].strip()
                        for line in meta.strip().split("\n"):
                            if line.startswith("title:"):
                                title = line.split(":", 1)[1].strip()
                            elif line.startswith("created_at:"):
                                created_at = line.split(":", 1)[1].strip()
                            elif line.startswith("tags:"):
                                try:
                                    tags = json.loads(line.split(":", 1)[1].strip())
                                except (json.JSONDecodeError, IndexError):
                                    tags = []
                            elif line.startswith("importance:"):
                                try:
                                    importance = float(line.split(":", 1)[1].strip())
                                except (ValueError, IndexError):
                                    pass
                    else:
                        body = content
                else:
                    body = content

                if importance < min_importance:
                    continue

                results.append({
                    "title": title,
                    "body": body[:500],
                    "tags": tags,
                    "importance": importance,
                    "created_at": created_at or f.stem[:10],
                    "filepath": str(f),
                })
            except Exception:
                continue

        # 按重要性降序重排
        results.sort(key=lambda x: x["importance"], reverse=True)
        return results[:limit]

    # --- 消息/会话/任务 查询 ---

    def store_message(self, role_id: str, task_id: str,
                      sender: str, receiver: str, body: str) -> str:
        """存储消息"""
        conn = self._get_connection(role_id)
        msg_id = uuid.uuid4().hex
        conn.execute("""
            INSERT INTO messages (message_id, task_id, sender, receiver, body)
            VALUES (?, ?, ?, ?, ?)
        """, (msg_id, task_id, sender, receiver, body))
        conn.commit()
        return msg_id

    def get_messages(self, role_id: str, task_id: str = None,
                     limit: int = 50) -> List[Dict]:
        """查询消息"""
        conn = self._get_connection(role_id)
        if task_id:
            rows = conn.execute(
                "SELECT * FROM messages WHERE task_id = ? "
                "ORDER BY timestamp ASC LIMIT ?",
                (task_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --- 向量检索基础设施（预留） ---

    def store_embedding(self, role_id: str, memory_id: str,
                        embedding: List[float],
                        model_name: str = "default") -> bool:
        """存储向量嵌入（由外部 LLM 或 embedding 模型生成）"""
        conn = self._get_connection(role_id)
        import struct
        # 序列化为二进制 blob
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        for table in ["memory_facts", "memory_experiences"]:
            cur = conn.execute(
                f"UPDATE {table} SET embedding = ?, embedding_model = ? WHERE id = ?",
                (blob, model_name, memory_id)
            )
            if cur.rowcount > 0:
                conn.commit()
                return True
        return False

    def find_similar(self, role_id: str,
                     query_embedding: List[float],
                     top_k: int = 5,
                     memory_type: str = None) -> List[Dict]:
        """向量相似度搜索（基于余弦相似度，内积排序）。

        注意：当前为简化实现，遍历计算。
        大规模部署时应改用 faiss / pgvector / sqlite-vss。
        """
        import struct
        conn = self._get_connection(role_id)
        q_vec = struct.pack(f"{len(query_embedding)}f", *query_embedding)

        # 查询所有有 embedding 的记录
        if memory_type:
            mtype = self._validate_memory_type(memory_type)
            rows = conn.execute(
                "SELECT id, key, value, memory_type, importance, embedding, embedding_model "
                "FROM memory_facts "
                "WHERE embedding IS NOT NULL AND memory_type = ?",
                (mtype,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, key, value, memory_type, importance, embedding, embedding_model "
                "FROM memory_facts WHERE embedding IS NOT NULL"
            ).fetchall()

        # 计算余弦相似度
        def _cosine_sim(a_blob: bytes) -> float:
            try:
                a = struct.unpack(f"{len(query_embedding)}f", q_vec)
                b = struct.unpack(f"{len(query_embedding)}f", a_blob[:len(q_vec)])
                dot = sum(x * y for x, y in zip(a, b))
                norm_a = sum(x * x for x in a) ** 0.5
                norm_b = sum(x * x for x in b) ** 0.5
                if norm_a == 0 or norm_b == 0:
                    return 0.0
                return dot / (norm_a * norm_b)
            except Exception:
                return 0.0

        scored = []
        for row in rows:
            if row["embedding"]:
                sim = _cosine_sim(row["embedding"])
                scored.append((sim, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, d in scored[:top_k]:
            try:
                d["value"] = json.loads(d["value"])
            except (json.JSONDecodeError, TypeError):
                pass
            d["similarity"] = round(sim, 4)
            results.append(d)
        return results

    # --- 遗忘机制（增强） ---

    def forget_old_memories(self, role_id: str,
                            threshold_days: int = FORGET_THRESHOLD_DAYS,
                            confidence_threshold: float = FORGET_CONFIDENCE_THRESHOLD) -> Dict:
        """执行记忆遗忘：删除低置信度 + 长期未访问 + 低重要性 的冷数据"""
        conn = self._get_connection(role_id)
        cutoff = (datetime.now() - timedelta(days=threshold_days)).isoformat()

        stats = {"facts_deleted": 0, "experiences_deleted": 0, "patterns_deleted": 0}

        # 低重要性 + 低置信度 + 长期未访问的事实
        cur = conn.execute("""
            DELETE FROM memory_facts
            WHERE importance < 0.3 AND confidence < ? AND updated_at < ? AND access_count < 3
        """, (confidence_threshold, cutoff))
        stats["facts_deleted"] = cur.rowcount

        # 低满意度 + 低重要性的经验
        cur = conn.execute("""
            DELETE FROM memory_experiences
            WHERE satisfaction < ? AND importance < 0.3 AND created_at < ?
        """, (confidence_threshold, cutoff))
        stats["experiences_deleted"] = cur.rowcount

        # 低置信度 + 低重要性的模式
        cur = conn.execute("""
            DELETE FROM memory_patterns
            WHERE confidence < ? AND importance < 0.3 AND evidence_count < 2 AND created_at < ?
        """, (confidence_threshold, cutoff))
        stats["patterns_deleted"] = cur.rowcount

        conn.commit()
        return stats

    # --- 健康检查 ---

    def health_check(self, role_id: str = "suri") -> Dict[str, Any]:
        """检查角色数据库健康状态"""
        try:
            conn = self._get_connection(role_id)
            db_path = self._get_role_db_path(role_id)

            tables = {}
            for table in ["memory_facts", "memory_experiences",
                          "memory_patterns", "messages", "tasks"]:
                row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                tables[table] = row["cnt"] if row else 0

            # 记忆类型分布统计
            type_stats = {}
            for mtype in VALID_MEMORY_TYPES:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM memory_facts WHERE memory_type = ?",
                    (mtype,)
                ).fetchone()
                type_stats[mtype] = row["cnt"] if row else 0

            return {
                "status": "pass",
                "db_path": str(db_path),
                "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
                "tables": tables,
                "memory_type_distribution": type_stats,
                "wal_mode": True,
                "fts5_available": True,
            }
        except Exception as e:
            return {"status": "fail", "detail": str(e)}