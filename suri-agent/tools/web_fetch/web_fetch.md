---
tool_id: web_fetch
description: 网页获取：获取 URL 内容/搜索关键词
permission: public
---

# web_fetch 工具

> 关联代码: `suri-agent/tools/web_fetch/scripts/main.py`

网页获取工具：为所有角色提供获取最新网络信息的能力，弥补模型知识截止日期的局限。

## 功能

| 操作 | 说明 |
|------|------|
| `fetch` | 获取指定 URL 的网页内容，提取纯文本 |
| `search` | 使用 DuckDuckGo 搜索关键词，返回结果列表 |

## 调用方式

```python
from core.tool_executor import ToolService

tool = ToolService(project_root, config)

# 获取网页内容
result = tool.execute('web_fetch', {
    'action': 'fetch',
    'url': 'https://platform.deepseek.com/docs',
    'max_length': 5000
})
# → {'success': True, 'data': {'url': '...', 'title': '...', 'text': '...'}, 'error': ''}

# 搜索关键词
result = tool.execute('web_fetch', {
    'action': 'search',
    'query': 'DeepSeek Chat 最新版本',
    'max_results': 5
})
# → {'success': True, 'data': {'query': '...', 'results': [{'title': '...', 'url': '...', 'snippet': '...'}]}, 'error': ''}
```

## 安全限制

- 只读操作，不修改任何本地文件
- 禁止访问本地地址（localhost、127.0.0.1 等）
- 仅支持 http/https 协议
- 返回内容长度默认限制 8000 字符，避免超出模型上下文
- 请求超时 15 秒

## 使用场景

- 查询最新 API 文档（如 DeepSeek、OpenAI 官方文档）
- 搜索技术问题的最新解决方案
- 获取最新产品发布信息
- 验证某个事实的最新状态

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-05-01 | 初始创建 web_fetch 工具 |
