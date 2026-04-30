"""
文件系统服务

职责：
- 提供统一的文件读写接口
- 所有写操作必须经过 SecurityService 校验
- 读操作直接执行（只读不校验）

原则：主程序不直接操作文件系统，所有文件交互通过此服务。
"""

from pathlib import Path
from typing import Optional, Dict, Any
from infrastructure.security import SecurityService


class FileService:
    """
    文件服务
    
    所有写操作（create/update/delete）必须携带 operator 和 approval_token。
    读操作（read/list）无需审批。
    """
    
    def __init__(self, project_root: Path, security: SecurityService):
        self.project_root = project_root
        self.security = security
    
    def read_file(self, rel_path: str) -> str:
        """读取文件内容（只读，无需审批）"""
        path = self.project_root / rel_path
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {rel_path}")
        return path.read_text(encoding='utf-8')
    
    def read_binary(self, rel_path: str) -> bytes:
        """读取二进制文件"""
        path = self.project_root / rel_path
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {rel_path}")
        return path.read_bytes()
    
    def list_directory(self, rel_path: str) -> list[str]:
        """列出目录内容"""
        path = self.project_root / rel_path
        if not path.exists() or not path.is_dir():
            return []
        return [str(p.relative_to(self.project_root)) for p in path.iterdir()]
    
    def write_file(
        self,
        rel_path: str,
        content: str,
        operator: str,
        approval_token: Optional[str] = None,
        mode: str = 'w'
    ) -> Dict[str, Any]:
        """
        写入文件（受安全钩子控制）
        
        Args:
            rel_path: 相对项目根目录的路径
            content: 文件内容
            operator: 操作者 role_id
            approval_token: 审批令牌（写操作必需）
            mode: 写入模式 'w'(覆盖) / 'a'(追加)
            
        Returns:
            {'success': bool, 'reason': str}
        """
        # 安全校验
        allowed, reason = self.security.pre_file_change_check(
            operator, rel_path, approval_token
        )
        if not allowed:
            return {'success': False, 'reason': reason}
        
        # 执行写入
        path = self.project_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
        
        return {'success': True, 'reason': f'[通过] {reason}'}
    
    def delete_file(
        self,
        rel_path: str,
        operator: str,
        approval_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """删除文件（受安全钩子控制）"""
        allowed, reason = self.security.pre_file_change_check(
            operator, rel_path, approval_token
        )
        if not allowed:
            return {'success': False, 'reason': reason}
        
        path = self.project_root / rel_path
        if path.exists():
            path.unlink()
            return {'success': True, 'reason': f'[通过] 已删除 {rel_path}'}
        return {'success': False, 'reason': f'文件不存在: {rel_path}'}
    
    def mkdir(
        self,
        rel_path: str,
        operator: str,
        approval_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建目录（受安全钩子控制）"""
        allowed, reason = self.security.pre_file_change_check(
            operator, rel_path, approval_token
        )
        if not allowed:
            return {'success': False, 'reason': reason}
        
        path = self.project_root / rel_path
        path.mkdir(parents=True, exist_ok=True)
        return {'success': True, 'reason': f'[通过] 已创建目录 {rel_path}'}
    
    def file_exists(self, rel_path: str) -> bool:
        """检查文件是否存在"""
        return (self.project_root / rel_path).exists()
    
    def get_mtime(self, rel_path: str) -> Optional[float]:
        """获取文件修改时间"""
        path = self.project_root / rel_path
        if path.exists():
            return path.stat().st_mtime
        return None
