"""
记忆服务

职责：
- 管理 state.db（SQLite）
- 维护角色私人记忆（profiles/<role>/memories/）
- 按 memory_config.md 策略自动归档/遗忘

原则：记忆读写通过此服务，不直接操作数据库或文件。
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from suri_agent.infrastructure.config import ConfigService


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
    
    数据来源：
    - state.db: 会话、任务、消息、审批、变更日志
    - profiles/<role>/memories/: 角色私人长期记忆
    """
    
    def __init__(self, project_root: Path, config: ConfigService):
        self.project_root = project_root
        self.config = config
        self.db_path = project_root / 'state.db'
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化数据库表（如果不存在）"""
        conn = sqlite3.connect(str(self.db_path))
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
    
    # ---- 任务管理 ----
    
    def create_task(self, task_id: str, session_id: str, requester: str,
                    target_dept: str, target_director: str) -> None:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO tasks (task_id, session_id, requester_role, target_department,
                             target_director, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, session_id, requester, target_dept, target_director, 'pending', now, now))
        conn.commit()
        conn.close()
    
    def update_task_status(self, task_id: str, status: str) -> None:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?
        ''', (status, now, task_id))
        conn.commit()
        conn.close()
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                'task_id': row[0], 'session_id': row[1], 'requester_role': row[2],
                'target_department': row[3], 'target_director': row[4],
                'status': row[5], 'created_at': row[6], 'updated_at': row[7],
                'retry_count': row[8]
            }
        return None
    
    def increment_retry(self, task_id: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET retry_count = retry_count + 1 WHERE task_id = ?', (task_id,))
        cursor.execute('SELECT retry_count FROM tasks WHERE task_id = ?', (task_id,))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        return row[0] if row else 0
    
    # ---- 消息管理 ----
    
    def save_message(self, message_id: str, task_id: str, sender: str,
                     receiver: str, body: Dict[str, Any]) -> None:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO messages (message_id, task_id, sender_role, receiver_role, body, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (message_id, task_id, sender, receiver, json.dumps(body), now))
        conn.commit()
        conn.close()
    
    def get_task_messages(self, task_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM messages WHERE task_id = ? ORDER BY timestamp', (task_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {'message_id': r[0], 'task_id': r[1], 'sender_role': r[2],
             'receiver_role': r[3], 'body': json.loads(r[4]), 'timestamp': r[5]}
            for r in rows
        ]
    
    # ---- 角色私人记忆 ----
    
    def save_role_memory(self, role_id: str, content: str, topic: str = '') -> str:
        """保存角色私人记忆到 profiles/<role>/memories/"""
        mem_dir = self.project_root / 'profiles' / role_id / 'memories'
        mem_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{topic}.md" if topic else f"{timestamp}.md"
        mem_path = mem_dir / filename
        mem_path.write_text(content, encoding='utf-8')
        return str(mem_path.relative_to(self.project_root))
    
    def list_role_memories(self, role_id: str) -> List[str]:
        """列出角色的所有记忆文件"""
        mem_dir = self.project_root / 'profiles' / role_id / 'memories'
        if not mem_dir.exists():
            return []
        return [str(p.relative_to(self.project_root)) for p in mem_dir.glob('*.md')]
    
    def read_role_memory(self, role_id: str, rel_path: str) -> str:
        """读取角色记忆"""
        path = self.project_root / rel_path
        return path.read_text(encoding='utf-8')
