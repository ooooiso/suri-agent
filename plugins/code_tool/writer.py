"""code_tool 写入模块 — 文件写入和追加。

安全规则（通过 security_service 执行）：
- plugins/{new_plugin}/ → 需用户审批
- plugins/{existing}/ → 需用户审批
- tests/ → 需用户审批
- roles/ → 需用户审批
- agent_framework/ → ❌ 禁止
- shared/interfaces/ → ❌ 禁止
- ~/.suri/ → ❌ 禁止
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def write_file(project_root: Path, file_path: str,
               content: str, append: bool = False) -> Dict[str, Any]:
    """写入文件。

    Args:
        project_root: 项目根目录
        file_path: 相对项目根目录的文件路径
        content: 文件内容
        append: 是否追加（True=追加，False=覆盖）

    Returns:
        {"success": True, "path": str, "action": "write"|"append"}
        或 {"error_code": int, "error_message": str}
    """
    abs_path = (project_root / file_path).resolve()
    project_root_resolved = project_root.resolve()

    # 安全检查：必须在项目根目录内
    try:
        abs_path.relative_to(project_root_resolved)
    except ValueError:
        return {
            "error_code": 4001,
            "error_message": f"路径越界: {file_path} 不在项目根目录内",
        }

    # 禁止写入的目录
    forbidden_prefixes = [
        "agent_framework/",
        "shared/interfaces/",
        ".suri/",
    ]
    for prefix in forbidden_prefixes:
        if file_path.startswith(prefix):
            return {
                "error_code": 4002,
                "error_message": f"禁止写入系统目录: {prefix}",
            }

    # 需要审批的目录
    approval_prefixes = [
        "plugins/",
        "tests/",
        "roles/",
    ]
    needs_approval = any(file_path.startswith(p) for p in approval_prefixes)

    try:
        # 确保父目录存在
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)

        action = "append" if append else "write"
        result: Dict[str, Any] = {
            "success": True,
            "path": file_path,
            "action": action,
            "needs_approval": needs_approval,
        }
        return result

    except PermissionError:
        return {
            "error_code": 4003,
            "error_message": f"无权限写入: {file_path}",
        }
    except OSError as e:
        return {
            "error_code": 4004,
            "error_message": f"写入失败: {e}",
        }


def append_file(project_root: Path, file_path: str,
                content: str) -> Dict[str, Any]:
    """追加内容到文件末尾。"""
    return write_file(project_root, file_path, content, append=True)


def create_file(project_root: Path, file_path: str,
                content: str) -> Dict[str, Any]:
    """创建新文件（如果已存在则返回错误）。"""
    abs_path = (project_root / file_path).resolve()
    if abs_path.exists():
        return {
            "error_code": 4005,
            "error_message": f"文件已存在: {file_path}",
        }
    return write_file(project_root, file_path, content)
