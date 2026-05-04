# formatter 消息格式化规范

> **插件归属**：`access`（`agent_framework/plugins/access/formatter.py`）
> **定位**：所有通道（CLI / Telegram / Web）共用的消息格式化器。
> 各通道可重写特定方法实现差异化渲染。

---

## 一、层次定位

```
所有通道插件（CLI / Telegram / Web / Desktop）
    │
    ▼
SessionHub 获取系统数据（插件列表、模型状态等）
    │
    ▼
MessageFormatter 静态方法渲染面板
    │
    └── format_plugin_list()     → 插件列表面板
    └── format_plugin_detail()   → 插件详情 7 区块
    └── format_model_status()    → LLM 模型状态面板
    └── format_startup_panel()   → 启动面板（插件列表 + 模型状态合并）
    └── format_response()        → 自然语言回复渲染
    └── format_error()           → 错误消息格式化
    └── format_decision()        → 决策选项展示
    │
    ▼
通道自己的 send() 方法输出到用户
```

**核心原则**：
- MessageFormatter 只做**格式化**，不关心来源和输出目标
- 所有方法都是 `@staticmethod`，纯函数
- 通道可以在子类重写特定方法实现差异化（如 Telegram 用 MarkdownV2）

---

## 二、插件类型与层级映射

```python
TYPE_MAP = {
    "core":        ("核心",   "系统内核"),
    "service":     ("服务",   "基础服务"),
    "capability":  ("能力",   "能力插件"),
    "execution":   ("执行",   "执行层"),
    "integration": ("接入",   "接入层"),
    "extension":   ("扩展",   "扩展插件"),
}

LAYER_MAP = {
    "core":        "core",
    "service":     "service",
    "capability":  "role",
    "execution":   "execution",
    "integration": "access",
    "extension":   "extension",
}
```

---

## 三、插件列表 /plugins 面板

### 3.1 数据结构

```python
plugins: List[Dict[str, Any]] = [
    {
        "id": "llm_gateway",
        "name": "llm_gateway",
        "type": "service",
        "status": "running",         # running / stopped / load_failed / upgrading / removed
        "heartbeat": 1,              # 秒，None = 尚未上报心跳
        "description": "5 家国产大模型路由",
        "version": "1.0.0",
    },
    ...
]
```

### 3.2 渲染输出

```
> /plugins

┌───────────────────────────────────────────────┐
│  Suri Agent 插件列表                           │
├─────┬───────────────────┬─────────┬───────────┤
│  #  │ 名称              │ 类型    │ 状态       │
├─────┼───────────────────┼─────────┼───────────┤
│  1  │ suri_core         │  核心   │ ✅ 运行中  │
│  2  │ access            │  接入   │ ✅ 运行中  │
│  3  │ llm_gateway       │  服务   │ ✅ 运行中  │
│  4  │ role_manager      │  能力   │ ✅ 运行中  │
│  5  │ agent_executor    │  执行   │ ✅ 运行中  │
│ ... │ ...               │  ...    │ ...       │
└─────┴───────────────────┴─────────┴───────────┘

提示: 输入插件编号 (如 1) 查看详情
```

### 3.3 状态图标定义

| status | 心跳 | 图标 | 说明 |
|--------|------|------|------|
| `running` | ≤ 10s | ✅ 运行中 | 正常心跳 |
| `running` | 10-30s | ⚠️ 响应延迟 | 心跳滞后 |
| `running` | > 30s | ❌ 无响应 | 心跳超时 |
| `running` | `None` | ⏳ 等待中 | 刚启动未上报 |
| `load_failed` | — | ❌ 加载失败 | 初始化报错 |
| `stopped` | — | ⏸ 已暂停 | 用户手动暂停 |
| `upgrading` | — | ❕ 升级中 | 升级操作中 |
| `removed` | — | 🗑️ 已卸载 | 已删除 |

---

## 四、插件详情 7 区块

### 4.1 触发方式

| 方式 | 示例 | 说明 |
|------|------|------|
| 直接输入编号 | `5` | 纯数字 + 回车 |
| 命令式 | `/plugin 5` | 显式命令 |
| 名称式 | `/plugin llm_gateway` | 用插件 ID 代替编号 |

### 4.2 完整面板示例

