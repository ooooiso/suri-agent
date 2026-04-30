---
tool_id: image_processor
name: 图像处理器
version: "0.1.0"
developer: dev_lead
owner: config_admin
status: active
---

# 图像处理器

## 功能概述

对图像进行裁剪、压缩、格式转换、基础调色等后处理操作。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| input_path | string | 是 | 输入图像路径 |
| output_path | string | 是 | 输出图像路径 |
| operation | string | 是 | crop / resize / compress / convert / adjust |
| options | object | 否 | 操作特定参数（如尺寸、质量、格式） |

## 调用方式

```python
from tools.image_processor.scripts.processor import process_image
result = process_image(input_path, output_path, operation, options)
```

## 安全要求

- 输入图像必须位于 `images/` 或 `profiles/<role>/skills/*/assets/` 下。
- 禁止处理包含敏感信息的图像（如身份证、密码截图）。
