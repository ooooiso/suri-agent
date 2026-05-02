"""code_tool 插件 — 代码操作工具（迭代 1：只读）。"""

import os
from pathlib import Path
from typing import Any, Dict, List

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority


class CodeToolPlugin(PluginInterface):
    """代码工具插件（迭代 1 只读版）。
    
    支持的操作：
    - read_file: 读取文件内容
    - list_dir: 列出目录内容
    - grep: 在文件中搜索文本
    - stat_project: 统计项目信息
    """

    def __init__(self):
        self._event_bus = None
        self._project_root: Path = None

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._project_root = Path(__file__).parent.parent.parent

    async def start(self) -> None:
        pass

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    def register_events(self) -> None:
        self._event_bus.subscribe("tool.call", self._on_tool_call)

    def _resolve_path(self, path: str) -> Path:
        """解析路径为绝对路径。"""
        p = Path(path)
        if p.is_absolute():
            return p
        root = self._project_root or Path(__file__).parent.parent.parent
        return root / p

    def read_file(self, path: str, offset: int = 0, 
                  limit: int = 100) -> Dict[str, Any]:
        """读取文件内容。"""
        try:
            target = self._resolve_path(path)
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

    def list_dir(self, path: str = ".") -> Dict[str, Any]:
        """列出目录内容。"""
        try:
            target = self._resolve_path(path)
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
            return {"items": items, "path": str(target.relative_to(self._project_root))}
        except Exception as e:
            return {"error_code": 3106, "error_message": str(e)}

    def grep(self, pattern: str, path: str = ".", 
             glob_pattern: str = "*") -> Dict[str, Any]:
        """在文件中搜索文本。"""
        try:
            target = self._resolve_path(path)
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
                                rel = str(fpath.relative_to(self._project_root)).replace("\\", "/")
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

    def stat_project(self, path: str = ".") -> Dict[str, Any]:
        """统计项目信息。"""
        try:
            target = self._resolve_path(path)
            if not target.exists():
                return {"error_code": 3109, "error_message": f"Path not found: {path}"}
            
            stats = {
                "total_files": 0,
                "total_dirs": 0,
                "total_lines": 0,
                "by_extension": {},
            }
            
            for root, dirs, files in os.walk(target):
                # 跳过隐藏目录和 git
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

    async def _on_tool_call(self, event: Event) -> None:
        """处理 tool.call 事件。"""
        tool_name = event.payload.get("tool_name", "")
        params = event.payload.get("params", {})
        
        result = None
        
        if tool_name == "code_tool.read_file":
            result = self.read_file(
                params.get("path", ""),
                int(params.get("offset", 0)),
                int(params.get("limit", 100)),
            )
        elif tool_name == "code_tool.list_dir":
            result = self.list_dir(params.get("path", "."))
        elif tool_name == "code_tool.grep":
            result = self.grep(
                params.get("pattern", ""),
                params.get("path", "."),
                params.get("glob", "*"),
            )
        elif tool_name == "code_tool.stat_project":
            result = self.stat_project(params.get("path", "."))
        else:
            # 不是本工具的事件，忽略
            return
        
        await self._event_bus.publish(Event(
            event_type="tool.result",
            source="code_tool",
            target=event.source,
            payload={
                "tool_name": tool_name,
                "result": result,
                "request_id": event.payload.get("request_id"),
            },
            priority=Priority.NORMAL,
        ))
