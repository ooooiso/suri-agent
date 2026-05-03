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
access 启动
    │
    ├── 首次运行 → 配置向导（ConfigWizard）
    │   ├─ 步骤 1：选择模型厂商
    │   ├─ 步骤 2：输入 API Key
    │   ├─ 步骤 3：配置 Telegram（可选，/skip 跳过）
    │   └─ 步骤 4：确认配置 → 保存 ~/.suri/config.json
    │   （子模型选择不在向导中，接入后通过对话或 /switch 命令切换）
    │
    ├── CLI 通道启动 → 进入交互模式
    │
    └── Telegram 通道启动（如配置启用）→ 开始轮询
```

### 2. 对话链路

```
用户输入消息（CLI 或 Telegram）
    │
    ▼
access 接收 → 包装为 user.input 事件
    │
    ▼
EventBus 分发 → role_manager 代理 suri 角色订阅处理
    │
    ▼
role_manager 读取 suri Soul → 组装 system prompt → 发布 llm.request
    │
    ▼
llm_gateway 调用模型 → 发布 llm.response
    │
    ▼
access 按 session_id 路由 → CLI 打印 / Telegram 发送
```

> **实现说明**：迭代 1 中 suri 角色尚未具备独立事件处理能力，由 role_manager 代理 suri 订阅 user.input 并转发 llm.request。迭代 2+ 引入 agent_registry 后，由真正的 suri Agent 处理。

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
| 5 | DeepSeek | `deepseek` | deepseek-v4-pro / deepseek-v4-flash（deepseek-chat 兼容） |

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

| 任务 | 输出文件 | 参考 PRD | 状态 |
|------|----------|----------|------|
| config_service 插件 | `plugins/config_service/plugin.py` | config_service.md | ✅ |
| config.json 读写 | `plugins/config_service/store.py` | config_service.md §配置存储 | ⏸️ 功能集成在 plugin.py，迭代 2 拆分 |
| log_service 插件 | `plugins/log_service/plugin.py` | log_service.md | ✅ |
| 分级日志输出 | `plugins/log_service/logger.py` | log_service.md §日志分级 | ⏸️ 功能集成在 plugin.py，迭代 2 拆分 |
| security_service 插件（基础） | `plugins/security_service/plugin.py` | security_service.md（简化） | ✅ |
| 路径白名单 | `plugins/security_service/sandbox.py` | security_spec.md §文件沙箱 | ⏸️ 功能集成在 plugin.py，迭代 2 拆分 |

**验收标准**：
- config_service 能读写 ~/.suri/config.json ✅
- log_service 能输出分级日志到文件 ✅
- security_service 能检查路径是否在白名单内 ✅

### Day 4-5：llm_gateway

| 任务 | 输出文件 | 参考 PRD | 状态 |
|------|----------|----------|------|
| llm_gateway 插件 | `plugins/llm_gateway/plugin.py` | llm_gateway.md | ✅ |
| 模型客户端基类 | `plugins/llm_gateway/client/base.py` | llm_gateway.md §统一接口 | ⏸️ 迭代 2 拆分 |
| 5 个厂商客户端 | `plugins/llm_gateway/client/{vendor}.py` | llm_gateway.md §多模型支持 | ⏸️ 迭代 2 拆分，当前在 plugin.py 中统一处理 |
| 路由与切换逻辑 | `plugins/llm_gateway/router.py` | llm_gateway.md §路由策略 | ⏸️ 迭代 2 拆分，基础切换在 plugin.py |
| 缓存层 | `plugins/llm_gateway/cache.py` | llm_gateway.md §响应缓存 | ⏸️ 迭代 2 |
| 重试与降级 | `plugins/llm_gateway/retry.py` | llm_gateway.md §失败处理 | ⏸️ 迭代 2 |

**验收标准**：
- 每个模型都能发送消息并返回响应 ⚠️（4/5，wenxin 需 access_token 流程，迭代 2 完善）
- 模型版本切换正常 ✅
- API 异常时返回友好错误，不崩溃 ✅

### Day 6-7：access CLI 通道

| 任务 | 输出文件 | 参考 PRD | 状态 |
|------|----------|----------|------|
| access 插件主入口 | `plugins/access/plugin.py` | access.md | ✅ |
| CLI 通道实现 | `plugins/access/cli.py` | access.md §CLI 通道 | ✅ |
| 配置向导 | `plugins/access/wizard.py` | deployment.md §首次运行向导 | ✅ |
| 命令解析器 | `plugins/access/command_parser.py` | access.md §命令解析 | ⏸️ 功能集成在 cli.py，迭代 2 拆分 |
| 历史记录 | `plugins/access/history.py` | access.md §历史记录 | ⏸️ 迭代 2 |

**验收标准**：
- 终端输入 `suri` 进入交互模式 ✅
- 首次运行弹出配置向导，能完整走完 ✅
- API Key 输入后自动验证可用性 ✅
- 支持 `/quit`、`/config`、`/switch_model` 等命令 ✅（/quit, /help, /status, /model, /reload, /logs）
- 普通消息发布 user.input 事件 ✅

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

| 任务 | 输出文件 | 参考 PRD | 状态 |
|------|----------|----------|------|
| role_manager 插件 | `plugins/role_manager/plugin.py` | role_manager.md（简化） | ✅ |
| 角色创建 | `plugins/role_manager/creator.py` | role_manager.md §目录初始化 | ⏸️ 功能集成在 plugin.py，迭代 2 拆分 |
| Soul 解析器 | `plugins/role_manager/soul_parser.py` | framework.md §Soul Schema | ✅ |
| suri 默认 Soul | `roles/suri/soul.md` | framework.md §Soul 模板 | ✅ |
| Telegram 通道 | `plugins/access/telegram.py` | access.md §Telegram 通道 | ✅ |
| Bot API 封装 | `plugins/access/telegram_bot.py` | access.md §Bot 交互 | ✅ |

**验收标准**：
- role_manager 能创建 suri 角色，生成 soul.md（含 code 技能）✅
- suri 角色能订阅 user.input 并调用 llm_gateway ✅（由 role_manager 代理）
- Telegram Bot 能接收消息并回复 ✅
- CLI 和 Telegram 的消息互不干扰 ✅（按 session_id 路由）

### Day 10-12：整合测试 + PRD 回归 + 代码能力验证

| 任务 | 说明 | 状态 |
|------|------|------|
| 单元测试 | EventBus / PluginManager / code_tool / security_service | ✅ 19 项通过 |
| 端到端测试 | 从启动到对话完整走一遍 | ⚠️ 需手动验证（需 API Key） |
| 代码阅读测试 | suri 读取 main.py → 分析 → 输出建议 | ⚠️ 需手动验证 |
| 项目分析测试 | suri 分析项目架构 → 输出报告 | ⚠️ 需手动验证 |
| 编码计划测试 | suri 读取 iteration_02.md → 输出开发计划 | ⚠️ 需手动验证 |
| 异常测试 | 断网、API Key 错误、模型超时、路径越界 | ⚠️ 部分覆盖（security_service 路径越界 ✅） |
| 配置测试 | 首次向导、热重载、跳过 Telegram | ✅ |
| PRD 回归 | 检查实现与 PRD 是否一致，不一致处更新 PRD | ✅ 本文件已同步更新 |

---

## 测试矩阵

### 基础功能测试

| 测试项 | 通过标准 | 状态 |
|--------|----------|------|
| 终端启动 | `python main.py` 正常启动，无异常退出 | ✅ |
| 首次向导 | 能完整配置模型+API Key+版本+Telegram，生成 config.json | ✅ |
| 5 模型对话 | 每个模型都能正常收发消息 | ⚠️（4/5，wenxin 需 access_token） |
| 版本切换 | 同一厂商内版本切换正常 | ✅ |
| 跨厂商切换 | 从模型 A 切换到模型 B 正常 | ✅ |
| 新增模型 | 配置新厂商模型后可用 | ✅ |
| 异常降级 | API 超时/错误时友好提示，可自然语言切换 | ✅ |
| Telegram 配置 | 输入 Token 后验证有效性，Bot 上线能收发消息 | ✅ |
| Telegram 跳过 | 输入 /skip 后正常进入会话，后续可唤醒配置 | ✅ |
| Telegram Token 验证 | 无效 Token 提示重新输入，不保存错误配置 | ✅ |
| 配置热重载 | 修改 config.json 后插件感知变更 | ✅ |
| 日志记录 | 所有事件和操作都有日志记录 | ✅ |
| 安全扫描 | 加载含 forbidden API 的插件被拒绝 | ✅ |

### 代码能力测试（迭代 1 新增）

| 测试项 | 通过标准 | 状态 |
|--------|----------|------|
| 读取文件 | suri 能读取 main.py 并返回内容 | ✅ |
| 列出目录 | suri 能列出 plugins/ 目录下的所有插件 | ✅ |
| 代码搜索 | suri 能在项目中搜索特定函数名 | ✅ |
| 项目统计 | suri 能统计项目文件数和代码行数 | ✅ |
| 代码分析 | suri 能分析 main.py 的功能和结构 | ⚠️ 需 LLM Key 手动验证 |
| 架构分析 | suri 能分析项目整体架构并输出报告 | ⚠️ 需 LLM Key 手动验证 |
| 开发计划 | suri 能读取 iteration_02.md 并输出开发计划 | ⚠️ 需 LLM Key 手动验证 |
| 伪代码生成 | suri 能为指定插件生成伪代码骨架 | ⚠️ 需 LLM Key 手动验证 |
| 路径越界防护 | 尝试读取 /etc/passwd 或 ~/.suri/config.json 时被拒绝 | ✅ |

---

## 文件结构（迭代 1 结束时应具备）

```
suri-agent/
  - main.py                          # 入口 ✅
  - .env.example                     # 环境变量示例 ✅
  - .kimi/                           # AI 开发规范 ✅
  - agent_framework/                 # ✅
    - __init__.py
    - event_bus/
      - __init__.py
      - bus.py                       # EventBus 实现 ✅
    - plugin_manager/
      - __init__.py
      - manager.py                   # PluginManager 实现 ✅
    - suri_core_plugin/
      - __init__.py
      - plugin.py                    # SuriCorePlugin ✅
    - migrations/
      - 001_initial.sql              # 初始 schema ✅
  - plugins/
    - access/                        # 统一接入 ✅
      - __init__.py
      - manifest.json
      - plugin.py                    # 主入口 ✅
      - cli.py                       # CLI 通道 ✅
      - telegram.py                  # Telegram 通道 ✅
      - telegram_bot.py              # Bot API 封装 ✅
      - wizard.py                    # 配置向导 ✅
      - command_parser.py            # ⏸️ 迭代 2 拆分，当前集成在 cli.py
      - history.py                   # ⏸️ 迭代 2
    - config_service/                # 配置管理 ✅
      - __init__.py
      - manifest.json
      - plugin.py                    # ✅ 含 config.json 读写
      - store.py                     # ⏸️ 迭代 2 拆分
    - llm_gateway/                   # LLM 网关 ✅
      - __init__.py
      - manifest.json
      - plugin.py                    # ✅ 含客户端、路由、切换逻辑
      - client/                      # ⏸️ 迭代 2 拆分
        - __init__.py
        - base.py
        - ernie.py
        - qwen.py
        - chatglm.py
        - kimi.py
        - deepseek.py
      - router.py                    # ⏸️ 迭代 2 拆分
      - cache.py                     # ⏸️ 迭代 2
      - retry.py                     # ⏸️ 迭代 2
    - log_service/                   # 日志 ✅
      - __init__.py
      - manifest.json
      - plugin.py                    # ✅ 含分级日志输出
      - logger.py                    # ⏸️ 迭代 2 拆分
    - security_service/              # 安全（含沙箱）✅
      - __init__.py
      - manifest.json
      - plugin.py                    # ✅ 含 AST 扫描 + 沙箱逻辑
      - ast_scanner.py              # ⏸️ 迭代 2 拆分
      - sandbox.py                   # ⏸️ 迭代 2 拆分
    - role_manager/                  # 角色管理 ✅
      - __init__.py
      - manifest.json
      - plugin.py                    # ✅ 含角色创建逻辑
      - creator.py                   # ⏸️ 迭代 2 拆分
      - soul_parser.py               # ✅ Soul 解析器
    - code_tool/                     # [新增] 代码阅读工具 ✅
      - __init__.py
      - manifest.json
      - plugin.py
      - reader.py
      - explorer.py
      - search.py
      - stats.py
    - [memory_service/]              # ⏸️ P1，迭代 2
  - shared/                          # ✅
    - __init__.py
    - interfaces/
      - __init__.py
      - plugin.py                    # PluginInterface ✅
    - utils/
      - __init__.py
      - event_types.py               # Event / Priority ✅
      - log.py                       # ⏸️ 迭代 2
      - db.py                        # ⏸️ 迭代 2
  - roles/
    - suri/
      - soul.md                      # 核心角色 Soul（YAML frontmatter）✅
  - tests/                           # ✅
    - __init__.py
    - framework/
      - __init__.py
      - base.py                      # ⏸️ 迭代 2
      - fixtures.py                  # ⏸️ 迭代 2
    - unit/                          # ✅
      - __init__.py
      - test_event_bus.py
      - test_plugin_manager.py
      - test_code_tool_modules.py
    - integration/                   # ✅
      - __init__.py
    - plugin/                        # ✅
      - __init__.py
      - test_code_tool.py
      - test_security_service.py
  - prd/                             # 产品文档 ✅
  - iteration_plan/                  # 本计划文档 ✅
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


