# 统一订阅规则 — 项目配置单一来源约定

> 本文件定义项目中所有配置的**唯一权威来源**，其他位置全部自动推导。
> 违反本文件的修改视为不完整。

---

## 核心原则

**每个领域只有一个权威来源，其他全部自动推导。**

新增/修改时，只需修改权威来源文件，其余位置由程序运行时自动解析。

---

## 权威来源清单

| 领域 | 权威来源 | 自动推导的位置 | 说明 |
|------|---------|---------------|------|
| **工具注册** | `tools/tool_registry.json` | 角色 Soul `tools` 字段、context.py `_get_available_tools()`、权限矩阵 | 权限级别（public/maintainer/role_id）自动决定角色可用性 |
| **工具说明文档** | `tools/tool_registry.md` | 纯人类可读说明，不用于业务逻辑 | 由 `ToolSyncRule.write_markdown()` 自动生成 |
| **模型预置配置** | `model/presets.json` | manager.py 的 `DEFAULT_CAPABILITIES`、`DEFAULT_MODEL_TYPES`、`DEFAULT_COST_TIER` 等 | 新增模型只需在 JSON 中加一行 |
| **日志分类** | `logs/categories.yaml` | logger.py `CATEGORIES` | 新增分类只需改 YAML |
| **规则注册** | `rules/*.py` 文件本身 | `rules/__init__.py` `RULE_CLASSES`、context.py 规则摘要 | 自动扫描目录发现规则类 |
| **流程注册** | `process/*.py` 文件本身 | `process/__init__.py` `PROCESS_CLASSES` | 自动扫描目录发现流程类 |
| **命令列表** | `cli.py` `_COMMAND_REGISTRY` | `/help` 输出 | 新增命令只需注册到字典 |
| **角色定义** | `group/<dept>/<role>/*.md` Soul 文件 | `group/group_function.md` 角色列表、cli.py 调度逻辑 | 主程序零硬编码角色名，全部从 Soul 扫描 |

---

## 各领域的操作约定

### 1. 新增工具

**必须修改的文件（3 个）：**
1. `tools/<tool_id>/scripts/main.py` — 工具代码
2. `tools/<tool_id>/<tool_id>.md` — 工具文档
3. `tools/tool_registry.json` — 注册 + 权限级别（业务配置）

**自动推导、无需修改的位置：**
- 角色 Soul 的 `tools` 字段 — `public` 工具自动对所有角色可用
- `core/context.py` — `_get_available_tools()` 从 `tool_registry.json` 动态解析
- `tools/tools.md` — 通用描述，无需逐条列举

### 2. 新增模型预置配置

**必须修改的文件（1 个）：**
1. `model/presets.json` — 在对应字典中添加条目

**自动推导、无需修改的位置：**
- `model/manager.py` — 运行时从 JSON 加载所有字典

### 3. 新增日志分类

**必须修改的文件（1 个）：**
1. `logs/categories.yaml` — 添加分类条目

**自动推导、无需修改的位置：**
- `infrastructure/logger.py` — `CATEGORIES` 从 YAML 加载

### 4. 新增规则

**必须修改的文件（2 个）：**
1. `rules/<rule_name>.py` — 规则代码（继承 `BaseRule`，设置 `rule_id`）
2. `suri-agent.md` 变更日志 — 记录变更

**自动推导、无需修改的位置：**
- `rules/__init__.py` — `RuleEngine` 自动扫描目录发现规则类
- `core/context.py` — `_get_rule_summary()` 从规则文件 docstring 动态生成摘要
- `rules/rules.md` — 通用描述，无需逐条列举

### 5. 新增流程

**必须修改的文件（2 个）：**
1. `process/<process_name>.py` — 流程代码（继承 `BaseProcess`，设置 `process_id`）
2. `suri-agent.md` 变更日志 — 记录变更

**自动推导、无需修改的位置：**
- `process/__init__.py` — `ProcessEngine` 自动扫描目录发现流程类
- `process/process.md` — 通用描述，无需逐条列举

