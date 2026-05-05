# Suri Agent 安全规范

> 本文档定义系统安全机制的技术实现规范，包括 AST 扫描器、文件沙箱、资源限制和审批令牌状态机。

---

## 1. AST 扫描器（AST Scanner）

### 1.1 扫描目标

所有通过 `PluginManager` 动态加载的插件文件（`.py`），在加载前必须完成 AST 扫描。

### 1.2 禁止操作清单

| 类别 | 禁止 API / 模式 | 说明 |
|------|----------------|------|
| 网络 | `socket.*` | 禁止原始网络通信；`urllib.request` 为标准库，在受控插件（如 llm_gateway）中允许使用 |
| 进程 | `subprocess.*`, `os.system`, `os.popen`, `os.exec*`, `os.spawn*` | 禁止创建子进程 |
| 代码执行 | `eval()`, `exec()`, `compile()`, `__import__` | 禁止动态代码执行；插件代码必须使用标准 `import` 语句 |
| 动态加载 | `ctypes.*`, `importlib.import_module`（非白名单）, `imp.*` | 禁止非受控动态加载 |
| 文件系统越界 | `os.chdir`, `os.makedirs`（绝对路径） | 禁止逃逸沙箱目录 |
| 反射危险 | `getattr(module, name)`（非白名单模块） | 禁止危险反射 |

### 1.3 扫描算法

```python
def scan_ast(source_code: str) -> ScanResult:
    tree = ast.parse(source_code)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = get_full_name(node.func)
            # 精确匹配，避免子字符串误报
            if func_name and any(
                func_name == f or func_name.endswith(f".{f}") for f in forbidden
            ):
                return ScanResult(passed=False, violation=func_name, line=node.lineno)
        
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            # 检查导入模块是否在禁止清单
            for alias in node.names:
                module = f"{node.module}.{alias.name}" if node.module else alias.name
                if module in FORBIDDEN_MODULES:
                    return ScanResult(passed=False, violation=module, line=node.lineno)
    
    return ScanResult(passed=True)
```

### 1.4 白名单机制

- 允许导入：标准库（`os`, `sys`, `json`, `re`, `datetime`, `typing`, `asyncio`, `pathlib`, `sqlite3` 等）
- 允许导入：项目内部模块（`shared.*`, `plugins.*` 中已加载的插件）
- 允许导入：第三方库（需显式声明在 manifest.json 的 `dependencies` 中）
- 禁止导入：任何未声明的网络、进程、加密库

### 1.5 扫描结果处理

| 结果 | 处理 |
|------|------|
| 通过 | 允许加载，记录日志 |
| 失败 | 拒绝加载，发布 `error.security` 事件，通知用户 |
| 可疑（使用动态特性） | 标记为 `needs_review`，加载但限制 `fs_permissions` 为只读 |

---

## 2. 文件沙箱（File Sandbox）

### 2.1 基本原则

- 插件只能访问其 `manifest.json` 中 `fs_permissions` 声明的目录
- 所有文件操作通过沙箱包装器执行，拒绝越界访问
- 运行时生成的数据必须写入 `~/.suri/runtime/` 下对应插件目录

### 2.2 路径白名单

```python
import os
from pathlib import Path

# 路径白名单配置（使用 os.path.abspath() 解析后的绝对路径）
SANDBOX_RULES = {
    "suri_core": {
        "read": ["~/.suri/", "agent_framework/"],
        "write": ["~/.suri/runtime/", "~/.suri/data/"]
    },
    "default_plugin": {
        "read": ["agent_framework/plugins/{type}/{plugin_name}/", "~/.suri/runtime/{plugin_name}/"],
        "write": ["~/.suri/runtime/{plugin_name}/"]
    }
}
```

### 2.3 沙箱包装器（含路径穿越防护）

```python
class SandboxFS:
    def __init__(self, plugin_id: str, permissions: FSPermissions):
        self.allowed_read = [self._resolve(p, plugin_id) for p in permissions.read]
        self.allowed_write = [self._resolve(p, plugin_id) for p in permissions.write]
    
    def _resolve(self, pattern: str, plugin_id: str) -> str:
        """解析路径模板并返回规范化的绝对路径"""
        path_str = pattern.replace("{type}", self.plugin_type).replace("{plugin_name}", plugin_id)
        path_str = os.path.expanduser(path_str)  # 展开 ~
        return os.path.abspath(path_str)          # 转为绝对路径
    
    def _validate_path(self, real_path: str, allowed_dirs: list) -> bool:
        """
        严格的路径校验，防止路径穿越攻击。
        使用 os.path.commonpath() 而非字符串 startswith 匹配。
        """
        real_path = os.path.abspath(os.path.realpath(real_path))  # 解析符号链接 + 规范化
        for allowed_dir in allowed_dirs:
            allowed_dir = os.path.abspath(allowed_dir)
            # 使用 commonpath 做严格的前缀匹配
            if os.path.commonpath([real_path, allowed_dir]) == allowed_dir:
                return True
        return False
    
    def read(self, path: str) -> bytes:
        real_path = os.path.abspath(os.path.realpath(path))
        if not self._validate_path(real_path, self.allowed_read):
            raise SecurityError(
                f"读取越界: {path} (解析后: {real_path}), "
                f"允许目录: {self.allowed_read}"
            )
        with open(real_path, "rb") as f:
            return f.read()
    
    def write(self, path: str, data: bytes) -> None:
        real_path = os.path.abspath(os.path.realpath(path))
        if not self._validate_path(real_path, self.allowed_write):
            raise SecurityError(
                f"写入越界: {path} (解析后: {real_path}), "
                f"允许目录: {self.allowed_write}"
            )
        # 额外检查：写入 agent_framework/ 或 role/suri/ 需审批令牌
        if self._is_protected_path(real_path):
            verify_approval_token(real_path)
        
        # 原子写入：临时文件 → rename，防止写入中断导致文件损坏
        tmp_path = real_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, real_path)  # 原子操作
    
    def _is_protected_path(self, path: str) -> bool:
        """检查路径是否属于受保护路径"""
        protected = [
            os.path.abspath("agent_framework/"),
            os.path.abspath("agent_framework/shared/interfaces/"),
            os.path.abspath("main.py"),
            os.path.abspath("roles/suri/"),
        ]
        return any(os.path.commonpath([path, p]) == p for p in protected)
```

