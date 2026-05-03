# 迭代 2：任务执行 + 代码编写开发 + 热更新 + 解耦

> 在迭代 1 基础上，让 suri 能够**执行复杂任务、写入代码文件、运行测试、调试修复**。同时建立热更新基础能力和解耦设计，消除硬编码。

---

## 目标

1. 复杂任务可分解、调度、跟踪到完成
2. Agent 有独立的生命周期和上下文
3. 任务受阻时有基础中断处理
4. **suri 能生成代码文件、运行测试、验证结果**
5. 测试框架完善，覆盖所有基础插件
6. **建立热更新基础能力** — 消除硬编码，数据外部化，支持热更新
7. **解耦设计** — 每个插件可独立迭代，迭代中通知框架整体更新

---

## 包含插件（4 个新增 + 6 个改造）

### 新增（4 个）

| # | 插件 | 说明 |
|---|------|------|
| 1 | **task_planner** | 任务分解、DAG 依赖管理、预设模板 |
| 2 | **agent_registry** | Agent CRUD、6 态跟踪、父子关系、进度查询 |
| 3 | **task_scheduler** | 优先级队列、并发控制、超时重试、LLM 等待 |
| 4 | **interrupt_handler** | 受阻分类、用户建议、升级通道（简化版，不依赖 role_comm） |

### 改造（6 个已有插件 + 基础设施）

| # | 任务 | 说明 | 优先级 |
|---|------|------|--------|
| 5 | **code_tool**（从只读升级为读写） | 新增 write_file、execute_test、run_linter | 🔴 |
| 6 | **test_framework** | 从外部工具升级为正式插件 | 🔴 |
| 7 | **task_planner 热更新** | 任务模板外部化到 YAML，支持热更新 | 🔴 |
| 8 | **interrupt_handler 热更新** | 关键词外部化到 YAML，支持热更新 | 🟡 |
| 9 | **role_manager 解耦** | Soul 模板外部化，工具说明外部化，不再代理 suri | 🔴 |
| 10 | **access 解耦** | 通道路由外部化，通道与逻辑分离 | 🟡 |
| 11 | **agent_registry 持久化** | 从内存存储迁移到 SQLite | 🟢 |
| 12 | **PluginManager 版本协商** | manifest.json 依赖声明，拓扑排序加载 | 🔴 |
| 13 | **plugin.upgraded 事件** | 升级通知机制，自动协调 | 🔴 |
| 14 | **EventBus 全局异常捕获** | 统一错误处理，发布 error.plugin_crash | 🟡 |

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
    ├─ 规则驱动：匹配预设模板（code/review/statistics/role_creation）
    ├─ LLM 驱动：无模板匹配时调用 LLM 生成 JSON 规划
    └─ 降级：LLM 失败时生成 generic_plan（按关键词拆分句子）
    │
    ▼
发布 task.planned → agent_registry 创建 Agent（每个步骤一个子 Agent）
    │
    ▼
task_scheduler 按优先级和依赖入队调度
    │
    ▼
每步执行前 → Agent 调用 llm_gateway 生成代码 → code_tool.write_file() 写入文件
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

### 4. 中断处理链路（迭代 2 新增）

```
任务执行受阻（如 API Key 失效、依赖失败）
    │
    ▼
task_scheduler 检测到超时/失败 → 发布 task.timeout / task.failed
    │
    ▼
interrupt_handler 接收 → 分类受阻原因（6 类）
    │
    ├─ dependency_failed / timeout → 自动重试（最多 2 次）
    ├─ missing_tool → 通过 user.input 升级到 suri 角色
    ├─ knowledge_gap → 通过 user.input 升级到 suri 角色
    ├─ permission_denied → 向用户展示决策菜单
    └─ resource_exhausted → 向用户展示决策菜单
    │
    ▼
用户决策 → continue / escalate / cancel
    │
    ▼
task_scheduler 继续 / 升级 / 取消任务
```

### 5. 热更新链路（迭代 2 新增）

```
外部数据变更（YAML 文件修改）
    │
    ▼
config_service 检测到变更 → 发布 config.updated 事件
    │
    ▼
各插件收到事件 → 重新加载外部数据
    ├─ task_planner → 重新加载任务模板
    ├─ interrupt_handler → 重新加载关键词
    ├─ role_manager → 重新加载 Soul 模板和工具说明
    └─ access → 重新加载通道路由
    │
    ▼
热更新完成，不影响运行中任务
```

