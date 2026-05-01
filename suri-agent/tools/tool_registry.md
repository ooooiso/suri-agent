# Suri 工具集清单

> 本文档是**纯说明文档**，描述 tools/ 目录下各工具的功能和用途。
> 
> **业务配置请见 `tool_registry.json`** — 工具权限、注册信息由代码从 JSON 读取，不从本文档解析。
> 
> 本文档的作用：帮助开发者和角色理解每个工具是做什么的，便于查阅。修改本文档**不影响**程序运行。

---

## 现有工具

| 工具名 | 说明 |
|--------|------|
| `file_read` | 读取文件内容 |
| `file_write` | 写入文件（需审批令牌） |
| `file_list` | 列出目录内容 |
| `shell_exec` | 执行 shell 命令（仅限 suri-dev） |
| `db_query` | 查询角色数据库 |
| `db_insert` | 插入数据到角色数据库 |
| `model_manager` | 模型管理：列出/切换/分类/生成文档 |
| `web_fetch` | 网页获取：获取 URL 内容/搜索关键词 |

## 权限级别说明

| 级别 | 说明 |
|------|------|
| `public` | 所有角色自动可用 |
| `maintainer` | maintainer 类型角色自动可用 |
| `<role_id>` | 仅指定角色可用 |

角色 Soul 中的 `tools` 字段只用于**显式覆盖**（白名单额外授权）。

## 工具创建规范

新工具由 `group/central/suri-dev` 创建，需遵循：

1. **单一职责** — 每个工具只做一件事
2. **输入校验** — 校验所有参数，防止注入攻击
3. **权限最小化** — 默认设为 `public`，涉及写入/执行的设为 `maintainer` 或特定角色
4. **日志记录** — 记录工具调用和结果
5. **配置分离** — 业务注册在 `tool_registry.json`，说明文档在本文档

**新增工具的操作清单：**
```
1. tools/<tool_id>/scripts/main.py    — 工具代码（必须）
2. tools/<tool_id>/<tool_id>.md      — 工具说明文档（必须）
3. tools/tool_registry.json          — 业务注册 + 权限级别（必须）
4. tools/tool_registry.md            — 本文档（说明用途，必须）
5. suri-agent.md 变更日志           — 记录变更（必须）
```

## 工具调用示例

```python
from core.tool_executor import ToolService

tool = ToolService(project_root, config)
result = await tool.execute('web_fetch', {'action': 'fetch', 'url': 'https://example.com'})
```

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-05-01 | 初始创建 |
| 2026-05-01 | **文档与业务分离**：业务注册迁移至 `tool_registry.json`，本文档恢复为纯说明文档 |
