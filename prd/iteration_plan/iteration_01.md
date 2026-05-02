# 迭代 1：终端与 Telegram 对话 + 代码阅读分析

> 实现用户通过终端和 Telegram 与 suri 对话，同时让 suri 具备**读取项目文件、分析代码、生成开发建议**的能力。

---

## 目标

1. 终端输入 `suri` 进入交互会话
2. 首次运行配置向导（模型 + API Key + Telegram，Telegram 可跳过）
3. 支持 5 个国内大模型，可切换版本（flash/pro）
4. 模型异常时支持自然语言切换/新增
5. Telegram Bot 对话链路完整
6. **suri 能读取项目文件、分析 PRD、输出代码建议**
7. 所有链路完整测试

---

## 包含插件（9 个）

| # | 插件 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | **suri_core** | P0 | EventBus + PluginManager，系统启动基础 |
| 2 | **access** | P0 | CLI 通道 + Telegram Bot 通道 |
| 3 | **config_service** | P0 | 配置存储、热重载、向导交互 |
| 4 | **llm_gateway** | P0 | 5 个国内模型接入、版本切换、异常处理 |
| 5 | **log_service** | P0 | 基础日志记录与查询 |
| 6 | **security_service** | P0 | 文件权限、敏感配置保护、**代码工具沙箱** |
| 7 | **role_manager** | P0 | 创建核心角色 suri、管理 Soul 文件、**注册 code 技能** |
| 8 | **code_tool** | P0 | **新增**：只读文件、目录列出、代码分析 |
| 9 | **memory_service** | P1 | 基础会话记忆存储（如时间允许） |

## 明确不包含（后续迭代）

task_planner、agent_registry、task_scheduler、role_comm、interrupt_handler、role_learner、upgrade_manager、doc_sync、cron_service、hooks_service、mcp_framework

---

## 核心功能链路

### 1. 启动链路

```
用户输入 "suri"
    │
    ▼
main.py（<20 行）
    │
    ▼
SuriCorePlugin.bootstrap() → 创建 EventBus → 创建 PluginManager
    │
    ▼
自注册 suri_core → 按依赖顺序加载其他插件
    │
    ▼
各插件 init() → register_events() → start()
    │
    ▼
access CLI 通道启动 → 进入交互模式
    │
    ├── 首次运行 → 配置向导
    │   ├─ 步骤 1：选择模型厂商
    │   ├─ 步骤 2：输入 API Key
    │   ├─ 步骤 3：选择模型版本
    │   ├─ 步骤 4：配置 Telegram（可选，/skip 跳过）
    │   └─ 步骤 5：确认配置
    │
    └── 非首次运行 → 直接进入会话
```

### 2. 对话链路

```
用户输入消息（CLI 或 Telegram）
    │
    ▼
access 接收 → 包装为 user.input 事件
    │
    ▼
EventBus 分发 → suri 角色订阅处理
    │
    ▼
suri 调用 llm_gateway 生成回复
    │
    ▼
回复通过 access 返回终端（或 Telegram）
```

### 3. 代码阅读链路（迭代 1 核心新增）

```
用户："分析一下 main.py 的代码"
    │
    ▼
suri 理解意图 → 调用 code_tool.read_file("main.py")
    │
    ▼
code_tool 通过 security_service 沙箱读取文件
    │
    ├─ 路径白名单检查：main.py 在允许范围内 ✅
    ├─ 读取内容
    └─ 返回文件内容
    │
    ▼
suri 将文件内容送入 llm_gateway
    │
    ▼
LLM 分析代码结构、功能、潜在问题
    │
    ▼
返回分析结果给用户
```

### 4. 项目分析链路

```
用户："分析一下我们项目的架构"
    │
    ▼
suri 调用 code_tool.list_dir(".") 递归列出项目结构
    │
    ├─ 读取关键文件：main.py、framework.md、plugin_development.md
    ├─ 读取插件 manifest.json 列表
    └─ 统计代码行数、插件数量
    │
    ▼
suri 将收集的信息组织成 prompt
    │
    ▼
LLM 生成项目架构分析、依赖关系图（文字版）、改进建议
    │
    ▼
返回结构化分析报告
```

### 5. 编码计划链路