---

## 迭代 1 体验优化与 Bug 修复记录

### 修复 1：`/reconfig` 后仍报 API Key 错误
**问题**：运行 `/reconfig` 删除了 `config.json`，但 `llm_gateway` 内存中的 `_api_keys` 未被清空，下次请求继续使用旧 Key，导致再次报错。

**修复**：
- `access` 的 `/reconfig` 处理：删除文件后发布 `system.config_changed`，`payload={"reason": "reconfig"}`
- `llm_gateway` 的 `_on_config_changed`：检测到 `reason="reconfig"` 时，先 `self._api_keys.clear()`，再重新加载

### 修复 2：错误提示重复打印
**问题**：同一错误事件在 CLI 中被输出两次，形成刷屏。

**修复**：`access._on_llm_error` 增加 5 秒去重窗口：
- 以 `session_id + error_code` 为 key 记录上次错误时间
- 5 秒内重复的错误直接静默丢弃

### 修复 3：终端交互体验优化（彻底重构）
**问题**：
- `input()` 和 `print()` 竞争 stdout，提示符被异步输出冲掉、错位、重复
- `────` 分隔线过于冗长
- 错误提示多行展开，占用过多屏幕空间

**修复**：
- **`cli.py` 彻底重构为线程分离 + ANSI 清行方案**：
  - 独立线程 `sys.stdin.readline()` 读取输入，通过 `asyncio.Queue` 传递给主事件循环
  - 系统输出使用 `\r\033[K`（回车 + 清除到行尾）清除当前行后再打印
  - 输出后自动重绘 `> ` 提示符，确保提示符始终在最底行
  - `access/plugin.py` 所有 CLI 输出统一通过 `self._cli.print_output()`，不再直接 `print()`
