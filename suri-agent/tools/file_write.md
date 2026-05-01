---
tool_id: file_write
description: 写入文件（需审批令牌）
permission: maintainer
---

# file_write

写入内容到指定文件。需要审批令牌。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | str | 是 | 文件路径 |
| content | str | 是 | 写入内容 |
| token | str | 是 | 审批令牌 |
