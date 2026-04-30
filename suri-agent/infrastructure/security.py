"""
安全服务

职责：
- 调用规则代码（FileOwnershipRule、SecurityRule）执行权限校验
- 提供审批令牌的注册与验证
- 所有文件写操作必须经过此服务校验

规则已代码化，不再解析 .md 文件。
"""

from pathlib import Path
from typing import Optional, Dict, Any
from infrastructure.config import ConfigService
from rules.file_ownership import FileOwnershipRule
from rules.security import SecurityRule


class SecurityService:
    """
    安全中心
    
    运行时调用规则代码：
    - FileOwnershipRule: 文件所有权校验
    - SecurityRule: 安全审批流程
    """
    
    def __init__(self, project_root: Path, config: ConfigService):
        self.config = config
        self.project_root = project_root
        self.file_ownership = FileOwnershipRule(project_root)
        self.security = SecurityRule(project_root)
    
    def check_permission(self, operator: str, target_path: str) -> tuple[bool, str]:
        """
        检查操作者是否有权修改目标路径
        
        Args:
            operator: 操作者 role_id
            target_path: 目标文件/目录路径
            
        Returns:
            (是否允许, 原因)
        """
        result = self.file_ownership.execute({
            "role_id": operator,
            "target_path": target_path,
        })
        
        if result["allowed"]:
            return True, f"{operator} 有权操作 {target_path}"
        
        owner = result.get("owner", "unknown")
        return False, f"{operator} 无权操作 {target_path}，控制角色为 {owner}"
    
    def validate_approval_token(self, token: str, target_path: str,
                                role_id: str = "") -> tuple[bool, str]:
        """
        验证审批令牌是否有效且覆盖目标文件
        
        Args:
            token: approval_token
            target_path: 待修改路径
            role_id: 操作者角色 ID
            
        Returns:
            (是否有效, 原因)
        """
        if not token:
            return False, "缺少审批令牌"
        
        valid = self.security.validate_token(token, target_path, role_id)
        if valid:
            return True, "文件在审批范围内"
        
        return False, f"{target_path} 不在审批范围内或令牌已过期"
    
    def create_change_report(self, requester: str, reason: str,
                            file_list: list, impact_analysis: str) -> Dict:
        """创建变更报告"""
        return self.security.create_change_report(
            requester, reason, file_list, impact_analysis
        )
    
    def issue_approval_token(self, report_id: str,
                            approved_files: list) -> str:
        """security_admin 审核通过后签发令牌"""
        return self.security.issue_token(report_id, approved_files)
    
    def register_approval(self, token: str, report: Dict) -> None:
        """注册一个已批准的审批令牌"""
        self.security._approval_tokens[token] = report
    
    def revoke_approval(self, token: str) -> None:
        """撤销审批令牌"""
        if token in self.security._approval_tokens:
            self.security._approval_tokens[token]["status"] = "revoked"
    
    def pre_file_change_check(
        self,
        operator: str,
        target_path: str,
        approval_token: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        文件修改前的综合检查（权限 + 审批）
        
        返回 (allow, reason)。
        """
        # 1. 权限检查
        allowed, reason = self.check_permission(operator, target_path)
        if not allowed:
            return False, f"[权限拒绝] {reason}"
        
        # 2. 豁免场景（自动操作无需审批）
        if self._is_exempt(target_path):
            return True, "[豁免] 自动操作无需审批"
        
        # 3. 监控范围检查
        if not self.security.is_monitored(target_path):
            return True, "[通过] 非监控路径"
        
        # 4. 审批检查
        if approval_token:
            valid, reason = self.validate_approval_token(
                approval_token, target_path, operator
            )
            if valid:
                return True, "[通过] 权限与审批均校验通过"
            return False, f"[审批拒绝] {reason}"
        
        return False, "[审批拒绝] 缺少有效的审批令牌"
    
    def _is_exempt(self, target_path: str) -> bool:
        """检查是否属于豁免场景"""
        exempt_patterns = [
            "resources/logs/",
            "resources/cache/",
            "resources/temp/",
            "resources/sessions/",
            "resources/memories/",
        ]
        for p in exempt_patterns:
            if target_path.startswith(p):
                return True
        return False
