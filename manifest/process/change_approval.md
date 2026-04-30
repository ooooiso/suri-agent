---
process_id: change_approval
name: 配置变更审批详细步骤
version: "0.1.0"
owner: security_admin
last_updated: 2026-04-30
---

# 配置变更审批详细步骤

## 适用范围

与 `security.md` 配套，适用于所有受监控文件的修改：

- 角色配置（Soul、技能、记忆）
- 工作流定义
- 平台规则与流程
- 通信配置
- 模型池配置
- 工具库代码

## 标准步骤

### Step 1: 准备变更报告

操作者（角色）按 `code_commit.md` 格式生成变更报告，明确：

- 变更原因（必须具体，禁止模糊表述）
- 受影响文件清单（逐文件列出路径和变动摘要）
- 影响分析（对系统、其他角色、运行中任务的潜在影响）

### Step 2: 所属角色发起

- 操作者必须是目标文件的**控制角色**（见 `file_ownership.md`）。
- 若非控制角色，需先获得控制角色的书面授权（在报告中附加授权声明）。

### Step 3: security_admin 审核

`security_admin`（瓦特）审核以下内容：

1. 操作者是否有权限。
2. 变更范围是否明确、无歧义。
3. 影响分析是否充分。
4. 是否符合平台规则（如 `communication_protocol.md`、`scheduling.md` 等）。

审核结果：
- **通过**：进入 Step 4。
- **驳回**：返回操作者，说明理由，可重新提交。

### Step 4: suri 请求用户确认

审核通过后，`suri` 在中台调度群向用户发送批准请求：

```
【变更审批请求】
请求者: {role_id}
变更文件: {file_list}
原因: {reason}
影响: {impact_analysis}

请回复"是"以批准执行。
```

### Step 5: 用户确认

- 用户回复 **"是"**（或等效确认）→ 进入 Step 6。
- 用户回复 **"否"** 或超时 24 小时 → 流程终止，通知操作者。

### Step 6: 执行修改

- 操作者执行报告范围内的修改。
- `pre_file_change` 钩子实时校验：文件是否在审批范围内、是否有有效的 `approval_token`。
- 超范围操作被**实时阻断**。

### Step 7: 记录日志

- `git_admin` 将变更追加到 `manifest/docs/changelog.md`。
- 变更报告永久保存于 `sessions/`。

## 紧急通道

- 紧急修复可先执行后补审批，但必须在 **10 分钟** 内补交报告。
- 连续 3 次紧急修复触发专项审查（`ops_admin` + `workflow_admin`）。
