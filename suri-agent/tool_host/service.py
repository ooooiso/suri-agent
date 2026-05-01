"""
Suri Tool Host — 工具运行时服务

职责：
1. 工具注册与动态加载
2. 工具执行（子进程隔离 / WASM 沙箱）
3. 参数校验与权限检查
4. MCP 框架宿主
5. 工具调用审计

包含模块：
- executor.py   → 工具执行器
- sandbox.py    → 沙箱环境
- registry.py   → 工具注册表
- mcp_host.py   → MCP 宿主

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class ToolHostService(SuriService):
    """
    工具运行时服务
    
    每个工具在独立子进程中执行，避免工具崩溃影响平台。
    危险工具（shell_exec）需通过 security 服务审批。
    """
    
    def __init__(self):
        super().__init__("suri-tool-host")
    
    def on_startup(self):
        """扫描并注册所有工具"""
        pass
    
    def on_run(self):
        """启动 gRPC 服务器，监听工具调用请求"""
        pass
    
    def on_shutdown(self):
        """终止所有运行中的工具子进程"""
        pass
    
    def on_persist_state(self):
        """工具服务无状态，无需持久化"""
        pass
    
    def on_restore_state(self):
        """工具服务无状态，无需恢复"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
