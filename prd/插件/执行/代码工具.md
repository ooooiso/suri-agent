# code_tool 插件 PRD

## 定位

**代码工具插件**。为角色提供安全的代码文件读写和代码操作能力。所有文件操作向 security_service 查询权限，受统一路径白名单和审批令牌约束。

**关键约束**：
- ✅ **迭代 1（已实现）**：read_file、list_dir、grep、stat_project（只读）
- ✅ **迭代 1 增强（已实现）**：write_file、append_file、create_file（写入）
- 📋 **迭代 2（规划中）**：execute_test、run_linter、execute_command（执行）
- 不解析业务代码语义，只提供文件操作原语
- 代码分析和理解由调用方（角色 + llm_gateway）完成
- **路径白名单由 security_service 统一管理**（code_tool 不维护自己的白名单）

---

## 功能需求

### 1. 文件读取（read_file）

- 读取指定路径的文件内容
- 支持偏移和行数限制（默认 100 行），防止大文件爆上下文
- 自动检测文件编码（UTF-8 为主）
- 支持二进制文件检测，拒绝读取二进制文件

### 2. 目录列出（list_dir）

- 列出指定目录的内容（文件和子目录）
- 支持递归列出（默认不递归，防止目录过深）
- 返回文件大小、修改时间、类型（文件/目录）

### 3. 代码搜索（grep）

- 在项目中按正则表达式搜索内容
- 支持 glob 过滤文件类型（默认 *.py）
- 返回匹配的文件路径、行号、匹配内容
- 限制最大返回结果数（默认 50 条）

### 4. 项目统计（stat_project）

- 统计项目基本信息
- 文件总数、代码行数、注释行数、空行数
- 插件数量（递归读取 agent_framework/plugins/ 所有子目录）
- 角色数量（读取 roles/ 目录）

### 5. 文件写入（write_file）【迭代 1 已实现】

- 写入或覆盖指定路径的文件
- 写入前调用 `security_service.can_write(path, caller_role)` 检查权限
- 安全检查通过后执行写入
- 写入前自动备份原文件（auto_backup: true）

### 6. 文件追加（append_file）【迭代 1 已实现】

- 追加内容到文件末尾
- 同样经过 `security_service.can_write()` 检查

### 7. 创建新文件（create_file）【迭代 1 已实现】

- 创建新文件，如果已存在则返回错误码 4005
- 同样经过 `security_service.can_write()` 检查

### 8. 测试执行（execute_test）【迭代 2 规划中】

- 在隔离环境运行测试
- 复制目标代码到临时目录
- 使用 Python 内置 unittest 运行
- 返回测试结果（通过/失败/错误列表）

### 9. 代码检查（run_linter）【迭代 2 规划中】

- 运行基础语法和风格检查
- 使用 Python 内置 ast 模块检查语法
- 检查导入是否有效（不实际导入，只检查模块名）
- 检查缩进一致性

### 10. 命令执行（execute_command）【迭代 2 规划中】

- 执行白名单内的系统命令
- 默认在临时目录执行
- 限制执行时间和输出大小

---

## 接口定义

### 订阅事件

- `tool.call`（tool_name = code_tool.*）→ 执行对应操作
- `tool.call` 中包含 `_meta` 字段（role_id, project_id, task_id, session_id），用于安全审计

### 发布事件

- `tool.result` — 操作成功结果
- `error.tool` — 操作失败（路径越界、权限不足、文件不存在等）

### 方法

```python
class CodeTool:
    # === 迭代 1（✅ 已实现）：只读 ===
    async def read_file(self, path: str, offset: int = 0, 
                        limit: int = 100) -> ReadResult
    
    async def list_dir(self, path: str, recursive: bool = False) -> DirListing
    
    async def grep(self, pattern: str, path: str = ".", 
                   glob: str = "*.py", max_results: int = 50) -> List[Match]
    
    async def stat_project(self) -> ProjectStats
    
    # === 迭代 1 增强（✅ 已实现）：写入 ===
    async def write_file(self, path: str, content: str) -> WriteResult
    
    async def append_file(self, path: str, content: str) -> WriteResult
    
    async def create_file(self, path: str, content: str) -> WriteResult
    
    # === 迭代 2（📋 规划中）：执行 ===
    async def execute_test(self, test_path: str) -> TestResult
    
    async def run_linter(self, path: str) -> LinterResult
    
    async def execute_command(self, command: str, 
                              args: List[str] = None) -> CommandResult
```

