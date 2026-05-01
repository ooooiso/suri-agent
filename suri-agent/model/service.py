"""
Suri Model — 模型服务

职责：
1. 统一 LLM 调用入口
2. 模型池管理（添加、删除、设置默认）
3. 智能路由（根据任务选择模型）
4. 自动降级与告警
5. Token 用量统计

包含模块：
- manager.py   → ModelManager
- router.py    → ModelRouter
- providers/   → 各厂商适配器

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class ModelService(SuriService):
    """
    模型中心服务
    
    所有 LLM 调用（包括 scheduler、role-engine、learning）
    都通过此服务，统一管理与计费。
    """
    
    def __init__(self):
        super().__init__("suri-model")
    
    def on_startup(self):
        """加载模型配置，测试 API Key"""
        pass
    
    def on_run(self):
        """启动 gRPC 服务器"""
        pass
    
    def on_shutdown(self):
        pass
    
    def on_persist_state(self):
        """模型服务无状态"""
        pass
    
    def on_restore_state(self):
        """模型服务无状态"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
