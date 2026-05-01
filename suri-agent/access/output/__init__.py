"""
输出框架

关联文档: suri-agent/access/output/output.md

职责：统一管理所有角色的输出形式、输出目标、投递方式。

核心组件：
- output_types: OutputPayload, OutputType, OutputChannel 定义
- output_channel: 各通道的具体实现（终端/文件/Telegram/Webhook/记忆/日志）
- output_router: 根据角色和类型自动路由到对应通道

使用方式：
    from access.output import OutputRouter, OutputPayload
    
    router = OutputRouter(project_root, memory, security, logger)
    
    # 文本输出
    router.deliver_text("你好", role_id="suri")
    
    # 代码输出（自动路由到终端+文件+日志+记忆）
    router.deliver_code("def hello(): pass", language="python", role_id="suri-dev")
    
    # 报告输出
    router.deliver_report("# 审核报告\n...", title="代码审查报告", role_id="document-review")
    
    # 告警输出
    router.deliver_alert("系统异常", priority="urgent")
"""

from .output_types import OutputPayload, OutputType, OutputChannel
from .output_channel import (
    BaseChannel, TerminalChannel, FileChannel, MemoryChannel,
    LoggerChannel, TelegramChannel, WebhookChannel
)
from .output_router import OutputRouter

__all__ = [
    'OutputPayload', 'OutputType', 'OutputChannel',
    'BaseChannel', 'TerminalChannel', 'FileChannel', 'MemoryChannel',
    'LoggerChannel', 'TelegramChannel', 'WebhookChannel',
    'OutputRouter',
]
