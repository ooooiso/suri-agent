---
version: "0.1.0"
owner: config_admin
last_updated: 2026-04-30
description: 公共工具注册索引，记录所有跨角色可复用工具
---

# 工具注册索引

## 已注册工具

| 工具 ID | 名称 | 路径 | 开发者 | 功能概述 | 调用权限 | 安全要求 |
|---------|------|------|--------|---------|---------|---------|
| image_processor | 图像处理器 | tools/image_processor/ | dev_lead | 图像裁剪、压缩、格式转换 | 设计部、资源部 | 不涉及敏感数据 |
| data_converter | 数据转换器 | tools/data_converter/ | script_dev | JSON/YAML/CSV 互转、文本分类 | 全部角色 | 输入需脱敏 |
| file_compressor | 文件压缩器 | tools/file_compressor/ | deploy_dev | 文件/目录压缩归档 | 全部角色 | 大文件需审批 |

## 注册流程

1. 开发部角色（dev_lead/script_dev/backend_dev）研发新工具。
2. 将工具放入 `tools/<tool_id>/`，包含 `tool.md`、`scripts/`、`references/`。
3. **内部测试**：由 `dev_lead` 组织测试，确保工具稳定、安全、文档完整。
4. 向 `config_admin` 提交注册申请（含功能说明、测试报告、调用权限、安全要求）。
5. `config_admin` 审核测试报告与注册申请。
6. 新工具及其注册信息需走 `security.md` 变更审批。
7. 审批通过后，`config_admin` 更新本索引，新工具上线。
8. 角色可在技能中声明依赖并调用。

## 注销流程

- 工具废弃需 `config_admin` 标记为 `deprecated`，保留 30 天后由 `file_admin` 清理。