```
用户："帮我规划迭代 2 的开发任务"
    │
    ▼
suri 读取 prd/iteration_plan/iteration_02.md
    │
    ▼
分析迭代 2 的目标、插件清单、依赖关系
    │
    ├─ 确定开发顺序（拓扑排序）
    ├─ 估算每个插件工作量
    ├─ 识别关键路径和风险点
    └─ 生成文件结构建议
    │
    ▼
返回详细的开发计划（含伪代码骨架）
    │
    ▼
用户确认后，suri 可逐文件生成伪代码输出到终端
```

---

## code_tool 插件设计

### 定位

suri 的**代码阅读工具**。只读，不写。所有文件操作通过 security_service 沙箱执行。

### 接口

```python
class CodeTool:
    """代码阅读工具，只读权限"""
    
    async def read_file(self, path: str, offset: int = 0, limit: int = 100) -> str:
        """读取文件内容，限制行数防止大文件爆上下文"""
        
    async def list_dir(self, path: str, recursive: bool = False) -> List[FileInfo]:
        """列出目录内容，可选递归"""
        
    async def grep(self, pattern: str, path: str = ".", glob: str = "*.py") -> List[Match]:
        """在项目中搜索匹配内容"""
        
    async def stat_project(self) -> ProjectStats:
        """统计项目信息：文件数、代码行数、插件数量等"""
```

### 安全限制

```python
ALLOWED_READ_PATHS = [
    "suri-agent/",           # 项目根目录
    "roles/",                # 角色目录
    "plugins/",              # 插件目录
    "prd/",                  # PRD 文档
    "shared/",               # 共享模块
    "tests/",                # 测试代码
]

FORBIDDEN_PATHS = [
    "~/.suri/config.json",   # 敏感配置
    "~/.suri/runtime/",      # 运行时数据
    "/etc/", "/usr/", "C:/",  # 系统目录
]
```

### 订阅事件

- `tool.call`（tool_name = code_tool.read_file / list_dir / grep / stat_project）

### 发布事件

- `tool.result` — 工具执行结果
- `error.tool` — 工具执行错误（路径越界、文件不存在等）

---

## 5 个国内模型（首批支持）

| # | 厂商 | 模型标识 | 版本示例 |
|---|------|----------|----------|
| 1 | 百度 | `ernie` | ernie-bot / ernie-bot-4 |
| 2 | 阿里 | `qwen` | qwen-turbo / qwen-plus / qwen-max |
| 3 | 智谱 | `chatglm` | glm-4-flash / glm-4-plus |
| 4 | 月之暗面 | `kimi` | kimi-moonshot-v1-8k / kimi-moonshot-v1-32k |
| 5 | DeepSeek | `deepseek` | deepseek-chat / deepseek-coder |

---

## suri 的 code 技能注册

在 `roles/suri/soul.md` 中注册 code 技能：

```yaml
skills:
  - code_read           # 读取项目文件
  - code_analyze        # 分析代码结构
  - project_overview    # 生成项目架构分析
  - dev_planning        # 制定开发计划
  - pseudocode_gen      # 生成伪代码
```

---

## 开发任务分解

### Day 1-2：suri_core + main.py

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| main.py 入口 | `main.py` | framework.md §启动流程 |
| EventBus 实现 | `agent_framework/event_bus/bus.py` | suri_core.md §EventBus |
| PluginManager 实现 | `agent_framework/plugin_manager/manager.py` | suri_core.md §PluginManager |
| SuriCorePlugin 实现 | `agent_framework/suri_core_plugin/plugin.py` | suri_core.md |
| PluginInterface 基类 | `shared/interfaces/plugin.py` | plugin_development.md §PluginInterface |
| Event 数据类 | `shared/utils/event_types.py` | event_registry.md |

**验收标准**：
- `python main.py` 能启动，suri_core 自注册成功
- 能加载一个空插件（manifest + plugin.py）
- EventBus 能发布和订阅事件

### Day 3：config_service + log_service + security_service（基础）

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| config_service 插件 | `plugins/config_service/plugin.py` | config_service.md |
| config.json 读写 | `plugins/config_service/store.py` | config_service.md §配置存储 |
| log_service 插件 | `plugins/log_service/plugin.py` | log_service.md |
| 分级日志输出 | `plugins/log_service/logger.py` | log_service.md §日志分级 |
| security_service 插件（基础） | `plugins/security_service/plugin.py` | security_service.md（简化） |
| 路径白名单 | `plugins/security_service/sandbox.py` | security_spec.md §文件沙箱 |

