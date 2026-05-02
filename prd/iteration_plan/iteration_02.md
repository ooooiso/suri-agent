# 迭代 2：任务执行 + 代码编写开发

> 在迭代 1 基础上，让 suri 能够**执行复杂任务、写入代码文件、运行测试、调试修复**。

---

## 目标

1. 复杂任务可分解、调度、跟踪到完成
2. Agent 有独立的生命周期和上下文
3. 任务受阻时有基础中断处理
4. **suri 能生成代码文件、运行测试、验证结果**
5. 测试框架完善，覆盖所有基础插件

---

## 包含插件（4 个新增）

| # | 插件 | 说明 |
|---|------|------|
| 1 | **task_planner** | 任务分解、DAG 依赖管理、预设模板 |
| 2 | **agent_registry** | Agent CRUD、6 态跟踪、父子关系、进度查询 |
| 3 | **task_scheduler** | 优先级队列、并发控制、超时重试、LLM 等待 |
| 4 | **interrupt_handler** | 受阻分类、用户建议、升级通道（简化版） |

## 完善（2 个）

| # | 插件 | 说明 |
|---|------|------|
| 5 | **code_tool**（从只读升级为读写） | 新增 write_file、execute_test、run_linter |
| 6 | **test_framework** | 从外部工具升级为正式插件，自动化测试覆盖 |

## 明确不包含

role_comm（迭代 3）、role_learner（迭代 4）、upgrade_manager（迭代 3 提前）、mcp_framework（迭代 5）

---

## 核心功能链路

### 1. 复杂任务执行

```
用户输入复杂需求："实现一个任务调度器插件"
    │
    ▼
suri 判断需要分解 → 调用 task_planner.plan()
    │
    ▼
task_planner 生成执行计划：
    ├─ 步骤 1：创建目录结构
    ├─ 步骤 2：编写 manifest.json
    ├─ 步骤 3：编写 plugin.py 骨架
    ├─ 步骤 4：实现核心逻辑
    ├─ 步骤 5：编写测试用例
    └─ 步骤 6：运行测试验证
    │
    ▼
发布 task.plan_ready → task_scheduler 接收
    │
    ▼
task_scheduler 按优先级和依赖入队调度
    │
    ▼
每步执行前 → agent_registry.create_agent() 创建 Agent
    │
    ▼
Agent 执行 → 调用 llm_gateway 生成代码 → code_tool.write_file() 写入文件
    │
    ▼
agent_registry 更新步骤状态 → 触发下一步
    │
    ▼
全部完成 → suri 汇总结果 → 运行测试 → 返回用户
```

### 2. 代码编写链路（迭代 2 核心新增）

```
suri 生成代码内容
    │
    ▼
code_tool.write_file(path="plugins/my_plugin/plugin.py", content="...")
    │
    ├─ security_service 检查：
    │   ├─ 路径是否在写白名单？
    │   ├─ 是否需要审批令牌？（首次写入新目录需审批）
    │   └─ 内容是否含 forbidden API？
    │
    ▼
写入文件 → 发布 hooks.file_changed
    │
    ▼
code_tool.execute_test(test_path="tests/plugin/my_plugin/")
    │
    ├─ 在临时目录运行测试
    ├─ 隔离环境，不影响生产数据
    └─ 返回测试结果
    │
    ▼
测试通过 → 标记完成
测试失败 → suri 分析错误 → 生成修复方案 → 重新写入
```

### 3. 开发辅助链路

```
用户："帮我实现一个 cron_service 插件"
    │
    ▼
suri 读取 prd/plugins/cron_service.md
    │
    ▼
分析 PRD 要求：
    ├─ 定位：定时任务调度
    ├─ 订阅事件：user.command（/cron）
    ├─ 发布事件：cron.{rule_id}
    ├─ 配置项：rules、misfire_grace_time、max_instances
    └─ 生命周期：init → start → stop → cleanup
    │
    ▼
suri 生成代码：
    ├─ manifest.json
    ├─ plugin.py（PluginInterface 实现）
    ├─ scheduler.py（定时调度核心）
    └─ store.py（规则持久化）
    │
    ▼
code_tool 逐文件写入 plugins/cron_service/
    │
    ▼
运行测试验证 → 通过 → 通知用户
```

---

## code_tool 升级（迭代 1 → 迭代 2）

### 新增接口

```python
class CodeTool:
    # 迭代 1 已有
    async def read_file(self, path: str, offset: int = 0, limit: int = 100) -> str
    async def list_dir(self, path: str, recursive: bool = False) -> List[FileInfo]
    async def grep(self, pattern: str, path: str = ".", glob: str = "*.py") -> List[Match]
    async def stat_project(self) -> ProjectStats
    
    # 迭代 2 新增
    async def write_file(self, path: str, content: str, 
                         require_approval: bool = True) -> WriteResult:
        """写入文件，默认需要审批令牌"""
        
    async def append_file(self, path: str, content: str) -> WriteResult:
        """追加内容到文件末尾"""
        
    async def execute_test(self, test_path: str) -> TestResult:
        """在隔离环境运行测试，返回结果"""
        
    async def run_linter(self, path: str) -> LinterResult:
        """运行基础代码检查（缩进、语法、导入）"""
        
    async def execute_command(self, command: str, args: List[str]) -> CommandResult:
        """执行白名单命令（python、git status、ls 等）"""
```

