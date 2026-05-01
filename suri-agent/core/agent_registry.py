"""
Agent 注册表

关联文档: suri-agent/core/core.md

职责：
- 创建/销毁/查询 Agent
- 维护 user_id → List[Agent] 映射
- 管理 Agent 的独立对话上下文（messages）
- 支持子 Agent（并行子任务）

V3.0 新增模块
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from core.task_state import TaskStateService, Agent, TaskStep


class AgentContext:
    """
    Agent 独立对话上下文
    
    每个 Agent 拥有独立的 messages 列表，与 suri 的主上下文隔离。
    这确保了多 Agent 并行时消息不串扰。
    """
    
    def __init__(self, agent_id: str, task_state: TaskStateService):
        self.agent_id = agent_id
        self.task_state = task_state
        self._messages: List[Dict[str, str]] = []
    
    def add_message(self, role: str, content: str) -> None:
        """添加消息到 Agent 上下文"""
        self._messages.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        self._persist_messages()
    
    def get_messages(self, limit: int = 50) -> List[Dict[str, str]]:
        """获取最近的 messages"""
        return self._messages[-limit:]
    
    def get_system_prompt(self, role_id: str, config) -> str:
        """获取 Agent 的系统提示（注入任务分解方法论）"""
        soul = config.get_role_soul(role_id) if config else None
        base_prompt = soul.body[:2000] if soul else f"你是 {role_id}"
        
        # V3.0: 注入任务分解方法论
        methodology = """

## 任务分解方法论（V3.0）

你在执行任何任务时，必须遵循以下步骤：
1. **理解需求** → 用自己的能力描述复述任务目标，确认输入输出。
2. **识别依赖** → 列出需要其他角色提供的前置材料或工具。
3. **确定子任务** → 将任务分解为可独立执行的子任务，每个子任务有明确的完成标准。
4. **估算与排序** → 给每个子任务标出所需资源、预计耗时，并行可能的尽量标记。
5. **执行与更新** → 每完成一个子任务，更新状态并通知调度者。
6. **闭环检查** → 全部完成后自我审查是否符合原始需求。

