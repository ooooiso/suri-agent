# code_tool 插件 PRD

## 定位

**代码工具插件**。为角色提供安全的代码文件读写和代码操作能力。所有文件操作通过 security_service 沙箱执行，受路径白名单和审批令牌约束。

**关键约束**：
- 迭代 1 实现只读 + 写入能力（read_file / list_dir / grep / stat_project / write_file / append_file / create_file）
- 迭代 2 扩展为完整读写能力（execute_test / run_linter / execute_command）
- 不解析业务代码语义，只提供文件操作原语
- 代码分析和理解由调用方（角色 + llm_gateway）完成

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
- 插件数量（读取 agent_framework/plugins/ 目录）
- 角色数量（读取 roles/ 目录）

### 5. 文件写入（write_file）【迭代 1 已实现】

- 写入或覆盖指定路径的文件
- 写入前检查路径是否在写白名单
- 禁止写入 agent_framework/、shared/interfaces/、~/.suri/
- agent_framework/plugins/、tests/、roles/ 目录写入需标记 needs_approval

### 6. 文件追加（append_file）【迭代 1 已实现】

- 追加内容到文件末尾
- 同样受写白名单约束

### 7. 创建新文件（create_file）【迭代 1 已实现】

- 创建新文件，如果已存在则返回错误码 4005

### 8. 测试执行（execute_test）【迭代 2 解锁】

- 在隔离环境运行测试
- 复制目标代码到临时目录
- 使用 Python 内置 unittest 运行
- 返回测试结果（通过/失败/错误列表）

### 9. 代码检查（run_linter）【迭代 2 解锁】

- 运行基础语法和风格检查
- 使用 Python 内置 ast 模块检查语法
- 检查导入是否有效（不实际导入，只检查模块名）
- 检查缩进一致性

### 10. 命令执行（execute_command）【迭代 2 解锁】

- 执行白名单内的系统命令
- 默认在临时目录执行
- 限制执行时间和输出大小

---

## 接口定义

### 订阅事件

- `tool.call`（tool_name = code_tool.*）→ 执行对应操作

### 发布事件

- `tool.result` — 操作成功结果
- `error.tool` — 操作失败（路径越界、权限不足、文件不存在等）

### 方法

```python
class CodeTool:
    # === 迭代 1：只读 ===
    async def read_file(self, path: str, offset: int = 0, 
                        limit: int = 100) -> ReadResult
    
    async def list_dir(self, path: str, recursive: bool = False) -> DirListing
    
    async def grep(self, pattern: str, path: str = ".", 
                   glob: str = "*.py", max_results: int = 50) -> List[Match]
    
    async def stat_project(self) -> ProjectStats
    
    # === 迭代 1 增强：写入 ===
    async def write_file(self, path: str, content: str) -> WriteResult
    
    async def append_file(self, path: str, content: str) -> WriteResult
    
    async def create_file(self, path: str, content: str) -> WriteResult
    
    # === 迭代 2：执行 ===
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

所有文件操作通过 security_service 沙箱执行。

### 读白名单

```python
ALLOWED_READ_PATHS = [
    "suri-agent/",           # 项目根目录
    "roles/",                # 角色目录
    "agent_framework/plugins/",              # 插件目录
    "prd/",                  # PRD 文档
    "agent_framework/shared/",               # 共享模块
    "tests/",                # 测试代码
    "agent_framework/",      # 核心框架（只读）
]
```

### 路径安全检查逻辑

1. **解析绝对路径**：将用户输入路径解析为绝对路径（基于项目根目录）
2. **标准化路径**：使用 `os.path.normpath` 消除 `..` 和 `.`  segments
3. **前缀匹配**：检查标准化后的路径是否以白名单目录开头
4. **禁止访问**：以下路径永远拒绝：
   - `~/.suri/` 运行时数据（含 config.json、密钥）
   - `/etc/`、`/usr/`、`/bin/` 等系统目录
   - 任何包含 `..` 试图逃逸项目根目录的路径
5. **错误返回**：路径检查失败时发布 `error.tool` 事件，错误码 `3100`（`code_tool.path_denied`），不暴露内部路径结构

### 写白名单【迭代 1 已实现】

```python
ALLOWED_WRITE_PATHS = [
    "agent_framework/plugins/{new_plugin}/",   # 新插件目录（首次需审批）
    "agent_framework/plugins/{existing_plugin}/", # 现有插件目录（需审批）
    "tests/",                  # 测试代码（需审批）
    "roles/",                  # 角色目录（需审批）
    "prd/",                    # PRD 文档（需审批）
]

FORBIDDEN_WRITE_PATHS = [
    "agent_framework/",        # 核心框架禁止写入
    "agent_framework/shared/interfaces/",      # 接口定义禁止写入
    "~/.suri/",                # 运行时数据禁止写入
    "main.py",                 # 入口文件禁止写入
]
```

### 命令白名单【迭代 2 解锁】

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
- 上游：security_service（沙箱权限检查、审批令牌验证）
- 下游：所有需要文件操作的角色和插件

---

## 内部模块结构

```
code_tool/
├── __init__.py              # 导出 CodeToolPlugin
├── manifest.json            # 插件元数据
├── plugin.py                # 插件主入口，事件路由
├── reader.py                # read_file 实现（迭代 1）
├── explorer.py              # list_dir 实现（迭代 1）
├── search.py                # grep 实现（迭代 1）
├── stats.py                 # stat_project 实现（迭代 1）
├── writer.py                # write_file / append_file / create_file（迭代 1 已实现）
├── test_runner.py           # execute_test（迭代 2 解锁）
└── executor.py              # execute_command（迭代 2 解锁）
```

**设计原则**：将各操作拆分为独立模块，便于单独测试和迭代解锁。`plugin.py` 仅负责事件订阅和参数分发，业务逻辑在各模块中实现。

## 生命周期

1. `init()` → 加载路径白名单配置
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
| `4003` | `code_tool.permission_denied` | 无权限写入 |
| `4004` | `code_tool.write_error` | 写入失败（OS 错误） |
| `4005` | `code_tool.file_exists` | 文件已存在（create_file） |

## 安全边界

- 所有文件操作必须通过 security_service 沙箱，不允许直接 os.open
- 读取操作限制行数和文件大小，防止内存溢出
- 写入操作默认需要审批令牌，禁止自动执行高危写入
- 命令执行限制在白名单内，超时强制终止
- 临时目录隔离，不影响生产数据
- **核心原则**：code_tool 是文件的"搬运工"，不解析语义，不做业务判断
