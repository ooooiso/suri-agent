"""
Telegram Bot 命令处理器

职责：
- 处理 /start, /bind_group, /create_role 等命令
- 将命令转换为内部操作

关联文档: development-plan/2.TELEGRAM_INTEGRATION_SPEC.md
"""

from typing import Dict, Any, Callable, Optional


class CommandHandler:
    """Telegram 命令处理器"""
    
    def __init__(self, config_service, projection_service, task_service):
        self.config = config_service
        self.projection = projection_service
        self.task = task_service
        self._commands: Dict[str, Callable] = {
            '/start': self._cmd_start,
            '/bind_group': self._cmd_bind_group,
            '/create_role': self._cmd_create_role,
            '/help': self._cmd_help,
            '/status': self._cmd_status,
        }
    
    async def handle(self, command_text: str, user_id: str, chat_id: str, 
                     is_group: bool = False) -> str:
        """
        处理命令
        
        Args:
            command_text: 完整的命令文本（如 "/bind_group design"）
            user_id: Telegram 用户 ID
            chat_id: 聊天 ID
            is_group: 是否为群组消息
        
        Returns:
            回复文本
        """
        parts = command_text.strip().split()
        cmd = parts[0].lower() if parts else ''
        args = parts[1:] if len(parts) > 1 else []
        
        handler = self._commands.get(cmd)
        if handler:
            return await handler(user_id, chat_id, args, is_group)
        
        return f"未知命令: {cmd}\n使用 /help 查看可用命令。"
    
    async def _cmd_start(self, user_id: str, chat_id: str, args: list, 
                         is_group: bool) -> str:
        """/start 命令"""
        return (
            "👋 你好！我是 Suri Agent。\n\n"
            "我可以帮你：\n"
            "• 分配任务给不同部门\n"
            "• 创建新的角色/部门\n"
            "• 协调跨部门协作\n\n"
            "直接发送消息即可开始任务，或使用 /help 查看命令。"
        )
    
    async def _cmd_bind_group(self, user_id: str, chat_id: str, args: list,
                              is_group: bool) -> str:
        """
        /bind_group <department_id>
        
        将当前 Telegram 群组绑定到指定部门。
        只有群组管理员可以执行。
        """
        if not is_group:
            return "❌ /bind_group 只能在群组中使用。"
        
        if not args:
            return (
                "用法: /bind_group <部门ID>\n"
                "示例: /bind_group design\n\n"
                "可用部门: central, design, engineering, ops, resource, hr"
            )
        
        dept_id = args[0].lower()
        
        # 验证部门是否存在
        dept_ids = self.config.list_departments()
        if dept_id not in dept_ids:
            return f"❌ 部门 '{dept_id}' 不存在。可用部门: {', '.join(dept_ids)}"
        
        # 绑定群组
        if self.projection:
            self.projection.bind_group(dept_id, chat_id)
        
        return (
            f"✅ 已将本群绑定到 **{dept_id}** 部门。\n"
            f"该部门的内部通信将投影到此群。"
        )
    
    async def _cmd_create_role(self, user_id: str, chat_id: str, args: list,
                               is_group: bool) -> str:
        """
        /create_role <role_id> [部门]
        
        触发 suri-hr 创建角色流程。
        """
        if not args:
            return (
                "用法: /create_role <角色ID> [部门]\n"
                "示例: /create_role designer design\n\n"
                "将触发 suri-hr 创建角色流程。"
            )
        
        role_id = args[0]
        dept = args[1] if len(args) > 1 else 'central'
        
        # 创建任务给 suri-hr
        # TODO: 实际调用 TaskService 创建任务
        return (
            f"📝 已收到创建角色请求：\n"
            f"角色 ID: {role_id}\n"
            f"所属部门: {dept}\n\n"
            f"suri-hr 将处理此请求。请确保已配置角色 Soul 和技能。"
        )
    
    async def _cmd_help(self, user_id: str, chat_id: str, args: list,
                        is_group: bool) -> str:
        """/help 命令"""
        return (
            "📖 可用命令：\n\n"
            "/start - 开始使用\n"
            "/help - 显示此帮助\n"
            "/status - 查看系统状态\n"
            "/bind_group <部门ID> - 绑定群到部门（仅群组）\n"
            "/create_role <角色ID> [部门] - 创建新角色\n\n"
            "💡 直接发送消息即可发起任务。"
        )
    
    async def _cmd_status(self, user_id: str, chat_id: str, args: list,
                          is_group: bool) -> str:
        """/status 命令"""
        roles = self.config.list_roles()
        groups = self.projection.get_bound_groups() if self.projection else {}
        
        lines = [
            "📊 Suri 状态",
            f"已加载角色: {len(roles)} 个",
            f"已绑定群组: {len(groups)} 个",
        ]
        if groups:
            lines.append("绑定详情:")
            for dept, gid in groups.items():
                lines.append(f"  • {dept} → {gid}")
        
        return "\n".join(lines)