执行过程中，如果遇到困难（缺少工具、知识不足等），必须立即向 suri 汇报并说明原因。
"""
        return base_prompt + methodology
    
    def build_chat_messages(self, role_id: str, config, task_hint: str = "") -> List[Dict[str, str]]:
        """构建完整的 chat messages（系统提示 + 历史消息 + 当前任务）"""
        messages = [
            {"role": "system", "content": self.get_system_prompt(role_id, config)},
        ]
        if task_hint:
            messages.append({"role": "system", "content": f"当前任务：{task_hint}"})
        messages.extend(self._messages)
        return messages
    
    def _persist_messages(self) -> None:
        """持久化消息到 Agent 的 DB 记录"""
        # 简化：只持久化最新的 20 条
        agent = self.task_state.get_agent(self.agent_id)
        if agent:
            # 通过 task_state 更新（简化实现）
            pass
    
    def clear(self) -> None:
        """清空上下文"""
        self._messages = []


class AgentRegistry:
    """
    Agent 注册表
    
    管理 Agent 的生命周期：
    - create: 创建新 Agent（主任务或子任务）
    - destroy: 销毁已完成/过期的 Agent
    - get: 查询 Agent
    - list_active: 列出用户的活跃 Agent
    """
    
    def __init__(self, project_root: Path, task_state: TaskStateService, config=None):
        self.project_root = project_root
        self.task_state = task_state
        self.config = config
        self._contexts: Dict[str, AgentContext] = {}  # agent_id -> AgentContext
    
    def create_agent(self, task_text: str, user_id: str, role_id: str = "",
                     parent_agent_id: Optional[str] = None,
                     steps: Optional[List[TaskStep]] = None,
                     task_id: str = "") -> Agent:
        """
        创建新 Agent
        
        Args:
            task_text: 用户原始需求
            user_id: 用户标识
            role_id: 执行角色（可选，创建时可能还未确定）
            parent_agent_id: 父 Agent ID（子任务时用到）
            steps: 预设步骤列表
            task_id: 任务 ID（可选，未提供则自动生成）
            
        Returns:
            新创建的 Agent
        """
        from infrastructure.config import ConfigService
        
        import random
        if not task_id:
            task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        agent = self.task_state.create_agent(
            task_id=task_id,
            task_name=task_text[:50],
            user_id=user_id,
            role_id=role_id,
            parent_agent_id=parent_agent_id,
            steps=steps,
        )
        
        # 创建独立上下文
        self._contexts[agent.agent_id] = AgentContext(agent.agent_id, self.task_state)
        
        return agent
    
    def create_sub_agent(self, parent_agent_id: str, subtask_description: str,
                         role_id: str, user_id: str) -> Agent:
        """
        创建子 Agent（用于并行子任务）
        
        Args:
            parent_agent_id: 父 Agent ID
            subtask_description: 子任务描述
            role_id: 执行子任务的角色
            user_id: 用户标识
            
        Returns:
            子 Agent
        """
        agent = self.create_agent(
            task_text=subtask_description,
            user_id=user_id,
            role_id=role_id,
            parent_agent_id=parent_agent_id,
            steps=[TaskStep(
                step_id="step_1",
                description=subtask_description,
                status="pending",
                assignee=role_id,
            )],
        )
        
        # 更新父 Agent 状态
        parent = self.task_state.get_agent(parent_agent_id)
        if parent:
            parent.status = "running"
            self.task_state._save_agent(parent)
        
        return agent
    
    def get_context(self, agent_id: str) -> Optional[AgentContext]:
        """获取 Agent 的上下文"""
        return self._contexts.get(agent_id)
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取 Agent"""
        return self.task_state.get_agent(agent_id)
    
    def list_user_agents(self, user_id: str) -> List[Agent]:
        """列出用户的所有活跃 Agent"""
        return self.task_state.get_active_agents(user_id)
    
    def update_step(self, agent_id: str, step_id: str, status: str,
                    block_reason: Optional[str] = None) -> bool:
        """
        更新 Agent 的步骤状态
        
        Returns:
            True 如果步骤顺利完成，False 如果步骤受阻
        """
        agent = self.task_state.get_agent(agent_id)
        if not agent:
            return False
        
        for step in agent.steps:
            if step.step_id == step_id:
                step.status = status
                if status == "in_progress":
                    step.started_at = datetime.now().isoformat()
                elif status in ("completed", "blocked"):
                    step.completed_at = datetime.now().isoformat()
                if block_reason:
                    step.block_reason = block_reason
                break
        
        # 检查是否全部完成
        if all(s.status == "completed" for s in agent.steps):
            agent.status = "completed"
        elif any(s.status == "blocked" for s in agent.steps):
            agent.status = "blocked"
        elif any(s.status == "in_progress" for s in agent.steps):
            agent.status = "running"
        
        self.task_state._save_agent(agent)
        return True
    
    def destroy_agent(self, agent_id: str) -> bool:
        """销毁 Agent（归档已完成任务）"""
        agent = self.task_state.get_agent(agent_id)
        if agent:
            agent.status = "archived"
            self.task_state._save_agent(agent)
            if agent_id in self._contexts:
                del self._contexts[agent_id]
            return True
        return False
    
    def cleanup_old_agents(self, user_id: str, max_age_hours: int = 24) -> int:
        """
        清理用户过期的 Agent
        
        Returns:
            清理的 Agent 数量
        """
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        
        agents = self.task_state.get_agents_by_user(user_id)
        cleaned = 0
        for agent in agents:
            if agent.status == "completed" and agent.updated_at < cutoff:
                self.destroy_agent(agent.agent_id)
                cleaned += 1
        
        return cleaned
    
    def get_user_overview(self, user_id: str) -> Dict[str, Any]:
        """获取用户的 Agent 概览"""
        agents = self.list_user_agents(user_id)
        return {
            "user_id": user_id,
            "active_count": len(agents),
            "agents": [a.to_dict() for a in agents],
        }
