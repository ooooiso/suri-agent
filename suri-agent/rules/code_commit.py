"""
代码/配置变更提交规范

职责：
- 验证变更报告完整性
- 紧急修复时限检查
- 变更日志记录
"""

import time
from typing import Dict, List
from rules.base import BaseRule


class CodeCommitRule(BaseRule):
    """代码/配置变更提交规范执行器"""
    
    rule_id = "code_commit"
    name = "代码/配置变更提交规范"
    owner = "git_admin"
    
    # 紧急修复补交时限（秒）
    EMERGENCY_DEADLINE = 600  # 10分钟
    # 紧急修复次数限制
    MAX_EMERGENCY_COUNT = 3
    # 限制时长（秒）
    RESTRICTION_DURATION = 86400  # 24小时
    
    REQUIRED_FIELDS = [
        "commit_id", "author_role", "timestamp",
        "reason", "changed_files", "impact_analysis",
    ]
    
    def __init__(self):
        self._emergency_count: Dict[str, int] = {}
        self._emergency_records: Dict[str, List[Dict]] = {}
    
    def validate(self, context: Dict) -> bool:
        report = context.get("report")
        if not report:
            return False
        return self.validate_change_report(report)
    
    def execute(self, context: Dict) -> Dict:
        report = context.get("report", {})
        is_emergency = context.get("is_emergency", False)
        author = report.get("author_role", "")
        
        if is_emergency:
            return self._handle_emergency(report, author)
        
        return {
            "success": True,
            "operation": "normal_commit",
            "report_id": report.get("commit_id"),
            "next_steps": [
                "submit_to_security_admin",
                "await_user_confirm",
                "execute_approved_changes",
                "record_changelog",
            ],
        }
    
    def validate_change_report(self, report: Dict) -> bool:
        """验证变更报告是否包含必填字段"""
        for field in self.REQUIRED_FIELDS:
            if field not in report:
                return False
        
        # changed_files 必须是列表且每项包含 path 和 summary
        files = report.get("changed_files", [])
        if not isinstance(files, list) or len(files) == 0:
            return False
        
        for f in files:
            if not isinstance(f, dict):
                return False
            if "path" not in f or "summary" not in f:
                return False
        
        return True
    
    def _handle_emergency(self, report: Dict, author: str) -> Dict:
        """处理紧急修复"""
        count = self._emergency_count.get(author, 0) + 1
        self._emergency_count[author] = count
        
        # 记录紧急修复
        if author not in self._emergency_records:
            self._emergency_records[author] = []
        self._emergency_records[author].append({
            "report": report,
            "timestamp": time.time(),
            "deadline": time.time() + self.EMERGENCY_DEADLINE,
            "supplement_submitted": False,
        })
        
        result = {
            "success": True,
            "operation": "emergency_fix",
            "report_id": report.get("commit_id"),
            "deadline": time.time() + self.EMERGENCY_DEADLINE,
            "emergency_count": count,
        }
        
        if count >= self.MAX_EMERGENCY_COUNT:
            result["alert"] = "max_emergency_exceeded"
            result["required_reviewers"] = ["ops_admin", "workflow_admin"]
        
        return result
    
    def check_emergency_deadline(self, author: str) -> List[Dict]:
        """检查该角色的紧急修复是否超时未补交"""
        now = time.time()
        overdue = []
        
        for record in self._emergency_records.get(author, []):
            if not record["supplement_submitted"] and now > record["deadline"]:
                overdue.append(record)
        
        return overdue
    
    def submit_supplement(self, author: str, report_id: str) -> bool:
        """补交紧急修复的变更报告"""
        for record in self._emergency_records.get(author, []):
            if record["report"].get("commit_id") == report_id:
                record["supplement_submitted"] = True
                return True
        return False
    
    def is_restricted(self, author: str) -> bool:
        """检查角色是否因紧急修复超限被限制提交"""
        count = self._emergency_count.get(author, 0)
        if count < self.MAX_EMERGENCY_COUNT:
            return False
        
        # 检查限制是否已过期（简化：按最后一次紧急修复时间 + 24小时）
        records = self._emergency_records.get(author, [])
        if not records:
            return False
        
        last_time = records[-1]["timestamp"]
        return (time.time() - last_time) < self.RESTRICTION_DURATION
    
    def record_changelog(self, report: Dict) -> Dict:
        """生成变更日志条目"""
        return {
            "commit_id": report.get("commit_id"),
            "author": report.get("author_role"),
            "timestamp": report.get("timestamp"),
            "reason": report.get("reason"),
            "files": [f["path"] for f in report.get("changed_files", [])],
        }