- 简化输出格式：
  - 正常响应：`Suri: {content}`
  - 错误：`⚠️  {error}  提示: /setkey <厂商> 修改 或 /switch <厂商> 切换`
  - 系统消息：`[Suri] {msg}`


### 修复 4：`/reconfig` 设计不合理（直接删除配置）
**问题**：
- `/reconfig` 直接删除整个 `config.json`，用户只是某个 Key 失效，却被迫重新配置所有内容
- 如果 Key 只是暂时不可用（网络/厂商问题），删除后恢复又要重配
- 没有"修改"只有"删除"，体验很差

**重新设计**：
1. **新增 `/setkey <厂商> [key]` 命令** — 最常见的"单个 Key 失效"场景：
   - `/setkey deepseek sk-xxx` → 直接修改，验证后保存
   - `/setkey deepseek` → 交互式输入 Key，验证后保存
   - 保存后自动发布 `system.config_changed`，llm_gateway 实时加载，无需重启

2. **`/reconfig` 改为配置菜单** — 不再默认删除：
   ```
   Suri 配置编辑
   ========================
   当前默认厂商: deepseek
   已配置厂商: ✅ deepseek
   Telegram: 未启用

   操作选项：
     1. 修改某个厂商的 API Key
     2. 添加新厂商
     3. 修改 Telegram Token
     4. 删除所有配置（需确认）
     0. 退出
   ```

