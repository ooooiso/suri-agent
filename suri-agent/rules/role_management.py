"""
角色生命周期管理规则

职责：
- 验证角色 ID 格式
- 创建角色（建立文件夹、Soul、技能索引）
- 修改角色（双重审核）
- 注销角色（归档、保留期）
"""

import re
import time
from pathlib import Path
from typing import Dict
from rules.base import BaseRule


class RoleManagementRule(BaseRule):
    """角色生命周期管理执行器"""
    
    rule_id = "role_management"
    name = "角色生命周期管理规则"
    owner = "hr_admin"
    
    ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
    ARCHIVE_RETENTION_DAYS = 30
    
    def validate(self, context: Dict) -> bool:
        operation = context.get("operation")
        if operation == "create":
            return self.validate_role_id(context.get("role_id", ""))
        return True
    
    def execute(self, context: Dict) -> Dict:
        operation = context.get("operation")
        
        if operation == "create":
            return self._execute_create(context)
        elif operation == "modify":
            return self._execute_modify(context)
        elif operation == "deprecate":
            return self._execute_deprecate(context)
        
        return {"success": False, "error": "unknown_operation"}
    
    def validate_role_id(self, role_id: str) -> bool:
        """验证角色 ID 格式：小写英文字母 + 下划线"""
        if not role_id or len(role_id) < 2:
            return False
        return bool(self.ROLE_ID_PATTERN.match(role_id))
    
    def _execute_create(self, context: Dict) -> Dict:
        """执行角色创建"""
        role_id = context.get("role_id")
        department = context.get("department")
        
        if not self.validate_role_id(role_id):
            return {"success": False, "error": "invalid_role_id"}
        
        return {
            "success": True,
            "operation": "create",
            "role_id": role_id,
            "required_files": [
                f"group/{department}/{role_id}/{role_id}.md",
                f"group/{department}/{role_id}/skills/skills.md",
                f"group/{department}/{role_id}/memories/",
                f"group/{department}/{role_id}/reference/files_i_use.md",
            ],
            "next_steps": [
                "write_soul_file",
                "update_function_index",
                "update_roles_mapping",
                "submit_security_approval",
            ],
        }
    
    def _execute_modify(self, context: Dict) -> Dict:
        """执行角色修改"""
        role_id = context.get("role_id")
        change_type = context.get("change_type")  # soul | skill | department | permission
        
        required_approvers = []
        
        if change_type == "soul":
            required_approvers = ["workflow_admin", "security_admin"]
        elif change_type == "skill":
            required_approvers = ["config_admin"]
        elif change_type == "department":
            required_approvers = ["security_admin"]
        elif change_type == "permission":
            required_approvers = ["security_admin", "suri"]
        
        return {
            "success": True,
            "operation": "modify",
            "role_id": role_id,
            "change_type": change_type,
            "required_approvers": required_approvers,
            "requires_user_confirm": True,
        }
    
    def _execute_deprecate(self, context: Dict) -> Dict:
        """执行角色注销"""
        role_id = context.get("role_id")
        successor = context.get("successor")
        
        return {
            "success": True,
            "operation": "deprecate",
            "role_id": role_id,
            "successor": successor,
            "actions": [
                "mark_status_deprecated",
                "archive_to_group_archived",
                "schedule_cleanup_after_30d",
                "update_function_index",
                "update_roles_mapping",
            ],
            "cleanup_date": time.time() + self.ARCHIVE_RETENTION_DAYS * 86400,
        }
    
    def is_archivable(self, role_id: str, archive_dir: Path) -> bool:
        """检查角色是否已过保留期，可清理"""
        role_archive = archive_dir / role_id
        if not role_archive.exists():
            return False
        
        mtime = role_archive.stat().st_mtime
        return (time.time() - mtime) > self.ARCHIVE_RETENTION_DAYS * 86400
