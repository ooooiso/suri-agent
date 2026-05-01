"""
上下文服务

关联文档: suri-agent/core/core.md

职责：
- 为每次角色调用组装完整的系统提示（System Prompt）
- 注入 Soul、关键规则摘要、个人文件权限地图、相关记忆
- 保证即使上下文丢失，核心约束仍在

原则：只读取外部配置，不内嵌业务逻辑。
"""

from typing import Dict, Any, Optional
from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService


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
        self._rule_summary_cache: Optional[str] = None
        self._rule_cache_mtime: float = 0.0
    
    def build_context(
        self,
        role_id: str,
        current_task: Optional[Dict[str, Any]] = None,
        include_memories: bool = True,
        model_info: Optional[Dict[str, str]] = None,
        session_id: str = ""
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
        
        # 4. 学习经验
        learning_insights = self._get_learning_insights(role_id, current_task)
        if learning_insights:
            parts.append(f"## 你的经验总结\n\n{learning_insights}")
        
        # 5. 全局组织记忆（仅 suri 角色注入，辅助调度决策）
        if role_id == 'suri':
            org_memory = self._get_org_memory()
            if org_memory:
                parts.append(f"## 组织共享记忆\n\n{org_memory}")
        
        # 6. 历史记忆（按会话隔离，多用户场景下避免消息混淆）
        if include_memories:
            memories = self._get_relevant_memories(role_id, current_task, session_id=session_id)
            if memories:
                parts.append(f"## 相关记忆\n\n{memories}")
        
        # 7. 可用工具列表
        available_tools = self._get_available_tools(role_id)
        if available_tools:
            parts.append(f"## 你可用的工具\n\n{available_tools}")
        
        # 8. 平台状态（当前模型信息，所有角色共享）
        if model_info:
            model_name = model_info.get('name', '未知')
            model_id = model_info.get('model_id', '未知')
            provider = model_info.get('provider', '未知')
            parts.append(
                f"## 当前平台状态\n\n"
                f"当前使用的模型: {model_name} ({model_id})\n"
                f"提供商: {provider}\n"
                f"说明: 你正在使用此模型处理当前任务。"
            )
        
        # 6. 当前任务
        if current_task:
            task_desc = self._format_task(current_task)
            parts.append(f"## 当前任务\n\n{task_desc}")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_rule_summary(self) -> str:
        """提取关键规则的摘要（注入到角色提示中）
        
        自动扫描 rules/ 目录下的规则文件，提取模块 docstring 作为规则描述。
        结果缓存，避免每次调用都扫描文件系统。
        """
        import re
        from pathlib import Path
        
        rules_dir = Path(__file__).parent.parent / 'rules'
        
        # 检查缓存是否有效（基于目录最新修改时间）
        if self._rule_summary_cache and rules_dir.exists():
            current_mtime = max(
                (f.stat().st_mtime for f in rules_dir.glob('*.py') if f.is_file()),
                default=0
            )
            if current_mtime <= self._rule_cache_mtime:
                return self._rule_summary_cache
        
        summaries = []
        if rules_dir.exists():
            for py_file in sorted(rules_dir.glob('*.py')):
                if py_file.name in ('base.py', '__init__.py'):
                    continue
                try:
                    content = py_file.read_text(encoding='utf-8')
                    doc_match = re.search(r'^"""(.*?)"""', content, re.DOTALL)
                    if doc_match:
                        lines = doc_match.group(1).strip().split('\n')
                        desc = lines[0].strip()
                        if desc:
                            summaries.append(f"- **{py_file.stem}**: {desc}")
                except Exception:
                    continue
        
        if summaries:
            result = "核心规则摘要（自动生成）：\n" + "\n".join(summaries)
        else:
            result = (
                "1. **调度规则**：任务由 suri 统一接收下发，禁止直接对接用户需求。\n"
                "2. **通信规则**：跨部门协作必须总监对总监，私聊需抄送调度群。\n"
                "3. **安全规则**：文件修改需审批令牌，超范围操作被实时阻断。"
            )
        
        # 更新缓存
        self._rule_summary_cache = result
        if rules_dir.exists():
            self._rule_cache_mtime = max(
                (f.stat().st_mtime for f in rules_dir.glob('*.py') if f.is_file()),
                default=0
            )
        return result
    
    def _get_files_map(self, role_id: str) -> str:
        """读取角色的 files_i_use.md"""
        try:
            soul = self.config.get_role_soul(role_id)
            dept = soul.meta.get('department', 'central') if soul else 'central'
            entry = self.config.get_file(f'group/{dept}/{role_id}/reference/files_i_use.md')
            if entry:
                return entry.body[:2000]  # 限制长度，避免提示过长
        except Exception:
            pass
        return ""
    
    def _get_relevant_memories(self, role_id: str, task: Optional[Dict[str, Any]],
                                session_id: str = "") -> str:
        """
        获取与当前任务相关的记忆
        
        多用户隔离：如果提供了 session_id，优先按会话过滤消息，
        避免不同用户的消息混在一起。
        """
        memories = []
        
        # 读取角色私人记忆文件列表（全局共享的长期记忆）
        mem_files = self.memory.list_role_memories(role_id)
        for mem_path in mem_files[:5]:  # 最近 5 条（已按时间倒序）
            try:
                content = self.memory.read_role_memory(role_id, mem_path)
                memories.append(f"- [{mem_path}]\n{content[:500]}")
            except Exception:
                continue
        
        # 读取历史消息（按会话隔离）
        if session_id:
            # 多用户场景：按 session_id 过滤，只取当前用户的消息
            messages = self.memory.get_session_messages(role_id, session_id, limit=10)
            for msg in messages:
                body = msg.get('body', {})
                mem = f"- {msg['sender_role']} → {msg['receiver_role']}: {body.get('content', '')[:200]}"
                memories.append(mem)
        elif task:
            # 单用户/终端场景：回退到按 task_id 过滤
            task_id = task.get('task_id')
            if task_id:
                messages = self.memory.get_task_messages(role_id, task_id)
                for msg in messages[-10:]:
                    body = msg.get('body', {})
                    mem = f"- {msg['sender_role']} → {msg['receiver_role']}: {body.get('content', '')[:200]}"
                    memories.append(mem)
        
        return "\n".join(memories) if memories else ""
    
    def _get_learning_insights(self, role_id: str, 
                               task: Optional[Dict[str, Any]]) -> str:
        """
        获取角色的学习经验，注入上下文
        
        调用 MemoryService 的筛选逻辑
        """
        task_hint = task.get('requirement', '') if task else ''
        return self.memory.get_recent_insights_for_context(
            role_id, 
            task_hint=task_hint,
            limit=5,
            max_chars=2000
        )
    
    def _get_available_tools(self, role_id: str) -> str:
        """
        获取角色可用的工具列表
        
        权限推导策略（与 tool_executor.py _can_use 保持一致）：
        1. 从 tool_registry.json 读取所有工具及其权限级别
        2. public → 所有角色自动可用
        3. maintainer → maintainer 类型角色自动可用
        4. 特定 role_id → 仅该角色可用
        5. 角色 Soul 中的 tools 字段 → 显式额外授权
        """
        import json
        from pathlib import Path
        
        soul = self.config.get_role_soul(role_id)
        if not soul:
            return ""
        
        # 从 tool_registry.json 读取工具列表（业务配置，非文档）
        registry_path = Path(__file__).parent.parent / 'tools' / 'tool_registry.json'
        available_tools = []
        
        if registry_path.exists():
            try:
                data = json.loads(registry_path.read_text(encoding='utf-8'))
                for tool in data.get('tools', []):
                    tool_id = tool.get('tool_id', '')
                    desc = tool.get('description', '')
                    permission = tool.get('permission', '')
                    
                    # 判断该角色是否有权限
                    has_access = False
                    if permission == 'public':
                        has_access = True
                    elif permission == 'maintainer' and soul.meta.get('type') == 'maintainer':
                        has_access = True
                    elif permission == role_id:
                        has_access = True
                    
                    # Soul 显式授权覆盖
                    soul_tools = soul.meta.get('tools', [])
                    if tool_id in soul_tools:
                        has_access = True
                    
                    if has_access:
                        available_tools.append((tool_id, desc))
            except Exception:
                pass
        
        if not available_tools:
            return (
                "你当前没有分配任何工具。\n"
                "如需工具支持，请向平台管理员申请。"
            )
        
        lines = []
        for tool_id, desc in available_tools:
            lines.append(f"- `{tool_id}`: {desc}")
        
        lines.append("\n如需使用工具，请在回复中明确说明要调用哪个工具及参数。")
        lines.append("如果你需要的工具不在列表中，请说明需求，由相关技术角色评估实现。")
        return "\n".join(lines)
    
    def _get_org_memory(self) -> str:
        """
        获取组织级共享记忆（所有角色的经验汇总）
        
        供 suri 做调度决策时参考，了解各角色的能力边界和历史经验。
        """
        try:
            roles = self.config.list_roles()
            if not roles:
                return ""
            
            parts = []
            for rid in roles:
                if rid == 'suri':
                    continue
                insights = self.memory.get_recent_insights_for_context(rid, limit=3, max_chars=500)
                if insights:
                    parts.append(f"**{rid}** 的最新经验:\n{insights}")
            
            return "\n\n".join(parts) if parts else ""
        except Exception:
            return ""
    
    def _format_task(self, task: Dict[str, Any]) -> str:
        """格式化任务描述"""
        lines = [
            f"任务 ID: {task.get('task_id', 'N/A')}",
            f"需求: {task.get('requirement', 'N/A')}",
            f"截止时间: {task.get('deadline', '未设定')}",
            f"优先级: {task.get('priority', 'normal')}",
        ]
        return "\n".join(lines)
