---
tool_id: db_query
description: 查询角色数据库
permission: public
---

# db_query

查询角色的 SQLite 数据库。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| role_id | str | 是 | 目标角色 |
| query | str | 是 | SQL 查询语句（只读） |
