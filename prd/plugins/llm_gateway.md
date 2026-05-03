# llm_gateway 插件 PRD

## 定位

大模型统一网关插件，是系统唯一对外模型调用出口。负责模型调用、上下文管理、智能路由、Token 统计、流式输出。

## 功能需求

### 1. 模型调用
- 支持 OpenAI 兼容格式（Chat Completions）
- 支持多提供商：Moonshot、DeepSeek、GLM、OpenAI、Anthropic
- 异步非阻塞调用（Python 标准库 `urllib.request` + `ssl`，零外部依赖）
- 超时 60s
- **零依赖原则**：不使用 httpx、requests、aiohttp 等第三方 HTTP 库

### 2. 智能路由
- 根据任务内容自动选择模型：
  - 代码/编程 → 推理模型（DeepSeek 等）
  - 长文本/总结 → 长上下文模型
  - 创意/写作 → 通用大模型
- 标签匹配打分机制
- 支持 `auto_select=True` 参数

### 3. 上下文管理
- 对话历史维护（按 session 隔离）— 由 `role_manager` 的 `_session_contexts` 管理
- 每次请求的 messages 结构：`[system_prompt, ...历史消息..., user_input]`
- system prompt 每次重新生成（含当前模型信息），不保存在历史中
- 历史消息上限 20 条（`MAX_HISTORY_MESSAGES`），超出后丢弃最早的
- Token 消耗统计（input/output/total/calls）
- 上下文窗口截断策略（预留）

**模型切换时上下文处理策略**：
- 切换模型后，历史消息**保留**在上下文中，不清空
- 因为 system prompt 中注入了当前模型信息（通过 `_inject_model_info`），LLM 知道自己在用哪个模型，不会混淆
- 切换前后模型能力差异大时（如从 deepseek 切到 kimi），历史消息中的工具调用结果仍然可用，只是新模型可能无法复现之前的工具调用
- 用户可通过 `/clear` 命令手动清空当前会话的上下文历史
- 未来（迭代 2+）可支持按角色隔离上下文：不同角色使用不同的 `_session_contexts`

**上下文 vs 记忆服务（memory_service）的区别**：

| 维度 | 会话上下文（_session_contexts） | 记忆服务（memory_service） |
|------|-------------------------------|---------------------------|
| **存储位置** | 内存（`Dict[str, List]`） | 磁盘（SQLite + Markdown 文件） |
| **生命周期** | 进程生命周期，进程重启后丢失 | 持久化，跨进程/跨天保留 |
| **用途** | 保持当前对话的连贯性（"刚才说了什么"） | 长期知识积累（"用户偏好什么"、"之前解决过什么问题"） |
| **数据量** | 小（20 条消息上限） | 大（可存储数千条记录） |
| **访问方式** | 自动注入到 LLM 请求的 messages 中 | 按需查询，通过 system prompt 注入 |
| **清理策略** | 超出上限自动丢弃最早的 | 按 TTL 归档或手动清理 |
| **实现位置** | `role_manager` 插件 | `memory_service` 插件（迭代 2+） |
| **迭代** | 迭代 1 已实现 | 迭代 2+ 规划中 |

**典型工作流**：
1. 用户说"帮我看看 main.py" → 上下文记录这条消息
2. suri 调用 code_tool 读取文件 → 上下文记录工具调用结果
3. 用户说"再帮我看看 plugin.py" → 上下文包含前两步，LLM 知道"再"指的是什么
4. 用户退出程序，第二天重新启动 → 上下文丢失（内存），但 memory_service 中可能保存了"用户经常分析代码"的洞察
5. memory_service 的洞察在 system prompt 中注入 → suri 知道"这个用户喜欢分析代码"，但不知道昨天具体说了什么

### 3a. 模型切换策略

**当前策略（迭代 1）— 全局切换**：
- `/switch <厂商> [模型]` 无 session_id → 修改全局默认模型
- CLI 切换后 Telegram 也受影响（所有通道共享同一全局默认模型）
- 优点：简单，管理员切换后所有通道受益
- 缺点：CLI 用户切换可能影响 Telegram 用户

**未来策略（迭代 2+）— 角色级模型配置**：
- 每个角色（soul.md）可配置默认模型：`default_model: deepseek/deepseek-v4-flash`
- `role_manager` 在 `llm.request` 中携带 `role_id`，`llm_gateway` 按角色选择模型
- 优先级：角色级 > 会话级 > 全局
- 不同角色可使用不同模型（如 suri 用 deepseek，图片生成角色用通义千问）
- 会话级覆盖（`_session_provider`/`_session_model`）保留供未来使用，当前未启用

