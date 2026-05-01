"""
Fixture 工厂函数

供 conftest.py 和非 pytest 测试复用，统一初始化核心服务。

关联文档: suri-agent/tests/README.md
"""

from pathlib import Path
from typing import Optional


def make_config_service(project_root: Optional[Path] = None):
    """创建并加载 ConfigService"""
    from infrastructure.config import ConfigService
    if project_root is None:
        from .utils import get_project_root
        project_root = get_project_root()
    cfg = ConfigService(project_root)
    cfg.load_all()
    return cfg


def make_memory_service(project_root: Optional[Path] = None, config=None):
    """创建 MemoryService"""
    from infrastructure.memory import MemoryService
    if project_root is None:
        from .utils import get_project_root
        project_root = get_project_root()
    if config is None:
        config = make_config_service(project_root)
    return MemoryService(project_root, config)


def make_security_service(project_root: Optional[Path] = None, config=None):
    """创建 SecurityService"""
    from infrastructure.security import SecurityService
    if project_root is None:
        from .utils import get_project_root
        project_root = get_project_root()
    if config is None:
        config = make_config_service(project_root)
    return SecurityService(project_root, config)


def make_logger_service(project_root: Optional[Path] = None):
    """创建 LoggerService"""
    from infrastructure.logger import LoggerService
    if project_root is None:
        from .utils import get_project_root
        project_root = get_project_root()
    return LoggerService(project_root)
