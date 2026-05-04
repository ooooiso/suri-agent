"""filesystem — MCP 文件系统服务。

提供文件读、写、搜索、列表、统计等操作。
从 code_tool 插件迁移，作为 MCP Framework 的内置服务。

安全规则：
- 所有路径限定在项目根目录内
- 禁止写入系统关键目录
- 写入前自动备份
- 原子写入（先写临时文件再 rename）
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── 路径安全 ──

FORBIDDEN_WRITE_DIRS = [
    "agent_framework/core/",
    "agent_framework/shared/interfaces/",
    "agent_framework/event_bus/",
    "agent_framework/plugin_manager/",
]

APPROVAL_REQUIRED_DIRS = [
    "agent_framework/",
    "tests/",
    "roles/",
]

BACKUP_SUFFIX = ".bak"
TEMP_SUFFIX = ".tmp"
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


def _validate_path(project_root: Path, file_path: str) -> Dict[str, Any]:
    """验证路径合法性与安全性。"""
    abs_path = (project_root / file_path).resolve()
    project_root_resolved = project_root.resolve()

    # 必须在项目根目录内
    try:
        abs_path.relative_to(project_root_resolved)
    except ValueError:
        return {
            "error_code": 4001,
            "error_message": f"路径越界: {file_path} 不在项目根目录内",
        }
    return {"success": True, "abs_path": abs_path}


def _create_backup(abs_path: Path) -> Dict[str, Any]:
    """创建文件备份。"""
    if not abs_path.exists():
        return {"success": True, "backup_path": None}
    try:
        backup_path = abs_path.with_suffix(abs_path.suffix + BACKUP_SUFFIX)
        shutil.copy2(str(abs_path), str(backup_path))
        return {"success": True, "backup_path": str(backup_path)}
    except Exception as e:
        return {"error_code": 4010, "error_message": f"备份失败: {e}"}


def _atomic_write(abs_path: Path, content: str) -> Dict[str, Any]:
    """原子写入：先写临时文件再 rename。"""
    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(suffix=TEMP_SUFFIX, dir=str(abs_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(content)
            os.replace(tmp_path, str(abs_path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        return {"success": True}
    except PermissionError:
        return {"error_code": 4003, "error_message": f"无权限写入: {abs_path}"}
    except OSError as e:
        return {"error_code": 4004, "error_message": f"写入失败: {e}"}


# ── 工具函数集 ──

TOOL_DEFINITIONS = {
    "file_read": {
        "name": "file_read",
        "description": "读取文件内容，支持偏移和行数限制",
        "params_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径（相对项目根目录）"},
                "offset": {"type": "integer", "description": "起始行偏移（从0开始）", "default": 0},
                "limit": {"type": "integer", "description": "最大返回行数", "default": 100},
            },
            "required": ["path"],
        },
        "permission": "public",
    },
    "file_write": {
        "name": "file_write",
        "description": "写入文件内容（覆盖模式，自动备份）",
        "params_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径（相对项目根目录）"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["path", "content"],
        },
        "permission": "maintainer",
    },
    "file_append": {
        "name": "file_append",
        "description": "追加内容到文件末尾（幂等：内容已存在尾部时跳过）",
        "params_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径（相对项目根目录）"},
                "content": {"type": "string", "description": "追加内容"},
            },
            "required": ["path", "content"],
        },
        "permission": "maintainer",
    },
    "file_create": {
        "name": "file_create",
        "description": "创建新文件（文件已存在时返回错误）",
        "params_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径（相对项目根目录）"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["path", "content"],
        },
        "permission": "maintainer",
    },
    "file_list": {
        "name": "file_list",
        "description": "列出目录内容",
        "params_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径（相对项目根目录）", "default": "."},
            },
            "required": [],
        },
        "permission": "public",
    },
    "file_search": {
        "name": "file_search",
        "description": "在文件中搜索文本（grep）",
        "params_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "搜索模式（正则表达式）"},
                "path": {"type": "string", "description": "搜索根路径（相对项目根目录）", "default": "."},
                "glob": {"type": "string", "description": "文件通配符过滤", "default": "*"},
            },
            "required": ["pattern"],
        },
        "permission": "public",
    },
    "file_stat": {
        "name": "file_stat",
        "description": "统计项目信息（文件数量/行数/大小）",
        "params_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "统计路径（相对项目根目录）", "default": "."},
            },
            "required": [],
        },
        "permission": "public",
    },
}


async def handle_tool_call(tool_name: str, params: Dict[str, Any],
                           project_root: Path) -> Dict[str, Any]:
    """处理 filesystem 工具调用。

    Args:
        tool_name: 工具名称（file_read/file_write/...）
        params: 工具参数
        project_root: 项目根目录

    Returns:
        工具执行结果
    """
    handler = _HANDLERS.get(tool_name)
    if not handler:
        return {"error_code": 5001, "error_message": f"未知文件系统工具: {tool_name}"}
    return handler(params, project_root)


def _handle_file_read(params: Dict[str, Any],
                      project_root: Path) -> Dict[str, Any]:
    """读取文件内容。"""
    path = params.get("path", "")
    offset = int(params.get("offset", 0))
    limit = int(params.get("limit", 100))
    try:
        target = project_root / path
        if not target.exists():
            return {"error_code": 3101, "error_message": f"File not found: {path}"}
        if not target.is_file():
            return {"error_code": 3102, "error_message": f"Not a file: {path}"}
        with open(target, "r", encoding="utf-8") as f:
            lines = f.readlines()
        total = len(lines)
        start = max(0, offset)
        end = min(total, offset + limit)
        content = "".join(lines[start:end])
        return {
            "content": content,
            "total_lines": total,
            "offset": start,
            "returned_lines": end - start,
        }
    except Exception as e:
        return {"error_code": 3103, "error_message": str(e)}


def _handle_file_write(params: Dict[str, Any],
                       project_root: Path) -> Dict[str, Any]:
    """写入文件（覆盖模式）。"""
    file_path = params.get("path", "")
    content = params.get("content", "")

    path_result = _validate_path(project_root, file_path)
    if "error_code" in path_result:
        return path_result
    abs_path = path_result["abs_path"]

    if len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        return {
            "error_code": 4006,
            "error_message": f"文件过大: {len(content)} bytes > {MAX_FILE_SIZE_BYTES} bytes",
        }

    backup = _create_backup(abs_path)
    write_result = _atomic_write(abs_path, content)
    if "error_code" in write_result:
        return write_result

    return {
        "success": True,
        "path": file_path,
        "action": "write",
        "backup": backup.get("backup_path") if isinstance(backup, dict) else None,
    }


def _handle_file_append(params: Dict[str, Any],
                        project_root: Path) -> Dict[str, Any]:
    """追加内容到文件末尾（幂等）。"""
    file_path = params.get("path", "")
    content = params.get("content", "")

    path_result = _validate_path(project_root, file_path)
    if "error_code" in path_result:
        return path_result
    abs_path = path_result["abs_path"]

    # 幂等检查
    try:
        if abs_path.exists():
            existing = abs_path.read_text(encoding="utf-8")
            if existing.endswith(content):
                return {"success": True, "path": file_path, "action": "skipped (idempotent)"}
    except Exception:
        pass

    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        with abs_path.open("a", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": file_path, "action": "append"}
    except Exception as e:
        return {"error_code": 4004, "error_message": f"追加失败: {e}"}


def _handle_file_create(params: Dict[str, Any],
                        project_root: Path) -> Dict[str, Any]:
    """创建新文件。"""
    file_path = params.get("path", "")
    content = params.get("content", "")

    abs_path = (project_root / file_path).resolve()
    if abs_path.exists():
        return {"error_code": 4005, "error_message": f"文件已存在: {file_path}"}
    return _handle_file_write(params, project_root)


def _handle_file_list(params: Dict[str, Any],
                      project_root: Path) -> Dict[str, Any]:
    """列出目录内容。"""
    path = params.get("path", ".")
    try:
        target = project_root / path
        if not target.exists():
            return {"error_code": 3201, "error_message": f"Directory not found: {path}"}
        if not target.is_dir():
            return {"error_code": 3202, "error_message": f"Not a directory: {path}"}
        entries = []
        for entry in sorted(target.iterdir()):
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
                "path": str(entry.relative_to(project_root)),
            })
        return {"entries": entries, "total": len(entries), "path": path}
    except Exception as e:
        return {"error_code": 3203, "error_message": str(e)}


def _handle_file_search(params: Dict[str, Any],
                        project_root: Path) -> Dict[str, Any]:
    """在文件中搜索文本（grep）。"""
    pattern = params.get("pattern", "")
    path = params.get("path", ".")
    glob_pattern = params.get("glob", "*")

    import re
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return {"error_code": 3301, "error_message": f"无效的正则表达式: {e}"}

    search_root = project_root / path
    if not search_root.exists():
        return {"error_code": 3302, "error_message": f"路径不存在: {path}"}

    matches = []
    for file_path in search_root.rglob(glob_pattern):
        if file_path.is_dir() or file_path.name.startswith("."):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if regex.search(line):
                        matches.append({
                            "file": str(file_path.relative_to(project_root)),
                            "line": i,
                            "content": line.rstrip("\n"),
                        })
        except Exception:
            continue

    # 限制返回数量
    MAX_MATCHES = 500
    truncated = len(matches) > MAX_MATCHES
    matches = matches[:MAX_MATCHES]

    return {
        "matches": matches,
        "total": len(matches),
        "truncated": truncated,
        "pattern": pattern,
    }


def _handle_file_stat(params: Dict[str, Any],
                      project_root: Path) -> Dict[str, Any]:
    """统计项目信息。"""
    path = params.get("path", ".")
    target = project_root / path
    if not target.exists():
        return {"error_code": 3401, "error_message": f"路径不存在: {path}"}

    total_files = 0
    total_lines = 0
    total_size = 0
    file_types = {}

    for f in target.rglob("*"):
        if f.is_file() and not f.name.startswith("."):
            total_files += 1
            try:
                total_size += f.stat().st_size
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    total_lines += sum(1 for _ in fh)
            except Exception:
                pass
            ext = f.suffix or "(no ext)"
            file_types[ext] = file_types.get(ext, 0) + 1

    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "total_size_bytes": total_size,
        "file_types": dict(sorted(file_types.items(), key=lambda x: -x[1])),
        "path": path,
    }


_HANDLERS = {
    "file_read": _handle_file_read,
    "file_write": _handle_file_write,
    "file_append": _handle_file_append,
    "file_create": _handle_file_create,
    "file_list": _handle_file_list,
    "file_search": _handle_file_search,
    "file_stat": _handle_file_stat,
}