### 4. 流式输出
- SSE Server-Sent Events 流式返回
- 逐字/逐句推送
- 支持接入层中转 SSE

### 5. 降级策略
- 默认模型失败时自动切换备用模型 ⏸️ 迭代 2
- 401/403/429/503 时提示重新配置 ✅
- 连续降级告警（预留）

### 6. 异常处理与重试
- **统一异常分类**：
  - 401/403 → `PermissionError`（API Key 无效或权限不足）
  - 429/502/503 → `ConnectionError`（服务限流或不可用）
  - 其他 HTTP 错误 → 通用异常
- **重试逻辑**：429/502/503 最多重试 2 次，指数退避（1s → 2s）
- **前置检查**：API Key 编码检查（非 ASCII 字符提前报错）
- **错误信息**：包含可操作建议（如 `/setkey <厂商> 修改` 或 `/switch <厂商> 切换`）

### 6. 模型支持状态（迭代 1）

| 厂商 | 状态 | 说明 |
|------|------|------|
| DeepSeek | ✅ 完整 | OpenAI 兼容格式。模型：`deepseek-v4-pro` / `deepseek-v4-flash` / `deepseek-chat`（兼容） |
| Moonshot (Kimi) | ✅ 完整 | OpenAI 兼容格式 |
| 智谱 (ChatGLM) | ✅ 完整 | OpenAI 兼容格式 |
| 阿里通义 | ✅ 完整 | OpenAI 兼容格式 |
| 百度文心 | ⚠️ 待完善 | 需 OAuth2 access_token 流程，迭代 2 实现 |

### 6. 首次运行引导
- 交互式模型配置向导
- 品牌选择 → 型号自动测试 → 保存配置
- 无模型时阻塞运行

## 接口定义

### 订阅事件
- `llm.request` → 处理模型请求
- `system.config_changed` → 重新加载 config.json 中的 API Key 和模型配置
- `user.command`（command=switch）→ 切换当前使用的厂商和模型

### 发布事件
- `llm.response` — 模型成功响应
- `llm.error` — 模型调用失败

## 事件 Payload Schema

### 订阅事件

#### `llm.request`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 请求唯一标识 |
| `model_id` | string | 否 | 指定模型，空则使用默认模型 |
| `messages` | array | 是 | 消息列表，格式 `[{"role": "user", "content": "..."}]` |
| `temperature` | float | 否 | 温度参数，默认 0.7 |
| `stream` | boolean | 否 | 是否流式输出，默认 false |
| `timeout` | float | 否 | 超时（秒），默认 60 |
| `task_id` | string | 否 | 关联任务 ID |

#### `user.command`（command=switch）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `command` | string | 是 | 固定值 `"switch"` |
| `args` | array | 是 | `[provider, model?]`，如 `["deepseek", "deepseek-v4-flash"]` |
| `session_id` | string | 否 | 会话标识，用于隔离不同会话的模型选择 |

**说明**：
- 仅指定厂商时使用该厂商默认模型：`["deepseek"]` → 使用 `deepseek-v4-pro`
- 同时指定厂商和模型：`["deepseek", "deepseek-v4-flash"]`
- 迭代 1 中 `session_id` 参数保留但未启用，所有切换均为全局生效
- 迭代 2+ 引入角色级模型配置后，`session_id` 用于会话级临时覆盖

### 发布事件

#### `llm.response`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 对应请求 ID |
| `model_id` | string | 是 | 实际使用的模型 |
| `content` | string | 是 | 模型响应内容 |
| `usage` | object | 是 | token 使用统计 `{"input": 1024, "output": 512, "total": 1536}` |
| `finish_reason` | string | 否 | 结束原因：stop / length / error |
| `duration_ms` | integer | 否 | 调用耗时 |

#### `llm.error`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 对应请求 ID |
| `error_code` | integer | 是 | 错误码 |
| `error_type` | string | 是 | 错误类型：rate_limit / timeout / model_unavailable / invalid_request |
| `message` | string | 是 | 错误描述 |
| `retryable` | boolean | 是 | 是否可重试 |

