#!/usr/bin/env python3
"""
file_read 工具

读取指定文件的内容。
"""

from pathlib import Path


def execute(path: str, project_root: str = "", **kwargs) -> dict:
    """读取文件内容"""
    try:
        target = Path(path)
        if not target.is_absolute() and project_root:
            target = Path(project_root) / target
        
        target = target.resolve()
        
        if not target.exists():
            return {"success": False, "error": f"文件不存在: {path}"}
        
        if not target.is_file():
            return {"success": False, "error": f"路径不是文件: {path}"}
        
        content = target.read_text(encoding='utf-8')
        return {"success": True, "content": content, "path": str(target)}
    
    except Exception as e:
        return {"success": False, "error": str(e)}
