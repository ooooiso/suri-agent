#!/usr/bin/env python3
"""
file_write 工具

写入内容到指定文件。需要审批令牌（由调用方验证）。
"""

from pathlib import Path


def execute(path: str, content: str, project_root: str = "", **kwargs) -> dict:
    """写入文件内容"""
    try:
        target = Path(path)
        if not target.is_absolute() and project_root:
            target = Path(project_root) / target
        
        target = target.resolve()
        
        # 确保父目录存在
        target.parent.mkdir(parents=True, exist_ok=True)
        
        target.write_text(content, encoding='utf-8')
        
        return {
            "success": True,
            "path": str(target),
            "size": len(content.encode('utf-8'))
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}
