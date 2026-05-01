#!/usr/bin/env python3
"""
db_query 工具

查询角色的 SQLite 数据库（只读）。
"""

import sqlite3
from pathlib import Path


def execute(role_id: str, query: str, project_root: str = "", **kwargs) -> dict:
    """执行只读 SQL 查询"""
    try:
        root = Path(project_root) if project_root else Path.cwd()
        db_path = root / 'group' / 'central' / role_id / 'memories' / 'role.db'
        
        if not db_path.exists():
            return {"success": False, "error": f"数据库不存在: {db_path}"}
        
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            result.append({k: row[k] for k in row.keys()})
        
        conn.close()
        
        return {
            "success": True,
            "count": len(result),
            "rows": result
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}