### 6. 新增命令

**必须修改的文件（1 个）：**
1. `access/tui/cli.py` — 添加命令处理逻辑 + 注册到 `_COMMAND_REGISTRY`

**自动推导、无需修改的位置：**
- `/help` 输出 — 从 `_COMMAND_REGISTRY` 自动生成

### 7. 新增角色（主程序零修改）

**新增角色只需在 group/ 域操作，主程序（suri-agent/）完全不需要修改。**

**必须修改的文件（2 个）：**
1. `group/<dept>/<role_id>/<role_id>.md` — 角色 Soul 文件（定义 keywords、capabilities、type、department）
2. `group/<dept>/<role_id>/` 目录结构 — memories/、reference/、skills/

**自动推导、无需修改的位置：**
- `cli.py` 调度逻辑 — `dispatch_keywords` 和 `role_keywords` 从 `ConfigService.list_roles()` 和 `get_role_keywords()` 动态获取
- `group/group_function.md` — 运行 `/sync` 命令或 `ConfigService.sync_group_function()` 自动生成完整角色索引
- 角色上下文中的技能列表 — `ConfigService.list_role_skills(role_id)` 运行时扫描 `group/<role>/skills/` 目录
- `suri-agent.md` 目录结构 — 通用描述，无需逐个列角色

---

## 禁止的行为

以下行为违反统一订阅原则，视为不完整提交：

1. ❌ 在 `tool_registry.json` 外的地方硬编码工具列表（如旧版的 `context.py TOOL_DESCRIPTIONS`）
2. ❌ 在 `presets.json` 外的地方硬编码模型配置（如旧版的 `manager.py DEFAULT_*` 字典）
3. ❌ 在 `logs/categories.yaml` 外的地方硬编码日志分类（如旧版的 `logger.py CATEGORIES`）
4. ❌ 在 `rules/__init__.py` 中手动 import 和注册规则类
5. ❌ 在 `process/__init__.py` 中手动 import 和注册流程类
6. ❌ 修改 `/help` 的打印内容而不同步 `_COMMAND_REGISTRY`
7. ❌ 在 `cli.py` 中硬编码角色名或角色关键词（必须从 `ConfigService` 动态获取）
8. ❌ 手动维护 `group/group_function.md` 的角色列表（必须由 `sync_group_function()` 自动生成）
9. ❌ 将纯介绍 `.md` 文件用于业务逻辑（如从 `group_function.md` 读取部门数据、从 `tool_registry.md` 读取权限）。业务配置必须使用独立文件（`.json` / `.yaml`）或直接从 Soul 文件扫描

---

## 事件记录

| 日期 | 变更 |
|------|------|
| 2026-05-01 | 建立统一订阅规则，重构 7 个逐一同步点位为自动推导 |
| 2026-05-01 | 工具注册：引入权限级别（public/maintainer/role_id），角色 Soul 不再需要逐个列工具 |
| 2026-05-01 | 模型配置：`manager.py` 5 个硬编码字典 → `presets.json` 单一来源 |
| 2026-05-01 | 日志分类：`logger.py` CATEGORIES → `logs/categories.yaml` 配置文件 |
| 2026-05-01 | 规则注册：`rules/__init__.py` 硬编码字典 → 运行时自动扫描目录 |
| 2026-05-01 | 流程注册：`process/__init__.py` 硬编码字典 → 运行时自动扫描目录 |
| 2026-05-01 | 命令路由：`cli.py` `/help` 硬编码文案 → `_COMMAND_REGISTRY` 字典自动生成 |
| 2026-05-01 | 规则摘要：`context.py` 硬编码摘要 → 从 `rules/*.py` docstring 动态生成 |
| 2026-05-01 | **文档与业务分离**：`tool_registry.md` / `group_function.md` 回归纯说明文档；业务配置迁移至 `tool_registry.json`；`ConfigService` 部门信息改为从 Soul 文件扫描 |
