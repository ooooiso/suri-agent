"""
角色管理层

职责：
- 调度角色之间的协同工作
- 管理角色之间的通信
- 执行角色搭建规则

独立于 core/ 的任务调度，专注于角色层面的组织与协作。
"""

from pathlib import Path
from role.coordinator import RoleCoordinator
from role.messenger import RoleMessenger
from role.builder import RoleBuilder


class RoleManager:
    """角色管理入口"""
    
    def __init__(self, project_root: Path, config=None):
        self.project_root = project_root
        self.coordinator = RoleCoordinator(project_root, config)
        self.messenger = RoleMessenger(project_root, config=config)
        self.builder = RoleBuilder(project_root)


__all__ = ["RoleManager", "RoleCoordinator", "RoleMessenger", "RoleBuilder"]