**验收标准**：
- config_service 能读写 ~/.suri/config.json
- log_service 能输出分级日志到文件
- security_service 能检查路径是否在白名单内

### Day 4-5：llm_gateway

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| llm_gateway 插件 | `plugins/llm_gateway/plugin.py` | llm_gateway.md |
| 模型客户端基类 | `plugins/llm_gateway/client/base.py` | llm_gateway.md §统一接口 |
| 5 个厂商客户端 | `plugins/llm_gateway/client/{vendor}.py` | llm_gateway.md §多模型支持 |
| 路由与切换逻辑 | `plugins/llm_gateway/router.py` | llm_gateway.md §路由策略 |
| 缓存层 | `plugins/llm_gateway/cache.py` | llm_gateway.md §响应缓存 |
| 重试与降级 | `plugins/llm_gateway/retry.py` | llm_gateway.md §失败处理 |

**验收标准**：
- 每个模型都能发送消息并返回响应
- 模型版本切换正常
- API 异常时返回友好错误，不崩溃

### Day 6-7：access CLI 通道

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| access 插件主入口 | `plugins/access/plugin.py` | access.md |
| CLI 通道实现 | `plugins/access/cli.py` | access.md §CLI 通道 |
| 配置向导 | `plugins/access/wizard.py` | deployment.md §首次运行向导 |
| 命令解析器 | `plugins/access/command_parser.py` | access.md §命令解析 |
| 历史记录 | `plugins/access/history.py` | access.md §历史记录 |

**验收标准**：
- 终端输入 `suri` 进入交互模式
- 首次运行弹出配置向导，能完整走完
- 支持 `/quit`、`/config`、`/switch_model` 等命令
- 普通消息发布 user.input 事件

### Day 8：code_tool 插件（迭代 1 核心新增）

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| code_tool 插件 | `plugins/code_tool/plugin.py` | 本迭代计划 §code_tool |
| 文件读取器 | `plugins/code_tool/reader.py` | security_spec.md §文件沙箱 |
| 目录遍历器 | `plugins/code_tool/explorer.py` | 本迭代计划 §code_tool |
| 代码搜索 | `plugins/code_tool/search.py` | 本迭代计划 §code_tool |
| 项目统计 | `plugins/code_tool/stats.py` | 本迭代计划 §code_tool |

**验收标准**：
- suri 能读取项目内任意 Python 文件
- suri 能列出目录结构
- suri 能搜索代码中的关键词
- 尝试读取白名单外路径时被拒绝并提示

### Day 9：role_manager + Telegram 通道

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| role_manager 插件 | `plugins/role_manager/plugin.py` | role_manager.md（简化） |
| 角色创建 | `plugins/role_manager/creator.py` | role_manager.md §目录初始化 |
| Soul 解析器 | `plugins/role_manager/soul_parser.py` | framework.md §Soul Schema |
| suri 默认 Soul | `roles/suri/soul.md` | framework.md §Soul 模板 |
| Telegram 通道 | `plugins/access/telegram.py` | access.md §Telegram 通道 |
| Bot API 封装 | `plugins/access/telegram_bot.py` | access.md §Bot 交互 |

**验收标准**：
- role_manager 能创建 suri 角色，生成 soul.md（含 code 技能）
- suri 角色能订阅 user.input 并调用 llm_gateway
- Telegram Bot 能接收消息并回复
- CLI 和 Telegram 的消息互不干扰

### Day 10-12：整合测试 + PRD 回归 + 代码能力验证

| 任务 | 说明 |
|------|------|
| 端到端测试 | 从启动到对话完整走一遍 |
| 代码阅读测试 | suri 读取 main.py → 分析 → 输出建议 |
| 项目分析测试 | suri 分析项目架构 → 输出报告 |
| 编码计划测试 | suri 读取 iteration_02.md → 输出开发计划 |
| 异常测试 | 断网、API Key 错误、模型超时、路径越界 |
| 配置测试 | 首次向导、热重载、跳过 Telegram |
| PRD 回归 | 检查实现与 PRD 是否一致，不一致处更新 PRD |

---

## 测试矩阵

### 基础功能测试

