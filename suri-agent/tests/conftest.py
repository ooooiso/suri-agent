"""
pytest 共享 fixture

供所有 pytest 格式的测试文件复用。

关联文档: suri-agent/tests/README.md
"""

import sys
from pathlib import Path
import pytest

# 确保 suri-agent 在路径中
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_SURI_AGENT = str(_PROJECT_ROOT / "suri-agent")
if _SURI_AGENT not in sys.path:
    sys.path.insert(0, _SURI_AGENT)

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.logger import LoggerService


@pytest.fixture(scope="session")
def project_root():
    """项目根目录"""
    return _PROJECT_ROOT


@pytest.fixture(scope="session")
def config(project_root):
    """已加载的 ConfigService"""
    cfg = ConfigService(project_root)
    cfg.load_all()
    return cfg


@pytest.fixture
def memory(project_root, config):
    """MemoryService"""
    return MemoryService(project_root, config)


@pytest.fixture
def security(project_root, config):
    """SecurityService"""
    return SecurityService(project_root, config)


@pytest.fixture
def logger(project_root):
    """LoggerService"""
    return LoggerService(project_root)
