"""
状态卡片渲染器

关联文档: suri-agent/core/core.md

职责：
- 从 TaskStateService 读取活跃 Agent
- 生成 ASCII/emoji 格式的任务状态看板
- 支持终端和 Telegram 两种输出格式

V3.0 新增模块
"""

from typing import List, Optional, Dict, Any
from core.task_state import TaskStateService, Agent


class StateCardRenderer:
    """
    状态卡片渲染器
    
    输出格式：
    ┌────────────────────────────────────────┐
    │ 📋 当前任务看板                          │
    │ 【任务A】优化登录模块                     │
    │   进度：步骤2/4 — 正在编写新认证逻辑      │
    │   状态：⏳ 进行中（开发角色执行中）        │
    └────────────────────────────────────────┘
    """
    
    STATUS_ICONS = {
        "pending": "⬜",
        "in_progress": "⏳",
        "completed": "✅",
        "blocked": "🚫",
    }
    
    AGENT_STATUS_ICONS = {
        "planning": "📝",
        "running": "🚀",
        "paused": "⏸️",
        "completed": "✅",
        "blocked": "🚫",
    }
    
    def __init__(self, task_state: TaskStateService):
        self.task_state = task_state
    
    def render(self, user_id: str, compact: bool = False) -> str:
        """
        渲染用户的任务状态看板
        
        Args:
            user_id: 用户标识
            compact: 为 True 时输出精简版（单行摘要）
            
        Returns:
            状态卡片文本
        """
        agents = self.task_state.get_active_agents(user_id)
        if not agents:
            return ""
        
        if compact:
            return self._render_compact(agents)
        return self._render_full(agents)
    
    def _render_full(self, agents: List[Agent]) -> str:
        """完整版状态卡片"""
        lines = []
        lines.append("─" * 44)
        lines.append("📋 当前任务看板")
        lines.append("")
        
        for agent in agents:
            icon = self.AGENT_STATUS_ICONS.get(agent.status, "📋")
            lines.append(f"{icon} 【{agent.task_name}】")
            lines.append(f"   进度：步骤{agent.progress}")
            
            current = agent.current_step
            if current:
                step_icon = self.STATUS_ICONS.get(current.status, "⬜")
                assignee = current.assignee or agent.role_id or "suri"
                lines.append(f"   当前：{step_icon} {current.description}（{assignee}）")
            
            # 显示受阻原因
            if agent.status == "blocked":
                blocked_steps = [s for s in agent.steps if s.status == "blocked" and s.block_reason]
                if blocked_steps:
                    lines.append(f"   ⚠️ 受阻：{blocked_steps[0].block_reason}")
            
            lines.append("")
        
        lines.append("─" * 44)
        return "\n".join(lines)
    
    def _render_compact(self, agents: List[Agent]) -> str:
        """精简版状态卡片（单行）"""
        if not agents:
            return ""
        parts = []
        for agent in agents:
            icon = self.AGENT_STATUS_ICONS.get(agent.status, "📋")
            parts.append(f"{icon} {agent.task_name}({agent.progress})")
        return " | ".join(parts)
    
    def render_single_task(self, agent: Agent) -> str:
        """
        渲染单个任务的步骤分解
        
        格式：
        正在为您处理"添加深色模式"。
        步骤分解：
        1. 分析现有样式文件 ✅
        2. 创建变量覆盖表 ⏳（开发角色进行中）
        3. 测试并交付 ⬜
        """
        lines = []
        lines.append(f'正在为您处理"{agent.task_name}"。')
        lines.append("步骤分解：")
        
        for i, step in enumerate(agent.steps, 1):
            icon = self.STATUS_ICONS.get(step.status, "⬜")
            assignee_info = f"（{step.assignee}）" if step.assignee else ""
            lines.append(f"{i}. {step.description} {icon}{assignee_info}")
        
        return "\n".join(lines)
    
    def render_telegram(self, user_id: str) -> str:
        """Telegram 格式的状态卡片（支持 Markdown）"""
        agents = self.task_state.get_active_agents(user_id)
        if not agents:
            return ""
        
        lines = []
        lines.append("*📋 当前任务看板*")
        lines.append("")
        
        for agent in agents:
            icon = self.AGENT_STATUS_ICONS.get(agent.status, "📋")
            lines.append(f"*{icon} {agent.task_name}*")
            lines.append(f"进度：步骤{agent.progress}")
            
            current = agent.current_step
            if current:
                step_icon = self.STATUS_ICONS.get(current.status, "⬜")
                lines.append(f"当前：{step_icon} {current.description}")
            
            if agent.status == "blocked":
                blocked = [s for s in agent.steps if s.status == "blocked" and s.block_reason]
                if blocked:
                    lines.append(f"⚠️ 受阻：_{blocked[0].block_reason}_")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def render_for_broadcast(self, agent: Agent, step: Any) -> str:
        """
        中台播报格式
        
        格式：【昵称】在【任务名】完成：子步骤描述
        """
        return f"【{agent.role_id}】在【{agent.task_name}】完成：{step.description}"
