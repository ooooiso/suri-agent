"""
Suri Gateway — 接入网关服务

职责：
1. 统一接收所有用户输入（CLI / Telegram / Web / JSON-RPC）
2. 协议转换：将各接入协议统一转换为内部 gRPC 调用
3. 输出路由：将服务结果路由到正确的输出通道
4. 用户会话管理

包含模块（未来拆分）：
- cli_server.py      → 终端交互
- telegram_bot.py    → Telegram Bot 连接
- web_server.py      → Web UI + SSE
- rpc_server.py      → JSON-RPC 服务
- output_router.py   → 输出路由（Terminal/File/Memory/Logger/Telegram）

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class GatewayService(SuriService):
    """
    接入网关服务
    
    对外：暴露 CLI / Telegram Webhook / HTTP / JSON-RPC
    对内：通过 gRPC 调用 scheduler 等后端服务
    """
    
    def __init__(self):
        super().__init__("suri-gateway")
    
    def on_startup(self):
        """启动各接入服务器"""
        # TODO: 启动 CLI / Telegram Bot / Web / RPC 服务器
        pass
    
    def on_run(self):
        """运行接入服务器事件循环"""
        # TODO: 阻塞等待连接
        pass
    
    def on_shutdown(self):
        """关闭所有接入服务器"""
        pass
    
    def on_persist_state(self):
        """保存活跃会话"""
        pass
    
    def on_restore_state(self):
        """恢复活跃会话"""
        pass
    
    def health_check(self) -> dict:
        """检查各接入端健康状态"""
        return {"status": "healthy"}
