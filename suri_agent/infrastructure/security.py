"""
安全服务

职责：
- 读取 file_ownership.md 和 security.md
- 校验操作者是否有权修改目标文件
- 校验文件操作是否已有有效审批令牌
- 提供审批令牌的生成与验证

原则：所有文件写操作必须经过此服务校验。
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from suri_agent.infrastructure.config import ConfigService


@dataclass
class OwnershipRule:
    path_pattern: str
    controller: str
    description: str


class SecurityService:
    """
    安全中心
    
    运行时读取：
    - manifest/rules/file_ownership.md
    - manifest/rules/security.md
    """
    
    def __init__(self, config: ConfigService):
        self.config = config
        self._ownership_rules: List[OwnershipRule] = []
        self._approval_tokens: Dict[str, Dict[str, Any]] = {}
        self._load_rules()
    
    def _load_rules(self) -> None:
        """加载安全规则到内存"""
        file_ownership = self.config.get_rule('file_ownership')
        if file_ownership:
            # 简单解析 Markdown 表格（实际可用更健壮的解析器）
            self._parse_ownership(file_ownership.body)
    
    def _parse_ownership(self, body: str) -> None:
        """解析 file_ownership.md 中的表格"""
        lines = body.split('\n')
        in_table = False
        for line in lines:
            if line.startswith('| `') and '---' not in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    path = parts[1].strip('`').strip()
                    controller = parts[2].strip()
                    desc = parts[3].strip()
                    if path and controller and path != '路径':
                        self._ownership_rules.append(
                            OwnershipRule(path, controller, desc)
                        )
    
    def check_permission(self, operator: str, target_path: str) -> tuple[bool, str]:
        """
        检查操作者是否有权修改目标路径
        
        Args:
            operator: 操作者 role_id
            target_path: 目标文件/目录路径
            
        Returns:
            (是否允许, 原因)
        """
        # 1. 查找所有权规则
        matched = self._match_ownership(target_path)
        if not matched:
            return False, f"未找到 {target_path} 的所有权规则，默认拒绝"
        
        # 2. 检查操作者是否是控制角色
        controllers = [c.strip() for c in matched.controller.split('/')]
        if operator in controllers:
            return True, f"{operator} 是 {target_path} 的控制角色"
        
        # 3. 检查是否是 hr_admin（对 profiles/ 有管理权）
        if operator == 'hr_admin' and target_path.startswith('profiles/'):
            return True, "hr_admin 拥有角色管理权限"
        
        # 4. 检查是否是 ops_admin（对 hooks/ 有管理权）
        if operator == 'ops_admin' and target_path.startswith('hooks/'):
            return True, "ops_admin 拥有钩子管理权限"
        
        return False, f"{operator} 无权操作 {target_path}，控制角色为 {matched.controller}"
    
    def _match_ownership(self, target_path: str) -> Optional[OwnershipRule]:
        """匹配所有权规则（支持通配符）"""
        for rule in self._ownership_rules:
            pattern = rule.path_pattern
            # 简单匹配：完全匹配或前缀匹配（如 profiles/<role>/）
            if pattern == target_path:
                return rule
            if pattern.endswith('/') and target_path.startswith(pattern.rstrip('/')):
                return rule
            if '<role>' in pattern:
                prefix = pattern.replace('<role>/', '')
                if target_path.startswith(prefix.rstrip('/')):
                    return rule
        return None
    
    def validate_approval_token(self, token: str, target_path: str) -> tuple[bool, str]:
        """
        验证审批令牌是否有效且覆盖目标文件
        
        Args:
            token: approval_token
            target_path: 待修改路径
            
        Returns:
            (是否有效, 原因)
        """
        if not token:
            return False, "缺少审批令牌"
        
        approval = self._approval_tokens.get(token)
        if not approval:
            return False, "审批令牌不存在或已过期"
        
        if approval.get('status') != 'approved':
            return False, "审批尚未通过"
        
        # 检查目标文件是否在审批范围内
        approved_files = approval.get('file_list', [])
        for f in approved_files:
            if target_path.startswith(f) or target_path == f:
                return True, "文件在审批范围内"
        
        return False, f"{target_path} 不在审批范围内"
    
    def register_approval(self, token: str, report: Dict[str, Any]) -> None:
        """注册一个已批准的审批令牌"""
        self._approval_tokens[token] = report
    
    def revoke_approval(self, token: str) -> None:
        """撤销审批令牌"""
        if token in self._approval_tokens:
            self._approval_tokens[token]['status'] = 'revoked'
    
    def pre_file_change_check(
        self,
        operator: str,
        target_path: str,
        approval_token: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        文件修改前的综合检查（权限 + 审批）
        
        这是 hooks/pre_file_change.py 的核心逻辑。
        返回 (allow, reason)。
        """
        # 1. 权限检查
        allowed, reason = self.check_permission(operator, target_path)
        if not allowed:
            return False, f"[权限拒绝] {reason}"
        
        # 2. 豁免场景（自动操作无需审批）
        if self._is_exempt(target_path):
            return True, "[豁免] 自动操作无需审批"
        
        # 3. 审批检查
        if approval_token:
            valid, reason = self.validate_approval_token(approval_token, target_path)
            if not valid:
                return False, f"[审批拒绝] {reason}"
            return True, "[通过] 权限与审批均校验通过"
        
        return False, "[审批拒绝] 缺少有效的审批令牌"
    
    def _is_exempt(self, target_path: str) -> bool:
        """检查是否属于豁免场景"""
        exempt_patterns = [
            'logs/',
            'cache/',
            'temp/',
            'sessions/',
            'memories/',
        ]
        for p in exempt_patterns:
            if target_path.startswith(p):
                return True
        return False
