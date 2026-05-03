# role_manager 插件 PRD

## 定位

角色生命周期管理插件，负责角色创建、销毁、配置管理、能力索引、技能模板管理。是角色体系的治理中心。

## 功能需求

### 1. 角色 CRUD

- 创建角色（简化流程）：
  1. 用户输入昵称 + 一句话定义
  2. suri 调用 llm_gateway 丰富 Soul 内容（职责、能力、关键词、方法论）⏸️ 迭代 2 自动丰富
  3. 向用户呈现完整 Soul 草案 ⏸️ 迭代 2
  4. 用户确认后，自动生成目录结构 + Soul 文件 + 默认配置 ✅
- 读取角色：解析 Soul 文件（YAML frontmatter + Markdown body）✅
- 更新角色：修改 Soul 文件（需审批流程）
- 删除角色：归档到 `_archived/`，保留 30 天后清理

### 2. 目录初始化

创建角色时自动生成：
```
roles/{role_id}/
├── soul.md               # Soul 文件
├── memories/
│   ├── role.db           # SQLite 记忆库
│   └── insights/         # 学习洞察
├── skills/               # 角色技能
├── scripts/              # 角色脚本
├── reference/            # 参考资料
└── output/               # 输出文件
```

### 3. 能力索引
- 扫描所有角色 Soul 文件，生成角色能力清单
- 关键词提取（keywords + capabilities）
- 角色类型索引（role_type: core/worker/admin/project_director）

### 4. 别名管理
- 支持角色别名映射（旧名 → canonical id）
- 别名解析统一入口

### 5. 技能模板管理
- 提供技能模板库（由 suri_hr 维护）
- 角色创建时可选继承模板
- 技能索引自动扫描

## 接口定义

### 订阅事件
- `user.input` → 代理 suri 角色处理：读取 Soul → 组装 system prompt → 发布 `llm.request`
- `user.command`（command=create_role / role.list）→ 创建角色或列出角色
- `role.create` → 直接创建角色（含 name、role_type、identity 等字段）

### 发布事件
- `role.created` / `role.destroyed`
- `role.skill_invoked`

## 配置项

```yaml
role_manager:
  role_base: "roles/"
  archive_base: "_archived/"
  default_skills: []
  auto_rebuild_core_roles: true
  soul_generation:
    model: "gpt-4o-mini"       # Soul 丰富用模型
    enable_auto_enrich: true   # 自动丰富 Soul 内容
```

## 事件 Payload Schema

### 订阅事件

#### `user.command`（command=create_role）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `command` | string | 是 | "create_role" |
| `args` | object | 是 | 参数，含 `nickname`、`definition` |
| `user_id` | string | 是 | 用户 ID |

#### `role.created`
触发更新索引，payload 同发布事件。

#### `role.create_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `nickname` | string | 是 | 角色昵称 |
| `definition` | string | 是 | 一句话定义 |
| `soul_draft` | string | 是 | suri 生成的完整 Soul 内容 |
| `user_id` | string | 是 | 用户 ID |

### 发布事件

#### `role.created`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role_id` | string | 是 | 角色 ID |
| `nickname` | string | 是 | 角色昵称 |
| `role_type` | string | 是 | 角色类型：core / worker / admin / project_director |
| `created_at` | string | 是 | 创建时间 |
| `soul_path` | string | 是 | Soul 文件路径 |

#### `role.destroyed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role_id` | string | 是 | 角色 ID |
| `destroyed_at` | string | 是 | 销毁时间 |
| `archived_path` | string | 否 | 归档路径 |

#### `role.skill_invoked`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role_id` | string | 是 | 角色 ID |
| `skill_name` | string | 是 | 技能名称 |
| `invoked_at` | string | 是 | 调用时间 |

## 依赖关系

- 上游：suri_core、config_service
- 下游：memory_service（初始化 role.db）、security_service（审批）、task_planner（获取角色信息）

## 角色类型

role_manager 管理以下角色类型分类：

