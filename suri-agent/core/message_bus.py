"""
消息总线（内部通信）

关联文档: suri-agent/core/core.md

职责：
- 轻量级内部消息队列，供角色间通信
- 支持状态广播（角色完成子步骤时发送）
- 支持定向消息（suri → 角色、角色 → suri）
- suri 订阅汇总，实时更新任务状态

V3.0 新增模块
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class Message:
    """内部消息"""
    msg_id: str
    sender: str           # 发送者 role_id
    receiver: str         # 接收者 role_id（或 "broadcast"）
    msg_type: str         # status_update | request_help | completion | interrupt
    content: str          # 消息内容
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "type": self.msg_type,
            "content": self.content,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
        }


class MessageBus:
    """
    消息总线
    
    实现方式：SQLite 持久化队列（轻量、可靠、支持重启后恢复）
    每条消息有 sender/receiver，支持广播和点对点
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.db_path = project_root / "suri-agent" / "state" / "message_bus.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化消息数据库"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    msg_id TEXT PRIMARY KEY,
                    sender TEXT,
                    receiver TEXT,
                    type TEXT,
                    content TEXT,
                    task_id TEXT,
                    agent_id TEXT,
                    timestamp TIMESTAMP,
                    consumed INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_msg_receiver ON messages(receiver)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_msg_task ON messages(task_id)
            ''')
            conn.commit()
    
    def publish(self, sender: str, receiver: str, msg_type: str, content: str,
                task_id: Optional[str] = None, agent_id: Optional[str] = None) -> Message:
        """
        发布消息
        
        Args:
            sender: 发送者 role_id
            receiver: 接收者 role_id（或 "broadcast" 广播）
            msg_type: 消息类型
            content: 消息内容
            task_id: 关联任务（可选）
            agent_id: 关联 Agent（可选）
            
        Returns:
            发送的消息对象
        """
        msg_id = f"msg_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(content) % 10000}"
        msg = Message(
            msg_id=msg_id,
            sender=sender,
            receiver=receiver,
            msg_type=msg_type,
            content=content,
            task_id=task_id,
            agent_id=agent_id,
        )
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (msg_id, sender, receiver, type, content, task_id, agent_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (msg.msg_id, msg.sender, msg.receiver, msg.msg_type, msg.content,
                  msg.task_id, msg.agent_id, msg.timestamp))
            conn.commit()
        
        return msg
    
    def broadcast_status(self, sender: str, content: str,
                         task_id: Optional[str] = None, agent_id: Optional[str] = None) -> Message:
        """广播状态更新（快捷方法）"""
        return self.publish(
            sender=sender,
            receiver="broadcast",
            msg_type="status_update",
            content=content,
            task_id=task_id,
            agent_id=agent_id,
        )
    
    def request_help(self, sender: str, content: str,
                     task_id: Optional[str] = None, agent_id: Optional[str] = None) -> Message:
        """请求帮助（快捷方法）"""
        return self.publish(
            sender=sender,
            receiver="suri",
            msg_type="request_help",
            content=content,
            task_id=task_id,
            agent_id=agent_id,
        )
    
    def consume(self, receiver: str, limit: int = 50) -> List[Message]:
        """
        消费消息（获取并标记为已消费）
        
        Args:
            receiver: 接收者 role_id
            limit: 最大消费条数
            
        Returns:
            消息列表
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM messages 
                WHERE (receiver = ? OR receiver = 'broadcast') AND consumed = 0
                ORDER BY timestamp ASC
                LIMIT ?
            ''', (receiver, limit))
            rows = cursor.fetchall()
            
            # 标记为已消费
            msg_ids = [row["msg_id"] for row in rows]
            if msg_ids:
                placeholders = ','.join('?' * len(msg_ids))
                cursor.execute(
                    f'UPDATE messages SET consumed = 1 WHERE msg_id IN ({placeholders})',
                    msg_ids
                )
                conn.commit()
            
            return [self._row_to_message(row) for row in rows]
    
    def peek(self, receiver: str, limit: int = 50) -> List[Message]:
        """查看消息（不标记为已消费）"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM messages 
                WHERE (receiver = ? OR receiver = 'broadcast') AND consumed = 0
                ORDER BY timestamp ASC
                LIMIT ?
            ''', (receiver, limit))
            rows = cursor.fetchall()
            return [self._row_to_message(row) for row in rows]
    
    def get_unread_count(self, receiver: str) -> int:
        """获取未读消息数量"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM messages 
                WHERE (receiver = ? OR receiver = 'broadcast') AND consumed = 0
            ''', (receiver,))
            return cursor.fetchone()[0]
    
    def get_broadcast_for_task(self, task_id: str, limit: int = 20) -> List[Message]:
        """获取某任务的所有广播消息"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM messages 
                WHERE task_id = ? AND receiver = 'broadcast'
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (task_id, limit))
            rows = cursor.fetchall()
            return [self._row_to_message(row) for row in rows]
    
    def cleanup_old_messages(self, max_age_hours: int = 24) -> int:
        """清理过期消息"""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM messages WHERE timestamp < ? AND consumed = 1', (cutoff,))
            conn.commit()
            return cursor.rowcount
    
    def _row_to_message(self, row: sqlite3.Row) -> Message:
        return Message(
            msg_id=row["msg_id"],
            sender=row["sender"],
            receiver=row["receiver"],
            msg_type=row["type"],
            content=row["content"],
            task_id=row["task_id"],
            agent_id=row["agent_id"],
            timestamp=row["timestamp"],
        )
