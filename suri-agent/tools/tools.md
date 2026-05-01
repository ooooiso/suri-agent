# tools/

> 关联代码: suri-agent/core/tool_executor.py, suri-agent/tools/tool_registry.json

公共工具库：跨角色可复用的工具集合。

角色可在技能中声明依赖并调用这些工具，无需重复实现。

## 当前工具

工具清单见 `tool_registry.md`，包含：

**已实现（有 Python 脚本）：**
- 文件操作（file_read, file_write, file_list）
- 数据库操作（db_query, db_insert）
- 模型管理（model_manager）— 列出/切换/分类/生成文档
- 网页获取（web_fetch）— 获取 URL 内容、搜索关键词
- 系统命令（shell_exec）— 仅限 suri-dev

**占位符（无实际脚本，仅文档）：**
- file_compressor、image_processor、data_converter

> **设计原则**：新增工具只需修改 `tool_registry.md` 一处注册即可生效。
> 角色权限、上下文描述全部自动推导，无需逐个修改角色 Soul 文件。
> 详见 `tool_registry.md` 的"权限级别说明"。

## 工具文档规范

每个工具目录下的 `.md` 文件必须在 YAML frontmatter 中声明：
```yaml
---
tool_id: <工具ID>
description: <功能描述>
permission: public|maintainer|<role_id>
---
```

## 事件记录

- 初始创建
- 2026-05-01: 重构权限体系，引入 `public/maintainer/role_id` 三级权限，角色 Soul 不再需要逐个列工具
- 2026-05-01: 修复 model_manager、web_fetch 工具缺少 frontmatter 导致 ConfigService 索引失败的问题