---

## 事件 Payload Schema

### 订阅事件

#### `tool.call`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tool_name` | string | 是 | 工具名称：code_tool.read_file / list_dir / grep / stat_project / write_file / execute_test / run_linter / execute_command |
| `params` | object | 是 | 工具参数（见各方法签名） |
| `caller_role` | string | 是 | 调用者角色 ID |
| `task_id` | string | 否 | 关联任务 ID |
| `request_id` | string | 是 | 请求唯一标识 |
| `_meta` | object | 否 | 上下文元数据（含 role_id, project_id, task_id, session_id） |

### 发布事件

#### `tool.result`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 对应请求 ID |
| `tool_name` | string | 是 | 工具名称 |
| `result` | object/string | 是 | 执行结果 |
| `duration_ms` | integer | 否 | 执行耗时 |

#### `error.tool`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 对应请求 ID |
| `tool_name` | string | 是 | 工具名称 |
| `error_code` | integer | 是 | 错误码（见 framework.md 3100-3199 工具段） |
| `error_message` | string | 是 | 错误描述 |
| `retryable` | boolean | 是 | 是否可重试 |

---

## 安全沙箱

**所有文件操作权限由 security_service 统一管理。**
code_tool 不维护自己的路径白名单，而是调用 `security_service.can_read(path, caller_role)` 和 `security_service.can_write(path, caller_role)`。

### 安全检查流程

```
收到 tool.call（含写入操作）
    │
    ├─ 1. 提取 _meta.role_id（调用者角色）
    ├─ 2. 调用 security_service.can_write(path, role_id)
    │       ├── → 返回 approved → 执行写入
    │       ├── → 返回 needs_approval → 发布 security.approval_required
    │       │       └── 用户确认后执行
    │       └── → 返回 denied → 发布 error.tool（错误码 4003）
    │
    └─ 3. 写入完成后发布 tool.result
    
注：插件升级等特殊场景（通过 upgrade_manager 发起）可由 security_service
    经审批后临时授予 agent_framework/ 等保护路径的写入权限。
    详见 security_service.md 的"审批令牌豁免"机制。
```

### 路径安全检查逻辑

```python
# 安全检查完全委托 security_service
# code_tool 只做"执行文件操作"这一件事

def _check_write_permission(self, path: str, caller_role: str) -> bool:
    """
    调 security_service 检查写入权限
    security_service 负责：
      - 路径白名单检查
      - 审批令牌验证（如需）
      - 保护路径拒绝（agent_framework/ 核心路径）
      - 升级豁免（通过 upgrade_manager 的审批可临时写入）
    """
    result = await self.security_service.can_write(
        path=path, 
        caller_role=caller_role,
        tool_call_meta=self._current_meta
    )
    return result.decision  # approved / needs_approval / denied
```

### 禁止访问路径（由 security_service 强制执行）

| 路径 | 保护级别 | 访问规则 |
|------|----------|---------|
| `~/.suri/` | 🔴 核心 | 永久拒绝（运行时数据、密钥） |
| `/etc/、/usr/、/bin/` 等系统目录 | 🔴 系统 | 永久拒绝 |
| `agent_framework/` | 🔴 框架 | 拒绝（需 upgrade_manager 审批豁免） |
| `agent_framework/shared/interfaces/` | 🔴 接口 | 拒绝（需 upgrade_manager 审批豁免） |
| `main.py` | 🔴 入口 | 拒绝（需 upgrade_manager 审批豁免） |
| `agent_framework/plugins/{type}/{name}/` | 🟡 插件 | 需审批令牌 |
| `roles/{role_id}/soul.md` | 🟡 角色 | 仅归属角色可写 |
| 其他项目内路径 | 🟢 普通 | 角色自管理或需审批 |

### 命令白名单【迭代 2 规划中】

