"""
Suri Scheduler — 调度编排服务

职责：
1. 任务全生命周期管理（创建、规划、分派、跟踪、完成）
2. Agent 注册表管理
3. 部门注册表管理
4. 审批状态机
5. 中断处理与升级

包含模块：
- task_dispatcher.py      → 任务接收、部门匹配、分派
- task_planner.py         → 任务分解、单/多角色规划
- agent_registry.py       → Agent 生命周期、独立上下文
- department_registry.py  → 部门扫描、能力匹配
- interrupt_handler.py    → 受阻分类、升级通道
- approval_service.py     → 审批状态机
- state_card.py           → 任务看板渲染

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class SchedulerService(SuriService):
    """
    调度编排服务 — 平台的"大脑"
    
    接收 gateway 的任务请求，规划执行步骤，
    分派给 role-engine，跟踪状态，汇总结果。
    """
    
    def __init__(self):
        super().__init__("suri-scheduler")
    
    def on_startup(self):
        """恢复未完成的任务状态"""
        # TODO: 从 platform.db 恢复 running 状态的 Agent
        pass
    
    def on_run(self):
        """启动 gRPC 服务器，监听任务请求"""
        pass
    
    def on_shutdown(self):
        """保存所有 Agent 状态"""
        pass
    
    def on_persist_state(self):
        """热升级前持久化状态"""
        pass
    
    def on_restore_state(self):
        """热升级后恢复状态"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