3. **删除配置需要输入 `DELETE` 确认**，防止误操作

4. **错误提示更新**：API Key 错误时提示 `/setkey <厂商> <key> 快速修改` 而不是 `/reconfig`

**新增文件**：
- `plugins/access/config_editor.py` — `ConfigEditor` 类，负责运行时配置的读写和菜单交互

**修改文件**：
- `plugins/access/cli.py` — 本地处理 `/setkey` 和 `/reconfig`
- `plugins/access/plugin.py` — 更新错误提示，Telegram `/reconfig` 发送帮助信息
- `plugins/llm_gateway/plugin.py` — 错误消息中提示 `/setkey` 而非 `/reconfig`
- `plugins/access/telegram.py` — 更新命令描述

---

## 迭代 1 优化与 Bug 修复记录（2026-05-03 批量修复）

### 修复 5：security_service 拦截 tool.call 后未放行通过检查的请求
**问题**：security_service 订阅 `tool.call` 事件后，对通过安全检查的请求没有放行（未发布 `tool.call` 给目标插件），导致所有工具调用都被静默拦截。

**修复**：在 `_on_tool_call` 中，安全检查通过后发布新的 `tool.call` 事件，target 指向目标插件。

### 修复 6：CLI input() 与 print_output() 竞争问题
**问题**：`input()` 阻塞主线程期间，异步输出无法打印，导致提示符被冲掉、输出错位。

