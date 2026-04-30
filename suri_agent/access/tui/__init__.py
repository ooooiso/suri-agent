"""
ui_gateway

Suri 图形化终端界面（TUI）的 JSON-RPC 后端服务。

为前端提供：
- 角色/任务/审批的查询与操作
- 文件浏览与编辑（受安全钩子保护）
- 平台状态监控
- 配置热重载

协议：JSON-RPC 2.0 over HTTP
"""

__version__ = "0.1.0"
