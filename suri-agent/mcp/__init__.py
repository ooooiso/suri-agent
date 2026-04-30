"""
mcp

Model Context Protocol 服务层

存放不断加入的 MCP 调用服务，支持自增长。
每个服务是一个独立子目录，内含自己的配置和实现。

核心框架（受保护，不可外部编辑）：
- mcp/base.py        MCP 服务基类
- mcp/registry.py    MCP 注册中心

具体服务（可自增长，可通过外部会话补充）：
- mcp/services/<service_name>/
"""

__version__ = "0.1.0"
