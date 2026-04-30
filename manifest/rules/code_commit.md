---
rule_id: code_commit
name: 代码/配置变更提交规范
version: "0.1.0"
owner: git_admin
last_updated: 2026-04-30
---

# 代码/配置变更提交规范

## 1. 变更报告必填字段

每次提交代码或配置变更时，必须生成包含以下字段的报告：

```yaml
commit_id: "commit_xxx"        # 唯一标识
author_role: "role_id"         # 作者角色 ID
timestamp: "2026-04-30T08:36:00Z"
reason: "变更原因（必须具体）"
changed_files:
  - path: "文件路径"
    summary: "变动摘要（增/删/改，影响范围）"
  - path: "..."
impact_analysis: |
  对现有系统、其他角色、运行中的任务的潜在影响。
approval_token: ""             # 审批通过后由 security_admin 回填
```

## 2. 提交流程

```
作者生成变更报告
    ↓
私聊提交给 security_admin
    ↓
security_admin 审核（权限、合规、影响）
    ↓
审核通过后，suri 在调度群请求用户确认
    ↓
用户回复"是"
    ↓
security_admin 回填 approval_token
    ↓
作者执行批准范围内的修改
    ↓
git_admin 记录到 changelog.md
```

## 3. 批量修改规范

- 批量修改必须**逐文件列出**，禁止模糊描述。
- 每个文件的变动必须独立说明，不得合并概括。
- 超出报告范围的文件操作将被钩子阻断。

## 4. 紧急修复

- 紧急情况下可先执行修复，但必须在 **10 分钟内** 补交变更报告。
- 紧急修复无需等待用户确认，但需 `security_admin` 事后审查。
- **超时未补交**：自动触发 `security_admin` 专项审查，限制该角色 24 小时内的新提交权限。
- 连续 3 次紧急修复将触发 `ops_admin` 和 `workflow_admin` 的专项审查。

## 5. 审计与追溯

- 所有变更报告永久保存于 `sessions/`。
- `git_admin` 负责将已执行的变更追加到 `docs/changelog.md`。
- 任何变更可在 `state.db` 中通过 `commit_id` 追溯完整上下文。