```
> 5

┌─ 5. llm_gateway ──────────────────────────────────────┐    ← 标题：编号.名称
│  5 家国产大模型路由与调度                                 │    ← 简述 description
│                                                        │
│  ── 基本信息 ──                                        │    ← 区块1
│  版本:    1.0.0                                        │
│  集层:    service (基础服务)                             │
│  状态:    ✅ 运行中 (心跳: 1s前)                        │
│                                                        │
│  ── 依赖关系 ──                                        │    ← 区块2
│  依赖:    suri_core, config_service                    │
│  被依赖:  access, agent_executor                       │
│                                                        │
│  ── 能力边界 ──                                        │    ← 区块3
│  权限:    system.*                                     │
│  作用域:  全局，所有会话共享                              │
│                                                        │
│  ── 提供的命令 ──                                      │    ← 区块4
│  /switch <厂商> [模型]  切换 LLM 厂商                   │
│  /setkey <厂商> [key]   修改 API Key                   │
│  /models                列出所有模型                    │
│  /model                 查看当前模型                    │
│                                                        │
│  ── 事件契约 ──                                        │    ← 区块5
│  订阅:  llm.request, user.command                      │
│  发布:  llm.response, llm.error                        │
│                                                        │
│  ── 配置项 ──                                          │    ← 区块6
│  default_provider: deepseek    默认厂商                 │
│                                                        │
│  ── 操作 ──                                            │    ← 区块7
│  /plugin start 3      启动插件                         │
│  /plugin stop 3       暂停插件                         │
│  /plugin restart 3    重启插件                         │
│  /plugin upgrade 3    升级插件                         │
│  /plugin remove 3     删除插件                         │
└────────────────────────────────────────────────────────┘
```

### 4.3 各区块数据来源

| 区块 | 数据来源 | 字段 |
|------|---------|------|
| 标题 | manifest.json | `name`, `({index}. {name})` |
| 简述 | manifest.json | `description` |
| 基本信息 | manifest.json + 运行时 | `version`, `type`, `_status`, `heartbeat` |
| 依赖关系 | manifest.json + 遍历 | `dependencies`, 反向依赖分析 |
| 能力边界 | manifest.json | `permissions`, 从 `event_subscriptions` 推导作用域 |
| 提供的命令 | COMMAND_REGISTRY | `get_plugin_commands(plugin_id)` |
| 事件契约 | manifest.json | `event_subscriptions`, `published_events` |
| 配置项 | manifest.json | `config_schema` |
| 操作 | manifest.json | `operations` 字段枚举 |

### 4.4 作用域推导规则

```python
从 event_subscriptions 推导作用域：
  订阅 session.* 或 user.* → "会话级"
  订阅 system.* → "全局，所有会话共享"
  两者都有 → "全局 + 会话级"
  其他 → "未知"
```

---

## 五、模型状态 /models 面板

### 5.1 数据结构

```python
providers: Dict[str, Dict] = {
    "deepseek": {
        "name": "DeepSeek",
        "models": ["deepseek-chat", "deepseek-v4-pro"],
        "default_model": "deepseek-chat",
    },
    ...
}
active_provider: str = "deepseek"
active_model: str = "deepseek-chat"
api_keys: Dict[str, str] = {"deepseek": "sk-xxx", ...}
health: Dict[str, ProviderHealth]  # 从 llm_gateway.get_health() 获取
```

### 5.2 渲染输出

```
> /models

┌──────────────────────────────────────────────────┐
│  LLM 模型状态                                      │
├──────────────────────────────────────────────────┤
│  🔵 当前会话: deepseek / deepseek-chat            │
├─────────┬─────────┬────────────────────┬──────────┤
│ deepseek│ ✅ 在线 │ deepseek-chat ◀   │ /switch  │
│         │         │ deepseek-v4-pro   │          │
│ kimi    │ ✅ 在线 │ moonshot-v1-8k    │ /switch  │
│ chatglm │ ❌ 离线 │ (未配置 API Key)  │ /setkey  │
├─────────┴─────────┴────────────────────┴──────────┤
│  快速切换: 在提示符后输入厂商名即可，例如 kimi      │
└──────────────────────────────────────────────────┘
```

### 5.3 状态推导（依赖 llm_gateway health）