```python
ALLOWED_COMMANDS = [
    "python", "python3",
    "git",                     # 仅限 status、diff、log 等只读子命令
    "ls", "dir", "find",
    "cat", "type", "head", "tail",
]

FORBIDDEN_COMMANDS = [
    "rm", "del", "rmdir",
    "sudo", "su",
    "curl", "wget", "ssh",
    "pip", "conda",
]
```

---

## 配置项

```yaml
code_tool:
  read:
    max_lines: 100              # 单次读取最大行数
    max_file_size_mb: 1         # 单次读取最大文件大小
    allowed_encodings: ["utf-8", "ascii"]
  write:
    require_approval: true      # 写入是否需要审批令牌
    auto_backup: true           # 写入前自动备份原文件
  execute:
    timeout_seconds: 60         # 命令执行超时
    max_output_lines: 500       # 最大输出行数
    temp_dir: "~/.suri/runtime/code_tool/temp/"
  grep:
    max_results: 50             # 最大返回结果数
    max_file_size_mb: 5         # 跳过超过此大小的文件
```

---

## 依赖关系

- 上游：suri_core（EventBus）
- 上游：security_service（统一权限管理、审批令牌验证）
- 下游：所有需要文件操作的角色和插件

---

## 内部模块结构

```
code_tool/
├── __init__.py              # 导出 CodeToolPlugin
├── manifest.json            # 插件元数据
├── plugin.py                # 插件主入口，事件路由 + 权限查询
├── reader.py                # read_file 实现（✅ 迭代 1）
├── explorer.py              # list_dir 实现（✅ 迭代 1）
├── search.py                # grep 实现（✅ 迭代 1）
├── stats.py                 # stat_project 实现（✅ 迭代 1）
├── writer.py                # write_file / append_file / create_file（✅ 迭代 1）
├── test_runner.py           # execute_test（📋 迭代 2）
└── executor.py              # execute_command（📋 迭代 2）
```

**设计原则**：将各操作拆分为独立模块，便于单独测试和迭代解锁。`plugin.py` 仅负责事件订阅和参数分发，业务逻辑在各模块中实现。

## 生命周期

1. `init()` → 获取 security_service 引用
2. `start()` → 注册 tool.call 事件处理器
3. `stop()` → 中断正在执行的命令
4. `cleanup()` → 清理临时目录

---

## 错误码

| 错误码 | 错误类型 | 说明 |
|--------|---------|------|
| `3101` | `code_tool.file_not_found` | 文件不存在 |
| `3102` | `code_tool.not_a_file` | 路径不是文件 |
| `3103` | `code_tool.read_error` | 读取失败（编码错误等） |
| `3104` | `code_tool.dir_not_found` | 目录不存在 |
| `3105` | `code_tool.not_a_directory` | 路径不是目录 |
| `3106` | `code_tool.list_dir_error` | 列出目录失败 |
| `3107` | `code_tool.path_not_found` | grep 目标路径不存在 |
| `3108` | `code_tool.grep_error` | 搜索执行失败 |
| `3109` | `code_tool.stat_path_not_found` | 统计路径不存在 |
| `3110` | `code_tool.stat_error` | 项目统计失败 |
| `4001` | `code_tool.path_out_of_bounds` | 路径越界（不在项目根目录内） |
| `4002` | `code_tool.forbidden_path` | 禁止写入系统目录 |
| `4003` | `code_tool.permission_denied` | 无权限写入（security_service 拒绝） |
| `4004` | `code_tool.write_error` | 写入失败（OS 错误） |
| `4005` | `code_tool.file_exists` | 文件已存在（create_file） |

## 安全边界

- 所有文件操作向 security_service 查询权限，不允许绕过
- code_tool 不维护路径白名单（消除与 security_service 的职责重叠）
- 读取操作限制行数和文件大小，防止内存溢出
- 写入操作默认需要审批令牌，禁止自动执行高危写入
- 保护路径（agent_framework/ 等）拒绝直接写入，通过 upgrade_manager 审批豁免
- 命令执行限制在白名单内，超时强制终止
- 临时目录隔离，不影响生产数据
- **核心原则**：code_tool 是文件的"搬运工"，不解析语义，不做业务判断