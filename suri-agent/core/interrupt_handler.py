"""
中断处理器

关联文档: suri-agent/core/core.md

职责：
- 当角色上报无法完成时（缺少工具、知识不足等），暂停当前步骤
- 向用户说明情况，提供扩展建议
- 等待用户决策：继续/升级/取消
- 支持自动升级（如转交 dev 开发工具、hr 招聘角色）

V3.0 新增模块
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from core.task_state import TaskStateService, Agent
from core.message_bus import MessageBus


@dataclass
class InterruptResult:
    """中断处理结果"""
    handled: bool          # 是否已处理
    action: str            # 采取的行动：wait | escalate | cancel | auto_resolve
    suggestion: str        # 给用户的建议文本
    new_agent_id: Optional[str] = None  # 如需创建新 Agent
    reason: str = ""


class InterruptHandler:
    """
    中断处理器
    
    处理流程：
    1. 角色上报 blocked（通过 MessageBus 发送 request_help）
    2. suri 检测到 blocked 消息，调用 InterruptHandler
    3. InterruptHandler 分析原因，生成建议
    4. suri 向用户展示中断说明和建议
    5. 用户决策：继续/升级/取消
    6. 根据决策执行：
       - 继续：等待角色继续尝试
       - 升级：转交更高层级角色或创建新资源
       - 取消：标记任务取消
    """
    
    def __init__(self, task_state: TaskStateService, message_bus: MessageBus,
                 config=None):
        self.task_state = task_state
        self.message_bus = message_bus
        self.config = config
    
    def handle(self, agent_id: str, block_reason: str) -> InterruptResult:
        """
        处理中断
        
        Args:
            agent_id: 受阻的 Agent ID
            block_reason: 受阻原因
            
        Returns:
            中断处理结果
        """
        agent = self.task_state.get_agent(agent_id)
        if not agent:
            return InterruptResult(
                handled=False,
                action="cancel",
                suggestion="Agent 不存在，任务已取消。",
                reason="agent_not_found"
            )
        
        # 分析受阻原因类型
        reason_type = self._classify_reason(block_reason)
        
        if reason_type == "missing_tool":
            return self._handle_missing_tool(agent, block_reason)
        elif reason_type == "knowledge_gap":
            return self._handle_knowledge_gap(agent, block_reason)
        elif reason_type == "permission_denied":
            return self._handle_permission_denied(agent, block_reason)
        elif reason_type == "dependency_failed":
            return self._handle_dependency_failed(agent, block_reason)
        else:
            return self._handle_generic_block(agent, block_reason)
    
    def _classify_reason(self, reason: str) -> str:
        """分类受阻原因"""
        reason_lower = reason.lower()
        
        if any(kw in reason_lower for kw in ["缺少工具", "没有工具", "tool not found", "缺少接口"]):
            return "missing_tool"
        
        if any(kw in reason_lower for kw in ["知识不足", "不了解", "不熟悉", "知识库缺失", "knowledge gap"]):
            return "knowledge_gap"
        
        if any(kw in reason_lower for kw in ["权限不足", "无权", "被拒绝", "permission denied", "无权操作"]):
            return "permission_denied"
        
        if any(kw in reason_lower for kw in ["依赖失败", "前置任务", "上游失败", "dependency"]):
            return "dependency_failed"
        
        return "unknown"
    
    def _handle_missing_tool(self, agent: Agent, reason: str) -> InterruptResult:
        """处理缺少工具"""
        suggestion = f"""【任务受阻】{agent.task_name}

原因：{reason}

建议：
1. 让开发角色（suri_dev）开发所需工具
2. 或者取消当前任务，先提交工具开发需求

请选择：
- [继续] 等待开发角色开发工具后继续
- [升级] 将任务转交给开发角色处理
- [取消] 取消当前任务"""
        
        return InterruptResult(
            handled=True,
            action="wait",
            suggestion=suggestion,
            reason="missing_tool"
        )
    
    def _handle_knowledge_gap(self, agent: Agent, reason: str) -> InterruptResult:
        """处理知识不足"""
        suggestion = f"""【任务受阻】{agent.task_name}

