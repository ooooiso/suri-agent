---
rule_id: security
name: 安全审批规则
version: "0.1.0"
owner: security_admin
last_updated: 2026-04-30
---

# 安全审批规则

## 1. 监控范围

以下目录及文件的所有增、删、改操作均受本规则约束：

- `profiles/` — 所有角色实例
- `tools/` — 公共工具库
- `manifest/` — 平台主配置
- `skills/` — suri 专属技能库
- `hooks/` — 事件钩子
- `config.yaml`、`.env`、`.SOUL.md`

## 2. 审批链

任何受监控操作必须遵循以下审批链：

```
操作者生成变更报告
    ↓
提交 security_admin 审核
    ↓
审核通过后，suri 在调度群向用户请求批准
    ↓
用户必须回复"是"（或等效确认）
    ↓
执行仅限于报告中列出的文件修改
```

## 3. 变更报告必填字段

- `report_id`: 唯一标识
- `requester`: 请求角色 ID
- `reason`: 变更原因
- `file_list`: 受影响文件清单（路径 + 变动摘要）
- `impact_analysis`: 影响分析
- `timestamp`: 提交时间

## 4. 执行限制

- 仅允许修改报告中列出的文件。
- 超出范围的文件操作将被 `pre_file_change` 钩子**实时阻断**。
- 批量修改必须逐文件列出，禁止模糊描述（如"等"、"相关文件"）。

## 5. security_admin 离线代理

若 `security_admin` 超过 30 分钟未响应审批请求：

1. suri 向 `ops_admin` 发送代理审批请求。
2. `ops_admin` 有权代行安全审核（权限有效期 4 小时）。
3. 若 `ops_admin` 也同时离线，suri 直接将审批请求升级至用户（绕过安全审核，但用户需承担更高注意义务）。
4. `security_admin` 恢复后，自动同步所有代审记录并复核。

## 6. 豁免场景

以下自动操作无需审批：

- 模型自动降级（由 `model_routing.md` 触发）。
- 缓存轮转与临时文件清理（由 `file_admin` 管理的 `cache/`、`temp/`）。
- 日志自动归档（由 `logs/` 轮转策略触发）。
- 只读查询操作（如读取配置文件、查询记忆）。

## 6. 安全钩子

`hooks/pre_file_change.py` 每次文件操作前强制读取本文件和 `file_ownership.md`，校验：

1. 操作者是否有权修改目标文件。
2. 该操作是否已有有效的审批令牌（`approval_token`）。
3. 目标文件是否在审批范围内。

任何一项不通过，操作被阻断并记录安全日志。
