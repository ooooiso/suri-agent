# 已注销角色存档区

## 说明

本目录存放已注销角色的归档文件夹，由 `hr_admin` 执行注销操作时移入。

## 保留策略

- 归档文件夹保留 **30 天**。
- 30 天后由 `file_admin` 自动清理。
- 清理前 `file_admin` 需向 `hr_admin` 确认无恢复需求。

## 目录命名规范

```
_archived/<role_id>_<注销日期>/
```

例如：`_archived/script_dev_2026-04-30/`

## 恢复流程

1. `hr_admin` 确认恢复需求。
2. 将文件夹移回 `profiles/<role_id>/`。
3. 更新 `function_index.md` 和 `roles_mapping.md`。
4. 重新激活角色 Soul 中的 `status` 字段。
5. 走安全审批流程。
