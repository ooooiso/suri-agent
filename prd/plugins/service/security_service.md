# security_service 插件 PRD

## 定位

**安全服务统一入口**。负责文件操作权限校验、代码变更审批、角色 Soul 文件保护、危险操作拦截、三清单审计、_meta 上下文校验。

**关键职责边界**：
- ✅ 统一管理路径白名单（所有文件操作插件共用同一白名单）
- ✅ 审批令牌机制（超时自动失效）
- ✅ 三清单变更审计（拦截→检查→放行/拒绝）
- ✅ _meta 上下文完整性校验（role_id/project_id/task_id/session_id）
- ✅ Soul 文件保护（仅 admin 可修改）
- ❌ **不直接执行文件操作**（这是 code_tool 的职责）
- ❌ **不直接管理代码扫描逻辑细节**（AST 扫描等安全分析由 security_scanner 子模块处理）

**设计原则**：security_service 是"安全入口"而非"安全实现"。它负责任务分发和策略执行，具体安全分析逻辑封装在细颗粒度的子模块中。

---

## 功能需求

### 1. 路径权限统一管理（取代各插件自行维护白名单）

```python
# 所有文件操作插件使用此接口查询权限，不自己维护白名单
async def can_read(self, path: str, caller_role: str) -> PermissionResult:
    """查询读取权限"""
    ...

async def can_write(self, path: str, caller_role: str, 
                    tool_call_meta: dict = None) -> PermissionResult:
    """查询写入权限"""
    ...
```

**权限结果**：
- `approved` — 允许操作
- `needs_approval` — 需要审批令牌（自动发布 `security.approval_required`）
- `denied` — 拒绝（记录审计日志）

**路径规则定义在配置文件中**（不在代码中硬编码）：
```yaml
security_service:
  path_rules:
    # 🔴 核心：永久拒绝
    - pattern: "~/.suri/**"
      permission: deny
    
    # 🔴 系统：永久拒绝
    - pattern: "/etc/**"
      permission: deny
    - pattern: "/usr/**"
      permission: deny
    
    # 🔴 框架：拒绝，需 upgrade_manager 审批豁免
    - pattern: "agent_framework/**"
      permission: deny_with_exemption
      exempt_source: "upgrade_manager"
    
    # 🟡 插件：需审批令牌
    - pattern: "agent_framework/plugins/{type}/{name}/**"
      permission: needs_approval
    
    # 🟡 角色：仅归属角色可写
    - pattern: "roles/{role_id}/soul.md"
      permission: owner_only
      owner_field: "role_id"
    
    # 🟢 普通：角色自管理或需审批
    - pattern: "roles/{role_id}/**"
      permission: self_managed
    
    # 🟢 项目：白名单路径
    - pattern: "works/{project_id}/**"
      permission: approved
    
    # 🟢 其他项目内路径
    - pattern: "**"
      permission: needs_approval_if_write
```

### 2. 文件所有权规则

- 路径 → 角色映射表
- `roles/{role_id}/` → 角色自身管理
- `agent_framework/` → 维护者角色（suri_dev），需升级审批
- `roles/suri/` → 核心角色，额外保护
- 资源目录（`resources/`）→ 平台统一管理

### 3. 审批流程

```
变更发起 → 安全扫描 → 用户确认 → 执行 → 审计日志

审批令牌机制：
  - 每次高危操作生成唯一 approval_token
  - 用户通过 /approve {token} 确认
  - 超时（300s）自动失效
  - 审批记录持久化到 SQLite（防重启丢失）
```

### 4. 三清单审计

三清单（Role/Plugin/Tool Registry）的变更需要经过安全检查：

```
三清单变更请求
    │
    ├─ 1. security_service 拦截变更事件
    ├─ 2. 检查变更来源是否授权：
    │      ├── Role Registry → 仅 role_manager 或 suri 可改
    │      ├── Plugin Registry → 仅 plugin_manager 可改
    │      └── Tool Registry → 仅 mcp_framework 可改
    ├─ 3. 检查变更内容的合法性：
    │      ├── schema 校验
    │      ├── 名称唯一性
    │      └── 引用完整性（技能引用的工具必须已注册）
    ├─ 4. 高风险变更（废弃/移除）需用户确认
    └─ 5. 通过后放行
```