### 写入安全规则

| 操作 | 限制 |
|------|------|
| 写入 `plugins/{new_plugin}/` | 需用户审批（首次） |
| 写入 `plugins/{existing_plugin}/` | 需用户审批 |
| 写入 `tests/` | 需用户审批 |
| 写入 `roles/` | 需用户审批 |
| 写入 `agent_framework/` | ❌ 禁止（核心代码） |
| 写入 `shared/interfaces/` | ❌ 禁止（接口定义） |
| 写入 `~/.suri/` | ❌ 禁止（运行时数据） |

### 命令白名单

```python
ALLOWED_COMMANDS = [
    "python", "python3",           # 运行 Python 脚本/测试
    "git",                         # git status、git diff（只读操作）
    "ls", "dir", "find",           # 列出文件
    "cat", "type", "head", "tail", # 查看文件（冗余，优先用 read_file）
]

FORBIDDEN_COMMANDS = [
    "rm", "del", "rmdir",          # 删除
    "sudo", "su",                  # 提权
    "curl", "wget", "ssh",         # 网络
    "pip", "conda",                # 包管理
]
```

---

## 开发任务分解

### Week 1：task_planner + agent_registry + code_tool 升级

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| task_planner 插件 | `plugins/task_planner/plugin.py` | task_planner.md |
| 任务分解引擎 | `plugins/task_planner/decomposer.py` | task_planner.md §任务分解 |
| DAG 管理 | `plugins/task_planner/dag.py` | task_planner.md §依赖管理 |
| 模板系统 | `plugins/task_planner/templates/` | task_planner.md §预设模板 |
| agent_registry 插件 | `plugins/agent_registry/plugin.py` | agent_registry.md |
| Agent 上下文 | `plugins/agent_registry/context.py` | agent_registry.md §AgentContext |
| SQLite 表创建 | `agent_framework/migrations/002_agents.sql` | database_schema.md |
| code_tool 写入能力 | `plugins/code_tool/writer.py` | security_spec.md §文件沙箱 |
| code_tool 测试执行 | `plugins/code_tool/test_runner.py` | test_framework.md |
| code_tool 命令执行 | `plugins/code_tool/executor.py` | security_spec.md §资源限制 |

### Week 2：task_scheduler + interrupt_handler + test_framework

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| task_scheduler 插件 | `plugins/task_scheduler/plugin.py` | task_scheduler.md |
| 优先级队列 | `plugins/task_scheduler/queue.py` | task_scheduler.md §PriorityQueue |
| 并发控制 | `plugins/task_scheduler/concurrency.py` | task_scheduler.md §ConcurrencyControl |
| 超时重试 | `plugins/task_scheduler/retry.py` | task_scheduler.md §TimeoutRetry |
| interrupt_handler 插件（简化） | `plugins/interrupt_handler/plugin.py` | interrupt_handler.md |
| 受阻分类 | `plugins/interrupt_handler/classifier.py` | interrupt_handler.md §受阻分类 |
| test_framework 插件 | `plugins/test_framework/plugin.py` | test_framework.md |
| EventBusFixture | `shared/utils/event_bus_fixture.py` | plugin_development.md §EventBusFixture |
| PluginTestHarness | `shared/utils/plugin_test_harness.py` | plugin_development.md §PluginTestHarness |
| TestBase | `tests/framework/base.py` | plugin_development.md §TestBase |
| RoleFixture | `tests/framework/fixtures.py` | plugin_development.md §RoleFixture |

---

## 测试矩阵

### 任务执行测试

| 测试项 | 通过标准 |
|--------|----------|
| 任务分解 | 复杂输入能分解为 3-10 个有依赖关系的步骤 |
| DAG 执行 | 依赖步骤按正确顺序执行 |
| Agent 生命周期 | 创建→运行→完成→销毁流程完整 |
| 父子 Agent | 子 Agent 完成更新父 Agent 进度 |
| 任务超时 | 超时后触发中断，可重试或取消 |
| 并发控制 | 同时运行任务数不超过配置上限 |

### 代码能力测试（迭代 2 新增）

| 测试项 | 通过标准 |
|--------|----------|
| 写入文件 | code_tool 能写入新插件目录 |
| 审批流程 | 首次写入新目录时触发用户审批 |
| 路径越界拒绝 | 尝试写入 agent_framework/ 时被拒绝 |
| 测试执行 | 能运行单元测试并返回结果 |
| 语法检查 | run_linter 能发现语法错误 |
| 命令白名单 | 允许 python、git status；拒绝 rm、sudo |
| 代码生成+验证 | suri 生成代码 → 写入 → 运行测试 → 通过 |

---

## 与迭代 1 的衔接

- 迭代 1 的 `user.input` 事件继续作为入口
- 新增 `task.plan_requested`、`task.plan_ready`、`task.created` 等事件
- code_tool 从只读扩展为读写，security_service 沙箱规则扩展
- agent_registry 依赖 memory_service（迭代 1 或本迭代实现）
