"""
Suri Security — 安全与文件服务

职责：
1. 权限校验（文件所有权、角色类型、审批令牌）
2. 统一文件操作（所有文件读写必经此服务）
3. 审批管理（变更报告、令牌签发与验证）
4. 核心角色 Soul 文件保护

包含模块：
- security_service.py  → 权限校验、令牌管理
- file_service.py      → 统一文件读写
- ownership_rule.py    → 文件所有权规则
- code_commit_rule.py  → 代码提交规则

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class SecurityService(SuriService):
    """
    安全与文件服务 — 平台的"守门人"
    
    任何文件写入操作都必须携带 operator + approval_token，
    经过此服务校验后方可执行。
    """
    
    def __init__(self):
        super().__init__("suri-security")
    
    def on_startup(self):
        """加载权限规则"""
        pass
    
    def on_run(self):
        """启动 gRPC 服务器"""
        pass
    
    def on_shutdown(self):
        pass
    
    def on_persist_state(self):
        """保存待处理审批"""
        pass
    
    def on_restore_state(self):
        """恢复待处理审批"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
