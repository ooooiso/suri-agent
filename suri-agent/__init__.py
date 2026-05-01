"""
suri-agent

Suri 智能体平台主程序

职责：
- 提供基础运行能力（配置加载、模型调用、通信、文件操作、记忆管理）
- 读取外部配置（group/、skills/、tools/），不内嵌业务逻辑
- 通过 ContextService 为角色组装运行时上下文
- 通过 TaskService 执行调度、审批、异常处理等核心流程
- 通过 MCPService 动态扩展角色能力

设计原则：
- 主程序与外部内容完全分离
- 主程序只提供基础调用能力
- 所有业务规则、角色定义、工作流程由外部 Markdown+YAML 配置驱动
"""

__version__ = "0.1.0"
