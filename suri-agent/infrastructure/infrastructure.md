# infrastructure/

> 关联代码: suri-agent/infrastructure/config.py, suri-agent/infrastructure/memory.py, suri-agent/infrastructure/security.py, suri-agent/infrastructure/filesystem.py, suri-agent/infrastructure/logger.py

基础设施层：平台的基础能力支撑。

提供配置加载、记忆存储、安全校验、文件操作和通用工具函数。

## 功能

- 配置加载器（扫描并解析所有 .md 配置文件）
- 记忆服务（SQLite 读写、上下文检索）
- 安全服务（权限校验、审批令牌管理）
- 文件服务（带安全拦截的文件操作）
- 通用工具函数

## ConfigService 角色 introspection 接口

新增方法，支持从 Soul 文件 frontmatter 动态读取角色元数据：

| 方法 | 说明 |
|------|------|
| `get_role_capabilities(role_id)` | 读取 `capabilities` 字段 |
| `get_role_output_channels(role_id)` | 读取 `output_channels` 字段 |
| `get_role_output_path(role_id)` | 读取 `output_path` 字段 |
| `get_role_type(role_id)` | 读取 `type` 字段（V2.0） |
| `get_roles_by_type(role_type)` | 按类型查找所有角色实例（V2.0） |
| `get_role_nickname(role_id)` | 读取 `nickname` 字段，回退到 `name` 或 `role_id`（V2.0） |
| `resolve_role_id(raw_role_id)` | 统一解析角色标识，支持别名自动转换（V2.0） |
| `list_roles(include_aliases=True)` | 列出所有角色，可选包含旧版别名（V2.0） |
| `ensure_core_roles()` | 自动重建缺失的核心角色 Soul 文件（V2.0） |

新增角色只需在 Soul frontmatter 中声明这些字段，无需修改代码。

## MemoryService 经验日志（V2.0/V3.0）

| 方法 | 说明 |
|------|------|
| `save_experience(role_id, task_id, action, result, feedback, tags)` | 保存角色经验卡片 |
| `get_experiences(role_id, limit, tag_filter)` | 查询角色经验日志，支持按标签过滤 |
| `get_experience_stats(role_id)` | 获取角色经验统计（总经验数、近7天数） |

经验日志是角色进化基础设施，用于任务类比检索和效率提升。

## SecurityService 核心角色保护（V2.0）

| 方法 | 说明 |
|------|------|
| `is_core_role(role_id)` | 检查是否为核心角色（不可删除） |
| `check_permission(operator, target_path)` | 检查操作者是否有权修改目标路径 |
| `pre_file_change_check(operator, target_path, approval_token)` | 文件修改前的综合检查（权限 + 审批） |

核心角色（suri, suri_dev, suri_hr, suri_review, suri_stats）的 Soul 文件受保护，仅 `suri_dev`（maintainer 类型）可修改。

## 事件记录

- 初始创建
- **安全服务修复**：`SecurityService.pre_file_change_check()` 调整检查顺序，豁免路径（resources/cache/、resources/temp/ 等）优先于权限检查，确保临时操作不被误拦截
- **P0 调度规则改造**：新增 `get_role_capabilities()`、`get_role_output_channels()`、`get_role_output_path()` 方法，支持全动态角色配置
- **V2.0 角色类型系统**：新增 `get_role_type()`、`get_roles_by_type()`、`resolve_role_id()`、`get_role_nickname()` 方法
- **V2.0 别名兼容**：`_ROLE_ALIASES` 映射支持旧名（如 `analyst`）自动解析为新名（`suri_stats`）
- **V2.0 核心角色保护**：`SecurityService.is_core_role()` 五大核心角色不可删除
- **V2.0 自动重建**：`ConfigService.ensure_core_roles()` 缺失时自动从模板重建 Soul 文件
- **V2.0 经验日志**：`MemoryService.save_experience()` 支持角色任务经验记录，按标签过滤检索
- **V3.0 经验保存自动化**：`cli.py` 的 `_summarize_result()` 和 `_summarize_multi_result()` 自动调用 `save_experience()` 保存各角色经验
