"""
输出通道实现

关联文档: suri-agent/access/output/output.md

提供各类输出通道的具体实现：
- TerminalChannel: 终端彩色文本输出
- FileChannel: 文件系统写入（带安全校验）
- TelegramChannel: Telegram Bot API（预留接口）
- WebhookChannel: HTTP POST 回调（预留接口）
- MemoryChannel: 角色记忆数据库存储
- LoggerChannel: 日志系统记录
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .output_types import OutputPayload, OutputType, OutputChannel


class BaseChannel(ABC):
    """输出通道抽象基类"""
    
    channel_id: OutputChannel = OutputChannel.TERMINAL
    
    @abstractmethod
    def deliver(self, payload: OutputPayload) -> Dict[str, Any]:
        """
        投递输出负载
        
        Returns:
            {'success': bool, 'channel': str, 'detail': str}
        """
        pass
    
    def can_handle(self, payload: OutputPayload) -> bool:
        """判断该通道是否能处理此类型的输出"""
        return True


class TerminalChannel(BaseChannel):
    """
    终端输出通道
    
    支持彩色文本、代码高亮、Markdown 渲染（简化）
    所有输出都经过终端，用于调试和用户直接交互。
    新增角色自动获得基于哈希的确定性颜色，无需修改代码。
    V2.0: 支持显示角色昵称而非内部标识。
    """
    
    channel_id = OutputChannel.TERMINAL
    
    # 特殊颜色（非角色）
    COLORS = {
        'alert': '\033[91m',      # 红色
        'reset': '\033[0m',
        'dim': '\033[90m',
        'bold': '\033[1m',
    }
    
    # 已知角色颜色覆盖（新旧名称都注册，确保 alias 兼容）
    ROLE_COLORS = {
        'suri': '\033[96m',           # 青色
        'suri_dev': '\033[92m',       # 绿色
        'suri-dev': '\033[92m',       # 兼容旧名
        'suri_hr': '\033[93m',        # 黄色
        'suri-hr': '\033[93m',        # 兼容旧名
        'suri_review': '\033[95m',    # 紫色
        'document-review': '\033[95m', # 兼容旧名
        'suri_stats': '\033[94m',     # 蓝色
        'analyst': '\033[94m',        # 兼容旧名
    }
    
    def __init__(self, config=None):
        self.config = config  # ConfigService，用于昵称查询
    
    def _get_role_color(self, role_id: str) -> str:
        """获取角色颜色（未知角色使用哈希确定性分配）"""
        if role_id in self.ROLE_COLORS:
            return self.ROLE_COLORS[role_id]
        # 为未知角色生成确定性颜色
        palette = ['\033[94m', '\033[95m', '\033[96m', '\033[92m', '\033[93m']
        idx = hash(role_id) % len(palette)
        return palette[idx]
    
    def _get_display_name(self, role_id: str) -> str:
        """获取角色的显示名称（优先使用昵称）"""
        if self.config:
            return self.config.get_role_nickname(role_id)
        return role_id
    
    def deliver(self, payload: OutputPayload) -> Dict[str, Any]:
        try:
            formatted = self._format(payload)
            print(formatted)
            return {'success': True, 'channel': 'terminal', 'detail': '已输出到终端'}
        except Exception as e:
            return {'success': False, 'channel': 'terminal', 'detail': str(e)}
    
    def _format(self, payload: OutputPayload) -> str:
        """根据类型格式化输出"""
        role = payload.role_id
        display_name = self._get_display_name(role)
        color = self._get_role_color(role)
        reset = self.COLORS['reset']
        dim = self.COLORS['dim']
        
        # 构建头部（显示昵称，hover/debug 保留 role_id）
        header = f"[{color}{display_name}{reset}]"
        if payload.title:
            header += f" {self.COLORS['bold']}{payload.title}{reset}"
        
        # 根据类型渲染内容
        if payload.type == OutputType.CODE:
            lang = payload.language or 'text'
            body = f"\n```{lang}\n{payload.content}\n```\n"
        elif payload.type == OutputType.MARKDOWN:
            body = f"\n{payload.content}\n"
        elif payload.type == OutputType.FILE:
            body = f"\n📄 文件已保存: {payload.content}\n"
        elif payload.type == OutputType.IMAGE:
            body = f"\n🖼️  图片: {payload.content}\n"
        elif payload.type == OutputType.VIDEO:
            body = f"\n🎬 视频: {payload.content}\n"
        elif payload.type == OutputType.ALERT:
            alert_color = self.COLORS['alert']
            body = f"\n{alert_color}⚠️ {payload.content}{reset}\n"
        elif payload.type == OutputType.REPORT:
            body = f"\n📊 {payload.title or '报告'}\n{payload.content[:500]}\n"
        else:
            body = f"\n{payload.content}\n"
        
        # 添加描述（如有）
        footer = ""
        if payload.description:
            footer = f"{dim}  {payload.description}{reset}\n"
        
        return f"{header}{body}{footer}"


class FileChannel(BaseChannel):
    """
    文件输出通道
    
    将输出内容写入文件系统，支持：
    - 代码文件 → suri-agent/ 下对应目录
    - 配置文件 → group/ 下角色目录
    - 报告文件 → logs/ 或 reports/ 目录
    - 审计文件 → 带时间戳的审计目录
    
    所有写操作经过 SecurityService 权限校验。
    新增角色只需在 Soul frontmatter 中声明 output_path，无需修改代码。
    """
    
    channel_id = OutputChannel.FILE
    
    def __init__(self, project_root: Path, security=None, logger=None, config=None):
        self.project_root = project_root
        self.security = security
        self.logger = logger
        self.config = config  # ConfigService，用于动态读取角色 output_path
    
    def deliver(self, payload: OutputPayload) -> Dict[str, Any]:
        try:
            filepath = self._resolve_path(payload)
            if not filepath:
                return {'success': False, 'channel': 'file', 'detail': '无法解析文件路径'}
            
            # 安全校验
            if self.security:
                allowed, reason = self.security.check_permission(payload.role_id, str(filepath))
                if not allowed:
                    return {'success': False, 'channel': 'file', 'detail': f'权限拒绝: {reason}'}
            
            # 写入文件
            path = self.project_root / filepath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload.content, encoding='utf-8')
            
            rel_path = str(path.relative_to(self.project_root))
            # 记录文件创建统计
            if self.logger:
                self.logger.log_file_created(
                    role_id=payload.role_id,
                    filepath=rel_path,
                    file_type=payload.type.value,
                    size=len(payload.content.encode('utf-8'))
                )
            return {'success': True, 'channel': 'file', 'detail': rel_path}
        except Exception as e:
            return {'success': False, 'channel': 'file', 'detail': str(e)}
    
    def _resolve_path(self, payload: OutputPayload) -> Optional[Path]:
        """根据角色和类型解析文件保存路径
        
        动态解析优先级：
        1. 从 ConfigService 读取角色 Soul 中的 output_path
        2. 回退到通用规则（resources/temp/）
        """
        role = payload.role_id
        filename = payload.filename or payload.title or f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 确保文件名安全
        safe_name = "".join(c if c.isalnum() or c in '._-' else '_' for c in filename)
        if not safe_name.endswith(('.md', '.py', '.json', '.yaml', '.txt', '.csv')):
            # 根据类型推断扩展名
            ext_map = {
                OutputType.CODE: '.py',
                OutputType.MARKDOWN: '.md',
                OutputType.REPORT: '.md',
                OutputType.TEXT: '.txt',
            }
            safe_name += ext_map.get(payload.type, '.txt')
        
        # 动态解析：优先从 Soul 文件读取 output_path
        if self.config:
            output_path = self.config.get_role_output_path(role)
            if output_path:
                base = Path(output_path)
                # document-review 历史行为：文件名加日期前缀
                if role == 'document-review':
                    return base / f"{datetime.now().strftime('%Y%m%d')}_{safe_name}"
                return base / safe_name
        
        # 通用回退
        return Path('resources/temp') / safe_name


class MemoryChannel(BaseChannel):
    """
    记忆输出通道
    
    将输出存入角色的记忆数据库，支持上下文回溯。
    """
    
    channel_id = OutputChannel.MEMORY
    
    def __init__(self, memory_service):
        self.memory = memory_service
    
    def deliver(self, payload: OutputPayload) -> Dict[str, Any]:
        try:
            role_id = payload.role_id
            task_id = payload.task_id or f"task_output_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 保存为角色记忆
            self.memory.save_message(
                role_id,
                message_id=f"msg_output_{datetime.now().strftime('%Y%m%d%H%M%S')}_{role_id}",
                task_id=task_id,
                sender=role_id,
                receiver='user',
                body={
                    'type': 'output',
                    'output_type': payload.type.value,
                    'content': payload.content,
                    'title': payload.title,
                    'description': payload.description,
                }
            )
            return {'success': True, 'channel': 'memory', 'detail': f'已存入 {role_id} 的记忆'}
        except Exception as e:
            return {'success': False, 'channel': 'memory', 'detail': str(e)}


class LoggerChannel(BaseChannel):
    """
    日志输出通道
    
    所有输出都会记录到日志系统，用于审计和调试。
    """
    
    channel_id = OutputChannel.LOGGER
    
    def __init__(self, logger_service):
        self.logger = logger_service
    
    def deliver(self, payload: OutputPayload) -> Dict[str, Any]:
        try:
            if not self.logger:
                return {'success': False, 'channel': 'logger', 'detail': '日志服务未初始化'}
            
            preview = payload.content[:100] + "..." if len(payload.content) > 100 else payload.content
            self.logger.runtime(
                "信息", "输出投递",
                f"[{payload.role_id}] 类型={payload.type.value} 通道={payload.target_channels} 内容={preview}"
            )
            
            # 告警级别输出同时写入 error 日志
            if payload.type == OutputType.ALERT or payload.priority in ('high', 'urgent'):
                self.logger.error_log("警告", "输出投递", f"[{payload.role_id}] {payload.content[:200]}")
            
            return {'success': True, 'channel': 'logger', 'detail': '已记录日志'}
        except Exception as e:
            return {'success': False, 'channel': 'logger', 'detail': str(e)}


class TelegramChannel(BaseChannel):
    """
    Telegram 输出通道（预留接口）
    
    实际实现需要接入 Telegram Bot API，发送消息/图片/文件。
    当前为占位符，提供接口规范。
    """
    
    channel_id = OutputChannel.TELEGRAM
    
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._enabled = bool(bot_token and chat_id)
    
    def deliver(self, payload: OutputPayload) -> Dict[str, Any]:
        if not self._enabled:
            return {'success': False, 'channel': 'telegram', 'detail': 'Telegram Bot 未配置'}
        
        try:
            # TODO: 实际接入 Telegram Bot API
            # send_message / send_photo / send_document
            return {
                'success': True,
                'channel': 'telegram',
                'detail': f'[模拟] 已发送到 Telegram chat={self.chat_id}'
            }
        except Exception as e:
            return {'success': False, 'channel': 'telegram', 'detail': str(e)}
    
    def can_handle(self, payload: OutputPayload) -> bool:
        """Telegram 不支持直接发送视频流，但支持 URL"""
        if payload.type in (OutputType.VIDEO, OutputType.AUDIO):
            return payload.content.startswith(('http://', 'https://'))
        return True


class WebhookChannel(BaseChannel):
    """
    Webhook 输出通道（预留接口）
    
    通过 HTTP POST 将输出推送到外部系统。
    """
    
    channel_id = OutputChannel.WEBHOOK
    
    def __init__(self, endpoint: str = ""):
        self.endpoint = endpoint
        self._enabled = bool(endpoint)
    
    def deliver(self, payload: OutputPayload) -> Dict[str, Any]:
        if not self._enabled:
            return {'success': False, 'channel': 'webhook', 'detail': 'Webhook 未配置'}
        
        try:
            # TODO: 实际发送 HTTP POST
            import json
            data = payload.to_dict()
            # requests.post(self.endpoint, json=data, timeout=10)
            return {
                'success': True,
                'channel': 'webhook',
                'detail': f'[模拟] 已 POST 到 {self.endpoint}'
            }
        except Exception as e:
            return {'success': False, 'channel': 'webhook', 'detail': str(e)}
