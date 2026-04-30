"""
规则基类

所有业务规则继承此类，提供统一的执行接口。
规则从配置描述变为可执行代码，直接参与调度决策。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseRule(ABC):
    """规则基类"""
    
    rule_id: str = ""
    name: str = ""
    version: str = "1.0.0"
    owner: str = ""
    
    @abstractmethod
    def validate(self, context: Dict[str, Any]) -> bool:
        """校验上下文是否满足规则条件"""
        pass
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行规则，返回执行结果"""
        pass
    
    def describe(self) -> str:
        """返回规则描述（用于日志和调试）"""
        return f"[{self.rule_id}] {self.name} v{self.version}"
