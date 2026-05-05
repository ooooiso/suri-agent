# Wiki Service 插件 PRD

> 基于 LLM 的知识库管理插件，在项目中建立/wiki 知识笔记，由各角色在使用中自动积累和检索。

---

## 一、定位

| 项目 | 内容 |
|------|------|
| **插件 ID** | `wiki_service` |
| **层级** | 能力层 (capability) |
| **对应目录** | `agent_framework/capability/wiki_service/` |
| **核心职责** | Wiki 知识库的创建、检索、LLM 自动维护 |
| **调用方式** | 事件驱动，由角色通过事件触发 |

---

## 二、三层隔离的 Wiki 存储

Wiki Service 遵循三层上下文隔离原则：

| 上下文层 | 存储路径 | 生命周期 | 共享范围 |
|---------|---------|---------|---------|
| **Ad-hoc 层** | 无（临时对话不产生 wiki） | — | — |
| **Project 层** | `/works/{project_name}/wiki/` | 项目存续期 | 项目内的所有角色 |
| **Global 层** | `~/.suri/data/knowledge/wiki/` | 永久 | 所有角色 |

### Project 层 Wiki（核心）

```
/works/
└── {project_name}/
    └── wiki/                          # ★ 项目级 Wiki（项目内共享）
        ├── README.md                  # 项目 wiki 首页
        ├── architecture/
        │   ├── overview.md
        │   └── decisions.md
        ├── guides/
        │   ├── setup.md
        │   └── workflow.md
        └── .wiki_history/             # 版本历史（隐藏）
            └── architecture/
                └── overview/
                    ├── v1.md
                    └── v2.md
```

### Global 层 Wiki（跨项目共享）

```
~/.suri/data/knowledge/wiki/          # ★ 全局 Wiki（跨项目共享）
├── best_practices/
│   ├── python_coding.md
│   └── api_design.md
└── templates/
    ├── project_readme.md
    └── decision_log.md
```

### 项目切换时 Wiki 的自动感知

```
角色从项目 A 切换到项目 B：
    │
    ├─ 1. memory_service 切换角色.db（step 1）
    ├─ 2. role_manager 切换 context.md（step 2）
    ├─ 3. wiki_service 切换知识库路径（step 3）
    │      └─ 从 /works/project_A/wiki/ → /works/project_B/wiki/
    ├─ 4. LLM 的 system prompt 中注入新项目的 wiki 摘要
    └─ 5. 角色在新项目中只能看到项目 B 的 wiki 和全局 wiki
```

---

## 三、功能需求

### F1: Wiki 读写管理

```
提供角色对项目中/wiki 目录的知识笔记做读写操作。
开发者在项目中建立 wiki 文件，主程序可以调用权限来读取并修改 wiki。
```

- **读取**：角色请求读取指定项目的 wiki 内容，返回 markdown 格式
- **写入**：角色请求更新/创建 wiki 条目，记录变更历史
- **搜索**：全文检索 wiki 内容，支持按项目维度过滤
- **路径**：`/works/{project_name}/wiki/`

### F2: LLM 驱动的知识建议

```
主程序通过 LLM 分析角色任务执行过程中的知识沉淀，主动建议补充 wiki。
```

- 角色完成任务后，LLM 分析是否有值得记录的知识
- 生成 wiki 草稿建议
- 向 suri 或用户呈现建议，确认后写入
- 建议自动附带当前 `project_id`，确保写入正确的项目

### F3: 项目隔离

```
每个项目拥有独立的 wiki 命名空间，角色只能访问其有权项目的 wiki。
```

- 项目级权限控制（通过 security_service）
- 跨项目引用需明确授权
- 切换项目时 wiki 路径自动切换

---

## 四、接口定义

### 事件

| 事件 | 方向 | 说明 |
|------|------|------|
| `wiki.read` | 角色 → wiki_service | 读取 wiki 条目（需 project_id） |
| `wiki.write` | 角色 → wiki_service | 创建/更新 wiki 条目（需 project_id） |
| `wiki.search` | 角色 → wiki_service | 搜索 wiki 内容（可指定 project_id） |
| `wiki.suggest` | role_learner → wiki_service | 建议补充 wiki |
| `wiki.suggested` | wiki_service → suri | 呈现 wiki 建议 |

### 事件数据

**wiki.read**
```json
{
  "project_id": "ecommerce_app",
  "path": "architecture/design.md",
  "version": "latest",
  "_meta": {
    "role_id": "developer",
    "session_id": "dev_session_01"
  }
}
```

**wiki.write**
```json
{
  "project_id": "ecommerce_app",
  "path": "architecture/design.md",
  "content": "# 架构设计\n...",
  "message": "更新架构设计说明",
  "_meta": {
    "role_id": "developer",
    "task_id": "T-001"
  }
}
```

### CLI 接口

```
suri wiki list [project]          # 列出 wiki 目录
suri wiki read [project/path]     # 读取 wiki 条目
suri wiki write [project/path]    # 编辑 wiki 条目
suri wiki search [project] <query># 搜索 wiki
```

---

## 五、配置项

```yaml
wiki_service:
  base_path: "/works/{project}/wiki/"     # Project 层 Wiki 存储根路径
  global_path: "~/.suri/data/knowledge/wiki/" # Global 层 Wiki 存储路径
  format: "markdown"                      # 仅支持 markdown
  llm_suggest: true                       # 是否启用 LLM 建议
  max_suggestions_per_day: 5              # 每日最大建议数
  version_control: true                   # 是否启用版本管理
```

---

## 六、依赖关系

| 依赖插件 | 依赖原因 |
|---------|---------|
| security_service | 项目访问权限校验 |
| llm_gateway | 生成 wiki 建议草稿 |
| config_service | 读取 wiki 配置 |
| log_service | 操作日志 |
| code_tool | 文件读写操作 |

---

## 七、与 memory_service 的区别

| 维度 | memory_service | wiki_service |
|------|---------------|-------------|
| **数据范围** | 角色个体记忆（SQLite） | 项目共享知识（Markdown 文件） |
| **存储格式** | 结构化数据（事实/经验/模式） | 自然语言 Markdown |
| **访问范围** | 角色私有 | 项目内角色共享 |
| **三层感知** | Ad-hoc / Project / Global 三层 DB | Project / Global 两层 |
| **LLM 角色** | 分析记忆用于学习 | 主动建议知识沉淀 |
| **生命周期** | 随角色创建/删除 | 随项目永久保留 |
| **用户可见** | 不可见 | 用户可直接编辑 wiki 文件 |

---

## 八、安全边界

1. **项目隔离** — 角色只能读写其项目权限内的 wiki
2. **写入审批** — 敏感项目可配置写入需用户确认
3. **版本回滚** — 保留历史版本，支持回滚
4. **内容审计** — 所有写入操作记录日志
5. **_meta 校验** — 所有事件中的 project_id 必须与调用者的当前项目一致