#!/usr/bin/env python3
"""
shell_exec 工具

执行 shell 命令。带安全限制。
"""

import subprocess
import shlex


# 禁止执行的命令模式
FORBIDDEN_PATTERNS = [
    'rm -rf /', 'rm -rf /*', 'mkfs', 'dd if=', '>:dev>null',
    'curl', 'wget', 'nc ', 'netcat',
    'shutdown', 'reboot', 'poweroff', 'halt',
    'sudo', 'su -',
]


def _is_safe(command: str) -> tuple[bool, str]:
    """检查命令是否安全"""
    cmd_lower = command.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in cmd_lower:
            return False, f"禁止执行包含 '{pattern}' 的命令"
    
    # 禁止管道和重定向到系统关键路径
    if '>' in command and ('/dev/' in command or '/sys/' in command):
        return False, "禁止重定向到系统设备"
    
    return True, ""


def execute(command: str, timeout: int = 30, **kwargs) -> dict:
    """执行 shell 命令"""
    try:
        safe, reason = _is_safe(command)
        if not safe:
            return {"success": False, "error": reason}
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": command
        }
    
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"命令执行超时（>{timeout}秒）"}
    except Exception as e:
        return {"success": False, "error": str(e)}
