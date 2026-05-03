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

## 四、生成方式

suri 通过 LLM 根据用户需求和角色模板生成 Soul 草案，流程：

```
用户需求
    │
    ▼
suri 调用 llm_gateway
    ├─ 输入：角色模板 + 用户需求
    ├─ 输出：完整的 soul.md 内容
    └─ 参数：temperature=0.7, max_tokens=2000
    │
    ▼
suri 呈现草案给用户确认
    │
    ├── 确认 → role_manager.create_role()
    ├── 修改 → 根据反馈调整
    └── 取消 → 流程终止