审计记录字段：
```json
{
  "registry_type": "role",
  "operation": "registered",
  "object_id": "developer_v2",
  "caller": "role_manager",
  "role_id": "suri_admin",
  "session_id": "dev_session_01",
  "result": "approved",
  "timestamp": "2026-05-04T12:00:00Z"
}
```

### 5. _meta 上下文校验

所有工具调用中的 `_meta` 上下文必须通过校验：

```python
def validate_tool_call_meta(tool_call: dict) -> bool:
    """
    校验规则：
      1. _meta 必须包含 role_id、project_id、task_id、session_id
      2. role_id 必须是已注册的有效角色
      3. project_id 必须与当前会话所属项目一致（如有）
      4. session_id 必须与当前活跃会话匹配
      5. 角色在当前项目中必须有权限使用此工具
    """
    meta = tool_call.get("_meta", {})
    
    required = ["role_id", "project_id", "task_id", "session_id"]
    for field in required:
        if field not in meta:
            return False
    
    if not role_registry.exists(meta["role_id"]):
        return False
    
    if meta["project_id"] and not self._is_project_active(meta["project_id"], meta["session_id"]):
        return False
    
    return True
```

### 6. 代码变更检查
- `pre_file_change_check()` — 变更前检查
- 静态分析危险操作
- 核心代码变更需额外确认

### 7. Soul 文件保护
- 仅 admin 类型角色可修改 Soul 文件
- 角色自身无权修改自己的 Soul

---

## 接口定义

### 订阅事件
- `tool.call`（涉及文件写入/执行时）→ 拦截检查，通过后重新发布事件放行
- `user.command`（/approve）→ 处理审批确认
- `triple.registry.*`（三清单变更事件）→ 拦截审计

### 发布事件
- `tool.call` — 安全检查通过后，重新发布事件给目标插件
- `error.security` — 权限拒绝
- `security.approval_required` — 需要用户审批

---

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
  
  # 路径权限规则（从 YAML 加载，支持热更新）
  path_rules_file: "~/.suri/data/configs/path_rules.yaml"
```

---

## 内部模块划分

为了保持 security_service 可维护，内部划分为独立模块：

```
security_service/
├── __init__.py
├── manifest.json
├── plugin.py              # 插件主入口（事件路由、依赖注入）
├── permission.py          # 路径权限查询（can_read/can_write/can_modify）
├── approval.py            # 审批令牌管理（生成/验证/超时/持久化）
├── registry_auditor.py    # 三清单变更审计
├── meta_validator.py      # _meta 上下文校验
├── scanner.py             # AST 安全扫描
└── config.yaml            # 路径规则配置文件
```

**拆分收益**：
- 每个模块职责单一（< 300 行）
- 独立测试，减少耦合
- 未来可拆分为独立插件（如 security_scanner）

---

## 事件 Payload Schema

### 订阅事件

#### `tool.call`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tool_name` | string | 是 | 工具名称 |
| `params` | object | 是 | 工具参数 |
| `caller_role` | string | 是 | 调用者角色 ID |
| `risk_level` | string | 否 | 风险级别预估 |
| `_meta` | object | 否 | 上下文元数据（会校验） |

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
| `resource_path` | string | 否 | 操作目标路径 |
| `timeout` | integer | 是 | 审批超时（秒）|

---

## 依赖关系

- 上游：suri_core（EventBus）、config_service（加载路径规则配置）
- 下游：mcp_framework（工具调用审批）、code_tool（文件操作权限查询）、role_manager（角色创建审批）、upgrade_manager（代码变更审批）

---

## 生命周期

1. `init()` → 加载权限规则、初始化审计器
2. `start()` → 标记就绪
3. `stop()` → 清理待处理审批
4. `cleanup()` → 释放资源

## 安全边界

- 自身是最高权限检查点，不可被绕过
- 审批状态持久化到 SQLite（防重启丢失）
- 异常操作记录到 error 日志
- 不直接执行文件操作（防止权限提升）