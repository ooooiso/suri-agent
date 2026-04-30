---
tool_id: file_compressor
name: 文件压缩器
version: "0.1.0"
developer: deploy_dev
owner: config_admin
status: active
---

# 文件压缩器

## 功能概述

对文件或目录进行压缩归档（zip/tar.gz），支持排除特定文件模式。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_path | string | 是 | 源文件或目录路径 |
| output_path | string | 是 | 输出压缩包路径 |
| format | string | 是 | zip / tar.gz |
| exclude_patterns | array | 否 | 排除的文件模式（如 ["*.log", "temp/"]） |

## 调用方式

```python
from tools.file_compressor.scripts.compressor import compress
compress(source_path, output_path, format, exclude_patterns)
```

## 安全要求

- 超过 100MB 的压缩任务需 `file_admin` 审批。
- 禁止压缩 `.env`、`state.db` 等敏感文件。
