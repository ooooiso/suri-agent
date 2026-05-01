"""
记忆服务

关联文档: suri-agent/memory/memory.md

职责：
- 每个角色拥有独立的记忆存储（group/<role>/memories/role.db）
- 每个角色拥有独立的会话存储
- 按 memory_config.md 策略自动归档/遗忘

原则：记忆读写通过此服务，不直接操作数据库或文件。
"""

import sqlite3
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
from infrastructure.config import ConfigService

INSIGHT_CATEGORIES = {"success_pattern", "improvement", "pitfall", "preference"}


@dataclass
class TaskRecord:
    task_id: str
    session_id: str
    requester_role: str
    target_department: str
    target_director: str
    status: str
    created_at: str
    updated_at: str
    retry_count: int


class MemoryService:
    """
    记忆管理中心
    
    每个角色拥有独立的 SQLite 数据库：
    - group/<role>/memories/role.db: 角色的任务、消息、审批记录
    - group/<role>/memories/*.md: 角色的私人长期记忆（文本形式）
    """
    
    def __init__(self, project_root: Path, config: ConfigService):
        self.project_root = project_root
        self.config = config
    
    def _get_role_dir(self, role_id: str) -> Path:
        """
        获取角色的根目录
        
        查找顺序：
        1. group/central/<canonical_role_id>/  （标准部门路径，别名已解析）
        2. group/<canonical_role_id>/          （回退兼容路径）
        
        注意：role_id 会先通过 ConfigService.resolve_role_id() 解析为 canonical id，
              确保别名（如 suri-dev）的数据始终写入 canonical 目录（suri_dev）。
        """
        # V2.0: 统一解析别名，确保数据写入 canonical 目录
        canonical_id = self.config.resolve_role_id(role_id)
        
        # 标准路径：group/central/<canonical_role>/
        central_path = self.project_root / 'group' / 'central' / canonical_id
        if central_path.exists():
            return central_path
        
        # 回退路径：group/<canonical_role>/
        fallback_path = self.project_root / 'group' / canonical_id
        return fallback_path
    
    def _get_role_db(self, role_id: str) -> Path:
        """获取角色的独立数据库路径"""
        role_dir = self._get_role_dir(role_id)
        mem_dir = role_dir / 'memories'
        mem_dir.mkdir(parents=True, exist_ok=True)
        db_path = mem_dir / 'role.db'
        self._init_role_db(db_path)
        return db_path
    
    def _init_role_db(self, db_path: Path) -> None:
        """初始化角色数据库表（启用 WAL 模式支持并发读写）"""
        with sqlite3.connect(str(db_path)) as conn:
            # 启用 WAL 模式：支持读写并发，避免写操作阻塞读操作
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            cursor = conn.cursor()
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    status TEXT
                )
            ''')
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    requester_role TEXT,
                    target_department TEXT,
                    target_director TEXT,
                    status TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    retry_count INTEGER DEFAULT 0
                )
            ''')
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    sender_role TEXT,
                    receiver_role TEXT,
                    body TEXT,
                    timestamp TIMESTAMP
                )
            ''')
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    report_id TEXT,
                    requester TEXT,
                    status TEXT,
                    approval_token TEXT,
                    user_response TEXT,
                    created_at TIMESTAMP,
                    resolved_at TIMESTAMP
                )
            ''')
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS changelogs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_id TEXT,
                    author_role TEXT,
                    changed_files TEXT,
                    reason TEXT,
                    approver TEXT,
                    timestamp TIMESTAMP
                )
            ''')
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    role_id TEXT,
                    model_id TEXT,
                    task_id TEXT,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    filepath TEXT,
                    file_type TEXT,
                    file_size INTEGER DEFAULT 0,
                    task_status TEXT,
                    duration_seconds REAL DEFAULT 0,
                    task_hint TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # V2.0: 经验日志表（角色进化基础设施）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS experiences (
                    exp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    role_id TEXT,
                    action TEXT,
                    result TEXT,
                    feedback TEXT,
                    reflection TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # V2.0: 经验日志索引（加速按角色/任务查询）
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_exp_role ON experiences(role_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_exp_task ON experiences(task_id)
            ''')
        
            conn.commit()
    
    # ---- 经验日志管理（V2.0 角色进化） ----
    
    def save_experience(self, role_id: str, task_id: str, action: str,
                        result: str = "", feedback: str = "", 
                        reflection: str = "", tags: str = "") -> None:
        """
        保存角色经验卡片
        
        Args:
            role_id: 角色标识
            task_id: 关联任务 ID
            action: 采取的动作摘要
            result: 结果描述
            feedback: 用户/系统反馈
            reflection: 反思（可由 LLM 后续生成）
            tags: 标签（逗号分隔，如 "coding,bugfix,success"）
        """
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO experiences 
                (task_id, role_id, action, result, feedback, reflection, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, role_id, action, result, feedback, reflection, tags))
            conn.commit()
    
    def get_experiences(self, role_id: str, limit: int = 50,
                        tag_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询角色的经验日志
        
        Args:
            role_id: 角色标识
            limit: 返回条数上限
            tag_filter: 按标签过滤（可选）
            
        Returns:
            经验卡片列表
        """
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if tag_filter:
                cursor.execute('''
                    SELECT * FROM experiences 
                    WHERE role_id = ? AND tags LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (role_id, f'%{tag_filter}%', limit))
            else:
                cursor.execute('''
                    SELECT * FROM experiences 
                    WHERE role_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (role_id, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_experience_stats(self, role_id: str) -> Dict[str, Any]:
        """
        获取角色的经验统计（用于进化监控面板）
        
        Returns:
            {
                'total_experiences': 总经验数,
                'recent_7d': 近7天经验数,
                'top_tags': 最常见标签,
            }
        """
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # 总经验数
            cursor.execute('SELECT COUNT(*) FROM experiences WHERE role_id = ?', (role_id,))
            total = cursor.fetchone()[0]
            
            # 近7天经验数
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute('''
                SELECT COUNT(*) FROM experiences 
                WHERE role_id = ? AND created_at > ?
            ''', (role_id, week_ago))
            recent_7d = cursor.fetchone()[0]
            
            return {
                'total_experiences': total,
                'recent_7d': recent_7d,
                'role_id': role_id,
            }
    
    # ---- 会话管理（角色级） ----
    
    def create_session(self, role_id: str, session_id: str, user_id: str) -> None:
        """为指定角色创建会话"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO sessions (session_id, user_id, start_time, status)
                VALUES (?, ?, ?, ?)
            ''', (session_id, user_id, now, 'active'))
            conn.commit()
    
    def close_session(self, role_id: str, session_id: str) -> None:
        """关闭指定角色的会话"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                UPDATE sessions SET end_time = ?, status = ? WHERE session_id = ?
            ''', (now, 'closed', session_id))
            conn.commit()
    
    def get_role_sessions(self, role_id: str) -> List[Dict[str, Any]]:
        """获取角色的所有会话"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sessions ORDER BY start_time DESC')
            rows = cursor.fetchall()
        return [
            {'session_id': r[0], 'user_id': r[1], 'start_time': r[2],
             'end_time': r[3], 'status': r[4]}
            for r in rows
        ]
    
    # ---- 任务管理（角色级） ----
    
    def create_task(self, role_id: str, task_id: str, session_id: str,
                    requester: str, target_dept: str, target_director: str) -> None:
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO tasks (task_id, session_id, requester_role, target_department,
                                 target_director, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, session_id, requester, target_dept, target_director, 'pending', now, now))
            conn.commit()
    
    def update_task_status(self, role_id: str, task_id: str, status: str) -> None:
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?
            ''', (status, now, task_id))
            conn.commit()
    
    def get_role_tasks(self, role_id: str) -> List[Dict[str, Any]]:
        """获取角色的所有任务"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC')
            rows = cursor.fetchall()
        return [
            {'task_id': r[0], 'session_id': r[1], 'requester_role': r[2],
             'target_department': r[3], 'target_director': r[4],
             'status': r[5], 'created_at': r[6], 'updated_at': r[7],
             'retry_count': r[8]}
            for r in rows
        ]
    
    def get_task(self, role_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """获取指定角色的指定任务"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()
        if row:
            return {
                'task_id': row[0], 'session_id': row[1], 'requester_role': row[2],
                'target_department': row[3], 'target_director': row[4],
                'status': row[5], 'created_at': row[6], 'updated_at': row[7],
                'retry_count': row[8]
            }
        return None
    
    def get_task_messages(self, role_id: str, task_id: str) -> List[Dict[str, Any]]:
        """获取指定任务的所有消息"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM messages WHERE task_id = ? ORDER BY timestamp', (task_id,))
            rows = cursor.fetchall()
        result = []
        for r in rows:
            try:
                body = json.loads(r[4])
            except json.JSONDecodeError:
                body = {}
            result.append({
                'message_id': r[0], 'task_id': r[1], 'sender_role': r[2],
                'receiver_role': r[3], 'body': body, 'timestamp': r[5]
            })
        return result
    
    def increment_retry(self, role_id: str, task_id: str) -> None:
        """增加任务重试次数"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE tasks SET retry_count = retry_count + 1 WHERE task_id = ?', (task_id,))
            conn.commit()
    
    # ---- 统计管理（角色级） ----
    
    def save_statistic(self, role_id: str, event_type: str, **kwargs) -> None:
        """保存统计事件到角色的 statistics 表"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO statistics (
                    event_type, role_id, model_id, task_id,
                    prompt_tokens, completion_tokens, total_tokens,
                    filepath, file_type, file_size,
                    task_status, duration_seconds, task_hint, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event_type,
                kwargs.get('role_id', ''),
                kwargs.get('model_id', ''),
                kwargs.get('task_id', ''),
                kwargs.get('prompt_tokens', 0),
                kwargs.get('completion_tokens', 0),
                kwargs.get('total_tokens', 0),
                kwargs.get('filepath', ''),
                kwargs.get('file_type', ''),
                kwargs.get('file_size', 0),
                kwargs.get('task_status', ''),
                kwargs.get('duration_seconds', 0),
                kwargs.get('task_hint', ''),
                datetime.now().isoformat()
            ))
            conn.commit()
    
    def get_statistics(self, role_id: str, event_type: str = "", 
                       since: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        """查询角色的统计事件"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            if event_type:
                cursor.execute('''
                    SELECT * FROM statistics WHERE event_type = ? 
                    AND (? = '' OR timestamp > ?)
                    ORDER BY timestamp DESC LIMIT ?
                ''', (event_type, since, since, limit))
            else:
                cursor.execute('''
                    SELECT * FROM statistics
                    WHERE (? = '' OR timestamp > ?)
                    ORDER BY timestamp DESC LIMIT ?
                ''', (since, since, limit))
            rows = cursor.fetchall()
        return [
            {
                'stat_id': r[0], 'event_type': r[1], 'role_id': r[2], 'model_id': r[3],
                'task_id': r[4], 'prompt_tokens': r[5], 'completion_tokens': r[6],
                'total_tokens': r[7], 'filepath': r[8], 'file_type': r[9],
                'file_size': r[10], 'task_status': r[11], 'duration_seconds': r[12],
                'task_hint': r[13], 'timestamp': r[14]
            }
            for r in rows
        ]
    
    def get_all_tasks(self, status: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        """遍历所有角色的 role.db 聚合任务列表"""
        all_tasks = []
        for role_dir in (self.project_root / "group").rglob("*/memories"):
            db_path = role_dir / "role.db"
            if not db_path.exists():
                continue
            role_id = role_dir.parent.name
            try:
                with sqlite3.connect(str(db_path)) as conn:
                    cursor = conn.cursor()
                    if status:
                        cursor.execute('''
                            SELECT * FROM tasks WHERE status = ? 
                            ORDER BY created_at DESC LIMIT ?
                        ''', (status, limit))
                    else:
                        cursor.execute('''
                            SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?
                        ''', (limit,))
                    rows = cursor.fetchall()
                    for r in rows:
                        all_tasks.append({
                            'task_id': r[0], 'session_id': r[1], 'requester_role': r[2],
                            'target_department': r[3], 'target_director': r[4],
                            'status': r[5], 'created_at': r[6], 'updated_at': r[7],
                            'retry_count': r[8], 'source_role': role_id
                        })
            except Exception:
                continue
        # 按 created_at 排序
        all_tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return all_tasks[:limit]
    
    def get_pending_approvals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """查询所有角色的待审批列表"""
        all_approvals = []
        for role_dir in (self.project_root / "group").rglob("*/memories"):
            db_path = role_dir / "role.db"
            if not db_path.exists():
                continue
            role_id = role_dir.parent.name
            try:
                with sqlite3.connect(str(db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT * FROM approvals WHERE status = 'pending'
                        ORDER BY created_at DESC LIMIT ?
                    ''', (limit,))
                    rows = cursor.fetchall()
                    for r in rows:
                        all_approvals.append({
                            'approval_id': r[0], 'report_id': r[1], 'requester': r[2],
                            'status': r[3], 'approval_token': r[4], 'user_response': r[5],
                            'created_at': r[6], 'resolved_at': r[7], 'source_role': role_id
                        })
            except Exception:
                continue
        return all_approvals
    
    # ---- 消息管理（角色级） ----
    
    def save_message(self, role_id: str, message_id: str, task_id: str,
                     sender: str, receiver: str, body: Dict[str, Any]) -> None:
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO messages (message_id, task_id, sender_role, receiver_role, body, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (message_id, task_id, sender, receiver, json.dumps(body), now))
            conn.commit()
    
    def get_role_messages(self, role_id: str) -> List[Dict[str, Any]]:
        """获取角色的所有消息"""
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM messages ORDER BY timestamp')
            rows = cursor.fetchall()
        result = []
        for r in rows:
            try:
                body = json.loads(r[4])
            except json.JSONDecodeError:
                body = {}
            result.append({
                'message_id': r[0], 'task_id': r[1], 'sender_role': r[2],
                'receiver_role': r[3], 'body': body, 'timestamp': r[5]
            })
        return result
    
    def get_session_messages(self, role_id: str, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取指定会话的所有消息（跨任务聚合，按时间排序）
        
        通过 JOIN tasks 表按 session_id 过滤，实现用户级消息隔离。
        """
        db_path = self._get_role_db(role_id)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.* FROM messages m
                JOIN tasks t ON m.task_id = t.task_id
                WHERE t.session_id = ?
                ORDER BY m.timestamp DESC
                LIMIT ?
            ''', (session_id, limit))
            rows = cursor.fetchall()
        result = []
        for r in rows:
            try:
                body = json.loads(r[4])
            except json.JSONDecodeError:
                body = {}
            result.append({
                'message_id': r[0], 'task_id': r[1], 'sender_role': r[2],
                'receiver_role': r[3], 'body': body, 'timestamp': r[5]
            })
        # 按时间正序返回（ oldest first ）
        result.reverse()
        return result
    
    def get_active_sessions(self, role_id: str, user_id: str = "", 
                            since_hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取角色的活跃会话列表
        
        Args:
            since_hours: 最近 N 小时内有活动的会话
        """
        db_path = self._get_role_db(role_id)
        cutoff = (datetime.now() - __import__('datetime').timedelta(hours=since_hours)).isoformat()
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute('''
                    SELECT * FROM sessions 
                    WHERE user_id = ? AND start_time > ? AND status = 'active'
                    ORDER BY start_time DESC
                ''', (user_id, cutoff))
            else:
                cursor.execute('''
                    SELECT * FROM sessions 
                    WHERE start_time > ? AND status = 'active'
                    ORDER BY start_time DESC
                ''', (cutoff,))
            rows = cursor.fetchall()
        return [
            {'session_id': r[0], 'user_id': r[1], 'start_time': r[2],
             'end_time': r[3], 'status': r[4]}
            for r in rows
        ]
    
    # ---- 角色私人记忆（文本文件） ----
    
    def save_role_memory(self, role_id: str, content: str, topic: str = '') -> str:
        """保存角色私人记忆到 group/<role>/memories/"""
        role_dir = self._get_role_dir(role_id)
        mem_dir = role_dir / 'memories'
        mem_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{topic}.md" if topic else f"{timestamp}.md"
        mem_path = mem_dir / filename
        mem_path.write_text(content, encoding='utf-8')
        return str(mem_path.relative_to(self.project_root))
    
    def list_role_memories(self, role_id: str) -> List[str]:
        """列出角色的所有记忆文件（按修改时间倒序，最新的在前）"""
        role_dir = self._get_role_dir(role_id)
        mem_dir = role_dir / 'memories'
        if not mem_dir.exists():
            return []
        files = [p for p in mem_dir.glob('*.md') if p.is_file()]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [str(p.relative_to(self.project_root)) for p in files]
    
    def read_role_memory(self, role_id: str, rel_path: str) -> str:
        """读取角色记忆"""
        path = self.project_root / rel_path
        return path.read_text(encoding='utf-8')
    
    # ---- 角色学习经验（insights） ----
    
    def _get_insights_dir(self, role_id: str) -> Path:
        """获取角色的经验目录"""
        role_dir = self._get_role_dir(role_id)
        insights_dir = role_dir / 'memories' / 'insights'
        insights_dir.mkdir(parents=True, exist_ok=True)
        return insights_dir
    
    def save_role_insight(self, role_id: str, insight_data: dict) -> str:
        """
        保存角色学习经验
        
        Args:
            insight_data: {
                'title': str,
                'category': str,  # success_pattern / improvement / pitfall / preference
                'situation': str,
                'key_point': str,
                'avoid': str,
                'confidence': float,
            }
        
        Returns:
            保存的文件相对路径
        """
        insights_dir = self._get_insights_dir(role_id)
        
        # 文件名：YYYYMMDD_HHMMSS_{ sanitized_title }.md
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = re.sub(r'[^\w\u4e00-\u9fff]+', '_', insight_data['title'])[:30]
        filename = f"{timestamp}_{safe_title}.md"
        filepath = insights_dir / filename
        
        # 构建 Markdown 内容（含 YAML frontmatter）
        content = self._build_insight_markdown(insight_data, timestamp)
        filepath.write_text(content, encoding='utf-8')
        
        return str(filepath.relative_to(self.project_root))
    
    def _build_insight_markdown(self, data: dict, timestamp: str) -> str:
        """构建经验文件的 Markdown 格式"""
        return f"""---
insight_id: ins_{timestamp}
category: {data['category']}
created_at: "{datetime.now().isoformat()}"
trigger_count: 1
confidence: {data.get('confidence', 0.5)}
ttl_days: 90
last_triggered: "{datetime.now().isoformat()}"
---

# {data['title']}

## 情境
{data['situation']}

## 要点
{data['key_point']}

## 避免
{data['avoid']}

## 验证记录
- [{datetime.now().strftime('%Y-%m-%d')}] 首次提取
"""
    
    def list_role_insights(self, role_id: str, limit: int = 50) -> list:
        """
        按时间倒序列出角色的经验文件
        
        Returns:
            [{ 'path': str, 'meta': dict, 'content': str, 'created_at': str }]
        """
        insights_dir = self._get_insights_dir(role_id)
        if not insights_dir.exists():
            return []
        
        results = []
        for md_file in sorted(insights_dir.glob('*.md'), reverse=True)[:limit]:
            content = md_file.read_text(encoding='utf-8')
            meta, body = self._parse_insight_frontmatter(content)
            results.append({
                'path': str(md_file.relative_to(self.project_root)),
                'meta': meta,
                'content': body,
                'created_at': meta.get('created_at', '')
            })
        return results
    
    def _parse_insight_frontmatter(self, content: str) -> tuple:
        """解析经验文件的 YAML frontmatter"""
        parts = content.split('---', 2)
        if len(parts) >= 3:
            meta_text = parts[1].strip()
            body = parts[2].strip()
            meta = self._simple_yaml_parse(meta_text)
            return meta, body
        return {}, content
    
    def _simple_yaml_parse(self, text: str) -> dict:
        """极简 YAML 解析（只处理 key: value 单层）"""
        result = {}
        for line in text.strip().split('\n'):
            if ':' in line and not line.startswith('#'):
                key, val = line.split(':', 1)
                val = val.strip().strip('"').strip("'")
                # 尝试类型转换
                if val.lower() in ('true', 'false'):
                    result[key.strip()] = val.lower() == 'true'
                else:
                    try:
                        result[key.strip()] = float(val) if '.' in val else int(val)
                    except ValueError:
                        result[key.strip()] = val
        return result
    
    def get_recent_insights_for_context(self, role_id: str, task_hint: str = "", 
                                         limit: int = 5, max_chars: int = 2000) -> str:
        """
        获取用于注入上下文的经验文本
        
        筛选逻辑（方案 A 轻量版）：
        1. 按时间取最近 30 天内的经验
        2. 按 confidence 降序排列
        3. 如 task_hint 不为空，做简单关键词匹配粗排
        4. 截取前 limit 条，总字符不超过 max_chars
        
        Returns:
            格式化的经验文本块，可直接注入 System Prompt
        """
        insights = self.list_role_insights(role_id, limit=100)
        
        # 过滤 30 天内
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        recent = [i for i in insights if i.get('created_at', '') > cutoff]
        
        # 按 confidence 降序
        recent.sort(key=lambda x: x.get('meta', {}).get('confidence', 0), reverse=True)
        
        # 关键词粗排（如有 task_hint）
        if task_hint:
            recent = self._keyword_rank(recent, task_hint)
        
        # 组装并截断
        parts = []
        total = 0
        for ins in recent[:limit]:
            meta = ins.get('meta', {})
            title = meta.get('category', 'insight').replace('_', ' ').title()
            block = f"### {title}: {ins['meta'].get('title', '未命名')}\n"
            block += f"{ins['content'][:300]}\n\n"  # 单条截断 300 字
            
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)
        
        return "\n".join(parts) if parts else ""
    
    def _keyword_rank(self, insights: list, hint: str) -> list:
        """极简关键词匹配排序"""
        hint_words = set(hint.lower().split())
        scored = []
        for ins in insights:
            text = (ins.get('meta', {}).get('title', '') + ' ' + ins.get('content', '')).lower()
            score = sum(1 for w in hint_words if w in text)
            scored.append((score, ins))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [i[1] for i in scored]
    
    def update_insight_trigger(self, role_id: str, insight_path: str) -> None:
        """
        更新经验的触发计数（经验被注入上下文时调用）
        
        使用 frontmatter 解析+重建，避免正则替换的格式脆弱性。
        """
        try:
            path = self.project_root / insight_path
            if not path.exists():
                return
            
            content = path.read_text(encoding='utf-8')
            meta, body = self._parse_insight_frontmatter(content)
            if not meta:
                return
            
            # 更新 trigger_count
            current_count = meta.get('trigger_count', 1)
            if isinstance(current_count, (int, float)):
                meta['trigger_count'] = int(current_count) + 1
            
            # 更新 last_triggered
            meta['last_triggered'] = datetime.now().isoformat()
            
            # 重建 frontmatter（保持与 _build_insight_markdown 一致的格式）
            lines = ['---']
            for key, val in meta.items():
                if isinstance(val, str):
                    lines.append(f'{key}: "{val}"')
                elif isinstance(val, bool):
                    lines.append(f'{key}: {str(val).lower()}')
                else:
                    lines.append(f'{key}: {val}')
            lines.append('---')
            
            new_content = '\n'.join(lines) + '\n\n' + body
            path.write_text(new_content, encoding='utf-8')
        except Exception:
            pass
