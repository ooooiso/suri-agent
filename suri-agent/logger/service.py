"""
Suri Logger — 日志中心服务

职责：
1. 接收所有服务的日志事件（UDP + gRPC）
2. 分类写入（runtime / error / schedule / role / system / statistics / tool_calls）
3. 结构化 JSON 日志（用于统计和审计）
4. Token 用量统计
5. 日志查询接口

包含模块：
- logger_service.py   → 日志写入与查询
- handlers/           → 各类日志处理器

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class LoggerService(SuriService):
    """
    日志中心服务
    
    业务服务通过 UDP 发送日志（不阻塞），
    查询请求通过 gRPC。
    """
    
    def __init__(self):
        super().__init__("suri-logger")
    
    def on_startup(self):
        """启动 UDP 接收器和 gRPC 服务器"""
        pass
    
    def on_run(self):
        """运行日志接收循环"""
        pass
    
    def on_shutdown(self):
        """刷新日志缓冲区，关闭文件"""
        pass
    
    def on_persist_state(self):
        """日志服务无状态"""
        pass
    
    def on_restore_state(self):
        """日志服务无状态"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
