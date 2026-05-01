---
tool_id: db_insert
description: 插入数据到角色数据库
permission: public
---

# db_insert

插入数据到角色的 SQLite 数据库。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| role_id | str | 是 | 目标角色 |
| table | str | 是 | 表名 |
| data | dict | 是 | 要插入的数据 |
