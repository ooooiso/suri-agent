"""
规则执行层

所有业务规则从 Markdown 描述迁移为可执行 Python 代码。
规则不再通过解析 .md 文件加载，而是直接实例化并调用。
"""

from pathlib import Path
from rules.base import BaseRule
from rules.scheduling import SchedulingRule
from rules.security import SecurityRule
from rules.file_ownership import FileOwnershipRule
from rules.model_routing import ModelRoutingRule
from rules.communication import CommunicationRule
from rules.role_management import RoleManagementRule
from rules.code_commit import CodeCommitRule


class RuleEngine:
    """规则引擎：统一管理所有规则的加载与执行"""
    
    RULE_CLASSES = {
        "scheduling": SchedulingRule,
        "security": SecurityRule,
        "file_ownership": FileOwnershipRule,
        "model_routing": ModelRoutingRule,
        "communication_protocol": CommunicationRule,
        "role_management": RoleManagementRule,
        "code_commit": CodeCommitRule,
    }
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._rules: dict = {}
        self._load_all()
    
    def _load_all(self):
        """初始化所有规则实例"""
        for rule_id, RuleClass in self.RULE_CLASSES.items():
            try:
                if rule_id in ["security", "file_ownership"]:
                    instance = RuleClass(self.project_root)
                else:
                    instance = RuleClass()
                self._rules[rule_id] = instance
            except Exception as e:
                print(f"[RuleEngine] 加载规则 {rule_id} 失败: {e}")
    
    def get(self, rule_id: str) -> BaseRule:
        """获取指定规则实例"""
        return self._rules.get(rule_id)
    
    def list_rules(self) -> list:
        """列出所有已加载的规则 ID"""
        return list(self._rules.keys())
    
    def execute(self, rule_id: str, context: dict) -> dict:
        """执行指定规则"""
        rule = self._rules.get(rule_id)
        if not rule:
            return {"success": False, "error": f"rule_not_found: {rule_id}"}
        
        if not rule.validate(context):
            return {"success": False, "error": "validation_failed"}
        
        return rule.execute(context)


# 便捷导出
__all__ = [
    "BaseRule",
    "SchedulingRule",
    "SecurityRule",
    "FileOwnershipRule",
    "ModelRoutingRule",
    "CommunicationRule",
    "RoleManagementRule",
    "CodeCommitRule",
    "RuleEngine",
]
