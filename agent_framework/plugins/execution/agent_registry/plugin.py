"""agent_registry 插件 — Agent 生命周期管理与持久化。"""

import json
import sqlite3
import time
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework.shared.interfaces.plugin import Agent, PluginInterface, TaskStep
from agent_framework.shared.utils.event_types import Event


class AgentRegistryPlugin(PluginInterface):
    """Agent 注册表插件。"""

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._conn: Optional[sqlite3.Connection] = None
        self._db_path: Optional[Path] = None
        self._status = "stopped"
        self._agents: Dict[str, Agent] = {}

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config

        # 初始化数据库
        db_path_setting = config.get("agent_registry", {}).get("db_path", "")
        if db_path_setting == ":memory:":
            self._conn = sqlite3.connect(":memory:")
        else:
            root = config.get("runtime_root", Path.cwd() / ".suri" / "runtime")
            self._db_path = Path(root) / "agent_registry" / "agents.db"
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))

        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

        # 从数据库恢复 Agent
        self._load_agents()

        self._status = "initialized"

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                parent_agent_id TEXT,
                role_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planning',
                steps TEXT NOT NULL DEFAULT '[]',
                user_id TEXT NOT NULL,
                plan_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
            CREATE INDEX IF NOT EXISTS idx_agents_user ON agents(user_id);
        """)
        self._conn.commit()

    def _load_agents(self) -> None:
        """从数据库加载所有 Agent。"""
        self._agents = {}
        try:
            rows = self._conn.execute("SELECT * FROM agents").fetchall()
            for row in rows:
                d = dict(row)
                d["steps"] = json.loads(d["steps"])
                agent = Agent(**d)
                self._agents[agent.agent_id] = agent
        except Exception:
            pass

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

    def register_events(self) -> None:
        pass

    # ── 公开 API ──

    def clear_db(self) -> None:
        """清空数据库（仅测试用）。"""
        if self._conn:
            self._conn.execute("DELETE FROM agents")
            self._conn.commit()
        self._agents = {}

    def create_agent(self, task_id: str, task_name: str, role_id: str,
                     user_id: str, parent_agent_id: Optional[str] = None,
                     steps: Optional[List[TaskStep]] = None) -> Agent:
        """创建新 Agent。"""
        now = datetime.now().isoformat()
        agent_id = f"{role_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        agent_steps = steps or []

        agent = Agent(
            agent_id=agent_id,
            task_id=task_id,
            task_name=task_name,
            parent_agent_id=parent_agent_id,
            role_id=role_id,
            status="planning",
            steps=agent_steps,
            user_id=user_id,
            plan_id=None,
            created_at=now,
            updated_at=now,
        )

        self._agents[agent_id] = agent
        self._save_agent(agent)
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取 Agent。"""
        return self._agents.get(agent_id)

    def list_agents(self, user_id: Optional[str] = None,
                    status: Optional[str] = None) -> List[Agent]:
        """列出 Agent。"""
        results = list(self._agents.values())
        if user_id:
            results = [a for a in results if a.user_id == user_id]
        if status:
            results = [a for a in results if a.status == status]
        return results

    def update_agent_status(self, agent_id: str, status: str) -> bool:
        """更新 Agent 状态。"""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent.status = status
        agent.updated_at = datetime.now().isoformat()
        self._save_agent(agent)
        return True

    def update_step_status(self, agent_id: str, step_id: str,
                           status: str, result: Optional[str] = None) -> bool:
        """更新步骤状态。"""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        for step in agent.steps:
            if step.step_id == step_id:
                step.status = status
                if result:
                    step.result = result
                agent.updated_at = datetime.now().isoformat()
                self._save_agent(agent)
                return True
        return False

    def get_agent_progress(self, agent_id: str) -> str:
        """获取 Agent 进度。"""
        agent = self._agents.get(agent_id)
        if not agent:
            return "0/0"
        return agent.progress

    def build_chat_messages(self, agent_id: str, user_input: str) -> List[Dict]:
        """构建聊天消息列表。"""
        agent = self._agents.get(agent_id)
        if not agent:
            return []
        
        system_content = f"你正在执行任务: {agent.task_name}\n"
        if agent.steps:
            steps_desc = "\n".join([
                f"- {s.step_id}: {s.description} ({s.status})"
                for s in agent.steps
            ])
            system_content += f"任务步骤:\n{steps_desc}\n"
        system_content += f"当前进度: {agent.progress}"
        
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_input},
        ]

    def _save_agent(self, agent: Agent) -> None:
        """保存 Agent 到数据库。"""
        if not self._conn:
            return
        self._conn.execute(
            """INSERT OR REPLACE INTO agents 
               (agent_id, task_id, task_name, parent_agent_id, role_id, status, steps, user_id, plan_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (agent.agent_id, agent.task_id, agent.task_name, agent.parent_agent_id,
             agent.role_id, agent.status, json.dumps([asdict(s) for s in agent.steps]),
             agent.user_id, agent.plan_id, agent.created_at, agent.updated_at),
        )
        self._conn.commit()

    # ── 事件处理 ──

    async def _on_agent_created(self, event: Event) -> None:
        """处理 agent.created 事件。"""
        pass

    async def _on_agent_completed(self, event: Event) -> None:
        """处理 agent.completed 事件。"""
        pass