| 类型 | `role_type` | 数量限制 | 是否可删除 | 典型示例 |
|------|-------------|---------|-----------|----------|
| **核心调度** | `core` | 唯一 | ❌ 不可删除 | suri |
| **工作角色** | `worker` | 不限 | ✅ 可删除 | 前端开发、文档撰写员 |
| **项目总监** | `project_director` | 不限 | ✅ 可删除 | 项目总监 |
| **管理角色** | `admin` | 不限 | ✅ 可删除 | 系统管理员 |

### 核心调度（core）— 唯一实例 suri

```
role_type: core, 数量：唯一, 可删除：❌
角色 ID 保留：suri（系统保留，不可被其他角色占用）
```

**suri 的职责**：判断用户需求 → 找到合适角色 → 协调任务 → 维护系统
**suri 不执行**：任何业务任务（写文档、写代码、数据分析等）
**suri 的特殊权限**：创建/删除角色、管理插件、升级自身、访问所有状态

### 工作角色（worker）

worker = 业务执行者：
- 接收 suri 分配的任务，分析需求、调用能力（插件/MCP/LLM）执行
- 自学自增技能，与其他角色协作通信
- **权限限制**：不能删除其他角色、不能修改系统配置、不能管理插件

### 项目总监（project_director）

project_director = 项目协调者：
- 接收项目，分解子任务，调度多个 worker 协作
- 监控进度，解决冲突和依赖，汇总交付物
- **权限**：调用 task_planner / task_scheduler / role_comm，请求 suri 创建新角色

### 管理角色（admin）

admin = 系统管理者：
- 角色管理（查看/停用/归档）、配置管理、安全审计、日志查看
- **权限限制**：不能删除 core 角色、不能修改插件代码、不能创建角色

### 角色类型选择决策树

```
创建角色时
├─ 系统调度需求？ → core（仅 suri）
├─ 项目协调需求？ → project_director
├─ 系统管理需求？ → admin
└─ 业务执行需求？ → worker
```

## 角色生命周期

role_manager 管理角色从创建到销毁的完整生命周期：

```
角色创建（suri 提案 → 用户确认 → role_manager.create_role()）
    │
    ▼
角色就绪（等待 suri 分配任务）
    │
    ▼
任务执行（循环：接收→分析→执行→返回→学习）
    │
    ├── 角色升级
    └── 角色停滞/异常 → interrupt_handler 介入
    │
    ▼
角色删除（suri 或用户发起）
    │
    ▼
数据归档（_archived/{role_id}/，保留30天自动清理）
```

### 状态定义

| 状态 | 说明 | 能否接收任务 | 能否自学 |
|------|------|------------|---------|
| `created` | 刚创建，正在初始化 | ❌ | ❌ |
| `ready` | 就绪，等待任务 | ✅ | ✅ |
| `busy` | 正在执行任务 | ❌ | ❌ |
| `blocked` | 被中断/受阻 | ❌ | ❌ |
| `upgrading` | 正在升级 | ❌ | ✅ |
| `archived` | 已归档 | ❌ | ❌ |
| `deleted` | 已删除 | ❌ | ❌ |

### 状态转换

```
created → ready  （初始化完成）
ready   → busy   （收到任务）
busy    → ready  （任务完成）
busy    → blocked（执行中中断/超时）
blocked → ready  （中断解决）
ready   → upgrading（升级中）
upgrading → ready（升级完成）
ready   → archived（被删除）
archived → deleted（30天后自动清理）
```

## 角色 CRUD

### 创建角色（完整流程）

**触发场景**：
1. 用户主动请求或 `/create_role` 命令
2. suri 检测到能力缺口（无角色匹配需求）
3. 现有角色（项目总监）请求创建新角色

**执行流程**：
```
用户输入昵称 + 一句话定义
    │
    ▼
suri 调用 llm_gateway 丰富 Soul 内容
├─ 昵称 → role_id（自动生成）
├─ 角色类型（默认 worker）
├─ 完整职责描述
├─ 能力清单（capabilities）
├─ 关键词（keywords）
├─ 工作方法论（methodology）
└─ 初始技能（基于需求）
    │
    ▼
向用户呈现完整 Soul 草案 → 确认/修改/取消
    │
    ▼
用户确认后：
├─ role_manager.create_role()
│   ├─ 创建目录结构
│   ├─ 写入 soul.md
│   ├─ 初始化 memories/ 数据库
│   ├─ 注册能力到能力索引
│   └─ 发布 role.created 事件
│
▼
角色就绪，可被调度
```

