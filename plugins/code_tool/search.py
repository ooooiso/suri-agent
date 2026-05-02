"""code_tool 搜索模块 — grep 实现。"""

from pathlib import Path
from typing import Any, Dict, List


def grep(project_root: Path, pattern: str, path: str = ".",
         glob_pattern: str = "*") -> Dict[str, Any]:
    """在文件中搜索文本。"""
    try:
        target = project_root / path if not Path(path).is_absolute() else Path(path)
        results = []

        if target.is_file():
            files = [target]
        elif target.is_dir():
            files = list(target.rglob(glob_pattern))
            files = [f for f in files if f.is_file()]
        else:
            return {"error_code": 3107, "error_message": f"Path not found: {path}"}

        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        if pattern in line:
                            rel = str(fpath.relative_to(project_root)).replace("\\", "/")
                            results.append({
                                "file": rel,
                                "line": lineno,
                                "text": line.rstrip("\n"),
                            })
                            if len(results) >= 50:
                                break
            except (UnicodeDecodeError, PermissionError):
                continue
            if len(results) >= 50:
                break

        return {"results": results, "total": len(results)}
    except Exception as e:
        return {"error_code": 3108, "error_message": str(e)}
