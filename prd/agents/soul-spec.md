# Soul 文件规范

> 定义角色灵魂文件（soul.md）的标准格式。每个角色必须有且仅有一个 Soul 文件，定义其身份、能力和边界。

---

## 一、格式

采用 YAML frontmatter + Markdown body 格式：

```yaml
---
role_id: "doc_writer"              # 角色唯一标识
nickname: "文档撰写员"              # 显示名称
role_type: "worker"                # core / worker / admin / project_director
version: "1.0.0"                   # Soul 版本
created_at: "2024-01-15T10:00:00Z" # 创建时间
updated_at: "2024-06-01T08:30:00Z" # 更新时间

# 能力清单 - 描述角色能做什么
capabilities:
  - "产品文档撰写"
  - "技术文档撰写" 
  - "需求分析"
  - "文档评审"

# 关键词 - 帮助 suri 匹配用户需求
keywords:
  - "文档"
  - "写作"
  - "需求"
  - "产品"
  - "技术"

# 技能列表
skills:
  - "document_writing"
  - "api_documentation"

# 工作方法论
methodology: "文档驱动，模板复用，持续迭代"

# 运行参数
context_window: 8000  # 上下文窗口大小
temperature: 0.7      # LLM 温度参数
---

# {nickname} - {一句话定义}

你是 {role_id}，{完整职责描述}。

## 核心职责

1. 职责1...
2. 职责2...
3. 职责3...

## 工作原则

1. 原则1...
2. 原则2...

## 示例任务

- 示例任务1：...
- 示例任务2：...
```

---

## 二、字段定义

### frontmatter 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role_id` | string | ✅ | 唯一标识，小写+下划线 |
| `nickname` | string | ✅ | 显示名称，中文 |
| `role_type` | string | ✅ | core/worker/admin/project_director |
| `version` | string | ✅ | 语义化版本 |
| `created_at` | datetime | ✅ | ISO 8601 格式 |
| `updated_at` | datetime | ✅ | ISO 8601 格式 |
| `capabilities` | string[] | ✅ | 能力清单，每个能力是一个短语 |
| `keywords` | string[] | ✅ | 搜索关键词，用于任务匹配 |
| `skills` | string[] | ❌ | 技能 ID 列表 |
| `methodology` | string | ❌ | 工作方法论描述 |
| `context_window` | int | ❌ | 默认 8000 |
| `temperature` | float | ❌ | 默认 0.7 |

### body 字段

Markdown body 中至少包含：
1. **一句话定义** — 紧跟在标题后
2. **核心职责** — 角色的主要职责清单
3. **工作原则** — 行为指导原则
4. **示例任务** — 常见任务的示例

---

## 三、命名规则

- `role_id`：小写字母 + 下划线，如 `doc_writer`, `frontend_dev`
- 文件路径：`~/.suri/runtime/roles/{role_id}/soul.md`
- 模板路径：`~/.suri/data/templates/soul_template.md`

---

## 四、完整 Soul Schema 参考

### 4.1 完整 frontmatter 字段（含可选字段）

```yaml
---
# == 基础标识（必填）==
role_id: "doc_writer"              # 唯一标识，小写+下划线
nickname: "文档撰写员"              # 显示名称
role_type: "worker"                # core / worker / admin / project_director

# == 版本管理（必填）==
version: "1.0.0"                   # 语义化版本（major.minor.patch）
created_at: "2024-01-15T10:00:00Z" # ISO 8601
updated_at: "2024-06-01T08:30:00Z" # ISO 8601
upgrade_history:                   # 升级历史（可选，追加记录）
  - version: "0.5.0"
    date: "2024-03-01"
    change: "初始创建"
  - version: "1.0.0"
    date: "2024-06-01"
    change: "正式版发布"

# == 能力声明（必填）==
capabilities:                      # 能力清单，用于能力匹配
  - "产品文档撰写"
  - "技术文档撰写"
  - "需求分析"
  - "文档评审"
keywords:                          # 搜索关键词
  - "文档"
  - "写作"
  - "需求"

# == 技能绑定（必填）==
skills:                            # 技能 ID 列表（指向 skills/{id}.json）
  - "document_writing"             # 必须对应 skills/ 下的技能文件
  - "api_documentation"            # 缺失时 role_manager 报 warning

# == 运行参数（可选）==
context_window: 8000               # 默认 8000
temperature: 0.7                   # 默认 0.7
max_tokens_per_response: 4096      # 单次响应最大 token，默认 4096

# == 资源限制（可选）==
resource_limits:                   # 覆盖系统默认值
  cpu_time_seconds: 300            # 单任务 CPU 时间，默认 300
  memory_mb: 512                   # 单任务内存限制，默认 512

# == 通信偏好（可选）==
communication:
  max_concurrent_messages: 5       # 最大并发消息数
  response_timeout_seconds: 60     # 消息响应超时

# == 生命周期（可选）==
lifecycle:
  status: "active"                 # active / paused / archived / deprecated
  auto_archive_days: 90            # 无活动自动归档天数（默认 90）
  last_active_at: "2024-06-01T08:30:00Z"  # 最后活跃时间
---
```

### 4.2 额外字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `upgrade_history` | array | ❌ | [] | 版本升级记录，每次修改 soul.md 追加一条 |
| `max_tokens_per_response` | int | ❌ | 4096 | 单次 LLM 响应最大 token 数 |
| `resource_limits` | object | ❌ | 系统默认 | 覆盖系统级资源限制 |
| `resource_limits.cpu_time_seconds` | int | ❌ | 300 | 单任务 CPU 时间上限 |
| `resource_limits.memory_mb` | int | ❌ | 512 | 单任务内存上限 |
| `communication` | object | ❌ | 系统默认 | 通信相关参数 |
| `communication.max_concurrent_messages` | int | ❌ | 5 | 最大并发消息数 |
| `communication.response_timeout_seconds` | int | ❌ | 60 | 消息响应超时 |
| `lifecycle` | object | ❌ | — | 生命周期管理 |
| `lifecycle.status` | string | ❌ | "active" | active / paused / archived / deprecated |
| `lifecycle.auto_archive_days` | int | ❌ | 90 | 无活动自动归档天数 |
| `lifecycle.last_active_at` | datetime | ❌ | — | 最后活跃时间 |

---

## 五、生成方式

suri 通过 LLM 根据用户需求和角色模板生成 Soul 草案，流程：

```
用户需求
    │
    ▼
suri 调用 llm_gateway
    ├─ 输入：角色模板 + 用户需求
    ├─ 输出：完整的 soul.md 内容（含 frontmatter）
    └─ 参数：temperature=0.7, max_tokens=2000
    │
    ▼
suri 呈现草案给用户确认
    │
    ├── 确认 → role_manager.create_role()
    ├── 修改 → 根据反馈调整
    └── 取消 → 流程终止
```

### 升级流程（Soul 更新）

```
升级触发（role_learner 建议 / suri 主动 / 用户要求）
    │
    ▼
suri 生成 Soul 更新方案（新版本 soul.md）
    │
    ▼
用户确认
    │
    ├── 确认 → role_manager.update_soul()
    │          ├── 备份当前 soul.md 到 ~/.suri/backup/soul/{role_id}_v{old_version}.md
    │          ├── 写入新 soul.md
    │          ├── 追加 upgrade_history
    │          └── 广播 role.soul_updated（或 role.skill_added/role.skill_removed）
    ├── 修改 → 调整
    └── 取消 → 流程终止
```