**修复**：CLI 重构为线程分离方案：
- 独立线程 `sys.stdin.readline()` 读取输入，通过 `asyncio.Queue` 传递给主事件循环
- 系统输出使用 `\r\033[K`（回车 + 清除到行尾）清除当前行后再打印
- 输出后自动重绘 `> ` 提示符

### 修复 7：config_editor 与 cli 的 input() 冲突
**问题**：ConfigEditor 使用同步 `input()`，CLI 使用异步 `_async_input`，两者竞争 stdin。

**修复**：ConfigEditor 接受可选的 `input_func` 参数，CLI 模式下传入 `cli._async_input`，统一输入方式。

### 修复 8：PluginManager 拓扑排序算法 Bug
**问题**：原算法计算的是"被依赖数"而非"依赖数"，导致排序结果不正确。例如 A 依赖 B，B 应排在 A 前面，但原算法可能将 A 排在 B 前面。

**修复**：重构 `_topological_sort` 方法：
- 构建反向图：`graph[name]` = 依赖 name 的节点集合
- 入度 = 当前节点依赖的节点数
- 入度为 0 的节点先加载（不依赖任何其他节点）

### 修复 9：EventBus 事件持久化主键冲突
**问题**：`_persist_event` 使用 `event.request_id` 作为主键，多个事件可能共享同一 request_id，导致 `INSERT OR IGNORE` 静默丢弃后续事件。

**修复**：移除 `event_id` 列，使用 SQLite 自增 ID 作为主键。

### 优化 10：配置编辑逻辑统一到 config_editor.py
**问题**：配置编辑逻辑分散在 `access/plugin.py`（`_run_config_editor`、`_edit_api_key`、`_add_provider`、`_edit_telegram`）和 `config_editor.py` 中，职责不清。

**修复**：删除 `access/plugin.py` 中的重复配置编辑方法，统一委托给 `ConfigEditor` 处理。`access/plugin.py` 只做事件路由。

### 优化 11：llm_gateway 异常处理完善
**问题**：`_send_request` 中异常处理不完善，HTTP 错误、网络超时等未区分，错误信息不友好。

**修复**：
- 统一异常处理：401/403 → PermissionError，429/502/503 → ConnectionError
- 增加重试逻辑：429/502/503 最多重试 2 次（指数退避）
- 增加 API Key 编码前置检查
- 错误信息包含可操作建议

