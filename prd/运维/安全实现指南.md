# 安全实现指南

> 指导 suri-agent 安全机制的实现细节。

---

## 一、路径白名单统一管理

所有文件操作权限由 `security_service` 统一管理，各插件不得自行维护白名单。

```python
# 插件中查询权限（正确方式）
result = await self.security_service.can_write(
    path=path,
    caller_role=caller_role,
    tool_call_meta=self._current_meta
)
# 返回值：approved / needs_approval / denied
```

**路径规则配置文件**：`~/.suri/data/configs/path_rules.yaml`

```yaml
security_service:
  path_rules:
    # 🔴 永久拒绝
    - pattern: "~/.suri/**"
      permission: deny
    - pattern: "/etc/**"
      permission: deny
    # 🔴 需审批豁免
    - pattern: "agent_framework/**"
      permission: deny_with_exemption
      exempt_source: "upgrade_manager"
    # 🟡 需审批令牌
    - pattern: "agent_framework/plugins/{type}/{name}/**"
      permission: needs_approval
    # 🟢 允许
    - pattern: "works/{project_id}/**"
      permission: approved
```

---

## 二、审批令牌机制

```python
class ApprovalManager:
    """审批令牌管理器"""
    
    def __init__(self):
        self._pending = {}  # token -> ApprovalRequest
    
    def create_approval(self, requester: str, operation: str,
                        resource_path: str, timeout: int = 300) -> str:
        """生成审批令牌，持久化到 SQLite"""
        token = uuid4().hex[:8]
        self._pending[token] = ApprovalRequest(
            token=token, requester=requester,
            operation=operation, resource_path=resource_path,
            expires_at=time.time() + timeout
        )
        self._persist_to_db(token, self._pending[token])
        return token
    
    async def approve(self, token: str) -> bool:
        """用户确认审批"""
        if token not in self._pending:
            return False
        request = self._pending[token]
        if time.time() > request.expires_at:
            return False  # 超时
        # 执行操作
        return True
```

---

## 三、_meta 上下文校验

所有工具调用的 `_meta` 字段必须包含 `role_id, project_id, task_id, session_id`。

```python
def validate_tool_call_meta(meta: dict) -> dict:
    """
    返回校验结果：{"valid": bool, "reason": str}
    """
    required = ["role_id", "project_id", "task_id", "session_id"]
    missing = [f for f in required if f not in meta]
    if missing:
        return {"valid": False, "reason": f"缺失字段: {missing}"}
    if not role_registry.exists(meta["role_id"]):
        return {"valid": False, "reason": "角色不存在"}
    if meta.get("project_id") and not is_project_active(meta["project_id"]):
        return {"valid": False, "reason": "项目不活跃"}
    return {"valid": True, "reason": "通过"}
```

---

## 四、三清单审计

security_service 拦截所有三清单变更事件：

| 清单 | 授权修改来源 | 高风险操作 |
|------|-------------|-----------|
| Role Registry | role_manager / suri | 废弃/删除角色 |
| Plugin Registry | plugin_manager | 废弃/删除插件 |
| Tool Registry | mcp_framework | 废弃/删除工具 |

**审计日志记录**：持久化到 `audit_log` 表，包含 caller / operation / result / timestamp。

---

## 五、Soul 文件保护

- 仅 `admin` 或 `core` 类型角色可修改 Soul 文件
- 角色自身无权修改自己的 Soul
- 修改前需经过 security_service 审批