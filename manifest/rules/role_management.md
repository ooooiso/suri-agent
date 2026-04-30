---
rule_id: role_management
name: 角色生命周期管理规则
version: "0.1.0"
owner: hr_admin
last_updated: 2026-04-30
---

# 角色生命周期管理规则

## 1. 创建角色

### 触发条件

角色创建可由以下两种方式触发：

1. **计划性创建**：`hr_admin` 根据平台发展规划主动提出。
2. **需求驱动创建**：`suri` 在处理用户需求时发现能力缺口，经用户确认后向 `hr_admin` 发起组织扩展请求。

### 步骤

1. **确定 ID**：`hr_admin` 确定全局唯一 `role_id`（小写 + 下划线）。
2. **建立文件夹**：在 `profiles/<role_id>/` 下按标准结构创建：
   - `<role_id>.md` — Soul 文件（使用 `templates/role_soul.md`）
   - `skills/skills.md` — 技能索引
   - `skills/<skill_name>/` — 具体技能包（含 `skill`、`assets/`、`references/`、`scripts/`）
   - `memories/` — 私人长期记忆目录
   - `reference/files_i_use.md` — 个人文件权限地图
3. **填写 Soul**：按模板完成人设、职责、能力边界、输入输出格式。
   - 若是需求驱动创建，Soul 中必须包含 `origin` 字段，记录该角色因哪个用户需求而创建。
4. **更新索引**：
   - 在 `function_index.md` 中新增部门条目（或添加到现有部门）。
   - 在 `docs/roles_mapping.md` 中新增角色黄页。
5. **安全审批**：整个创建过程涉及的新建文件需批量提交 `security.md` 审批流程。
6. **激活**：审批通过后，角色正式加入平台，suri 加载其 Soul 到上下文，并重新调度原需求。

### 命名规范

- role_id: 小写英文字母 + 下划线，如 `image_gen`、`security_admin`。
- 昵称: 中文或英文名，用于人类阅读。

## 2. 修改角色

- **Soul 变更**：
  1. 需走 `workflow.md` 自优化上报流程，经 `workflow_admin` 审核（评估角色定位与流程合理性）。
  2. 同时需提交 `security.md` 安全审批（确认权限范围与合规性）。
  3. 双重审核通过后，由 suri 向用户请求最终确认。
- **技能变更**：角色自身可修改技能，但涉及新增/删除技能需更新 `skills/skills.md` 并通知 suri；涉及工具调用需 `config_admin` 确认权限。
- **部门归属变更**：需同步更新 `function_index.md`，并通知原部门和新部门总监；走 `security.md` 审批。
- **权限提升**（如普通成员→总监）：需 `hr_admin` 发起，经 `security_admin` 审核，suri 向用户确认。

## 3. 注销角色

### 步骤

1. **影响评估**：`hr_admin` 评估该角色当前任务、协作关系和记忆价值。
2. **指定接任者**：
   - 若该角色为总监（`lead_role`），必须指定接任者并更新 `function_index.md`。
   - 若该角色有进行中的任务，需交接给同部门其他成员。
3. **状态标记**：将角色 Soul 中的 `status` 改为 `deprecated`。
4. **归档**：将 `profiles/<role_id>/` 整体移至 `profiles/_archived/<role_id>/`。
5. **保留期**：归档文件夹保留 **30 天**，到期后由 `file_admin` 清理。
6. **更新索引**：从 `function_index.md` 和 `docs/roles_mapping.md` 中移除或标记为已注销。

## 4. 禁止行为

- 禁止手动创建角色文件夹而不更新索引。
- 禁止删除其他角色的 `memories/` 目录。
- 禁止将已注销角色重新激活而不走完整创建流程。