### 2.4 受保护路径

| 路径 | 保护级别 | 写入要求 |
|------|----------|----------|
| `agent_framework/` | 🔴 核心 | security_service 审批 + admin 角色确认 |
| `agent_framework/shared/interfaces/` | 🔴 核心 | security_service 审批 + admin 角色确认 |
| `main.py` | 🔴 核心 | security_service 审批 + admin 角色确认 |
| `role/suri/` | 🔴 核心 | security_service 审批 + suri_hr 确认 |
| `agent_framework/plugins/*/*/plugin.py` | 🟡 敏感 | security_service 审批 |
| `~/.suri/config.json` | 🟡 敏感 | config_service 专用 API |
| `roles/{role_id}/`（非 suri）| 🟢 普通 | 归属角色自身可写，其他角色需审批 |

**迭代 1 实际实现**：security_service 插件在 `can_write()` 中硬编码禁止写入 `agent_framework/`、`agent_framework/shared/interfaces/`、`main.py`，无需审批令牌直接拒绝，发布 `error.tool`（error_code=1102）。

---

## 3. 资源限制（Resource Limits）

### 3.1 监控指标

| 指标 | 默认值 | 超限行为 |
|------|--------|----------|
| 单任务 CPU 时间 | 300 秒 | 发布 `task.timeout` |
| 单任务内存上限 | 512 MB | 发布 `error.plugin` + 取消任务 |
| 插件总内存上限 | 2 GB | 发布 `error.system` + 暂停插件 |
| EventBus 队列深度 | 10000 | 丢弃 LOW 优先级事件 |
| 并发 Agent 数 | 100 | 拒绝新建 Agent |
| 并发任务数 | 10 | 排队等待 |

### 3.2  enforcement 机制

- **CPU 时间**：asyncio.wait_for() 超时 + signal.SIGALRM（Unix）/ threading.Timer（Windows）
- **内存**：定期通过 `psutil.Process().memory_info().rss` 采样（如可用），否则通过 `sys.getsizeof()` 估算
- **队列深度**：EventBus 内部计数器，超限触发 backpressure

---

## 4. 三清单审计

三清单（Role Registry / Plugin Registry / Tool Registry）的所有变更必须通过安全审计。

### 4.1 审计范围

| 注册表 | 审计事件 | 审计内容 |
|--------|---------|---------|
| Role Registry | `role.registered` / `.updated` / `.deprecated` | 谁创建/修改/废弃了角色、角色的技能列表变更 |
| Plugin Registry | `plugin.registered` / `.updated` / `.deprecated` | 谁安装/更新/移除了插件、版本变更 |
| Tool Registry | `tool.registered` / `.updated` / `.deprecated` | 谁注册/修改/废弃了工具、工具 schema 变更 |

### 4.2 审计记录字段

```json
{
  "registry_type": "role",
  "operation": "updated",
  "object_id": "developer_v2",
  "old_state": {
    "skills": ["code_review", "debug"],
    "version": "1.0.0"
  },
  "new_state": {
    "skills": ["code_review", "debug", "refactor"],
    "version": "1.1.0"
  },
  "caller": {
    "role_id": "suri_admin",
    "session_id": "dev_session_01",
    "project_id": "ecommerce_app"
  },
  "result": "approved",
  "timestamp": "2026-05-04T12:00:00Z"
}
```

### 4.3 审计规则

1. 所有变更必须记录 before/after 快照
2. 变更来源必须可追溯（role_id + session_id + project_id）
3. 高风险变更（废弃/移除注册表项）需用户确认后才执行
4. 审计记录不可篡改（追加写入 + 时间戳校验）
5. 审计日志通过 log_service 持久化到 `logs/audit/` 目录

## 5. 工具调用审计

所有工具调用（包括内置服务和自定义工具）必须记录完整的审计日志。

