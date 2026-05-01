"""
配置变更审批流程执行器

职责：
- 管理变更报告的准备与校验
- 执行审批链（security_admin 审核 → 用户确认 → 执行）
- 处理紧急修复通道
- 变更日志记录
"""

from typing import Any, Dict
from process.base import BaseProcess


class ChangeApprovalProcess(BaseProcess):
    """配置变更审批详细步骤"""
    
    process_id = "change_approval"
    name = "配置变更审批流程"
    owner = "security_admin"
    
    # 紧急修复时限（秒）
    EMERGENCY_DEADLINE = 600  # 10分钟
    MAX_EMERGENCY_COUNT = 3
    USER_CONFIRM_TIMEOUT = 86400  # 24小时
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行变更审批流程"""
        step = context.get("step", "prepare_report")
        
        handlers = {
            "prepare_report": self._step_prepare_report,
            "initiate": self._step_initiate,
            "security_review": self._step_security_review,
            "user_confirm": self._step_user_confirm,
            "execute": self._step_execute,
            "record": self._step_record,
            "emergency": self._step_emergency,
        }
        
        handler = handlers.get(step)
        if not handler:
            return {"success": False, "error": f"unknown_step: {step}"}
        
        return handler(context)
    
    def _step_prepare_report(self, context: Dict) -> Dict:
        """Step 1: 准备变更报告"""
        report = context.get("report", {})
        required_fields = ["commit_id", "author_role", "timestamp", "reason", "changed_files", "impact_analysis"]
        
        missing = [f for f in required_fields if f not in report]
        if missing:
            return {"success": False, "step": "prepare_report", "error": f"missing_fields: {missing}"}
        
        # 校验 changed_files 逐文件列出
        files = report.get("changed_files", [])
        if not isinstance(files, list) or len(files) == 0:
            return {"success": False, "step": "prepare_report", "error": "changed_files_empty"}
        
        for f in files:
            if not isinstance(f, dict) or "path" not in f or "summary" not in f:
                return {"success": False, "step": "prepare_report", "error": "invalid_file_entry"}
        
        return {
            "success": True,
            "step": "prepare_report",
            "next_step": "initiate",
            "report_id": report.get("commit_id"),
        }
    
    def _step_initiate(self, context: Dict) -> Dict:
        """Step 2: 所属角色发起"""
        operator = context.get("operator")
        owner = context.get("owner")
        
        if operator == owner:
            return {"success": True, "step": "initiate", "next_step": "security_review"}
        
        # 非控制角色需有授权
        authorization = context.get("authorization")
        if authorization:
            return {"success": True, "step": "initiate", "next_step": "security_review", "note": "with_authorization"}
        
        return {
            "success": False,
            "step": "initiate",
            "error": "not_controller",
            "required": f"must be {owner} or have written authorization",
        }
    
    def _step_security_review(self, context: Dict) -> Dict:
        """Step 3: security_admin 审核"""
        checks = {
            "permission_check": "操作者是否有权限",
            "scope_clarity": "变更范围是否明确、无歧义",
            "impact_sufficiency": "影响分析是否充分",
            "rule_compliance": "是否符合平台规则",
        }
        
        return {
            "success": True,
            "step": "security_review",
            "checks": checks,
            "next_step": "user_confirm",
            "note": "security_admin returns approve or reject with reason",
        }
    
    def _step_user_confirm(self, context: Dict) -> Dict:
        """Step 4-5: suri 请求用户确认"""
        report = context.get("report", {})
        
        return {
            "success": True,
            "step": "user_confirm",
            "message_template": {
                "title": "【变更审批请求】",
                "requester": report.get("author_role"),
                "files": [f["path"] for f in report.get("changed_files", [])],
                "reason": report.get("reason"),
                "impact": report.get("impact_analysis"),
                "action": "请回复'是'以批准执行",
            },
            "valid_responses": ["是", "yes", "确认"],
            "reject_responses": ["否", "no", "拒绝"],
            "timeout_seconds": self.USER_CONFIRM_TIMEOUT,
            "timeout_action": "流程终止，通知操作者",
        }
    
    def _step_execute(self, context: Dict) -> Dict:
        """Step 6: 执行修改"""
        token = context.get("approval_token")
        approved_files = context.get("approved_files", [])
        
        return {
            "success": True,
            "step": "execute",
            "constraints": [
                "仅允许修改报告中列出的文件",
                "pre_file_change 钩子实时校验 approval_token",
                "超范围操作被实时阻断",
            ],
            "token": token,
            "approved_files": approved_files,
        }
    
    def _step_record(self, context: Dict) -> Dict:
        """Step 7: 记录日志"""
        report = context.get("report", {})
        
        return {
            "success": True,
            "step": "record",
            "actions": [
                "git_admin 将变更追加到 resources/sessions/changelog.md",
                "变更报告永久保存于 resources/sessions/",
            ],
            "changelog_entry": {
                "commit_id": report.get("commit_id"),
                "author": report.get("author_role"),
                "timestamp": report.get("timestamp"),
                "reason": report.get("reason"),
                "files": [f["path"] for f in report.get("changed_files", [])],
            },
        }
    
    def _step_emergency(self, context: Dict) -> Dict:
        """紧急修复通道"""
        emergency_count = context.get("emergency_count", 0)
        
        result = {
            "success": True,
            "step": "emergency",
            "allowed": True,
            "note": "可先执行修复，后补审批",
            "supplement_deadline_seconds": self.EMERGENCY_DEADLINE,
        }
        
        if emergency_count >= self.MAX_EMERGENCY_COUNT:
            result["alert"] = "max_emergency_exceeded"
            result["required_reviewers"] = ["ops_admin", "workflow_admin"]
        
        return result