### 6. 解耦链路（迭代 2 新增）

```
role_manager 不再代理 suri：
    │
    ▼
用户输入 → role_manager 只提供角色数据
    │
    ▼
发布 role.context_ready 事件
    │
    ▼
suri 角色自己订阅该事件 → 获取 Soul 数据
    │
    ▼
suri 自行构建 system prompt → 调用 llm_gateway
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

### Week 1：task_planner + agent_registry + code_tool 升级 + 热更新基础设施

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| task_planner 插件 | `plugins/task_planner/plugin.py` | task_planner.md |
| 任务分解引擎 | `plugins/task_planner/decomposer.py` | task_planner.md §任务分解 |
| DAG 管理 | `plugins/task_planner/dag.py` | task_planner.md §依赖管理 |
| 模板系统 | `plugins/task_planner/templates/` | task_planner.md §预设模板 |
| agent_registry 插件 | `plugins/agent_registry/plugin.py` | agent_registry.md |
| Agent 上下文 | `plugins/agent_registry/context.py` | agent_registry.md §AgentContext |
| SQLite 表创建 | `agent_framework/migrations/002_agents.sql` | database_schema.md |
| code_tool 测试执行 | `plugins/code_tool/test_runner.py` | test_framework.md |
| code_tool 命令执行 | `plugins/code_tool/executor.py` | security_spec.md §资源限制 |
| **task_planner 热更新** | `plugins/task_planner/plugin.py` + `~/.suri/data/templates/task_templates.yaml` | task_planner.md §热更新 |
| **PluginManager 版本协商** | `agent_framework/plugin_manager/manager.py` | hot_reload_rules.md |
| **plugin.upgraded 事件** | `agent_framework/plugin_manager/manager.py` + `shared/utils/event_types.py` | hot_reload_rules.md |

### Week 2：task_scheduler + interrupt_handler + test_framework + 解耦改造

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
| **interrupt_handler 热更新** | `plugins/interrupt_handler/plugin.py` + `~/.suri/data/configs/interrupt_keywords.yaml` | interrupt_handler.md §热更新 |
| **role_manager 解耦** | `plugins/role_manager/plugin.py` + `~/.suri/data/templates/soul_template.md` + `~/.suri/data/templates/tool_descriptions.yaml` | role_manager.md §解耦 |
| **access 解耦** | `plugins/access/plugin.py` + `~/.suri/data/configs/channel_routes.yaml` | access.md §解耦 |
| **agent_registry SQLite 持久化** | `plugins/agent_registry/plugin.py` | agent_registry.md §持久化 |
| **EventBus 全局异常捕获** | `agent_framework/event_bus/bus.py` | hot_reload_rules.md |

---

## 测试矩阵

### task_planner 测试（~15 个）

| 测试项 | 通过标准 |
|--------|----------|
| 规则驱动规划 | 匹配 code 模板生成 6 步，依赖关系正确 |
| LLM 驱动规划 | mock LLM 返回 JSON 规划，解析正确 |
| LLM 失败降级 | LLM 返回无效 JSON 时降级为 generic_plan |
| DAG 构建 | 正确解析 depends_on，构建有向无环图 |
| 循环依赖检测 | 发现循环依赖时抛出错误事件 |
| get_ready_steps | 返回依赖已满足的步骤（depends_on 全部 completed） |
| update_step_status | 状态变更后 get_ready_steps 更新 |
| 步骤数超限截断 | 超过 20 步时截断并告警 |
| 空任务输入 | 空字符串返回最小 plan（1 步：分析需求） |
| 多角色规划 | involved_roles 包含所有涉及角色 |

### agent_registry 测试（~15 个）

| 测试项 | 通过标准 |
|--------|----------|
| create_agent | 生成 agent_id（格式 `{role_id}_{timestamp}_{random}`），状态 planning |
| create_sub_agent | parent_agent_id 正确关联，父 Agent 进度更新 |
| 6 态流转 | planning→running→completed 完整链路 |
| blocked 状态 | block_agent 后状态变为 blocked，可恢复为 running |
| paused/cancelled | pause 和 cancel 状态转换正确 |
| 进度计算 | progress 返回 "completed/total" 格式 |
| 父子进度聚合 | 子 Agent 完成 → 父 Agent 进度更新 |
| get_user_stats | 按 user_id 统计 total/active/completed |
| AgentContext 隔离 | 不同 Agent 的消息历史不共享 |
| SQLite 持久化 | 重启后从数据库恢复活跃 Agent |
| 超上限拒绝 | 超过 100 个活跃 Agent 时拒绝创建 |
| 级联销毁 | destroy_agent(cascade=True) 销毁所有子 Agent |
| cleanup_old_agents | 清理超过 24 小时的已完成 Agent |

### task_scheduler 测试（~12 个）

| 测试项 | 通过标准 |
|--------|----------|
| 优先级排序 | CRITICAL 先于 HIGH，HIGH 先于 NORMAL |
| 同优先级 FIFO | 先入队的先执行 |
| 并发控制 | 同时运行任务数不超过 max_concurrent |
| 超时处理 | 超过 timeout 后发布 task.timeout |
| 重试机制 | 最多 3 次，退避间隔 [0, 30, 120] 秒 |
| 重试耗尽 | 第 3 次失败后标记 task.failed，不再重试 |
| LLM 等待 | 等待 llm.response 事件，收到后继续执行 |
| LLM 错误处理 | 收到 llm.error 时触发 task.failed，不继续等待 |
| 取消任务 | cancel 后发布 task.cancelled，从队列移除 |
| 暂停/恢复 | pause 后排队任务保留，resume 后继续执行 |
| 动态调整优先级 | priority_changed 后重新入队排序 |
| 异常隔离 | 单个任务异常不影响队列中其他任务 |

### interrupt_handler 测试（~10 个）

| 测试项 | 通过标准 |
|--------|----------|
| 6 类原因分类 | 关键词匹配正确（中英文混合） |
| missing_tool 处理 | 通过 user.input 升级到 suri 角色 |
| knowledge_gap 处理 | 通过 user.input 升级到 suri 角色 |
| permission_denied 处理 | 向用户展示决策菜单（继续/取消） |
| dependency_failed 自动重试 | 发布 retry_requested，不超过 2 次 |
| timeout 自动重试 | 发布 retry_requested，不超过 2 次 |
| 用户决策 | continue → 继续执行；cancel → 取消任务 |
| 决策超时 | 超时后默认等待，不自动取消 |
| 连续重试失败后升级 | 重试 2 次仍失败 → 向用户展示决策菜单 |
| 升级消息格式 | 通过 formatter 统一格式化，CLI 用数字菜单 |

### code_tool 升级测试（~8 个）

| 测试项 | 通过标准 |
|--------|----------|
| execute_test | 运行 pytest 并返回 passed/failed 计数 |
| run_linter | 发现语法错误（缩进、未定义变量） |
| execute_command | 白名单命令执行并返回 stdout/stderr |
| 命令白名单 | 允许 python/git/ls，拒绝 rm/sudo/curl |
| 写入审批 | 首次写入新目录时 require_approval=True |
| 路径越界 | 写入 agent_framework/ 被拒绝 |
| 测试失败修复循环 | 生成→测试→失败→修复→通过 |

### 热更新测试（~10 个）

| 测试项 | 通过标准 |
|--------|----------|
| task_planner 模板外部化 | 从 YAML 文件加载模板，热更新后生效 |
| task_planner 内置模板 fallback | YAML 文件不存在时使用代码内默认值 |
| interrupt_handler 关键词外部化 | 从 YAML 文件加载关键词，热更新后生效 |
| interrupt_handler 关键词冲突检测 | 加载时检测重叠并告警 |
| role_manager Soul 模板外部化 | 从外部文件加载模板 |
| role_manager 工具说明外部化 | 从 YAML 文件加载工具说明 |
| role_manager 不再代理 suri | 发布 role.context_ready 事件 |
| access 通道路由外部化 | 从 YAML 文件加载通道配置 |
| agent_registry SQLite 持久化 | 重启后恢复活跃 Agent |
| 热更新不影响运行中任务 | 热更新时正在处理的任务不受影响 |

### 基础设施测试（~8 个）

| 测试项 | 通过标准 |
|--------|----------|
| 版本协商 | 依赖顺序正确加载，循环依赖检测 |
| 版本校验 | 版本不匹配时拒绝加载 |
| 升级通知 | 插件升级后自动发布 plugin.upgraded |
| 不兼容检测 | 依赖方检测到不兼容并阻止升级 |
| 全局异常捕获 | 订阅者异常不影响其他订阅者 |
| EventBusFixture 与真实 EventBus 一致 | 接口签名统一 |

### 集成测试（~5 个）

| 测试项 | 通过标准 |
|--------|----------|
| 完整链路 | 复杂任务 → task_planner 分解 → agent_registry 创建 Agent → task_scheduler 调度 → code_tool 执行 → 完成 |
| 中断链路 | 任务受阻 → interrupt_handler 分类 → 用户决策 → 继续/取消 |
| 父子 Agent | 主任务分解 → 子任务完成 → 父任务进度更新 |
| 超时重试 | 任务超时 → 重试 → 成功/失败 |
| 并发任务 | 多个任务同时执行，不超过并发上限 |

**总计：约 83 个测试**

---

## 与迭代 1 的衔接

- 迭代 1 的 `user.input` 事件继续作为入口
- 新增 `task.plan_requested`、`task.planned`、`task.created` 等事件
- code_tool 从只读扩展为读写，security_service 沙箱规则扩展
- agent_registry 的 AgentContext 与 role_manager 的会话上下文职责分离：
  - role_manager：管"用户与 suri 的对话上下文"（session_id 维度）
  - agent_registry：管"Agent 执行任务的上下文"（agent_id 维度）
- interrupt_handler 的升级通道不依赖 role_comm（迭代 3），统一走 user.input 事件由 suri 角色转发
- 热更新能力由已有插件改造提供，不新增插件

---

## 风险与回退

| 风险 | 概率 | 应对 |
|------|------|------|
| task_planner LLM 规划不稳定 | 中 | 规则驱动优先，LLM 规划失败降级为 generic_plan |
| agent_registry SQLite 并发问题 | 低 | WAL 模式 + 连接池 |
| task_scheduler 死锁 | 中 | 所有异步操作加超时，任务异常隔离 |
| interrupt_handler 升级通道简化 | 低 | 走 user.input 由 suri 转发，不依赖 role_comm |
| 83 个测试工作量过大 | 中 | 核心功能测试优先（约 60 个），边缘场景可推迟 |
| 4 个新插件 + 6 个改造同时开发耦合度高 | 中 | 按依赖顺序开发：agent_registry → task_planner → task_scheduler → interrupt_handler → 热更新 → 解耦 |

---

## 迭代 2 已知问题 & 优化项（开发中发现）

### 代码层面

| # | 问题 | 影响 | 建议修复 |
|---|------|------|----------|
| 1 | `task_planner._template_to_plan` 的 depends_on 自引用 bug | 循环依赖检测误报 | 改为 `depends_on = [steps[i-1].step_id]` |
| 2 | `task_planner._generic_plan` 拆分逻辑将 `manifest.json` 中的 `.` 当作分隔符 | 多拆分出段落 | 改用更智能的拆分策略（只拆分中文句号+换行） |
| 3 | `task_planner` 关键词匹配冲突（"创建" vs "创建角色"） | 匹配到错误模板 | 优先匹配更长关键词，支持 AND 匹配 |
| 4 | `interrupt_handler._classify_reason` 关键词重叠（"timeout" 同时出现在 dependency_failed 和 timeout） | 误判原因类型 | 已修复（从 dependency_failed 移除 timeout） |
| 5 | EventBus subscribe 是异步方法但被同步调用 | 222 个 RuntimeWarning | 让 `register_events()` 变成 async 方法 |
| 6 | `PluginTestHarness.run_lifecycle` 是异步方法但被同步调用 | 生命周期测试未真正执行 | 测试中加 `await` |
| 7 | `task_planner._wait_for_llm_response` 事件订阅未取消 | 长期运行内存泄漏 | EventBus 支持 `unsubscribe` |
| 8 | agent_registry 使用内存存储而非数据库 | 重启后数据丢失 | 接入 SQLite 持久化 |
| 9 | task_scheduler 插件无测试 | 质量风险 | 迭代 3 补充约 12 个测试 |

### 架构层面

| # | 问题 | 建议 |
|---|------|------|
| 1 | 插件间依赖关系未显式声明 | manifest.json 增加 `dependencies` 和 `optional_dependencies`，PluginManager 按拓扑排序加载 |
| 2 | 配置管理分散在各插件中 | 统一通过 config_service 管理，支持热更新 |
| 3 | 缺少全局错误处理中间件 | EventBus 支持全局 error handler，统一处理未捕获异常 |
| 4 | EventBusFixture 与真实 EventBus 行为不一致 | 统一接口签名，让 Fixture 完全模拟真实行为 |