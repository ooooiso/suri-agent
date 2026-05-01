"""
测试框架工具函数

关联文档: suri-agent/tests/README.md
"""

import sys
from pathlib import Path

# 颜色常量
G = '\033[92m'
R = '\033[91m'
Y = '\033[93m'
RST = '\033[0m'


def get_project_root() -> Path:
    """
    统一计算项目根目录

    兼容 tests/、tests/unit/、tests/fullforce/ 任意层级。
    向上查找直到发现 group/ 和 suri-agent/ 目录并存的位置。
    """
    current = Path(__file__).resolve()
    # 从 framework/utils.py 向上找：framework/ -> tests/ -> suri-agent/ -> 项目根
    candidate = current.parent.parent.parent.parent
    if (candidate / "group").exists() and (candidate / "suri-agent").exists():
        return candidate
    # 回退：向上3层（从 tests/ 或 tests/unit/ 到项目根）
    fallback = current.parent.parent.parent
    if (fallback / "group").exists() and (fallback / "suri-agent").exists():
        return fallback
    raise RuntimeError(f"无法定位项目根目录，从 {current} 向上查找失败")


def ok(test_id: str, msg: str) -> None:
    """打印通过标记"""
    print(f"  {G}✓{RST} [{test_id}] {msg}")


def fail(test_id: str, msg: str) -> None:
    """打印失败标记"""
    print(f"  {R}✗{RST} [{test_id}] {msg}")


def setup_sys_path() -> None:
    """
    将 suri-agent/ 加入 sys.path，供非 pytest 测试使用

    应在测试文件顶部调用一次。
    """
    project_root = get_project_root()
    suri_agent = str(project_root / "suri-agent")
    if suri_agent not in sys.path:
        sys.path.insert(0, suri_agent)
