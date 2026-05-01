#!/usr/bin/env python3
"""
db_insert 工具

插入数据到角色的 SQLite 数据库。
"""

import sqlite3
from pathlib import Path


def execute(role_id: str, table: str, data: dict, project_root: str = "", **kwargs) -> dict:
    """插入数据到指定表"""
    try:
        root = Path(project_root) if project_root else Path.cwd()
        db_path = root / 'group' / 'central' / role_id / 'memories' / 'role.db'
        
        if not db_path.exists():
            return {"success": False, "error": f"数据库不存在: {db_path}"}
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())
        
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor.execute(query, values)
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        
        return {
            "success": True,
            "row_id": row_id,
            "table": table
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}
