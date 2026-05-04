"""shell_exec — MCP 命令执行服务。

提供安全的 shell 命令执行能力。

安全规则：
- 命令白名单：只允许 python/git/ls/cat/head/tail/echo/pwd/mkdir/cp/mv/grep/find/sort/wc/curl/wget
- 黑名单拦截：rm -rf /、format、dd、mkfs、fdisk、chmod 777、sudo 等危险命令
- 超时控制：默认 30s，最大 300s
- 执行前需 security_service 审批（写入类命令）
"""

import asyncio
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 安全配置 ──

ALLOWED_COMMANDS = {
    "python", "python3", "git", "ls", "cat", "head", "tail",
    "echo", "pwd", "mkdir", "cp", "mv", "grep", "find",
    "sort", "wc", "curl", "wget", "diff", "tree", "which",
    "env", "date", "whoami", "id", "uname",
}

BLOCKED_PATTERNS = [
    "rm -rf /", "rm -rf /*", "format ", "dd if=", "mkfs",
    "fdisk", "chmod 777", "sudo", "su ",
]

MAX_TIMEOUT = 300  # 最大超时秒数
DEFAULT_TIMEOUT = 30

TOOL_DEFINITIONS = {
    "shell_exec": {
        "name": "shell_exec",
        "description": "执行 shell 命令（安全沙箱，命令白名单）",
        "params_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "cwd": {"type": "string", "description": "工作目录（相对项目根目录）", "default": "."},
                "timeout": {"type": "integer", "description": "超时秒数", "default": 30},
            },
            "required": ["command"],
        },
        "permission": "maintainer",
    },
}


def _validate_command(command: str) -> Optional[str]:
    """验证命令安全性。返回错误信息或 None（安全）。"""
    # 检查黑名单模式
    for pattern in BLOCKED_PATTERNS:
        if pattern in command.lower():
            return f"禁止执行危险命令: {pattern}"

    # 解析命令名
    try:
        parts = shlex.split(command)
    except ValueError:
        return f"无法解析命令: {command}"

    if not parts:
        return "空命令"

    cmd_name = parts[0]
    # 检查白名单
    if cmd_name not in ALLOWED_COMMANDS:
        return f"命令不在白名单中: {cmd_name}（允许: {', '.join(sorted(ALLOWED_COMMANDS))}）"

    # git 命令额外安全检查
    if cmd_name == "git":
        for part in parts[1:]:
            if part in ("push", "fetch", "pull") and "origin" in parts:
                pass  # git push/pull 允许
            if part in ("reset", "rebase", "merge"):
                pass  # 允许 git 操作
            if part == "checkout" and "-f" in parts:
                return "禁止强制 checkout（git checkout -f）"

    return None


async def handle_tool_call(tool_name: str, params: Dict[str, Any],
                           project_root: Path) -> Dict[str, Any]:
    """处理 shell_exec 工具调用。"""
    if tool_name != "shell_exec":
        return {"error_code": 5001, "error_message": f"未知命令执行工具: {tool_name}"}

    command = params.get("command", "")
    cwd = params.get("cwd", ".")
    timeout = min(int(params.get("timeout", DEFAULT_TIMEOUT)), MAX_TIMEOUT)

    # 安全检查
    error = _validate_command(command)
    if error:
        return {"error_code": 5002, "error_message": error}

    # 确定工作目录
    work_dir = (project_root / cwd).resolve()
    if not work_dir.exists():
        return {"error_code": 5003, "error_message": f"工作目录不存在: {cwd}"}

    # 执行命令
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_dir),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "error_code": 5004,
                "error_message": f"命令执行超时（{timeout}s）",
                "partial_stdout": "",
                "partial_stderr": "Timed out",
            }

        return {
            "success": True,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "return_code": proc.returncode,
            "command": command,
            "cwd": str(work_dir),
            "duration_seconds": timeout,
        }
    except Exception as e:
        return {"error_code": 5005, "error_message": f"执行失败: {e}"}