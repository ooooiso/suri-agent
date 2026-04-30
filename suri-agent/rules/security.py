"""
安全审批规则

职责：
- 判断文件操作是否在监控范围内
- 管理审批链（生成报告 → 审核 → 用户确认 → 执行）
- 验证审批令牌
- 处理离线代理
"""

import time
from typing import Dict, List, Optional
from pathlib import Path
from rules.base import BaseRule
from rules.file_ownership import FileOwnershipRule


class SecurityRule(BaseRule):
    """安全审批规则执行器"""
    
    rule_id = "security"
    name = "安全审批规则"
    owner = "security_admin"
    
    # 受监控路径前缀
    MONITORED_PREFIXES = [
        "group/",
        "suri-agent/tools/",
        "skills/",
        "suri-agent/hooks/",
        "config.yaml",
        ".env",
    ]
    
    # 豁免操作
    EXEMPT_OPERATIONS = [
        "model_auto_fallback",
        "cache_rotation",
        "temp_cleanup",
        "log_archive",
        "read_only_query",
    ]
    
    # 离线代理阈值（秒）
    OFFLINE_THRESHOLD = 1800  # 30分钟
    PROXY_EXPIRY = 14400      # 4小时
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.file_ownership = FileOwnershipRule(project_root)
        self._approval_tokens: Dict[str, Dict] = {}
    
    def validate(self, context: Dict) -> bool:
        """校验操作是否通过安全审批"""
        operation = context.get("operation")
        if operation in self.EXEMPT_OPERATIONS:
            return True
        
        target_path = context.get("target_path")
        if not target_path:
            return False
        
        if not self.is_monitored(target_path):
            return True  # 非监控路径无需审批
        
        token = context.get("approval_token")
        role_id = context.get("role_id")
        
        return self.validate_token(token, target_path, role_id)
    
    def execute(self, context: Dict) -> Dict:
        """执行安全校验"""
        operation = context.get("operation", "")
        target_path = context.get("target_path", "")
        role_id = context.get("role_id", "")
        token = context.get("approval_token")
        
        # 豁免检查
        if operation in self.EXEMPT_OPERATIONS:
            return {"allowed": True, "reason": "exempt_operation"}
        
        # 监控范围检查
        if not self.is_monitored(target_path):
            return {"allowed": True, "reason": "not_monitored"}
        
        # 所有权检查
        if not self.file_ownership.can_modify(role_id, target_path):
            return {
                "allowed": False,
                "reason": "unauthorized",
                "owner": self.file_ownership.get_owner(target_path),
            }
        
        # 审批令牌检查
        if not token:
            return {
                "allowed": False,
                "reason": "approval_required",
                "next_step": "submit_change_report",
            }
        
        token_valid = self.validate_token(token, target_path, role_id)
        return {
            "allowed": token_valid,
            "reason": "token_valid" if token_valid else "token_invalid",
        }
    
    def is_monitored(self, path: str) -> bool:
        """检查路径是否在安全监控范围内"""
        path = path.lstrip("/")
        for prefix in self.MONITORED_PREFIXES:
            if path.startswith(prefix) or path == prefix:
                return True
        return False
    
    def create_change_report(self, requester: str, reason: str,
                            file_list: List[Dict], impact_analysis: str) -> Dict:
        """创建变更报告"""
        report_id = f"report_{int(time.time() * 1000)}"
        return {
            "report_id": report_id,
            "requester": requester,
            "reason": reason,
            "file_list": file_list,
            "impact_analysis": impact_analysis,
            "timestamp": time.time(),
            "status": "pending_review",
            "approval_token": None,
        }
    
    def issue_token(self, report_id: str, approved_files: List[str]) -> str:
        """security_admin 审核通过后签发令牌"""
        token = f"tkn_{report_id}_{int(time.time())}"
        self._approval_tokens[token] = {
            "report_id": report_id,
            "approved_files": approved_files,
            "issued_at": time.time(),
            "expires_at": time.time() + 86400,  # 24小时有效
        }
        return token
    
    def validate_token(self, token: Optional[str], target_path: str,
                      role_id: str) -> bool:
        """验证审批令牌是否有效且覆盖目标文件"""
        if not token:
            return False
        
        record = self._approval_tokens.get(token)
        if not record:
            return False
        
        # 检查是否过期
        if time.time() > record["expires_at"]:
            return False
        
        # 检查目标文件是否在审批范围内
        approved_files = record.get("approved_files", [])
        return target_path in approved_files
    
    def check_offline_proxy(self, security_admin_last_seen: float,
                           ops_admin_last_seen: float) -> Optional[str]:
        """
        检查是否需要离线代理。
        返回可代理审批的角色 ID，或 None（直接升级至用户）。
        """
        now = time.time()
        
        if now - security_admin_last_seen < self.OFFLINE_THRESHOLD:
            return None  # security_admin 在线，无需代理
        
        if now - ops_admin_last_seen < self.OFFLINE_THRESHOLD:
            return "ops_admin"  # ops_admin 代行
        
        return "user"  # 双方都离线，升级至用户
