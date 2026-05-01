"""
任务状态中心

关联文档: suri-agent/core/core.md

职责：
- 管理 Agent 的生命周期数据（创建、查询、更新、销毁）
- 管理 TaskStep 的状态流转（待办→进行中→已完成→受阻）
- 提供状态卡片渲染数据
- 持久化到 SQLite（suri-agent/state/agents.db）

V3.0 新增模块
"""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class TaskStep:
    """任务步骤"""
    step_id: str
    description: str
    status: str = "pending"  # pending | in_progress | completed | blocked
    assignee: str = ""       # 执行者 role_id
    estimated_time: Optional[int] = None  # 预计耗时（秒）
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    block_reason: Optional[str] = None
    depends_on: List[str] = None  # 依赖的前置步骤 ID 列表
    result: Optional[str] = None  # 步骤执行结果摘要
    
    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskStep":
        return cls(**d)


@dataclass
class Agent:
    """任务 Agent"""
    agent_id: str
    task_id: str
    task_name: str = ""
    parent_agent_id: Optional[str] = None
    role_id: str = ""
    status: str = "planning"  # planning | running | paused | completed | blocked
    steps: List[TaskStep] = None
    user_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "parent_agent_id": self.parent_agent_id,
            "role_id": self.role_id,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Agent":
        steps = [TaskStep.from_dict(s) for s in d.get("steps", [])]
        return cls(
            agent_id=d["agent_id"],
            task_id=d["task_id"],
            task_name=d.get("task_name", ""),
            parent_agent_id=d.get("parent_agent_id"),
            role_id=d.get("role_id", ""),
            status=d.get("status", "planning"),
            steps=steps,
            user_id=d.get("user_id", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )
    
    @property
    def progress(self) -> str:
        """进度描述，如 '2/4'"""
        if not self.steps:
            return "0/0"
        completed = sum(1 for s in self.steps if s.status == "completed")
        return f"{completed}/{len(self.steps)}"
    
    @property
    def current_step(self) -> Optional[TaskStep]:
        """当前进行中的步骤"""
        for s in self.steps:
            if s.status == "in_progress":
                return s
        # 如果没有进行中的，返回第一个待办的
        for s in self.steps:
            if s.status == "pending":
                return s
        return None


class TaskStateService:
    """
    任务状态中心
    
    管理所有 Agent 和步骤状态，支持：
    - Agent CRUD
    - 步骤状态流转
    - 按用户查询活跃 Agent
    - 状态统计
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.state_dir = project_root / "suri-agent" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "agents.db"
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化状态数据库"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    task_name TEXT,
                    parent_agent_id TEXT,
                    role_id TEXT,
                    status TEXT,
                    steps_json TEXT,
                    user_id TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_agents_user ON agents(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)
            ''')
            
            conn.commit()
    
    def create_agent(self, task_id: str, task_name: str, user_id: str,
                     role_id: str = "", parent_agent_id: Optional[str] = None,
                     steps: Optional[List[TaskStep]] = None) -> Agent:
        """创建新 Agent"""
        import random
        agent_id = f"agent_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}_{random.randint(1000, 9999)}"
        now = datetime.now().isoformat()
        agent = Agent(
            agent_id=agent_id,
            task_id=task_id,
            task_name=task_name,
            parent_agent_id=parent_agent_id,
            role_id=role_id,
            status="planning",
            steps=steps or [],
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self._save_agent(agent)
        return agent
    
    def _save_agent(self, agent: Agent) -> None:
        """持久化 Agent"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO agents 
                (agent_id, task_id, task_name, parent_agent_id, role_id, status, steps_json, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                agent.agent_id, agent.task_id, agent.task_name,
                agent.parent_agent_id, agent.role_id, agent.status,
                json.dumps([s.to_dict() for s in agent.steps], ensure_ascii=False),
                agent.user_id, agent.created_at, datetime.now().isoformat()
            ))
            conn.commit()
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取单个 Agent"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM agents WHERE agent_id = ?', (agent_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_agent(row)
            return None
    
    def get_agents_by_user(self, user_id: str, status_filter: Optional[List[str]] = None) -> List[Agent]:
        """获取用户的所有 Agent"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if status_filter:
                placeholders = ','.join('?' * len(status_filter))
                cursor.execute(
                    f'SELECT * FROM agents WHERE user_id = ? AND status IN ({placeholders}) ORDER BY created_at DESC',
                    (user_id, *status_filter)
                )
            else:
                cursor.execute(
                    'SELECT * FROM agents WHERE user_id = ? ORDER BY created_at DESC',
                    (user_id,)
                )
            rows = cursor.fetchall()
            return [self._row_to_agent(row) for row in rows]
    
    def get_active_agents(self, user_id: str) -> List[Agent]:
        """获取用户的活跃 Agent（planning/running/paused/blocked）"""
        return self.get_agents_by_user(user_id, ["planning", "running", "paused", "blocked"])
    
    def update_agent_status(self, agent_id: str, status: str) -> bool:
        """更新 Agent 状态"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE agents SET status = ?, updated_at = ? WHERE agent_id = ?',
                (status, datetime.now().isoformat(), agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def update_agent_steps(self, agent_id: str, steps: List[TaskStep]) -> bool:
        """更新 Agent 的步骤"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE agents SET steps_json = ?, updated_at = ? WHERE agent_id = ?',
                (json.dumps([s.to_dict() for s in steps], ensure_ascii=False), datetime.now().isoformat(), agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def update_agent_role(self, agent_id: str, role_id: str) -> bool:
        """更新 Agent 的执行角色"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE agents SET role_id = ?, updated_at = ? WHERE agent_id = ?',
                (role_id, datetime.now().isoformat(), agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def complete_agent(self, agent_id: str) -> bool:
        """标记 Agent 为已完成"""
        return self.update_agent_status(agent_id, "completed")
    
    def block_agent(self, agent_id: str, reason: str) -> bool:
        """标记 Agent 为受阻"""
        agent = self.get_agent(agent_id)
        if agent:
            agent.status = "blocked"
            # 更新当前步骤的受阻原因
            for step in agent.steps:
                if step.status == "in_progress":
                    step.status = "blocked"
                    step.block_reason = reason
                    break
            self._save_agent(agent)
            return True
        return False
    
    def _row_to_agent(self, row: sqlite3.Row) -> Agent:
        """数据库行转 Agent 对象"""
        steps_json = row["steps_json"] or "[]"
        try:
            steps_data = json.loads(steps_json)
        except Exception:
            steps_data = []
        return Agent(
            agent_id=row["agent_id"],
            task_id=row["task_id"],
            task_name=row["task_name"] or "",
            parent_agent_id=row["parent_agent_id"],
            role_id=row["role_id"] or "",
            status=row["status"] or "planning",
            steps=[TaskStep.from_dict(s) for s in steps_data],
            user_id=row["user_id"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户任务统计"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status, COUNT(*) FROM agents WHERE user_id = ?
                GROUP BY status
            ''', (user_id,))
            stats = dict(cursor.fetchall())
            return {
                "user_id": user_id,
                "total": sum(stats.values()),
                "active": stats.get("planning", 0) + stats.get("running", 0) + stats.get("paused", 0) + stats.get("blocked", 0),
                "completed": stats.get("completed", 0),
                "by_status": stats,
            }
