---
tool_id: model_manager
description: 模型管理：列出/切换/分类/生成文档
permission: public
---

# model_manager 工具

> 关联代码: `suri-agent/tools/model_manager/scripts/main.py`

模型管理工具：为所有角色提供统一的模型查询、切换、分类和文档生成能力。

## 功能

| 操作 | 说明 |
|------|------|
| `list` | 列出所有已配置模型，按 `model_type` 分组 |
| `switch` | 切换默认模型 |
| `get_default` | 获取当前默认模型信息 |
| `classify` | 为所有模型重新分类（根据预置表） |
| `generate_docs` | 生成可用模型配置文档（Markdown） |

## 调用方式

```python
from core.tool_executor import ToolService

tool = ToolService(project_root, config)

# 列出模型
result = tool.execute('model_manager', {'action': 'list'})
# → {'success': True, 'data': {'groups': {'text_chat': [...], 'vision': [...]}, 'count': 3}, 'error': ''}

# 切换默认模型
result = tool.execute('model_manager', {'action': 'switch', 'model_id': 'deepseek-chat'})
# → {'success': True, 'data': {'model_id': 'deepseek-chat', 'name': 'DeepSeek Chat'}, 'error': ''}

# 重新分类
result = tool.execute('model_manager', {'action': 'classify'})
# → {'success': True, 'data': {'updated': [...], 'total': 3}, 'error': ''}

# 生成文档
result = tool.execute('model_manager', {'action': 'generate_docs'})
# → {'success': True, 'data': {'output_path': '...', 'model_count': 3}, 'error': ''}
```

## 模型分类体系

工具依赖 `suri-agent/model/manager.py` 中定义的分类体系：

| 类型 | 说明 |
|------|------|
| `text_chat` | 文本对话模型 |
| `text_completion` | 文本补全模型 |
| `image_generation` | 图片生成模型 |
| `vision` | 视觉理解模型 |
| `audio` | 语音模型 |
| `embedding` | 嵌入模型 |

新增类型时，在 `manager.py` 的 `MODEL_TYPE_DESCRIPTIONS` 中注册，然后运行 `classify` 操作。

## CLI 集成

终端中通过 `/models` 命令调用此工具的 `list` + `switch` 能力，提供交互式体验。
