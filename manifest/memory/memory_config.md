---
config_id: memory_config
name: 全局记忆策略
version: "0.1.0"
owner: config_admin
last_updated: 2026-04-30
---

# 全局记忆策略

## 保留策略

| 记忆类型 | 保留期限 | 存储位置 |
|---------|---------|---------|
| 全局长期记忆 | 90 天 | `memories/` + `state.db` |
| 角色私人记忆 | 90 天 | `profiles/<role>/memories/` |
| 会话记录 | 30 天 | `sessions/` + `state.db` |
| 审批消息 | 90 天 | `sessions/` |
| 日志 | 30 天 | `logs/` |

## 遗忘规则

- 超过保留期的记忆自动标记为 `archived`。
- `archived` 记忆再保留 30 天后由 `file_admin` 清理。
- 用户明确删除的记忆立即清除并记录审计日志。
- 角色可主动归档自己的私人记忆，归档后不再加载到活跃上下文。

## 跨角色共享

```yaml
cross_role_share: false  # 当前关闭
shared_topics:
  - "平台规则变更"
  - "跨部门项目上下文"
  - "用户偏好设置"
```

- 关闭时，角色只能访问自己的 `memories/` 和全局规则文件。
- 开启后，角色可按权限访问其他角色的 `memories/` 中标记为 `shared` 的内容。
- 切换 `cross_role_share` 需走 `security.md` 审批。

## 角色私人记忆

每个角色的 `profiles/<role>/memories/` 目录存放其私人长期记忆：

- 保留期限：默认跟随全局 90 天，可被角色私有配置覆盖（不得超过 90 天）。
- 访问权限：仅角色自身和 `security_admin`（审计时）可读取。
- 修改规则：角色可自由写入自己的 `memories/`，但批量清理或格式变更需走 `security.md` 审批。
- 跨角色共享：关闭时，角色间不可互相访问私人记忆；开启时，仅标记为 `shared` 的记忆可被授权角色访问。

## 覆盖规则

角色私有 Soul 或 `config` 中可覆盖以下参数：

- `personal_retention_days`（私人记忆保留天数，不得超过全局 90 天）
- `auto_archive_after`（自动归档期限）

全局策略作为默认值，角色私有配置作为覆盖值。
