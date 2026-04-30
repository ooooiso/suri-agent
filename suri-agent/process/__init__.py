"""
流程执行层

所有平台级流程已代码化，运行时直接调用。
角色内部流程由角色在 group/<role>/ 中自行定义，不通过此处管理。
"""

from pathlib import Path

from process.base import BaseProcess
from process.workflow import WorkflowProcess
from process.change_approval import ChangeApprovalProcess


class ProcessEngine:
    """流程引擎：统一管理所有平台级流程"""
    
    PROCESS_CLASSES = {
        "workflow": WorkflowProcess,
        "change_approval": ChangeApprovalProcess,
    }
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._processes: dict = {}
        self._load_all()
    
    def _load_all(self):
        """初始化所有流程实例"""
        for process_id, ProcessClass in self.PROCESS_CLASSES.items():
            try:
                self._processes[process_id] = ProcessClass()
            except Exception as e:
                print(f"[ProcessEngine] 加载流程 {process_id} 失败: {e}")
    
    def get(self, process_id: str) -> BaseProcess:
        """获取指定流程实例"""
        return self._processes.get(process_id)
    
    def list_processes(self) -> list:
        """列出所有已加载的流程 ID"""
        return list(self._processes.keys())
    
    def execute(self, process_id: str, context: dict) -> dict:
        """执行指定流程"""
        process = self._processes.get(process_id)
        if not process:
            return {"success": False, "error": f"process_not_found: {process_id}"}
        return process.execute(context)


__all__ = [
    "BaseProcess",
    "WorkflowProcess",
    "ChangeApprovalProcess",
    "ProcessEngine",
]
