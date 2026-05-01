"""
输出类型定义

关联文档: suri-agent/access/output/output.md

定义所有支持的输出格式和元数据标准。
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class OutputType(str, Enum):
    """输出类型枚举"""
    TEXT = "text/plain"           # 纯文本
    MARKDOWN = "text/markdown"    # Markdown
    CODE = "code/block"           # 代码块（含语言标识）
    FILE = "file/path"            # 文件路径（已写入文件系统）
    IMAGE = "image/url"           # 图片 URL
    VIDEO = "video/url"           # 视频 URL
    AUDIO = "audio/url"           # 音频 URL
    REPORT = "report/json"        # 结构化报告
    ALERT = "alert/text"          # 告警通知
    STATUS = "status/text"        # 状态更新


class OutputChannel(str, Enum):
    """输出通道枚举"""
    TERMINAL = "terminal"         # 终端 stdout
    FILE = "file"                 # 文件系统
    TELEGRAM = "telegram"         # Telegram Bot
    WEBHOOK = "webhook"           # HTTP 回调
    MEMORY = "memory"             # 角色记忆数据库
    LOGGER = "logger"             # 日志系统


@dataclass
class OutputPayload:
    """
    输出负载：一次输出的完整数据包
    
    所有角色产生的输出，无论形式如何，都封装为 OutputPayload，
    由 OutputRouter 决定投递到哪些通道。
    """
    # 核心字段
    type: OutputType                    # 输出类型
    content: str                        # 主体内容（文本/URL/路径/JSON）
    
    # 元数据
    role_id: str = "suri"               # 产生输出的角色
    task_id: str = ""                   # 关联的任务ID
    user_id: str = ""                   # 目标用户ID
    session_id: str = ""                # 关联的会话ID
    
    # 格式增强
    title: str = ""                     # 标题（用于报告/文件）
    description: str = ""               # 描述/摘要
    language: str = ""                  # 代码语言（CODE类型时）
    filename: str = ""                  # 文件名（FILE类型时）
    mime_type: str = ""                 # MIME类型
    
    # 路由控制
    target_channels: List[OutputChannel] = field(default_factory=list)  # 显式指定通道
    priority: str = "normal"            # 优先级：low/normal/high/urgent
    
    # 扩展数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于日志、Webhook投递）"""
        return {
            "type": self.type.value,
            "content": self.content,
            "role_id": self.role_id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "title": self.title,
            "description": self.description,
            "language": self.language,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "target_channels": [c.value for c in self.target_channels],
            "priority": self.priority,
            "metadata": self.metadata,
        }
    
    @classmethod
    def text(cls, content: str, role_id: str = "suri", **kwargs) -> "OutputPayload":
        """快捷创建文本输出"""
        return cls(type=OutputType.TEXT, content=content, role_id=role_id, **kwargs)
    
    @classmethod
    def markdown(cls, content: str, role_id: str = "suri", **kwargs) -> "OutputPayload":
        """快捷创建 Markdown 输出"""
        return cls(type=OutputType.MARKDOWN, content=content, role_id=role_id, **kwargs)
    
    @classmethod
    def code(cls, content: str, language: str = "", role_id: str = "suri", **kwargs) -> "OutputPayload":
        """快捷创建代码输出"""
        return cls(type=OutputType.CODE, content=content, role_id=role_id, language=language, **kwargs)
    
    @classmethod
    def file(cls, filepath: str, content: str = "", role_id: str = "suri", **kwargs) -> "OutputPayload":
        """快捷创建文件输出"""
        file_content = content if content else filepath
        return cls(type=OutputType.FILE, content=file_content, role_id=role_id, filename=filepath, **kwargs)
    
    @classmethod
    def report(cls, content: str, title: str = "", role_id: str = "suri", **kwargs) -> "OutputPayload":
        """快捷创建报告输出"""
        return cls(type=OutputType.REPORT, content=content, role_id=role_id, title=title, **kwargs)
    
    @classmethod
    def alert(cls, content: str, priority: str = "high", role_id: str = "suri", **kwargs) -> "OutputPayload":
        """快捷创建告警输出"""
        return cls(type=OutputType.ALERT, content=content, role_id=role_id, priority=priority, **kwargs)
    
    @classmethod
    def image(cls, url: str, description: str = "", role_id: str = "suri", **kwargs) -> "OutputPayload":
        """快捷创建图片输出"""
        return cls(type=OutputType.IMAGE, content=url, role_id=role_id, description=description, **kwargs)
    
    @classmethod
    def video(cls, url: str, description: str = "", role_id: str = "suri", **kwargs) -> "OutputPayload":
        """快捷创建视频输出"""
        return cls(type=OutputType.VIDEO, content=url, role_id=role_id, description=description, **kwargs)
