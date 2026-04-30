"""
模型管理模块

职责：
- 管理模型配置（添加、删除、列出、选择）
- 调用外部模型 API 生成回复
- 首次启动时引导用户配置模型和 API Key
"""

from model.manager import ModelManager, ModelConfig

__all__ = ["ModelManager", "ModelConfig"]
