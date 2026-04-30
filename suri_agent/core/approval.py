"""
审批服务

职责：
- 管理审批流程的状态机
- 接收变更报告，转发 security_admin 审核
- 审核通过后，通过 suri 向用户请求确认
- 监听用户回复，处理"是"/"否"/模糊回复/超时
- 生成和验证 approval_token

原则：审批规则由外部 security.md 和 change_approval.md 驱动。
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from suri_agent.infrastructure.config import ConfigService
from suri_agent.infrastructure.memory import MemoryService
from suri_agent.infrastructure.security import SecurityService


class ApprovalService:
    """
    审批引擎
    
    流程：
    报告提交 → security_admin 审核 → suri 请求用户 → 用户确认 → 生成 token → 执行
    """
    
    def __init__(self, config: ConfigService, memory: MemoryService, security: SecurityService):
        self.config = config
        self.memory = memory
        self.security = security
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}
    
    def submit_report(self, report: Dict[str, Any]) -> str:
        """
        提交变更报告，启动审批流程
        
        Args:
            report: 变更报告（含 report_id, requester, reason, file_list, impact_analysis）
            
        Returns:
            approval_id
        """
        approval_id = f"approval_{uuid.uuid4().hex[:8]}"
        
        record = {
            'approval_id': approval_id,
            'report_id': report.get('report_id', ''),
            'requester': report.get('requester', ''),
            'file_list': report.get('file_list', []),
            'reason': report.get('reason', ''),
            'impact': report.get('impact_analysis', ''),
            'status': 'pending_security_review',
            'security_review': None,
            'user_response': None,
            'approval_token': None,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        self._pending_approvals[approval_id] = record
        
        # TODO: 通知 security_admin 审核
        print(f"[ApprovalService] 新审批请求 {approval_id} 来自 {record['requester']}")
        
        return approval_id
    
    def security_review(self, approval_id: str, decision: str, reviewer: str, reason: str = '') -> bool:
        """
        security_admin 审核
        
        Args:
            approval_id: 审批 ID
            decision: 'approve' 或 'reject'
            reviewer: 审核者 role_id
            reason: 驳回理由
        """
        record = self._pending_approvals.get(approval_id)
        if not record:
            return False
        
        if record['status'] != 'pending_security_review':
            return False
        
        if decision == 'approve':
            record['status'] = 'pending_user_confirm'
            record['security_review'] = {'reviewer': reviewer, 'result': 'approved'}
            # TODO: 通知 suri 向用户请求确认
            print(f"[ApprovalService] {approval_id} 安全审核通过，等待用户确认")
        else:
            record['status'] = 'rejected'
            record['security_review'] = {'reviewer': reviewer, 'result': 'rejected', 'reason': reason}
            # TODO: 通知请求者
            print(f"[ApprovalService] {approval_id} 被 security_admin 驳回: {reason}")
        
        return True
    
    def user_confirm(self, approval_id: str, response: str) -> Dict[str, Any]:
        """
        处理用户回复
        
        Args:
            approval_id: 审批 ID
            response: 用户原始回复文本
            
        Returns:
            {'success': bool, 'approval_token': str or None, 'reason': str}
        """
        record = self._pending_approvals.get(approval_id)
        if not record:
            return {'success': False, 'approval_token': None, 'reason': '审批不存在'}
        
        if record['status'] != 'pending_user_confirm':
            return {'success': False, 'approval_token': None, 'reason': f'当前状态: {record["status"]}'}
        
        # 检查是否超时
        expires = datetime.fromisoformat(record['expires_at'])
        if datetime.now() > expires:
            record['status'] = 'timeout'
            return {'success': False, 'approval_token': None, 'reason': '审批已超时'}
        
        # 解析用户回复
        normalized = response.strip().lower()
        if normalized in ['是', 'yes', 'y', '确认', '批准', 'approve']:
            token = f"token_{uuid.uuid4().hex[:12]}"
            record['status'] = 'approved'
            record['user_response'] = response
            record['approval_token'] = token
            
            # 注册到安全服务
            self.security.register_approval(token, record)
            
            # TODO: 通知请求者执行
            print(f"[ApprovalService] {approval_id} 用户已批准，令牌: {token}")
            return {'success': True, 'approval_token': token, 'reason': '用户已确认'}
        
        elif normalized in ['否', 'no', 'n', '拒绝', 'reject']:
            record['status'] = 'rejected'
            record['user_response'] = response
            return {'success': False, 'approval_token': None, 'reason': '用户拒绝'}
        
        else:
            # 模糊回复
            return {'success': False, 'approval_token': None, 'reason': '模糊回复'}
    
    def check_timeout(self) -> list[str]:
        """检查超时的审批，返回超时列表"""
        timeouts = []
        now = datetime.now()
        for approval_id, record in self._pending_approvals.items():
            if record['status'] in ['pending_security_review', 'pending_user_confirm']:
                expires = datetime.fromisoformat(record['expires_at'])
                if now > expires:
                    record['status'] = 'timeout'
                    timeouts.append(approval_id)
                    print(f"[ApprovalService] {approval_id} 已超时")
        return timeouts
    
    def get_status(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """获取审批状态"""
        return self._pending_approvals.get(approval_id)