### 5.1 审计日志字段

```json
{
  "timestamp": "2026-05-04T12:00:00Z",
  "tool_name": "filesystem.write_file",
  "params_safe": {
    "path": "works/ecommerce_app/src/main.py",
    "content_hash": "sha256:xxxxx"
  },
  "_meta": {
    "role_id": "developer",
    "project_id": "ecommerce_app",
    "task_id": "T-001",
    "session_id": "dev_session_01"
  },
  "result": {
    "success": true,
    "duration_ms": 150
  }
}
```

### 5.2 _meta 完整性校验

每次工具调用前必须验证 `_meta` 上下文完整性：

```python
def audit_tool_call(tool_call: dict) -> AuditResult:
    meta = tool_call.get("_meta", {})
    
    # 1. 必填字段存在性
    required_fields = ["role_id", "project_id", "task_id", "session_id"]
    missing = [f for f in required_fields if f not in meta]
    if missing:
        return AuditResult(
            passed=False,
            reason=f"_meta 缺少必填字段: {missing}"
        )
    
    # 2. role_id 合法性（必须在 Role Registry 中）
    if not role_registry.exists(meta["role_id"]):
        return AuditResult(
            passed=False,
            reason=f"角色 {meta['role_id']} 未注册"
        )
    
    # 3. session_id 活跃性（必须在 session-hub 中有活跃会话）
    if not session_hub.is_active(meta["session_id"]):
        return AuditResult(
            passed=False,
            reason=f"会话 {meta['session_id']} 不活跃或已过期"
        )
    
    # 4. 项目一致性（如有 project_id，需与当前会话匹配）
    active_session = session_hub.get_session(meta["session_id"])
    if meta["project_id"] and active_session.project_id != meta["project_id"]:
        return AuditResult(
            passed=False,
            reason=f"项目不一致: 工具调用使用 {meta['project_id']}，但当前会话在 {active_session.project_id}"
        )
    
    # 5. 记录审计日志
    log_service.audit("tool_call", {
        "tool_name": tool_call["name"],
        "caller": meta["role_id"],
        "project": meta["project_id"],
        "task": meta["task_id"]
    })
    
    return AuditResult(passed=True)
```

### 5.3 敏感工具特殊审计

以下工具的调用需要额外安全处理：

| 工具 | 额外审计 |
|------|---------|
| `filesystem.write_file` | 记录写入路径 + 内容 hash，保护路径需审批令牌 |
| `shell_exec.run_command` | 记录完整命令（脱敏密码），高危命令需审批 |
| `config_service.set_config` | 记录更改的配置键，敏感配置不记录值 |
| role_manager.create_role | 记录角色名称 + 基础能力，审批后执行 |
| upgrade_manager.upgrade | 记录旧版本 + 新版本，必须用户确认 |

## 6. 审批令牌状态机（Approval Token State Machine）

### 6.1 令牌生命周期

```
[创建] ──▶ PENDING ──▶ [用户审批] ──▶ APPROVED ──▶ [消费] ──▶ CONSUMED
                              │
                              ├──▶ [用户拒绝] ──▶ REJECTED
                              │
                              └──▶ [300秒超时] ──▶ EXPIRED
```

### 6.2 令牌创建

```python
class ApprovalToken:
    token: str           # UUID
    requester: str       # role_id / plugin_id / user_id
    operation: str       # file_modify / soul_modify / plugin_install / plugin_upgrade
    resource: str        # 目标路径/角色ID/插件名
    expires_at: datetime # 创建时间 + 300s
    status: TokenStatus  # pending / approved / rejected / expired / consumed
```

### 6.3 审批流程

1. **发起**：角色/插件调用 `security_service.request_approval(operation, resource)`
2. **创建**：security_service 生成 token，写入 `approval_tokens` 表，发布 `security.approval_required`
3. **呈现**：access 插件将审批请求路由给用户（CLI 提示 / Telegram 消息）
4. **决策**：用户回复 `approve {token}` 或 `reject {token}`，access 发布 `user.decision`
5. **执行**：security_service 验证 token，更新状态，通知请求者
6. **消费**：请求者凭 approved token 执行操作，security_service 标记为 consumed

### 6.4 自动审批规则

| 场景 | 规则 |
|------|------|
| 角色修改自身 output/ | 自动批准（归属目录） |
| 角色读取其他角色 memories/ | 拒绝（跨角色隔离） |
| admin 修改非核心文件 | 自动批准（admin 权限） |
| 任何对 `agent_framework/` 的修改 | 必须人工审批 |
| suri_core 自升级 | 必须人工审批 + 冒烟测试 |

---

## 7. suri_hr 定义

`suri_hr` 不是独立角色，而是 **admin 角色的安全审批别名**。

- 当审批涉及 Soul 修改、角色删除、核心代码变更时，需要 `suri_hr` 级别的确认
- 实际执行者是具有 `admin` 角色的实体（suri 角色本身具有 admin 权限）
- 在单用户部署中，用户即 `suri_hr`
- 在多角色部署中，指定一个 admin 角色承担 `suri_hr` 职责