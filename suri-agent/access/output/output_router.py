"""
输出路由器

关联文档: suri-agent/access/output/output.md

职责：
- 根据 (角色, 输出类型, 优先级) 自动选择输出通道
- 支持角色自定义路由规则
- 支持通道链式投递（一次输出可路由到多个通道）

路由策略：
┌─────────────┬─────────────────────────────────────────────┐
│ 角色        │ 默认路由通道                                 │
├─────────────┼─────────────────────────────────────────────┤
│ suri        │ terminal + logger + memory                  │
│ suri-dev    │ terminal + file + logger + memory           │
│ suri-hr     │ terminal + file + logger + memory           │
│ document-review │ terminal + file + logger + memory       │
│ (future)    │ terminal + telegram + file + logger         │
└─────────────┴─────────────────────────────────────────────┘
"""

from typing import Dict, List, Any, Optional
from pathlib import Path

from .output_types import OutputPayload, OutputType, OutputChannel
from .output_channel import (
    BaseChannel, TerminalChannel, FileChannel, MemoryChannel,
    LoggerChannel, TelegramChannel, WebhookChannel
)


class OutputRouter:
    """
    输出路由器
    
    核心方法：
    - register_channel(): 注册通道实例
    - route(): 根据负载自动选择通道
    - deliver(): 执行投递（单通道或多通道）
    """
    
    # 最小回退路由：仅保留 suri 作为默认回退
    # 其他角色路由应由调用方通过 role_routes 传入（从 Soul 文件动态生成）
    DEFAULT_ROUTES: Dict[str, List[OutputChannel]] = {
        'suri': [OutputChannel.TERMINAL, OutputChannel.LOGGER, OutputChannel.MEMORY],
    }
    
    # 角色类型 → 路由模板（新增角色自动匹配，无需改代码）
    # key 为 capability 关键字，value 为对应路由模板
    _ROUTE_TEMPLATES: Dict[str, List[OutputChannel]] = {
        'terminal': [OutputChannel.TERMINAL, OutputChannel.LOGGER, OutputChannel.MEMORY],
        'file': [OutputChannel.TERMINAL, OutputChannel.FILE, OutputChannel.LOGGER, OutputChannel.MEMORY],
        'telegram': [OutputChannel.TERMINAL, OutputChannel.FILE, OutputChannel.TELEGRAM, OutputChannel.LOGGER],
    }
    
    # 输出类型 → 强制通道（覆盖角色默认）
    TYPE_OVERRIDES: Dict[OutputType, List[OutputChannel]] = {
        OutputType.ALERT: [OutputChannel.TERMINAL, OutputChannel.LOGGER],
        OutputType.STATUS: [OutputChannel.LOGGER],
    }
    
    # 优先级 → 额外通道
    PRIORITY_BOOST: Dict[str, List[OutputChannel]] = {
        'urgent': [OutputChannel.TELEGRAM, OutputChannel.WEBHOOK],
        'high': [OutputChannel.TELEGRAM],
    }
    
    def __init__(self, project_root: Path, memory=None, security=None, logger=None,
                 role_routes: Optional[Dict[str, List[OutputChannel]]] = None,
                 config=None):
        self.project_root = project_root
        self._channels: Dict[OutputChannel, BaseChannel] = {}
        # 优先使用传入的角色路由（动态生成），否则使用硬编码回退
        self._role_routes: Dict[str, List[OutputChannel]] = dict(role_routes or self.DEFAULT_ROUTES)
        
        # 注册默认通道
        self.register_channel(OutputChannel.TERMINAL, TerminalChannel(config))
        self.register_channel(OutputChannel.FILE, FileChannel(project_root, security, logger, config))
        self.register_channel(OutputChannel.LOGGER, LoggerChannel(logger))
        
        if memory:
            self.register_channel(OutputChannel.MEMORY, MemoryChannel(memory))
        
        # 预留通道（未配置时不可用）
        self.register_channel(OutputChannel.TELEGRAM, TelegramChannel())
        self.register_channel(OutputChannel.WEBHOOK, WebhookChannel())
    
    def register_channel(self, channel_id: OutputChannel, channel: BaseChannel) -> None:
        """注册输出通道实例"""
        self._channels[channel_id] = channel
    
    def set_role_route(self, role_id: str, channels: List[OutputChannel]) -> None:
        """为指定角色设置自定义路由"""
        self._role_routes[role_id] = channels
    
    def route(self, payload: OutputPayload) -> List[OutputChannel]:
        """
        根据负载自动选择通道列表
        
        决策逻辑：
        1. 如果 payload 显式指定了 target_channels，优先使用
        2. 根据输出类型查找 TYPE_OVERRIDES
        3. 根据角色查找 DEFAULT_ROUTES
        4. 根据优先级添加 PRIORITY_BOOST
        5. 过滤掉 can_handle=False 的通道
        """
        channels: List[OutputChannel] = []
        
        # 1. 显式指定
        if payload.target_channels:
            channels = list(payload.target_channels)
        # 2. 类型覆盖
        elif payload.type in self.TYPE_OVERRIDES:
            channels = list(self.TYPE_OVERRIDES[payload.type])
        # 3. 角色默认
        else:
            channels = list(self._role_routes.get(payload.role_id, 
                            self.DEFAULT_ROUTES.get('suri', [])))
        
        # 4. 优先级提升
        if payload.priority in self.PRIORITY_BOOST:
            for ch in self.PRIORITY_BOOST[payload.priority]:
                if ch not in channels:
                    channels.append(ch)
        
        # 5. 过滤无法处理的通道
        result = []
        for ch in channels:
            channel = self._channels.get(ch)
            if channel and channel.can_handle(payload):
                result.append(ch)
        
        return result
    
    def deliver(self, payload: OutputPayload) -> List[Dict[str, Any]]:
        """
        投递输出到所有选定的通道
        
        Returns:
            每个通道的投递结果列表
        """
        channels = self.route(payload)
        results = []
        
        for ch_id in channels:
            channel = self._channels.get(ch_id)
            if channel:
                result = channel.deliver(payload)
                result['channel_id'] = ch_id.value
                results.append(result)
        
        return results
    
    def deliver_text(self, content: str, role_id: str = "suri", **kwargs) -> List[Dict[str, Any]]:
        """快捷投递文本"""
        payload = OutputPayload.text(content, role_id=role_id, **kwargs)
        return self.deliver(payload)
    
    def deliver_code(self, content: str, language: str = "", role_id: str = "suri",
                     filename: str = "", **kwargs) -> List[Dict[str, Any]]:
        """快捷投递代码（同时输出到终端和文件）
        
        V2.0: 默认 role_id 改为 "suri"，调用方必须显式指定实际产出角色
        """
        payload = OutputPayload.code(content, language=language, role_id=role_id, 
                                     filename=filename, **kwargs)
        return self.deliver(payload)
    
    def deliver_file(self, filepath: str, content: str = "", role_id: str = "suri", 
                     **kwargs) -> List[Dict[str, Any]]:
        """快捷投递文件
        
        V2.0: 默认 role_id 改为 "suri"，调用方必须显式指定实际产出角色
        """
        payload = OutputPayload.file(filepath, content=content, role_id=role_id, **kwargs)
        return self.deliver(payload)
    
    def deliver_report(self, content: str, title: str = "", role_id: str = "suri", 
                       **kwargs) -> List[Dict[str, Any]]:
        """快捷投递报告
        
        V2.0: 默认 role_id 改为 "suri"，调用方必须显式指定实际产出角色
        """
        payload = OutputPayload.report(content, title=title, role_id=role_id, **kwargs)
        return self.deliver(payload)
    
    def deliver_alert(self, content: str, role_id: str = "suri", 
                      priority: str = "high", **kwargs) -> List[Dict[str, Any]]:
        """快捷投递告警"""
        payload = OutputPayload.alert(content, priority=priority, role_id=role_id, **kwargs)
        return self.deliver(payload)
