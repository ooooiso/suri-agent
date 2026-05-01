"""
Suri 测试框架

为单元测试和全力量测试提供共享基础设施。

关联文档: suri-agent/tests/README.md
"""

from .utils import get_project_root, ok, fail, G, R, Y, RST
from .fixtures import (
    make_config_service,
    make_memory_service,
    make_security_service,
    make_logger_service,
)
from .base import BaseTest

__all__ = [
    "get_project_root", "ok", "fail", "G", "R", "Y", "RST",
    "make_config_service", "make_memory_service",
    "make_security_service", "make_logger_service",
    "BaseTest",
]
