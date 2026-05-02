# security_service 插件 PRD

## 定位

安全审批与权限控制插件，负责文件操作权限校验、代码变更审批、角色 Soul 文件保护、危险操作拦截。

## 功能需求

### 1. 文件所有权规则

- 路径 → 角色映射表
- `roles/{role_id}/` → 角色自身管理
- `agent_framework/` → 维护者角色（suri_dev）
- `role/suri/` → 核心角色，额外保护
- 资源目录（`resources/`）→ 平台统一管理

### 2. 权限校验

- `can_modify(role_id, path)` → bool
- 支持角色自管理、admin 全权、maintainer 代码空间、reviewer 审核权限
- 豁免路径优先（如 `resources/temp/`）

### 3. 审批流程
- 变更发起 → 安全扫描 → 用户确认 → 执行 → 审计日志
- 审批令牌（token）机制
- 超时自动失效（默认 300s）

### 4. 代码变更检查
- `pre_file_change_check()` — 变更前检查
- 静态分析危险操作
- 核心代码变更需额外确认

### 5. Soul 文件保护
- 仅 admin 类型角色可修改 Soul 文件
- 角色自身无权修改自己的 Soul
- 修改需 suri_hr 审批

## 接口定义

### 订阅事件
- `tool.call`（涉及文件写入/执行时）→ 拦截检查
- `user.command`（/approve）→ 处理审批确认

### 发布事件
- `error.security` — 权限拒绝

## 配置项

```yaml
security_service:
  approval_timeout: 300
  enable_sandbox: true
  protected_paths:
    - "agent_framework/"
    - "roles/suri/"
  exempt_paths:
    - "resources/temp/"
    - "resources/cache/"
```

## 事件 Payload Schema

### 订阅事件

#### `tool.call`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tool_name` | string | 是 | 工具名称 |
| `params` | object | 是 | 工具参数 |
| `caller_role` | string | 是 | 调用者角色 ID |
| `risk_level` | string | 否 | 风险级别预估 |

#### `user.command`（command=/approve）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `command` | string | 是 | 命令名称 |
| `args` | object | 是 | 参数，含 `token`、`decision` |
| `user_id` | string | 是 | 用户 ID |

### 发布事件

#### `error.security`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `error_code` | integer | 是 | 错误码 |
| `violation_type` | string | 是 | 违规类型：permission_denied / dangerous_op / quota_exceeded |
| `resource` | string | 是 | 被访问的资源路径 |
| `caller` | string | 是 | 调用者 ID |
| `message` | string | 是 | 拒绝原因 |

#### `security.approval_required`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `approval_id` | string | 是 | 审批单 ID |
| `requester` | string | 是 | 请求者 |
| `operation` | string | 是 | 待审批操作 |
| `timeout` | integer | 是 | 审批超时（秒）|

## 依赖关系

- 上游：suri_core、config_service
- 下游：mcp_framework（工具调用审批）、role_manager（角色创建审批）、upgrade_manager（代码变更审批）

## 生命周期

1. `init()` → 加载权限规则
2. `start()` → 标记就绪
3. `stop()` → 清理待处理审批
4. `cleanup()` → 释放锁

## 安全边界

- 自身是最高权限检查点，不可被绕过
- 审批状态持久化到 SQLite（防重启丢失）
- 异常操作记录到 error 日志
