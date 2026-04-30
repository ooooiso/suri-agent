"""
记忆服务

职责：
- 每个角色拥有独立的记忆存储（group/<role>/memories/role.db）
- 每个角色拥有独立的会话存储
- 按 memory_config.md 策略自动归档/遗忘

原则：记忆读写通过此服务，不直接操作数据库或文件。
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from infrastructure.config import ConfigService


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
    
    def _get_role_db(self, role_id: str) -> Path:
        """获取角色的独立数据库路径"""
        mem_dir = self.project_root / 'group' / role_id / 'memories'
        mem_dir.mkdir(parents=True, exist_ok=True)
        db_path = mem_dir / 'role.db'
        self._init_role_db(db_path)
        return db_path
    
    def _init_role_db(self, db_path: Path) -> None:
        """初始化角色数据库表"""
        conn = sqlite3.connect(str(db_path))
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
        
        conn.commit()
        conn.close()
    
    # ---- 会话管理（角色级） ----
    
    def create_session(self, role_id: str, session_id: str, user_id: str) -> None:
        """为指定角色创建会话"""
        db_path = self._get_role_db(role_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO sessions (session_id, user_id, start_time, status)
            VALUES (?, ?, ?, ?)
        ''', (session_id, user_id, now, 'active'))
        conn.commit()
        conn.close()
    
    def close_session(self, role_id: str, session_id: str) -> None:
        """关闭指定角色的会话"""
        db_path = self._get_role_db(role_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE sessions SET end_time = ?, status = ? WHERE session_id = ?
        ''', (now, 'closed', session_id))
        conn.commit()
        conn.close()
    
    def get_role_sessions(self, role_id: str) -> List[Dict[str, Any]]:
        """获取角色的所有会话"""
        db_path = self._get_role_db(role_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions ORDER BY start_time DESC')
        rows = cursor.fetchall()
        conn.close()
        return [
            {'session_id': r[0], 'user_id': r[1], 'start_time': r[2],
             'end_time': r[3], 'status': r[4]}
            for r in rows
        ]
    
    # ---- 任务管理（角色级） ----
    
    def create_task(self, role_id: str, task_id: str, session_id: str,
                    requester: str, target_dept: str, target_director: str) -> None:
        db_path = self._get_role_db(role_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO tasks (task_id, session_id, requester_role, target_department,
                             target_director, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, session_id, requester, target_dept, target_director, 'pending', now, now))
        conn.commit()
        conn.close()
    
    def update_task_status(self, role_id: str, task_id: str, status: str) -> None:
        db_path = self._get_role_db(role_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?
        ''', (status, now, task_id))
        conn.commit()
        conn.close()
    
    def get_role_tasks(self, role_id: str) -> List[Dict[str, Any]]:
        """获取角色的所有任务"""
        db_path = self._get_role_db(role_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [
            {'task_id': r[0], 'session_id': r[1], 'requester_role': r[2],
             'target_department': r[3], 'target_director': r[4],
             'status': r[5], 'created_at': r[6], 'updated_at': r[7],
             'retry_count': r[8]}
            for r in rows
        ]
    
    # ---- 消息管理（角色级） ----
    
    def save_message(self, role_id: str, message_id: str, task_id: str,
                     sender: str, receiver: str, body: Dict[str, Any]) -> None:
        db_path = self._get_role_db(role_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO messages (message_id, task_id, sender_role, receiver_role, body, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (message_id, task_id, sender, receiver, json.dumps(body), now))
        conn.commit()
        conn.close()
    
    def get_role_messages(self, role_id: str) -> List[Dict[str, Any]]:
        """获取角色的所有消息"""
        db_path = self._get_role_db(role_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM messages ORDER BY timestamp')
        rows = cursor.fetchall()
        conn.close()
        return [
            {'message_id': r[0], 'task_id': r[1], 'sender_role': r[2],
             'receiver_role': r[3], 'body': json.loads(r[4]), 'timestamp': r[5]}
            for r in rows
        ]
    
    # ---- 角色私人记忆（文本文件） ----
    
    def save_role_memory(self, role_id: str, content: str, topic: str = '') -> str:
        """保存角色私人记忆到 group/<role>/memories/"""
        mem_dir = self.project_root / 'group' / role_id / 'memories'
        mem_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{topic}.md" if topic else f"{timestamp}.md"
        mem_path = mem_dir / filename
        mem_path.write_text(content, encoding='utf-8')
        return str(mem_path.relative_to(self.project_root))
    
    def list_role_memories(self, role_id: str) -> List[str]:
        """列出角色的所有记忆文件"""
        mem_dir = self.project_root / 'group' / role_id / 'memories'
        if not mem_dir.exists():
            return []
        return [str(p.relative_to(self.project_root)) for p in mem_dir.glob('*.md')]
    
    def read_role_memory(self, role_id: str, rel_path: str) -> str:
        """读取角色记忆"""
        path = self.project_root / rel_path
        return path.read_text(encoding='utf-8')
