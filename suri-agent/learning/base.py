"""学习器基类

关联文档: suri-agent/learning/learning.md
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseLearner(ABC):
    """所有学习器的抽象基类"""
    
    learner_id: str = ""
    name: str = ""
    version: str = "1.0.0"
    
    @abstractmethod
    async def learn(self, context: Dict[str, Any]) -> Optional[str]:
        """
        执行学习，返回学习成果文本
        
        Args:
            context: 包含任务ID、角色ID、状态等信息的字典
            
        Returns:
            经验文本，或 None（无可学习的内容）
        """
        pass
    
    def describe(self) -> str:
        return f"[{self.learner_id}] {self.name} v{self.version}"
