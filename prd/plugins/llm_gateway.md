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
- 对话历史维护（按 session 隔离）
- Token 消耗统计（input/output/total/calls）
- 上下文窗口截断策略（预留）

### 4. 流式输出
- SSE Server-Sent Events 流式返回
- 逐字/逐句推送
- 支持接入层中转 SSE

### 5. 降级策略
- 默认模型失败时自动切换备用模型
- 401/403/429/503 时提示重新配置
- 连续降级告警（预留）

### 6. 首次运行引导
- 交互式模型配置向导
- 品牌选择 → 型号自动测试 → 保存配置
- 无模型时阻塞运行

## 接口定义

### 订阅事件
- `llm.request` → 处理模型请求

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

## 配置项

```yaml
llm_gateway:
  models:
    - model_id: "glm-4"
      provider: "glm"
      base_url: "https://open.bigmodel.cn/api/paas/v4"
      api_key: ""  # 从环境变量读取，格式：SURI_{PROVIDER}_API_KEY（如 SURI_DEEPSEEK_API_KEY）
      is_default: true
      tags: ["general", "long-context"]
      context_window: 128000
  default_model: "glm-4"
  timeout: 60.0
  max_retries: 3
```

## 依赖关系

- 上游：suri_core
- 下游：task_scheduler（等待 LLM 响应）、各接入插件（返回响应给用户）

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

1. `init()` → 加载 model_config.json、读取环境变量 API Key
5. `cleanup()` → 无额外资源需清理（标准库 urllib 无需关闭客户端）
2. `register_events()` → 订阅 llm.request
3. `start()` → 标记就绪
4. `stop()` → 关闭待处理请求


## 安全边界

- API Key 不记录到日志
- 请求内容脱敏（密码、Token）
- 响应错误信息不暴露内部堆栈