| 测试项 | 通过标准 |
|--------|----------|
| 终端启动 | `python main.py` 正常启动，无异常退出 |
| 首次向导 | 能完整配置模型+API Key+版本+Telegram，生成 config.json |
| 5 模型对话 | 每个模型都能正常收发消息 |
| 版本切换 | 同一厂商内版本切换正常 |
| 跨厂商切换 | 从模型 A 切换到模型 B 正常 |
| 新增模型 | 配置新厂商模型后可用 |
| 异常降级 | API 超时/错误时友好提示，可自然语言切换 |
| Telegram 配置 | 输入 Token 后 Bot 上线，能收发消息 |
| Telegram 跳过 | 输入 /skip 后正常进入会话，后续可唤醒配置 |
| 配置热重载 | 修改 config.json 后插件感知变更 |
| 日志记录 | 所有事件和操作都有日志记录 |
| 安全扫描 | 加载含 forbidden API 的插件被拒绝 |

### 代码能力测试（迭代 1 新增）

| 测试项 | 通过标准 |
|--------|----------|
| 读取文件 | suri 能读取 main.py 并返回内容 |
| 列出目录 | suri 能列出 plugins/ 目录下的所有插件 |
| 代码搜索 | suri 能在项目中搜索特定函数名 |
| 项目统计 | suri 能统计项目文件数和代码行数 |
| 代码分析 | suri 能分析 main.py 的功能和结构 |
| 架构分析 | suri 能分析项目整体架构并输出报告 |
| 开发计划 | suri 能读取 iteration_02.md 并输出开发计划 |
| 伪代码生成 | suri 能为指定插件生成伪代码骨架 |
| 路径越界防护 | 尝试读取 /etc/passwd 或 ~/.suri/config.json 时被拒绝 |

---

## 文件结构（迭代 1 结束时应具备）

```
suri-agent/
  - main.py                          # 入口
  - .env                             # 环境变量（gitignore）
  - .kimi/                           # AI 开发规范
  - agent_framework/
    - __init__.py
    - event_bus/
      - __init__.py
      - bus.py                       # EventBus 实现
    - plugin_manager/
      - __init__.py
      - manager.py                   # PluginManager 实现
    - suri_core_plugin/
      - __init__.py
      - plugin.py                    # SuriCorePlugin
    - migrations/
      - 001_initial.sql              # 初始 schema
  - plugins/
    - suri_core/                     # 内核插件
      - manifest.json
      - plugin.py
    - access/                        # 统一接入
      - manifest.json
      - plugin.py
      - cli.py
      - telegram.py
      - telegram_bot.py
      - wizard.py
      - command_parser.py
      - history.py
    - config_service/                # 配置管理
      - manifest.json
      - plugin.py
      - store.py
    - llm_gateway/                   # LLM 网关
      - manifest.json
      - plugin.py
      - client/
        - __init__.py
        - base.py
        - ernie.py
        - qwen.py
        - chatglm.py
        - kimi.py
        - deepseek.py
      - router.py
      - cache.py
      - retry.py
    - log_service/                   # 日志
      - manifest.json
      - plugin.py
      - logger.py
    - security_service/              # 安全（含沙箱）
      - manifest.json
      - plugin.py
      - ast_scanner.py
      - sandbox.py                   # 文件沙箱
    - role_manager/                  # 角色管理
      - manifest.json
      - plugin.py
      - creator.py
      - soul_parser.py
    - code_tool/                     # [新增] 代码阅读工具
      - manifest.json
      - plugin.py
      - reader.py
      - explorer.py
      - search.py
      - stats.py
    - [memory_service/]              # 如时间允许
  - shared/
    - __init__.py
    - interfaces/
      - __init__.py
      - plugin.py
    - utils/
      - __init__.py
      - event_types.py
      - log.py
      - db.py
  - roles/
    - suri/
      - soul.md                      # 核心角色 Soul（含 code 技能）
  - tests/
    - __init__.py
    - framework/
      - base.py
      - fixtures.py
    - unit/
    - integration/
  - prd/                             # 产品文档
  - iteration_plan/                  # 本计划文档
```

---

## 风险与回退

| 风险 | 概率 | 应对 |
|------|------|------|
| LLM API 接入复杂 | 中 | 先实现 1-2 个模型，其余后续补充 |
| Telegram Bot 网络问题 | 中 | 提供本地 mock 模式用于开发测试 |
| code_tool 路径越界 | 低 | security_service 白名单严格限制 |
| 大文件读取爆上下文 | 中 | code_tool 限制读取行数（默认 100 行） |
| 12 天工期紧张 | 中 | memory_service 可推迟到迭代 2 |