### 优化 12：role_manager 集成 code_tool 调用能力
**问题**：suri 的 system prompt 中没有工具调用说明，LLM 不知道可以调用 code_tool。

**修复**：在 `_on_user_input` 的 system prompt 中注入 code_tool 调用说明，包含 4 个可用工具的调用格式和参数说明。

### 优化 13：补充单元测试
**新增测试文件**：
- `tests/plugin/test_access.py` — 14 个测试（CLISession、ConfigEditor、ConfigWizard）
- `tests/plugin/test_llm_gateway.py` — 14 个测试（初始化、切换、聊天、事件处理、命令）
- `tests/plugin/test_role_manager.py` — 12 个测试（初始化、角色 CRUD、事件处理、命令）

**测试结果**：48/48 全部通过（含原有 8 个单元测试）

---

## 迭代 1 增强版（2026-05-03 通道共生 + 写入能力 + 测试框架）

### 优化 14：通道基类 + 共用格式化（通道共生架构）

**背景**：suri 的能力（对话、工具调用、代码分析等）是所有通道共享的，CLI/Telegram/Web/飞书只是不同的"显示层"。需要设计好共用模块，让各通道能按自身能力渲染输出。

**新增文件**：
- `plugins/access/base.py` — `BaseChannel` 抽象基类，所有通道继承
  - `send_message()` — 发送文本消息
  - `send_decision()` — 发送决策菜单
  - `send_status()` — 发送状态信息
- `plugins/access/formatter.py` — `MessageFormatter` 共用格式化器
  - `format_response()` — 格式化 LLM 响应
  - `format_error()` — 格式化错误消息（按错误码区分提示）
  - `format_status()` — 格式化模型配置状态面板
  - `format_decision()` — 格式化决策菜单
  - `format_system()` — 格式化系统消息
  - `format_success()` — 格式化成功消息
  - `format_model_switch()` — 格式化模型切换成功消息

**通道能力矩阵**：

| 能力 | CLI | Telegram | Web | 飞书 |
|------|-----|----------|-----|------|
| 文本对话 | ✅ | ✅ | ✅ | ✅ |
| Markdown 渲染 | ⚠️ 纯文本 | ✅ | ✅ | ✅ |
| 图片输出 | ❌ | ✅ | ✅ | ✅ |
| 交互式菜单 | ✅ ANSI | ⚠️ 按钮 | ✅ | ⚠️ |
| 文件上传 | ❌ | ✅ | ✅ | ✅ |
| 流式输出 | ⚠️ 逐行 | ✅ | ✅ SSE | ✅ |
| 命令补全 | ✅ readline | ❌ | ✅ | ❌ |

### 优化 15：终端显示全面优化

**状态面板**：启动时显示模型配置状态面板：
```
  Suri Agent CLI 模式

📋 模型配置状态：
  ✅ DeepSeek (deepseek-chat) — 已配置，可用
  ❌ Moonshot (Kimi) — 未配置 API Key
  ❌ 智谱 (ChatGLM) — 未配置 API Key
  ❌ 阿里通义 — 未配置 API Key
  ❌ 百度文心 — 未配置 API Key

当前默认模型: deepseek/deepseek-chat

常用命令:
  /help     显示完整帮助
  /status   查看系统状态
  /model    查看当前模型
  /setkey   修改 API Key
  /reconfig 进入配置菜单
  /logs     查看日志路径
  /quit     退出程序

直接输入文字开始对话，或输入命令。
```

**异常恢复菜单**：LLM 调用失败时自动弹出交互式恢复菜单：
```
⚠️  DeepSeek API Key 无效或已过期

┌─────────────────────────────────────┐
│  模型连接异常，请选择操作：           │
│                                     │
│  1. 修改 DeepSeek 的 API Key        │
│  2. 切换到其他已配置厂商             │
│  3. 添加新厂商并切换                 │
│  4. 忽略，继续使用当前模型           │
│                                     │
│  请选择 [1-4]:                      │
└─────────────────────────────────────┘
```