原因：{reason}

建议：
1. 让 HR 角色（suri_hr）为当前角色注入相关知识
2. 或者让 suri 直接回答（如果问题较简单）

请选择：
- [继续] 等待知识注入后继续
- [升级] 将任务转交给 suri 直接处理
- [取消] 取消当前任务"""
        
        return InterruptResult(
            handled=True,
            action="wait",
            suggestion=suggestion,
            reason="knowledge_gap"
        )
    
    def _handle_permission_denied(self, agent: Agent, reason: str) -> InterruptResult:
        """处理权限不足"""
        suggestion = f"""【任务受阻】{agent.task_name}

原因：{reason}

建议：
1. 由 suri 向用户申请临时权限
2. 或者让 HR 角色调整角色权限配置

请选择：
- [继续] 申请权限后继续
- [升级] 将任务转交给有权限的角色
- [取消] 取消当前任务"""
        
        return InterruptResult(
            handled=True,
            action="wait",
            suggestion=suggestion,
            reason="permission_denied"
        )
    
    def _handle_dependency_failed(self, agent: Agent, reason: str) -> InterruptResult:
        """处理依赖失败"""
        suggestion = f"""【任务受阻】{agent.task_name}

原因：{reason}

建议：
1. 检查前置任务状态，等待修复
2. 或者 suri 重新调度前置任务

请选择：
- [继续] 等待依赖修复后继续
- [升级] 让 suri 重新调度依赖任务
- [取消] 取消当前任务"""
        
        return InterruptResult(
            handled=True,
            action="wait",
            suggestion=suggestion,
            reason="dependency_failed"
        )
    
    def _handle_generic_block(self, agent: Agent, reason: str) -> InterruptResult:
        """处理通用受阻"""
        suggestion = f"""【任务受阻】{agent.task_name}

原因：{reason}

建议：
1. 让 suri 分析问题并提供替代方案
2. 或者将任务分解为更小的子任务

请选择：
- [继续] 等待 suri 提供替代方案
- [升级] 将任务转交给 suri 重新规划
- [取消] 取消当前任务"""
        
        return InterruptResult(
            handled=True,
            action="wait",
            suggestion=suggestion,
            reason="unknown"
        )
    
    def escalate_to_dev(self, agent_id: str, tool_requirement: str) -> str:
        """
        将工具开发需求转交给 dev
        
        Returns:
            新创建的 Agent ID（dev 的开发任务）
        """
        from core.agent_registry import AgentRegistry
        
        agent = self.task_state.get_agent(agent_id)
        if not agent:
            return ""
        
        # 通过 MessageBus 通知 dev
        self.message_bus.publish(
            sender="suri",
            receiver="suri_dev",
            msg_type="escalation",
            content=f"任务 {agent.task_name} 需要新工具：{tool_requirement}",
            task_id=agent.task_id,
            agent_id=agent_id,
        )
        
        # 创建 dev 的 Agent（工具开发子任务）
        # 简化：返回空字符串，实际由 suri 后续处理
        return ""
    
    def escalate_to_hr(self, agent_id: str, role_requirement: str) -> str:
        """
        将角色创建需求转交给 hr
        
        Returns:
            新创建的 Agent ID（hr 的角色创建任务）
        """
        agent = self.task_state.get_agent(agent_id)
        if not agent:
            return ""
        
        self.message_bus.publish(
            sender="suri",
            receiver="suri_hr",
            msg_type="escalation",
            content=f"任务 {agent.task_name} 需要新角色/能力：{role_requirement}",
            task_id=agent.task_id,
            agent_id=agent_id,
        )
        
        return ""
    
    def cancel_task(self, agent_id: str, reason: str = "") -> bool:
        """取消任务"""
        agent = self.task_state.get_agent(agent_id)
        if agent:
            agent.status = "cancelled"
            self.task_state._save_agent(agent)
            
            # 广播取消通知
            self.message_bus.broadcast_status(
                sender="suri",
                content=f"任务 {agent.task_name} 已取消。原因：{reason}",
                task_id=agent.task_id,
                agent_id=agent_id,
            )
            return True
        return False
