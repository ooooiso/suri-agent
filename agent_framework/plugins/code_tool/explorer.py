"""code_tool 目录浏览模块 — list_dir 实现。"""

from pathlib import Path
from typing import Any, Dict, List


def list_dir(project_root: Path, path: str = ".") -> Dict[str, Any]:
    """列出目录内容。"""
    try:
        target = project_root / path if not Path(path).is_absolute() else Path(path)
        if not target.exists():
            return {"error_code": 3104, "error_message": f"Directory not found: {path}"}
        if not target.is_dir():
            return {"error_code": 3105, "error_message": f"Not a directory: {path}"}

        items = []
        for item in target.iterdir():
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })

        items.sort(key=lambda x: (x["type"] != "directory", x["name"]))
        return {"items": items, "path": str(target.relative_to(project_root))}
    except Exception as e:
        return {"error_code": 3106, "error_message": str(e)}
