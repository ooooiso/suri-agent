"""
RPC 方法集合

职责：
- 定义所有暴露给 TUI 前端的 JSON-RPC 方法
- 每个方法对应一个 suri-agent 核心能力的查询或操作
- 方法名采用 suri.xxx 命名空间

设计原则：
- 只读操作直接查询服务实例
- 写操作必须经过安全校验
- 异步方法统一返回 dict 或 awaitable dict
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from suri_agent.infrastructure.config import ConfigService
from suri_agent.infrastructure.memory import MemoryService
from suri_agent.infrastructure.security import SecurityService
from suri_agent.infrastructure.filesystem import FileService
from suri_agent.core.approval import ApprovalService
from suri_agent.core.task_dispatcher import TaskService


class RPCHandler:
    """
    JSON-RPC 方法处理器
    
    初始化时注入 suri-agent 核心服务实例，
    所有 RPC 方法通过 self.services 访问底层能力。
    """
    
    def __init__(
        self,
        config: ConfigService,
        memory: MemoryService,
        security: SecurityService,
        filesystem: FileService,
        approval: ApprovalService,
        task: TaskService,
        project_root: Path
    ):
        self.config = config
        self.memory = memory
        self.security = security
        self.filesystem = filesystem
        self.approval = approval
        self.task = task
        self.project_root = project_root
        
        # 方法注册表：method_name -> handler_fn
        self._methods = self._register_methods()
    
    def _register_methods(self) -> Dict[str, Any]:
        """注册所有 RPC 方法"""
        return {
            # ---- 平台状态 ----
            'suri.getStatus': self.get_status,
            'suri.getVersion': self.get_version,
            'suri.reloadConfig': self.reload_config,
            
            # ---- 角色管理 ----
            'suri.getRoles': self.get_roles,
            'suri.getRoleDetail': self.get_role_detail,
            'suri.getRoleSkills': self.get_role_skills,
            'suri.getRoleMemories': self.get_role_memories,
            
            # ---- 任务管理 ----
            'suri.getTasks': self.get_tasks,
            'suri.getTaskDetail': self.get_task_detail,
            'suri.getTaskMessages': self.get_task_messages,
            'suri.sendMessage': self.send_message,
            
            # ---- 审批管理 ----
            'suri.getPendingApprovals': self.get_pending_approvals,
            'suri.getApprovalDetail': self.get_approval_detail,
            'suri.approve': self.approve_request,
            'suri.reject': self.reject_request,
            
            # ---- 文件浏览 ----
            'suri.getDirectoryTree': self.get_directory_tree,
            'suri.readFile': self.read_file,
            'suri.writeFile': self.write_file,
            
            # ---- 日志查询 ----
            'suri.getLogs': self.get_logs,
            
            # ---- 规则/流程查询 ----
            'suri.getRules': self.get_rules,
            'suri.getProcesses': self.get_processes,
            'suri.getModelPool': self.get_model_pool,
        }
    
    def get_method(self, name: str) -> Optional[Any]:
        """获取指定 RPC 方法"""
        return self._methods.get(name)
    
    def list_methods(self) -> List[str]:
        """列出所有可用方法"""
        return list(self._methods.keys())
    
    # ==================== 平台状态 ====================
    
    def get_status(self, **kwargs) -> Dict[str, Any]:
        """获取平台整体运行状态"""
        return {
            'platform': 'Suri',
            'version': '0.1.0',
            'status': 'running',
            'roles_count': len(self.config.list_roles()),
            'rules_count': len(self.config.list_rules()),
            'timestamp': time.time(),
        }
    
    def get_version(self, **kwargs) -> Dict[str, Any]:
        """获取版本信息"""
        return {'version': '0.1.0', 'api_version': '2.0'}
    
    def reload_config(self, **kwargs) -> Dict[str, Any]:
        """热重载所有外部配置"""
        self.config.load_all()
        return {'success': True, 'message': f'已重载 {len(self.config._registry)} 个配置文件'}
    
    # ==================== 角色管理 ====================
    
    def get_roles(self, **kwargs) -> List[Dict[str, Any]]:
        """获取所有角色列表"""
        roles = []
        for role_id in self.config.list_roles():
            entry = self.config.get_role_soul(role_id)
            if entry:
                roles.append({
                    'role_id': role_id,
                    'name': entry.meta.get('name', role_id),
                    'nickname': entry.meta.get('nickname', ''),
                    'department': entry.meta.get('department', ''),
                    'status': entry.meta.get('status', 'active'),
                })
        return roles
    
    def get_role_detail(self, role_id: str, **kwargs) -> Dict[str, Any]:
        """获取角色详细信息（Soul 完整内容）"""
        entry = self.config.get_role_soul(role_id)
        if not entry:
            return {'error': f'角色 {role_id} 不存在'}
        
        return {
            'role_id': role_id,
            'meta': entry.meta,
            'soul': entry.body,
            'skills': self._get_role_skills_list(role_id),
            'memories_count': len(self.memory.list_role_memories(role_id)),
        }
    
    def get_role_skills(self, role_id: str, **kwargs) -> List[Dict[str, Any]]:
        """获取角色技能列表"""
        return self._get_role_skills_list(role_id)
    
    def _get_role_skills_list(self, role_id: str) -> List[Dict[str, Any]]:
        """内部：读取角色的 skills.md"""
        skills_md = self.config.get_file(f'profiles/{role_id}/skills/skills.md')
        if not skills_md:
            return []
        
        # 简单解析 skills.md 中的表格
        skills = []
        for line in skills_md.body.split('\n'):
            if line.startswith('|') and 'skill' in line.lower() and '---' not in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3 and parts[1]:
                    skills.append({
                        'skill_id': parts[1],
                        'path': parts[2] if len(parts) > 2 else '',
                        'status': parts[3] if len(parts) > 3 else 'unknown',
                    })
        return skills
    
    def get_role_memories(self, role_id: str, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """获取角色私人记忆列表"""
        mem_files = self.memory.list_role_memories(role_id)
        result = []
        for mem_path in mem_files[-limit:]:
            try:
                content = self.memory.read_role_memory(role_id, mem_path)
                result.append({
                    'path': mem_path,
                    'preview': content[:500],
                    'size': len(content),
                })
            except Exception:
                continue
        return result
    
    # ==================== 任务管理 ====================
    
    def get_tasks(self, status: Optional[str] = None, limit: int = 50, **kwargs) -> List[Dict[str, Any]]:
        """获取任务列表"""
        # TODO: 从 state.db 查询任务列表
        # 当前返回模拟数据
        return []
    
    def get_task_detail(self, task_id: str, **kwargs) -> Dict[str, Any]:
        """获取任务详情"""
        task = self.memory.get_task(task_id)
        if not task:
            return {'error': f'任务 {task_id} 不存在'}
        return task
    
    def get_task_messages(self, task_id: str, limit: int = 50, **kwargs) -> List[Dict[str, Any]]:
        """获取任务的消息历史"""
        return self.memory.get_task_messages(task_id)[-limit:]
    
    def send_message(self, to: str, content: str, msg_type: str = 'text', **kwargs) -> Dict[str, Any]:
        """
        发送消息（TUI 模拟发送）
        
        Args:
            to: 接收者 role_id 或群组 ID
            content: 消息内容
            msg_type: 消息类型
        """
        # TODO: 通过 CommService 实际发送
        # 当前仅记录到数据库
        msg_id = f"ui_msg_{int(time.time())}"
        self.memory.save_message(
            message_id=msg_id,
            task_id='',
            sender='user',
            receiver=to,
            body={'type': msg_type, 'content': content}
        )
        return {'success': True, 'message_id': msg_id}
    
    # ==================== 审批管理 ====================
    
    def get_pending_approvals(self, **kwargs) -> List[Dict[str, Any]]:
        """获取待处理的审批列表"""
        # TODO: 从 ApprovalService 查询
        return []
    
    def get_approval_detail(self, approval_id: str, **kwargs) -> Dict[str, Any]:
        """获取审批详情"""
        record = self.approval.get_status(approval_id)
        if not record:
            return {'error': f'审批 {approval_id} 不存在'}
        return record
    
    def approve_request(self, approval_id: str, **kwargs) -> Dict[str, Any]:
        """批准审批请求"""
        result = self.approval.user_confirm(approval_id, '是')
        return result
    
    def reject_request(self, approval_id: str, **kwargs) -> Dict[str, Any]:
        """拒绝审批请求"""
        result = self.approval.user_confirm(approval_id, '否')
        return result
    
    # ==================== 文件浏览 ====================
    
    def get_directory_tree(self, root: str = '.', depth: int = 3, **kwargs) -> Dict[str, Any]:
        """
        获取项目目录树
        
        Args:
            root: 起始目录（相对项目根目录）
            depth: 最大深度
        """
        def build_tree(path: Path, current_depth: int) -> Dict[str, Any]:
            if current_depth > depth:
                return {'name': path.name, 'type': 'dir', 'truncated': True}
            
            node = {'name': path.name, 'type': 'dir' if path.is_dir() else 'file'}
            if path.is_dir():
                children = []
                try:
                    for child in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                        if child.name.startswith('.git'):
                            continue
                        children.append(build_tree(child, current_depth + 1))
                except PermissionError:
                    pass
                node['children'] = children
            else:
                node['size'] = path.stat().st_size
            return node
        
        target = self.project_root / root
        if not target.exists():
            return {'error': f'目录不存在: {root}'}
        
        return build_tree(target, 0)
    
    def read_file(self, rel_path: str, **kwargs) -> Dict[str, Any]:
        """读取文件内容（只读，无需审批）"""
        try:
            content = self.filesystem.read_file(rel_path)
            return {
                'path': rel_path,
                'content': content,
                'size': len(content),
            }
        except Exception as e:
            return {'error': str(e)}
    
    def write_file(self, rel_path: str, content: str, operator: str,
                   approval_token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        写入文件（受安全钩子控制）
        
        Args:
            rel_path: 相对路径
            content: 文件内容
            operator: 操作者 role_id
            approval_token: 审批令牌
        """
        return self.filesystem.write_file(rel_path, content, operator, approval_token)
    
    # ==================== 日志查询 ====================
    
    def get_logs(self, limit: int = 100, level: Optional[str] = None, **kwargs) -> List[str]:
        """获取运行日志"""
        log_path = self.project_root / 'logs' / 'suri.log'
        if not log_path.exists():
            return []
        
        lines = log_path.read_text().split('\n')
        if level:
            lines = [l for l in lines if level.upper() in l]
        return lines[-limit:]
    
    # ==================== 规则/流程查询 ====================
    
    def get_rules(self, **kwargs) -> List[Dict[str, Any]]:
        """获取所有规则列表"""
        rules = []
        for rule_id in self.config.list_rules():
            entry = self.config.get_rule(rule_id)
            if entry:
                rules.append({
                    'rule_id': rule_id,
                    'name': entry.meta.get('name', rule_id),
                    'owner': entry.meta.get('owner', ''),
                    'version': entry.meta.get('version', ''),
                })
        return rules
    
    def get_processes(self, **kwargs) -> List[Dict[str, Any]]:
        """获取所有流程列表"""
        processes = []
        # 从 config registry 中筛选 process 文件
        for rel_path, entry in self.config._registry.items():
            if 'process/' in rel_path and entry.meta.get('process_id'):
                processes.append({
                    'process_id': entry.meta.get('process_id'),
                    'name': entry.meta.get('name', ''),
                    'owner': entry.meta.get('owner', ''),
                })
        return processes
    
    def get_model_pool(self, **kwargs) -> Dict[str, Any]:
        """获取模型池信息"""
        entry = self.config.get_model_pool()
        if not entry:
            return {'error': '模型池未加载'}
        return {
            'meta': entry.meta,
            'body': entry.body,
        }
