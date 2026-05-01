"""
角色协同调度器

职责：
- 协调多角色之间的任务分配
- 处理跨部门协作流程
- 管理角色间的依赖关系
- 调度角色工作流
"""

from pathlib import Path
from typing import Dict, List, Any, Optional


class RoleCoordinator:
    """角色协同调度器"""
    
    def __init__(self, project_root: Path, config=None):
        self.project_root = project_root
        self.config = config  # ConfigService，用于动态读取角色 capabilities
    
    def _get_role_capabilities(self, role_id: str) -> List[str]:
        """动态获取角色能力列表（从 Soul 文件）"""
        if self.config:
            return self.config.get_role_capabilities(role_id)
        # 硬编码回退（仅用于无 config 的测试场景）
        return []
    
    def assign_task(self, task: Dict[str, Any], 
                   available_roles: List[str]) -> Dict[str, Any]:
        """
        根据任务类型和角色能力，分配任务给合适的角色
        
        Args:
            task: 任务描述（含 type, requirement, priority）
            available_roles: 可用角色列表
            
        Returns:
            分配结果（assigned_role, reason）
        """
        task_type = task.get("type", "")
        
        best_role = None
        best_score = 0
        
        for role in available_roles:
            caps = self._get_role_capabilities(role)
            score = sum(1 for c in caps if c in task_type.lower())
            if score > best_score:
                best_score = score
                best_role = role
        
        if not best_role:
            best_role = "suri"  # 默认回退到 suri
        
        return {
            "assigned_role": best_role,
            "reason": f"角色 {best_role} 最匹配任务类型 {task_type}",
            "task": task,
        }
    
    def coordinate_cross_department(self, 
                                    requester_role: str,
                                    provider_roles: List[str],
                                    task: Dict[str, Any]) -> Dict[str, Any]:
        """
        协调跨部门协作
        
        Args:
            requester_role: 需求方角色
            provider_roles: 提供方角色列表
            task: 协作任务
            
        Returns:
            协作协调结果
        """
        return {
            "success": True,
            "coordinator": "suri",
            "requester": requester_role,
            "providers": provider_roles,
            "task": task,
            "rules": [
                "需求方总监向提供方总监发起私聊请求",
                "私聊内容必须抄送 suri",
                "每 30 分钟同步进度至 suri",
            ],
            "sync_interval": 1800,
        }
    
    def resolve_dependencies(self, 
                            role_id: str,
                            required_outputs: List[str]) -> Dict[str, Any]:
        """
        解析角色执行任务的依赖关系
        
        Args:
            role_id: 当前角色
            required_outputs: 需要的输入/前置输出
            
        Returns:
            依赖解析结果
        """
        return {
            "role_id": role_id,
            "dependencies": required_outputs,
            "status": "ready" if not required_outputs else "waiting",
            "note": "依赖由 suri 统一协调，角色无需直接对接",
        }
