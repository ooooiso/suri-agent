"""code_tool 统计模块 — stat_project 实现。"""

import os
from pathlib import Path
from typing import Any, Dict


def stat_project(project_root: Path, path: str = ".") -> Dict[str, Any]:
    """统计项目信息。"""
    try:
        target = project_root / path if not Path(path).is_absolute() else Path(path)
        if not target.exists():
            return {"error_code": 3109, "error_message": f"Path not found: {path}"}

        stats = {
            "total_files": 0,
            "total_dirs": 0,
            "total_lines": 0,
            "by_extension": {},
        }

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            stats["total_dirs"] += len(dirs)

            for fname in files:
                if fname.startswith("."):
                    continue
                stats["total_files"] += 1
                fpath = Path(root) / fname
                ext = Path(fname).suffix or "(no ext)"

                if ext not in stats["by_extension"]:
                    stats["by_extension"][ext] = {"count": 0, "lines": 0}
                stats["by_extension"][ext]["count"] += 1

                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        lines = sum(1 for _ in f)
                    stats["total_lines"] += lines
                    stats["by_extension"][ext]["lines"] += lines
                except (UnicodeDecodeError, PermissionError):
                    pass

        return stats
    except Exception as e:
        return {"error_code": 3110, "error_message": str(e)}
