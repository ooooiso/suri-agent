"""agent_registry 插件 — Agent 生命周期管理"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.interfaces.plugin import (
    PluginInterface, Agent, TaskStep, TaskPlan
)
from shared.utils.event_types import Event, Priority


class AgentRegistryPlugin(PluginInterface):
    """Agent 生命周期管理插件。
    
    创建、跟踪、查询 Agent 状态。管理 Agent 的完整生命周期。
    """
    
    def __init__(self):
        self.name = "agent_registry"
        self.event_bus = None
        self.config = {}
        self._agents: Dict[str, Agent] = {}  # agent_id -> Agent
        self._db_path = None
    
    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        """初始化插件"""
        self.event_bus = event_bus
        self.config = config.get("agent_registry", {})
        self._db_path = config.get("db_path", "~/.suri/data/agent_registry.db")
    
    def register_events(self) -> None:
        """注册事件订阅"""
        self.event_bus.subscribe("task.planned", self._on_task_planned)
        self.event_bus.subscribe("task.completed", self._on_task_completed)
        self.event_bus.subscribe("task.failed", self._on_task_failed)
        self.event_bus.subscribe("task.timeout", self._on_task_timeout)
        self.event_bus.subscribe("agent.block_requested", self._on_block_requested)
    
    async def start(self) -> None:
        """启动插件"""
        pass
    
    async def pause(self) -> None:
        """暂停插件"""
        pass
    
    async def resume(self) -> None:
        """恢复插件"""
        pass
    
    async def stop(self) -> None:
        """停止插件"""
        pass
    
    async def cleanup(self) -> None:
        """清理资源"""
        self._agents.clear()
    
    # --- 事件处理 ---
    
    async def _on_task_planned(self, event: Event) -> None:
        """任务规划完成，创建 Agent"""
        payload = event.payload
        task_name = payload.get("task_name", "")
        steps_data = payload.get("steps", [])
        involved_roles = payload.get("involved_roles", [])
        plan_id = payload.get("plan_id", "")
        
        # 创建 Agent
        agent = self.create_agent(
            task_id=plan_id,
            task_name=task_name,
            role_id=involved_roles[0] if involved_roles else "suri",
            user_id=event.source or "system",
            plan_id=plan_id,
            steps=[TaskStep(**s) for s in steps_data],
        )
        
        # 发布 Agent 创建事件
        await self.event_bus.publish(Event(
            event_type="agent.created",
            source=self.name,
            payload={
                "agent_id": agent.agent_id,
                "task_name": agent.task_name,
                "role_id": agent.role_id,
                "status": agent.status,
                "steps_count": len(agent.steps),
            }
        ))
    
    async def _on_task_completed(self, event: Event) -> None:
        """任务完成，更新 Agent 状态"""
        task_id = event.payload.get("task_id", "")
        agent = self._find_agent_by_task(task_id)
        if agent:
            self.update_agent_status(agent.agent_id, "completed")
    
    async def _on_task_failed(self, event: Event) -> None:
        """任务失败，更新 Agent 状态"""
        task_id = event.payload.get("task_id", "")
        agent = self._find_agent_by_task(task_id)
        if agent:
            self.update_agent_status(agent.agent_id, "blocked")
    
    async def _on_task_timeout(self, event: Event) -> None:
        """任务超时，更新 Agent 状态"""
        task_id = event.payload.get("task_id", "")
        agent = self._find_agent_by_task(task_id)
        if agent:
            self.update_agent_status(agent.agent_id, "blocked")
    
    async def _on_block_requested(self, event: Event) -> None:
        """Agent 受阻"""
        agent_id = event.payload.get("agent_id", "")
        reason = event.payload.get("reason", "")
        block_type = event.payload.get("block_type", "unknown")
        
        agent = self._agents.get(agent_id)
        if agent:
            agent.status = "blocked"
            # 更新当前步骤状态
            current = agent.current_step
            if current:
                current.status = "blocked"
                current.block_reason = reason
    
    # --- 核心方法 ---
    
    def create_agent(self, task_id: str, task_name: str,
                     role_id: str, user_id: str,
                     plan_id: str = None,
                     parent_agent_id: str = None,
                     steps: List[TaskStep] = None) -> Agent:
        """创建 Agent"""
        now = datetime.now().isoformat()
        agent_id = self._generate_agent_id(role_id)
        
        agent = Agent(
            agent_id=agent_id,
            task_id=task_id,
            task_name=task_name,
            parent_agent_id=parent_agent_id,
            role_id=role_id,
            status="planning",
            steps=steps or [],
            user_id=user_id,
            plan_id=plan_id,
            created_at=now,
            updated_at=now,
        )
        
        self._agents[agent_id] = agent
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取 Agent"""
        return self._agents.get(agent_id)
    
    def list_agents(self, user_id: str = None,
                    status: str = None) -> List[Agent]:
        """列出 Agent"""
        agents = list(self._agents.values())
        if user_id:
            agents = [a for a in agents if a.user_id == user_id]
        if status:
            agents = [a for a in agents if a.status == status]
        return sorted(agents, key=lambda a: a.created_at, reverse=True)
    
    def update_agent_status(self, agent_id: str,
                            status: str) -> bool:
        """更新 Agent 状态"""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent.status = status
        agent.updated_at = datetime.now().isoformat()
        return True
    
    def update_step_status(self, agent_id: str, step_id: str,
                           status: str, result: str = None) -> bool:
        """更新步骤状态"""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        
        for step in agent.steps:
            if step.step_id == step_id:
                step.status = status
                if result:
                    step.result = result
                if status == "in_progress":
                    step.started_at = datetime.now().isoformat()
                elif status == "completed":
                    step.completed_at = datetime.now().isoformat()
                agent.updated_at = datetime.now().isoformat()
                return True
        
        return False
    
    def get_agent_progress(self, agent_id: str) -> str:
        """获取 Agent 进度"""
        agent = self._agents.get(agent_id)
        if not agent:
            return "0/0"
        return agent.progress
    
    def build_chat_messages(self, agent_id: str,
                            task_hint: str) -> List[Dict]:
        """构建 LLM 聊天消息（AgentContext）"""
        agent = self._agents.get(agent_id)
        if not agent:
            return []
        
        messages = []
        
        # 1. System prompt
        system_prompt = f"""你是一个 AI 助手，角色 ID: {agent.role_id}
当前任务: {agent.task_name}
进度: {agent.progress}
当前步骤: {agent.current_step.description if agent.current_step else '无'}"""
        
        messages.append({"role": "system", "content": system_prompt})
        
        # 2. 任务提示
        if task_hint:
            messages.append({"role": "user", "content": task_hint})
        
        return messages
    
    def _generate_agent_id(self, role_id: str) -> str:
        """生成 Agent ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = uuid.uuid4().hex[:6]
        return f"{role_id}_{timestamp}_{random_suffix}"
    
    def _find_agent_by_task(self, task_id: str) -> Optional[Agent]:
        """通过任务 ID 查找 Agent"""
        for agent in self._agents.values():
            if agent.task_id == task_id:
                return agent
        return None
