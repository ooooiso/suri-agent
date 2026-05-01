"""
Suri Memory — 记忆与上下文服务

职责：
1. 所有数据持久化（平台级 + 角色级）
2. 上下文组装（Soul + 规则 + 经验注入）
3. 经验 Insight 管理
4. 会话与消息管理

包含模块：
- memory_service.py   → 数据存取
- context_service.py  → 系统提示组装
- schema.py           → 数据库 Schema

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class MemoryService(SuriService):
    """
    记忆中心服务
    
    管理平台级数据（tasks、sessions、approvals）和角色级数据（messages、experiences）。
    所有服务通过此服务读写数据，禁止直接访问 SQLite 文件。
    """
    
    def __init__(self):
        super().__init__("suri-memory")
    
    def on_startup(self):
        """初始化数据库连接池"""
        pass
    
    def on_run(self):
        """启动 gRPC 服务器"""
        pass
    
    def on_shutdown(self):
        """关闭数据库连接"""
        pass
    
    def on_persist_state(self):
        """数据已在数据库中，无需额外持久化"""
        pass
    
    def on_restore_state(self):
        """数据从数据库读取，无需额外恢复"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
