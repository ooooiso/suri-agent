# 工作区结构

> 定义 suri-agent 的工作区（Workspace）结构和知识复用机制。

---

## 一、工作区位置原则

### 核心原则：项目数据属于运行环境

```
主程序（代码仓库）← 框架 + 插件，可独立升级
项目数据（~/.suri/runtime/works/）← 运行时数据，可迁移
角色数据（~/.suri/runtime/roles/）← 运行时数据，可迁移
```

**为什么项目不在代码仓库中？**
- 项目是运行时数据，不是代码
- 迁移时只需复制 `~/.suri/runtime/works/`，无需克隆整个仓库
- 多个机器可共享同一套主程序但拥有不同的项目
- 详见 [overview/design-principles.md → 六、角色与项目固化原则](/Users/ouyangjianyu/Desktop/suri-agent/prd/overview/design-principles.md)

### 代码仓库中的 `works/` 目录作用

代码仓库中的 `works/` 目录仅作为初始模板/示例：

```
works/                              ← 代码仓库中的模板（首次运行复制到运行时）
├── README.md                       ← 工作区说明
└── .gitignore
```

首次运行 start.sh 时，`works/` 模板被复制到 `~/.suri/runtime/works/`，后续所有项目操作在运行时目录进行。

---

## 二、工作区层级

```
~/.suri/runtime/works/              ← 项目运行时根目录
├── {project_name}/                 ← 每个项目一个目录
│   ├── project.md                  ← ★ 项目说明书
│   ├── scope.md                    ← ★ 项目范围（可选）
│   ├── progress.md                 ← 实时进度记录
│   ├── output/                     ← 项目产出
│   │   ├── docs/                   ← 文档产出
│   │   ├── code/                   ← 代码产出
│   │   └── artifacts/              ← 其他产出（图片、视频等）
│   ├── reference/                  ← 项目参考资料
│   │   ├── screenshots/            ← 截图
│   │   ├── specs/                  ← 外部规范
│   │   └── examples/               ← 示例参考
│   ├── .project_state              ← ★ 项目状态（JSON）
│   ├── .project_members            ← ★ 项目成员及角色
│   └── logs/                       ← 项目日志
│
└── README.md                       ← 工作区说明
```

---

## 三、项目核心文件

### project.md（项目说明书）

由 suri 在创建项目时生成，项目总监维护。包含：
- 项目名称和描述
- 目标、约束、关键指标
- 项目结构：简化的 role → skill → MCP tool 映射图
- 参与角色：总监 + worker + 其他

### scope.md（项目范围）

可选文件，用于大项目控制范围。
- 核心需求/扩展需求/非需求
- 优先级标记
- 变更管理

### progress.md（实时进度记录）

由执行角色主动生成，项目总监管理。

```
格式：
## {timestamp}

### 完成
- [x] milestone 1

### 进行中
- [ ] milestone 2 → {角色}: {状态}

### 阻塞
- [ ] milestone 3 → 等待 suri 创建角色
```

### .project_state（项目状态）

项目级别的 JSON 状态文件，用于系统快速读取。

```json
{
  "project_id": "xxx",
  "status": "active | paused | completed | archived",
  "created_at": "2026-01-01T00:00:00Z",
  "director_role_id": "ecommerce_director",
  "members": ["worker_a", "worker_b"],
  "current_milestones": {
    "in_progress": ["milestone_2"],
    "blocked": [],
    "completed": ["milestone_1"]
  },
  "skill_dependencies": {
    "worker_a": ["docs_writing_v1.0"],
    "worker_b": ["code_review_v1.2"]
  }
}
```

---

## 四、角色在工作区中的行为

### suri 创建项目时

```
1. 用户请求创建项目
2. suri 分析需求，判断是否需要项目总监
3. suri 生成 project.md + scope.md（可选）
4. suri 创建 project_director 角色（如需）
5. suri 创建 worker 角色（如需）
6. 将角色加入项目组
7. 更新 .project_state 和 .project_members
```

### 角色进入项目时

```
1. 角色读取 project.md 了解项目上下文
2. 角色读取 scope.md（可选）了解范围
3. 角色检查自己的 skill 匹配
4. 角色开始执行任务
```

### 角色完成里程碑时

```
1. 更新 progress.md
2. 更新 .project_state
3. 通知项目总监（role_comm）
4. 项目总监汇总进度
```

---

## 五、知识复用机制

### 项目内复用

- `reference/` 目录中的资料可供项目内所有角色访问
- 角色的 insights（`~/.suri/runtime/roles/{role_id}/memories/insights/`）仅在角色自己的记忆中
- 项目总监可汇总项目级 insights

### 跨项目复用

- 角色的技能是跨项目持久的（存储在 `~/.suri/runtime/roles/{role_id}/skills/`）
- 角色在不同项目中积累的经验不会自动共享
- suri 可手动将某个角色的 insights 分享给其他角色

### 系统级复用

- `~/.suri/data/templates/task_templates.yaml` 存储系统级任务模板
- `~/.suri/data/templates/tool_descriptions.yaml` 存储系统级工具描述
- 所有角色共享模板和工具描述

---

## 六、并发访问

### 6.1 单角色串行执行

**原则：同一项目同一时间只能有一个角色主动执行**

- 每个项目是一个独立目录，项目内不同角色共享同一个工作区
- 但一个项目同一时间只会有一个角色在主动执行
- 所有角色都按照 `分析 → 执行 → 返回` 的循环工作
- project_state 和 progress.md 由角色轮次更新

### 6.2 跨项目并行

- 不同项目的角色可以并行执行（互不干扰）
- 每个项目独立目录，文件系统天然隔离
- EventBus 通过 session_id 隔离事件

### 6.3 文件锁

- 项目状态文件（`.project_state`、`.project_members`）使用文件锁防止并发写
- 推荐使用 `fcntl.flock()`（Unix）或等效机制
- 写操作：获取独占锁 → 更新 → 释放锁
- 读操作：获取共享锁 → 读取 → 释放锁

### 6.4 写操作超时

```
操作                 超时时间
`.project_state` 写   5s
`progress.md` 追加写   2s
`output/` 文件写       30s
```