**HTTP 状态码映射**：
| HTTP 状态 | 错误类型 | 处理策略 | 用户操作建议 |
|-----------|----------|----------|-------------|
| 401 | invalid_request | API Key 无效或过期 | 运行 `/reconfig` 重新配置，或 `/switch` 切换模型 |
| 403 | invalid_request | 权限不足 | 检查账号权限，或切换模型 |
| 429 | rate_limit | 请求过频 | 稍后重试，或 `/switch` 切换模型 |
| 503 | model_unavailable | 模型服务暂不可用 | `/switch` 切换到其他模型 |
| 3002 | config_missing | 未配置 API Key | 运行 `/reconfig` 重新配置 |
| 超时 | timeout | 请求超时 | 可重试，或切换模型 |

**错误降级策略**：
- 401/403/3002 → 提示重新配置或切换模型，不死等
- 429/503 → 提示切换模型或稍后重试
- 所有错误事件均携带 `provider` 字段和 `retryable` 标志，供接入层决策 |

## 配置项

```yaml
llm_gateway:
  models:
    - model_id: "glm-4"
      provider: "glm"
      base_url: "https://open.bigmodel.cn/api/paas/v4"
      api_key: ""  # 从环境变量或 ~/.suri/config.json 读取
      is_default: true
      tags: ["general", "long-context"]
      context_window: 128000
  default_model: "glm-4"
  timeout: 60.0
  max_retries: 3
```

**API Key 读取优先级**：
1. `~/.suri/config.json` 中 `llm_gateway.providers.{name}.api_key`（向导保存）
2. 环境变量 `SURI_{PROVIDER}_API_KEY`（如 `SURI_DEEPSEEK_API_KEY`）
3. manifest 中的默认空值

## 依赖关系

- 上游：suri_core
- 下游：task_scheduler（等待 LLM 响应）、各接入插件（返回响应给用户）

## 接口方法

### `set_provider(provider, model=None, session_id=None)`
切换当前使用的厂商和模型。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `provider` | string | 是 | 厂商标识 |
| `model` | string | 否 | 模型标识，空则使用厂商默认 |
| `session_id` | string | 否 | 若指定，仅切换该会话的模型；否则切换全局默认 |

**模型选择优先级（迭代 1）**：
1. 全局默认（`_active_provider` / `_active_model`）— 所有通道共享

**模型选择优先级（迭代 2+ 角色级）**：
1. 角色级配置（soul.md 中的 `default_model`）— 最精确
2. 会话级覆盖（`_session_provider[session_id]`）— 临时切换
3. 全局默认（`_active_provider` / `_active_model`）— 兜底

**当前实现说明**：
- `set_provider()` 支持 `session_id` 参数，但迭代 1 中所有调用均不传 session_id
- `_session_provider`/`_session_model` 数据结构已预留，供迭代 2 角色级配置使用
- 迭代 1 中 `/switch` 始终修改全局默认，所有通道共享

### `chat(messages, provider=None, model=None, session_id=None)`
发送聊天请求。若 `session_id` 存在且该会话有模型覆盖，优先使用会话级模型。

### `_inject_model_info(messages, provider, model)`
在 `messages` 的第一个 `system` role 消息末尾注入当前运行环境信息，让角色知道自己正在通过哪个模型服务，以及切换模型的命令格式。若无 `system` message，则在开头插入一条。

注入内容示例：
```
[当前运行环境] 你正在通过 deepseek/deepseek-v4-pro 模型为用户服务。
用户可以通过命令 '/switch <厂商> [模型]' 切换模型，
例如 '/switch kimi' 或 '/switch deepseek deepseek-v4-flash'。
```

## 数据模型

### Token 统计
```json
{
  "model_id": "glm-4",
  "input": 1024,
  "output": 512,
  "total": 1536,
  "calls": 10
}
```

## 生命周期

1. `init()` → 加载 manifest 配置、读取环境变量 API Key
2. `_load_from_config_file()` → 从 `~/.suri/config.json` 加载向导保存的配置（API Key、默认厂商、模型列表）
3. `register_events()` → 订阅 `llm.request`、`user.command`、`system.config_changed`
4. `start()` → 标记就绪
5. `stop()` → 关闭待处理请求
6. `cleanup()` → 无额外资源需清理（标准库 urllib 无需关闭客户端）

### `system.config_changed` 处理
- 普通配置变更（如热重载）：调用 `_load_from_config_file()` 重新加载
- `/reconfig` 重置（`reason: "reconfig"`）：**先清空内存中的 `_api_keys`**，再重新加载。确保删除 `config.json` 后内存中不再残留旧 Key，避免用户运行 `/reconfig` 后仍然收到 "API Key 无效" 错误


## 安全边界

- API Key 不记录到日志
- 请求内容脱敏（密码、Token）
- 响应错误信息不暴露内部堆栈