**角色创建信息表**：

| 输入 | 用户提供 | role_manager/LLM 生成 |
|------|---------|----------------------|
| 昵称 | ✅ 必填 | — |
| 一句话定义 | ✅ 必填 | — |
| 完整职责描述 | — | ✅ LLM 生成 |
| 能力清单 | — | ✅ LLM 生成 |
| 关键词 | — | ✅ LLM 生成 |
| 工作方法论 | — | ✅ LLM 生成 |
| 初始技能 | — | ✅ LLM 生成 |
| Soul 文件 | — | ✅ 基于以上组装 |

### 读取角色

解析 Soul 文件（YAML frontmatter + Markdown body）→ 见「Soul 解析器」章节

### 更新角色

修改 Soul 文件 → 需审批流程（security_service）

### 删除角色

```
删除发起（suri / 用户）
    │
    ├── core（suri） → 拒绝（核心角色不可删除）
    │
    └── 其他类型
        ├─ busy → 等待完成或强制中断
        └─ ready → 直接删除
        │
        ▼
    归档到 _archived/{role_id}/
    │
    ├── 从能力索引移除
    ├── 发布 role.destroyed 事件
    └── 30天后自动物理删除（cron_service）
```

### 角色存储

```yaml
~/.suri/runtime/roles/
├── suri/                 # 核心角色（不可删除）
├── doc_writer/           # 工作角色
│   ├── soul.md
│   ├── memories/
│   │   ├── role.db
│   │   └── insights/
│   ├── skills/
│   ├── scripts/
│   ├── reference/
│   └── output/
├── project_director_01/  # 项目总监
└── _archived/            # 已删除角色的归档
```

### 与 agent_registry 的边界

见 agent_registry.md「与 role_manager 的边界」。简要概括：
- **role_manager = HR**：管理角色的长期身份、Soul、技能、能力索引
- **agent_registry = 调度板**：管理任务的临时执行实例、状态跟踪、进度
- **协作**：task_planner 通过 role_manager 的能力索引匹配角色，通过 agent_registry 创建执行实例

## Soul 解析器（soul_parser.py）

负责解析 `soul.md` 的 YAML frontmatter + Markdown body 格式。

### 解析逻辑
```python
parse_soul(content: str) -> {"frontmatter": dict, "body": str}
```

**YAML frontmatter 支持字段**：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role_id` | string | 是 | 唯一标识，小写+数字+下划线 |
| `nickname` | string | 是 | 显示名称，1-50 字符 |
| `role_type` | string | 是 | core / worker / admin / project_director |
| `version` | string | 是 | 语义化版本 |
| `capabilities` | array[string] | 是 | 至少 1 项能力 |
| `keywords` | array[string] | 否 | 搜索关键词 |
| `skills` | array[string] | 否 | 已激活技能 |
| `methodology` | string | 否 | 工作方法论，≤2000 字符 |
| `context_window` | integer | 否 | 默认 8000 |
| `temperature` | float | 否 | 默认 0.7 |

**build_system_prompt()**：
- 读取 `soul.md` 的 frontmatter 和 body
- 提取 Identity / Responsibilities / Constraints / Skills 段落
- 组装为 LLM system prompt

### Soul 模板（roles/suri/soul.md）

迭代 1 提供核心角色 suri 的默认 Soul 模板，直接使用 `roles/suri/soul.md`，角色数据全部在项目根目录 `roles/` 下，纳入 Git 版本控制。

## 处理 user.input（迭代 2 解耦改造）

迭代 1 中，suri 角色尚未具备独立 Agent 执行能力，由 role_manager 代理处理 user.input。
迭代 2 解耦改造后，role_manager 不再代理 suri，改为发布 `role.context_ready` 事件：

```
user.input 事件
    │
    ▼
