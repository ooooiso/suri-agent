"""
流程基类

所有平台级流程继承此类，提供统一的执行接口。
流程已代码化，直接参与调度执行。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseProcess(ABC):
    """流程基类"""
    
    process_id: str = ""
    name: str = ""
    version: str = "1.0.0"
    owner: str = ""
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行流程，返回执行结果"""
        pass
    
    def describe(self) -> str:
        """返回流程描述"""
        return f"[{self.process_id}] {self.name} v{self.version}"