```python
从 ProviderHealth 推导在线状态：

last_success == 0 and last_error == 0
  → ⏳ 待机（有 Key，但从未发起过请求）

last_success > last_error
  → ✅ 在线（最近一次调用成功）

last_success < last_error
  → ⚠️ 异常（最近一次调用失败）

未配置 API Key（api_keys 中无此厂商）
  → ❌ 离线
```

### 5.4 快速切换

面板底部提示用户直接输入厂商名切换：

```
> kimi                                 ← 直接输入厂商名
✅ 已切换到 kimi
```

---

## 六、启动面板 format_startup_panel

### 6.1 渲染内容

整合`插件列表` + `模型状态`为一张完整启动展示：

```
╔═════════════════════════════════════════════════╗
║  Suri Agent v1.0.0 已就绪                       ║
╚═════════════════════════════════════════════════╝

  #  │ 名称            │ 所属层     │ 状态     │ 说明
 ────┼─────────────────┼────────────┼──────────┼──────────────────
  1  │ suri_core       │ core       │ ✅ 运行中 │ 系统内核与健康检查
  2  │ access          │ access     │ ✅ 运行中 │ CLI/Telegram 多通道接入
  3  │ llm_gateway     │ service    │ ✅ 运行中 │ 5 家国产大模型路由与调度
  ...
 15  │ security_service│ service    │ ✅ 运行中 │ 权限审计安全管控

  输入编号查看插件详情，/help 查看更多命令

┌─ LLM 模型状态 ─────────────────────────────────┐
│ 🔵 当前会话: deepseek / deepseek-chat            │
├─────────┬─────────┬───────────────────────────┤
│ deepseek│ ✅ 在线 │ deepseek-chat ◀           │
│ kimi    │ ✅ 在线 │ moonshot-v1-8k            │
│ chatglm │ ❌ 离线 │ (未配置 API Key)          │
└─────────┴─────────┴───────────────────────────┘
```

### 6.2 与 /plugins + /models 的关系

- **`format_startup_panel`** = `format_plugin_list` + `format_model_status` 合并
- `format_startup_panel` 只在系统启动时显示一次
- 后续用户通过 `/plugins` 和 `/models` 分别查看

---

## 七、其他格式化方法

### 7.1 `format_error`

```python
@staticmethod
def format_error(error_code: int, message: str, provider: str) -> str:
    """格式化错误消息。

    根据错误码给出上下文相关的修复提示。

    Args:
        error_code: HTTP 错误码或自定义错误码
        message: 错误描述
        provider: 厂商 ID

    错误码映射:
        401/403 → "⚠️  {message}  提示: /setkey {provider} 修改Key"
        429     → "⚠️  {message}  提示: 稍后重试 或 /switch 切换"
        503     → "⚠️  {message}  提示: /switch 切换 或稍后重试"
        3002    → "⚠️  {message}  提示: /setkey {provider} 添加Key"
        其他    → "⚠️  {message}"
    """
```

### 7.2 `format_decision`

```python
@staticmethod
def format_decision(question: str, options: List[str]) -> str:
    """渲染决策选项面板。

    用于 interrupt_handler 向用户呈现多项选择。
    面板带编号，用户输入编号选择。

    输出示例:
        ┌─────────────────────────────────────┐
        │  请选择 LLM 降级策略                  │
        │                                     │
        │  1. 切换到 DeepSeek                  │
        │  2. 切换到 Kimi                      │
        │  3. 等待后重试                       │
        │                                     │
        │  请选择 [1-3]:                       │
        └─────────────────────────────────────┘

    Args:
        question: 顶部的提问文字
        options: 选项列表
    """
```

### 7.3 `format_system`

```python
@staticmethod
def format_system(msg: str) -> str:
    """格式化系统消息，输出 [Suri] 前缀。

    Args:
        msg: 系统消息内容

    Returns:
        "[Suri] {msg}"
    """
```

### 7.4 `format_success`

```python
@staticmethod
def format_success(msg: str) -> str:
    """格式化成功消息，带 ✅ 前缀。

    Args:
        msg: 成功描述

    Returns:
        "✅ {msg}"
    """
```

### 7.5 `format_model_switch`

```python
@staticmethod
def format_model_switch(provider: str, model: str) -> str:
    """格式化模型切换成功消息。

    Args:
        provider: 厂商 ID
        model: 模型名

    Returns:
        "✅ 已切换到 {provider}/{model}"
    """
```

