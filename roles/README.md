# 角色清单

> 所有角色的快速索引。suri 通过此清单查询角色能力、调度任务。
> 每个角色一个目录，包含 `soul.md`（角色定义）和 `meta.json`（元信息）。

---

## 角色列表

| 角色 ID | 昵称 | 类型 | 技能标签 | 渠道 | 状态 |
|---------|------|------|---------|------|------|
| `suri` | Suri | core | `create_role`, `maintain_system`, `schedule_tasks`, `upgrade_self`, `create_project`, `create_bot` | CLI | active |

---

## 角色元信息规范

每个角色目录下必须包含 `meta.json`：

```json
{
  "role_id": "角色唯一标识",
  "nickname": "显示名称",
  "role_type": "core | worker | project_manager",
  "version": "1.0.0",
  "status": "active | paused | archived",
  "created_at": "创建时间",
  "updated_at": "更新时间",
  "channel": {
    "type": "telegram | cli",
    "bot_token": "机器人Token（如有）",
    "group_id": "所在群组ID（如有）"
  },
  "skills": ["技能1", "技能2"],
  "project_id": "所属项目ID（如有）",
  "parent_role": "父角色ID（如有）"
}
```

---

## 角色类型说明

| 类型 | 说明 | 权限 |
|------|------|------|
| `core` | 核心调度（suri） | 修改一切 |
| `project_manager` | 项目经理 | 调度项目内角色 |
| `worker` | 普通执行者 | 调用工具和大模型 |

---

## 快速查询

### 按技能查询

```
grep -r "skills:" roles/*/meta.json
```

### 按类型查询

```
grep -r '"role_type": "worker"' roles/*/meta.json
```

### 按状态查询

```
grep -r '"status": "active"' roles/*/meta.json