role_manager._on_user_input()
    │
    ├─ 追加用户消息到会话上下文
    ├─ 获取 suri 的 Soul 数据
    │
    ▼
发布 role.context_ready 事件
    payload: {
        "role_id": "suri",
        "session_id": "...",
        "soul_content": "...",
        "tool_descriptions": [...],
        "history": [...],
        "original_event": {...}
    }
    │
    ▼
suri 角色订阅 role.context_ready
    ├─ 获取 Soul 数据
    ├─ 自行构建 system prompt
    ├─ 调用 llm_gateway
    └─ 处理 LLM 响应
```

**解耦收益**：
- role_manager 不再依赖 llm_gateway
- suri 角色可以独立控制自己的 system prompt 构建逻辑
- 新增角色只需订阅 `role.context_ready` 即可获得 Soul 数据

## 生命周期

1. `init()` → 扫描现有角色、加载索引、确保 suri 存在
2. `register_events()` → 订阅 `user.input`、`user.command`、`role.create`
3. `start()` → 确保核心角色存在、广播角色就绪
4. `stop()` → 保存索引状态
5. `cleanup()` → 释放文件锁

## 迭代 1 特殊说明

> **角色代理模式**：迭代 1 中 suri 角色尚未具备独立 Agent 执行能力，`user.input` 由 role_manager 代理处理：读取 `suri/soul.md` 的 YAML frontmatter 和 body，构建 system prompt，通过 `llm.request` 调用 llm_gateway。迭代 2 引入 agent_registry 后，由真正的 suri Agent 独立订阅和处理 `user.input`。

## 热更新与解耦

### 1. Soul 模板外部化

当前 `SOUL_TEMPLATE` 硬编码在 `plugin.py` 中，新建角色时无法热更新。

**优化方案**：
- 创建 `~/.suri/data/templates/soul_template.md` 作为外部模板
- `create_role()` 从外部文件读取模板
- 保留代码内 fallback（仅当外部文件不存在时）

### 2. 工具调用说明外部化

当前 `_get_system_prompt()` 中的工具调用说明硬编码在代码中，新增工具需改代码。

**优化方案**：
- 创建 `~/.suri/data/templates/tool_descriptions.yaml`
- `_get_system_prompt()` 从外部文件读取工具说明
- 新增工具时只需修改 YAML 文件

### 3. 不再代理 suri 角色

当前 `_on_user_input()` 直接代理 suri 角色，构建 system prompt 并发布 `llm.request`。

**优化方案**：
- `_on_user_input()` 改为只提供角色数据
- 发布 `role.context_ready` 事件，由 suri 角色自己订阅
- suri 角色通过 `role.context_ready` 事件获取 Soul 数据

### 4. 热更新事件订阅

```python
def register_events(self):
    self.event_bus.subscribe("config.updated", self._on_config_updated)

async def _on_config_updated(self, event: Event):
    if event.payload.get("plugin_id") == "role_manager":
        self._load_external_templates()
        self._load_tool_descriptions()
```

## 内置角色模板

role_manager 系统内置以下角色模板，suri 创建新角色时加载为 LLM 上下文生成 Soul 草案：

| 模板 | 适用 | 说明 |
|------|------|------|
| `suri` | 核心调度 | 内置在 `roles/suri/soul.md`，不可删除 |
| `project_director` | 项目管理 | 项目中自动创建，管理多角色协作 |

### 模板使用流程

```
角色创建请求
    │
    ▼
role_manager 加载对应模板
    │
    ▼
调用 llm_gateway
  → system: "这是一份角色模板：\n{模板内容}\n\n请根据用户需求生成 Soul 草案"
  → 输出：完整的 soul.md
    │
    ▼
suri 呈现草案给用户确认
    │
    ├── 确认 → role_manager.create_role()
    ├── 修改 → 根据反馈调整
    └── 取消 → 流程终止
```

### 添加新模板
- 用户或 suri 可在 `~/.suri/data/templates/soul_template.md` 中添加新的角色模板
- 新模板配置在 `config_service` 中注册

## 安全边界

- Soul 文件修改需审批（security_service）
- 核心角色（suri）禁止删除