### 7.6 `format_current_model`

```python
@staticmethod
def format_current_model(provider: str, provider_name: str,
                         model: str, status: str) -> str:
    """渲染简化版当前模型信息（/model 命令使用）。

    Args:
        provider: 厂商 ID
        provider_name: 厂商中文名
        model: 模型名
        status: 状态描述，如 "在线"/"离线"

    输出示例:
        ────────────────────────────────────────
        当前模型: DeepSeek / deepseek-chat [在线]
        ────────────────────────────────────────
    """
```

### 7.7 `format_response`

```python
@staticmethod
def format_response(content: str) -> str:
    """格式化自然语言回复。

    当前实现简单地添加 "Suri: " 前缀。
    未来可扩展示意者标识、时间戳等。

    Args:
        content: LLM 回复文本

    Returns:
        "Suri: {content}"
    """
```

---

## 八、数据来源总览

| 格式化方法 | 数据来源 | 调用时机 |
|-----------|---------|---------|
| `format_plugin_list()` | `PluginManager._plugins` | `/plugins` 命令、启动面板 |
| `format_plugin_detail()` | `PluginManager._plugins` + `COMMAND_REGISTRY` | 输入编号、`/plugin <N>` |
| `format_startup_panel()` | `PluginManager._plugins` + `llm_gateway` | 系统启动 |
| `format_model_status()` | `llm_gateway.list_providers()` + `get_health()` | `/models` 命令、启动面板 |
| `format_current_model()` | `llm_gateway` 当前激活配置 | `/model` 命令 |
| `format_decision()` | `interrupt_handler` | 需要用户决策时 |
| `format_error()` | `llm_gateway.chat()` 返回 | API 调用失败时 |
| `format_response()` | `llm_gateway.chat()` 返回 | LLM 回复时 |
| `format_system()` | EventBus 通知 | 系统消息通知 |
| `format_success()` | 操作结果 | 命令执行成功 |
| `format_model_switch()` | 切换操作结果 | 模型切换成功 |

---

## 九、空状态定义

所有面板在数据为空时的统一文案：

| 场景 | 渲染 |
|------|------|
| 无插件 | `"📋 暂无已加载的插件。"` |
| 无 LLM 厂商 | `"📋 未配置任何 LLM 厂商。使用 /setkey 或 /reconfig 配置。"` |
| 插件详情不存在 | `"❌ 未找到插件信息。"` |
| 插件无命令 | `"（无直接 CLI 命令，通常由 LLM 代理调用）"` |
| 无依赖 | `"无"` |
| 无被依赖 | `"无"` |
| 无配置项 | `"（无配置项）"` |
| 无可用操作 | `"（无可用操作）"` |
| 事件发布为空 | `"（暂无）"` |
| 快捷切换失败 | 走正常 `format_error()` |

---

## 十、通用渲染规则

### 10.1 ANSI 颜色

| 场景 | 颜色 |
|------|------|
| 标题、`[suri]` 前缀 | 青色（`\033[36m`） |
| 成功消息 | 绿色（`\033[32m`） |
| 警告、错误 | 黄色/红色（`\033[33m`/`\033[31m`） |
| 模型/厂商名 | 洋红（`\033[35m`） |
| 强调 | 粗体（`\033[1m`） |
| 次强调 | 暗色（`\033[2m`） |

### 10.2 面板宽度

所有面板使用固定宽度 `PANEL_WIDTH = 75` 字符。

### 10.3 截断规则

内容超过面板宽度时截断，末尾加 `…`：

```python
def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"
```

---

## 十一、通道扩展规则

通道可重写 MessageFormatter 实现差异化渲染：

```python
class CliFormatter(MessageFormatter):
    """CLI 通道使用 ANSI 文本面板渲染"""
    pass  # 复用父类所有方法

class TelegramFormatter(MessageFormatter):
    """Telegram 通道使用 MarkdownV2 渲染"""
    @staticmethod
    def format_plugin_list(plugins):
        # 使用 MarkdownV2 语法重新实现
        pass

class WebFormatter(MessageFormatter):
    """Web 通道使用 HTML 渲染"""
    @staticmethod
    def format_plugin_list(plugins):
        # 返回 HTML <table> 字符串
        pass