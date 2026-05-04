"""code_tool 读取模块 — read_file 实现。"""

from pathlib import Path
from typing import Any, Dict


def read_file(project_root: Path, path: str, offset: int = 0,
              limit: int = 100) -> Dict[str, Any]:
    """读取文件内容。"""
    try:
        target = project_root / path if not Path(path).is_absolute() else Path(path)
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
