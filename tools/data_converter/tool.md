---
tool_id: data_converter
name: 数据转换器
version: "0.1.0"
developer: script_dev
owner: config_admin
status: active
---

# 数据转换器

## 功能概述

在 JSON、YAML、CSV 等格式间进行数据转换，以及基础的文本分类与关键词提取。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| input_data | string/object | 是 | 输入数据 |
| input_format | string | 是 | json / yaml / csv / text |
| output_format | string | 是 | json / yaml / csv / text |
| operation | string | 否 | convert / classify / extract_keywords |

## 调用方式

```python
from tools.data_converter.scripts.converter import convert
result = convert(input_data, input_format, output_format, operation)
```

## 安全要求

- 输入数据需脱敏，禁止包含 API Key、密码等敏感信息。
- 分类结果仅供内部调度使用，不得外发。
