"""⚠️ DEPRECATED — 已迁移到 channels/cli/channel.py。

新架构：CLIChannelPlugin 作为独立通道插件，注册到 SessionHub。
支持：
- PromptManager 提示符管理
- 三种交互范式（命令式/浏览式/对话式）
- 插件列表面板 + 编号查看详情
- 模型状态面板 + 厂商快速切换
- COMMAND_REGISTRY 命令路由
- Tab 命令补全
- 输入回显

请使用 channel.py 中的 CLIChannelPlugin 替代。
"""

from agent_framework.plugins.access.channels.cli.channel import CLIChannelPlugin

# 向后兼容：暴露 CLISession 别名
CLISession = CLIChannelPlugin

