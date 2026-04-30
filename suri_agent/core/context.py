"""
上下文服务

职责：
- 为每次角色调用组装完整的系统提示（System Prompt）
- 注入 Soul、关键规则摘要、个人文件权限地图、相关记忆
- 保证即使上下文丢失，核心约束仍在

原则：只读取外部配置，不内嵌业务逻辑。
"""

from typing import Dict, Any, List, Optional
from suri_agent.infrastructure.config import ConfigService
from suri_agent.infrastructure.memory import MemoryService


class ContextService:
    """
    角色上下文构建器
    
    每次调用角色前，组装以下内容为系统提示：
    1. 角色 Soul（profiles/<role>/<role>.md）
    2. 关键规则摘要（scheduling + communication + security）
    3. 个人文件权限地图（files_i_use.md）
    4. 相关历史记忆（从 state.db 和 memories/ 读取）
    5. 当前任务描述
    """
    
    def __init__(self, config: ConfigService, memory: MemoryService):
        self.config = config
        self.memory = memory
    
    def build_context(
        self,
        role_id: str,
        current_task: Optional[Dict[str, Any]] = None,
        include_memories: bool = True
    ) -> str:
        """
        构建角色的完整系统提示
        
        Args:
            role_id: 目标角色 ID
            current_task: 当前任务信息（可选）
            include_memories: 是否注入历史记忆
            
        Returns:
            组装好的系统提示文本
        """
        parts = []
        
        # 1. 角色 Soul
        soul = self.config.get_role_soul(role_id)
        if soul:
            parts.append(f"## 你的身份\n\n{soul.body}")
        else:
            parts.append(f"## 你的身份\n\n角色 ID: {role_id}")
        
        # 2. 关键规则摘要（防遗忘机制）
        rule_summary = self._get_rule_summary()
        parts.append(f"## 你必须遵守的规则\n\n{rule_summary}")
        
        # 3. 个人文件权限地图
        files_map = self._get_files_map(role_id)
        if files_map:
            parts.append(f"## 你的文件权限\n\n{files_map}")
        
        # 4. 历史记忆
        if include_memories:
            memories = self._get_relevant_memories(role_id, current_task)
            if memories:
                parts.append(f"## 相关记忆\n\n{memories}")
        
        # 5. 当前任务
        if current_task:
            task_desc = self._format_task(current_task)
            parts.append(f"## 当前任务\n\n{task_desc}")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_rule_summary(self) -> str:
        """提取关键规则的摘要（注入到角色提示中）"""
        rules = []
        
        scheduling = self.config.get_rule('scheduling')
        if scheduling:
            rules.append("1. **调度规则**：任务由 suri 统一接收下发，禁止直接对接用户需求。")
        
        comm = self.config.get_rule('communication_protocol')
        if comm:
            rules.append("2. **通信规则**：跨部门协作必须总监对总监，私聊需抄送调度群。")
        
        security = self.config.get_rule('security')
        if security:
            rules.append("3. **安全规则**：文件修改需审批令牌，超范围操作被实时阻断。")
        
        return "\n".join(rules) if rules else "（规则加载中）"
    
    def _get_files_map(self, role_id: str) -> str:
        """读取角色的 files_i_use.md"""
        try:
            entry = self.config.get_file(f'profiles/{role_id}/reference/files_i_use.md')
            if entry:
                return entry.body[:2000]  # 限制长度，避免提示过长
        except Exception:
            pass
        return ""
    
    def _get_relevant_memories(self, role_id: str, task: Optional[Dict[str, Any]]) -> str:
        """获取与当前任务相关的记忆"""
        memories = []
        
        # 读取角色私人记忆文件列表
        mem_files = self.memory.list_role_memories(role_id)
        for mem_path in mem_files[-5:]:  # 最近 5 条
            try:
                content = self.memory.read_role_memory(role_id, mem_path)
                memories.append(f"- [{mem_path}]\n{content[:500]}")
            except Exception:
                continue
        
        # 读取相关任务历史消息
        if task:
            task_id = task.get('task_id')
            if task_id:
                messages = self.memory.get_task_messages(task_id)
                for msg in messages[-10:]:  # 最近 10 条消息
                    body = msg.get('body', {})
                    mem = f"- {msg['sender_role']} → {msg['receiver_role']}: {body.get('content', '')[:200]}"
                    memories.append(mem)
        
        return "\n".join(memories) if memories else ""
    
    def _format_task(self, task: Dict[str, Any]) -> str:
        """格式化任务描述"""
        lines = [
            f"任务 ID: {task.get('task_id', 'N/A')}",
            f"需求: {task.get('requirement', 'N/A')}",
            f"截止时间: {task.get('deadline', '未设定')}",
            f"优先级: {task.get('priority', 'normal')}",
        ]
        return "\n".join(lines)
