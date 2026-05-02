# role_manager 插件 PRD

## 定位

角色生命周期管理插件，负责角色创建、销毁、配置管理、能力索引、技能模板管理。是角色体系的治理中心。

## 功能需求

### 1. 角色 CRUD

- 创建角色（简化流程）：
  1. 用户输入昵称 + 一句话定义
  2. suri 调用 llm_gateway 丰富 Soul 内容（职责、能力、关键词、方法论）
  3. 向用户呈现完整 Soul 草案
  4. 用户确认后，自动生成目录结构 + Soul 文件 + 默认配置
- 读取角色：解析 Soul 文件（YAML frontmatter + Markdown body）
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
- `user.command`（command=create_role）→ 创建角色（简化流程）
- `role.create_requested`（含 nickname、definition、soul_draft）→ suri 丰富后创建
- `role.created` → 更新索引
- `role.skill_suggested` → 评估技能建议，创建/更新技能模板

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

### 与 agent_registry 的边界

见 agent_registry.md「与 role_manager 的边界」。简要概括：
- **role_manager = HR**：管理角色的长期身份、Soul、技能、能力索引
- **agent_registry = 调度板**：管理任务的临时执行实例、状态跟踪、进度
- **协作**：task_planner 通过 role_manager 的能力索引匹配角色，通过 agent_registry 创建执行实例

## 生命周期

1. `init()` → 扫描现有角色、加载索引
2. `start()` → 确保核心角色存在、广播角色就绪
3. `stop()` → 保存索引状态
4. `cleanup()` → 释放文件锁

## 安全边界

- Soul 文件修改需审批（security_service）
- 核心角色（suri）禁止删除
- 角色间数据隔离
