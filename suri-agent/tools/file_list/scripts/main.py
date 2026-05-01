#!/usr/bin/env python3
"""
file_list 工具

列出指定目录下的文件和子目录。
"""

from pathlib import Path


def execute(path: str = ".", project_root: str = "", **kwargs) -> dict:
    """列出目录内容"""
    try:
        target = Path(path)
        if not target.is_absolute() and project_root:
            target = Path(project_root) / target
        
        target = target.resolve()
        
        if not target.exists():
            return {"success": False, "error": f"目录不存在: {path}"}
        
        if not target.is_dir():
            return {"success": False, "error": f"路径不是目录: {path}"}
        
        files = []
        dirs = []
        for item in target.iterdir():
            if item.name.startswith('.'):
                continue
            if item.is_dir():
                dirs.append(item.name)
            else:
                files.append(item.name)
        
        return {
            "success": True,
            "path": str(target),
            "files": sorted(files),
            "directories": sorted(dirs)
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}
