"""
Suri Role Engine — 角色引擎服务

职责：
1. 角色运行时框架（管理多个角色实例）
2. 角色间通信（通过 MessageBus）
3. 角色创建与 Soul 管理
4. 跨部门协作协调
5. 角色上下文管理（对话历史、系统提示组装）

包含模块：
- runtime.py          → 角色实例管理
- messenger.py        → 角色间通信
- builder.py          → 角色创建、Soul 模板
- coordinator.py      → 任务分配、协作协调
- context_manager.py  → 角色对话上下文

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class RoleEngineService(SuriService):
    """
    角色引擎服务
    
    内部运行多个角色实例（suri、suri_dev、suri_hr、suri_review、suri_stats）。
    每个角色有独立的上下文和对话历史。
    角色间通过 NATS 消息总线异步通信。
    """
    
    def __init__(self):
        super().__init__("suri-role-engine")
    
    def on_startup(self):
        """加载所有角色 Soul，初始化角色实例"""
        pass
    
    def on_run(self):
        """启动 gRPC 服务器，监听步骤执行请求"""
        pass
    
    def on_shutdown(self):
        """保存角色上下文"""
        pass
    
    def on_persist_state(self):
        """保存当前执行中的步骤上下文"""
        pass
    
    def on_restore_state(self):
        """恢复角色上下文"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