**输出格式优化**：
- 正常响应：`Suri: {content}`
- 错误：`⚠️  {error}  提示: /setkey <厂商> 修改 或 /switch <厂商> 切换`
- 系统消息：`[Suri] {msg}`
- 模型切换成功：`✅ 已切换到 {provider}/{model}`
- 配置修改成功：`✅ {provider} API Key 已更新`

**错误去重**：同一 session 的同一错误码在 5 秒内只显示一次，避免重复刷屏。

### 优化 16：共用路由层重构

**修改文件**：`plugins/access/plugin.py`

**改动**：
- `_on_llm_response` — 按 session_id 路由到对应通道（CLI 用 `print_output`，Telegram 用 `send_response`）
- `_on_llm_error` — 统一错误格式化 + 去重 + 401/403/3002 自动触发恢复菜单
- `_on_user_command` — 处理 status/model/reload/reconfig/logs 命令
- `_send_response` — 统一发送响应到对应通道

### 优化 17：code_tool 写入能力提前（从迭代 2 提前到迭代 1）

**背景**：让 suri 在迭代 1 就具备代码生成能力，而不仅仅是代码阅读。

**新增文件**：
- `plugins/code_tool/writer.py` — 文件写入模块
  - `write_file()` — 写入/覆盖文件
  - `append_file()` — 追加内容到文件末尾
  - `create_file()` — 创建新文件（已存在则返回错误）

**安全规则**：
| 路径 | 权限 |
|------|------|
| `plugins/{new_plugin}/` | 需用户审批 |
| `plugins/{existing}/` | 需用户审批 |
| `tests/` | 需用户审批 |
| `roles/` | 需用户审批 |
| `agent_framework/` | ❌ 禁止 |
| `shared/interfaces/` | ❌ 禁止 |
| `~/.suri/` | ❌ 禁止 |

**修改文件**：`plugins/code_tool/plugin.py` — 注册 `code_tool.write_file`、`code_tool.append_file`、`code_tool.create_file` 事件处理

### 优化 18：测试框架全面优化

**新增文件**：
- `tests/framework/base.py` — 测试框架基类
  - `AsyncTestCase` — 自动创建/销毁 EventBus 的异步测试基类
  - `EventCollector` — 事件收集器，在测试中收集特定事件
- `tests/plugin/test_access_events.py` — 10 个测试
  - LLM 响应路由、错误去重、不同错误码去重、system.ready、user.command status/logs
  - formatter 格式化测试（401/3002/状态面板/决策菜单）
- `tests/plugin/test_code_tool_events.py` — 10 个测试
  - 事件处理（read_file、list_dir、未知 tool_name）
  - writer 模块（写入、追加、创建、已存在、越界、禁止目录、需审批标记）

**测试结果**：79/79 全部通过

### 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `plugins/access/base.py` | 通道基类 |
| 新增 | `plugins/access/formatter.py` | 共用格式化 |
| 重写 | `plugins/access/cli.py` | 状态面板 + 恢复菜单 + 双模式输入 |
| 重写 | `plugins/access/plugin.py` | 共用路由层 + LLM 在线/离线状态管理 |
| 新增 | `plugins/code_tool/writer.py` | 文件写入 |
| 修改 | `plugins/code_tool/plugin.py` | 注册写入事件 |
| 新增 | `tests/framework/base.py` | 测试基类 |
| 新增 | `tests/plugin/test_access_events.py` | access 事件测试 |
| 新增 | `tests/plugin/test_code_tool_events.py` | code_tool 事件测试 |
| 修改 | `.kimi/AGENTS.md` | 新增 AI 开发参考铁律 |
| 修改 | `prd/iteration_plan/iteration_01.md` | 追加本增强版记录 |
| 修改 | `prd/plugins/access.md` | 更新文件结构 + CLI 描述 + 双模式设计 |
| 修改 | `prd/plugins/code_tool.md` | 更新接口（写入提前到迭代 1） |
| 修改 | `prd/file_directory.md` | 更新文件结构 |
| 修改 | `prd/plugins/llm_gateway.md` | 明确全局切换策略 + 未来角色级模型配置 |
