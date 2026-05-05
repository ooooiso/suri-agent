# CLI 通道

> 终端交互通道。最轻量级的接入方式，纯文本 + ANSI 渲染。

---

## 一、定位

CLI 通道是 suri-agent 默认的接入方式，也是最基础的通道实现。

**特点**：
- 零依赖，终端天然可用
- 纯文本交互，无富 UI
- 适合开发调试场景
- 作为 session-hub 的默认 fallback

**终端是 Suri Agent 的默认访问通道，也是最核心的交互界面**。所有其他通道（Telegram、Web）的能力都从终端衍生。

| 维度 | 说明 |
|------|------|
| 通道类型 | cli |
| 交互模式 | 命令行 + 自然语言混合 |
| 渲染格式 | ANSI 文本（纯文本降级） |
| 优先级 | 最高（本地优先） |

---

## 二、能力清单

```json
{
  "name": "channel.cli",
  "channel_type": "cli",
  "version": "1.0.0",
  "capabilities": {
    "core": {
      "text": true,
      "markdown": true,
      "commands": true
    },
    "media": {
      "images": false,
      "video": false,
      "audio": false,
      "files": false,
      "file_max_size_mb": 0
    },
    "interaction": {
      "buttons": false,
      "forms": false
    },
    "streaming": {
      "text_stream": true,
      "file_stream": false
    },
    "ui": {
      "rich_ui": false,
      "notifications": false,
      "dynamic_content": false,
      "offline_mode": false,
      "local_storage": false
    },
    "extras": {
      "clipboard": false,
      "voice": false,
      "location": false,
      "identity": false
    }
  },
  "degrade_chain": {
    "rich": ["markdown", "text"],
    "video": ["image", "text"],
    "file": ["text"],
    "html": ["text"],
    "image": ["text"]
  }
}
```

---

## 三、架构层次

```
┌──────────────────────────────────────────────┐
│              用户终端 (Terminal)               │
├──────────────────────────────────────────────┤
│  channels/cli/channel.py                     │
│  ┌────────────────────────────────────────┐  │
│  │  CLIChannelPlugin                      │  │
│  │  ┌────────────┐ ┌───────────────────┐  │  │
│  │  │ 输入循环    │ │ 输出渲染器         │  │  │
│  │  │ - stdin    │ │ - ANSI 格式化     │  │  │
│  │  │ - readline │ │ - 面板渲染         │  │  │
│  │  │ - 历史     │ │ - 流式输出         │  │  │
│  │  └────────────┘ └───────────────────┘  │  │
│  │  ┌────────────────────────────────┐  │  │
│  │  │  命令路由                       │  │  │
│  │  │  /xxx → 本地命令               │  │  │
│  │  │  数字 → 插件编号查看            │  │  │
│  │  │  自然语言 → LLM                │  │  │
│  │  └────────────────────────────────┘  │  │
│  └────────────────────────────────────────┘  │
├──────────────────────────────────────────────┤
│              SessionHub 会话中枢               │
├──────────────────────────────────────────────┤
│           EventBus 事件总线                    │
├──────────────────────────────────────────────┤
│  PluginManager + 各插件实例                    │
│  (所有数据源从这里来)                          │
└──────────────────────────────────────────────┘
```

### 3.1 用户输入数据流

```
用户键盘输入
    │
    ▼
CLIChannelPlugin._input_loop()
（异步读取 stdin）
    │
    ▼
SessionMessage { session_id, channel_type, content }
    │
    ▼
SessionHub.route_user_input()
    ├── 命令检测（是否 / 开头）
    ├── 插件编号检测（纯数字）
    └── 自然语言路由
        │
        ├─ /xxx → 本地命令处理器 → 渲染输出 → 终端
        ├─ 数字 → 插件详情查询 → 渲染面板 → 终端
        └─ 文本 → llm.request 事件 → LLM → 渲染 → 终端
```

### 3.2 插件列表数据流

```
用户输入 /plugins
    │
    ▼
CLI 发布 user.command { command: "plugins" }
    │ 或从 PluginManager 直接读取
    ▼
PluginManager._plugins
→ 遍历 { plugin_id → PluginInstance }
→ 读取 instance._status / instance._running / instance._manifest
    │
    ▼
MessageFormatter.format_plugin_list(plugins_data)
    → 渲染带编号 + 状态图标的面板
    │
    ▼
终端显示
```

### 3.3 状态同步数据流（事件驱动）

```
PluginManager 内部状态变化
    │
    ├─ plugin.stop()      → 发布 plugin.status_changed
    ├─ plugin.start()     → 发布 plugin.status_changed
    ├─ plugin.upgrade()   → 发布 plugin.manifest_updated
    ├─ 加载新插件          → 发布 system.plugin_loaded
    └─ 卸载插件            → 发布 system.plugin_unloaded
    │
    ▼
EventBus.publish()
    │
    ▼
CLIChannelPlugin._on_plugin_event()
    │
    ├─ 当前显示的是插件列表 → 自动重绘
    ├─ 当前显示的是该插件详情 → 刷新对应区块
    └─ 当前是空闲 > 提示符 → 输出通知，不破坏输入
```

### 3.4 解耦原则

1. **数据不硬编码** — 插件列表从 PluginManager 动态获取，LLM 厂商从 llm_gateway 获取
2. **命令声明式** — 插件通过 manifest.json 的 `commands` 字段声明自己的命令，终端自动发现
3. **面板渲染集中** — 所有格式化都在 `MessageFormatter`，通道只需调用静态方法
4. **状态事件驱动** — 所有状态变化通过 EventBus 通知，通道被动订阅刷新

---

## 四、交互模式

终端支持三种交互范式：

| 范式 | 示例 | 说明 |
|------|------|------|
| **命令式** | `/plugins` `/switch kimi` | 以 `/` 开头，本地处理，不依赖 LLM |
| **浏览式** | `5`（输入纯数字） | 查看对应编号的插件详情 |
| **对话式** | `今天天气怎么样` | 自然语言，走 LLM 处理（需在线） |

### 4.1 命令式（/xxx）

```
> /plugins                                     ← 用户输入
                                                ← 系统输出面板
  #  │ 名称            │ 层    │ 状态
 ────┼─────────────────┼───────┼──────────
  1  │ suri_core       │ core  │ ✅ 运行中
  ...
>                                              ← 提示符恢复
```

**规则**：
- 以 `/` 开头的输入被视为命令
- 命令优先匹配内置处理器，再匹配 COMMAND_REGISTRY 注册命令
- 命令处理完成后立即恢复提示符

### 4.2 浏览式（纯数字）

```
> 5                                        ← 用户输入编号

┌─ 5. llm_gateway ──────────────────────┐
│  5 家国产大模型路由与调度               │
│                                        │
│  ── 基本信息 ──                        │
│  状态: ✅ 运行中                        │
│  版本: 1.0.0  集层: service            │
│                                        │
│  ── 依赖关系 ──                        │
│  依赖: suri_core, config_service       │
│  被依赖: access                        │
│                                        │
│  ── 能力边界 ──                        │
│  权限: system.*                        │
│  作用域: 全局，所有会话共享             │
│                                        │
│  ── 提供的命令 ──                      │
│  /switch /setkey /models /model        │
│                                        │
│  ── 事件契约 ──                        │
│  订阅: llm.request, user.command       │
│  发布: llm.response, llm.error         │
│                                        │
│  ── 配置项 ──                          │
│  default_provider: deepseek            │
│                                        │
│  ── 操作 ──                            │
│  /plugin start 3  启动                 │
│  /plugin stop 3   暂停                 │
│  /plugin restart 3 重启                │
│  /plugin upgrade 3 升级                │
│  /plugin remove 3 删除                 │
└────────────────────────────────────────┘
>                                          ← 提示符恢复
```

**判断逻辑**：
```
用户输入 → 去除首尾空白
    │
    ├─ 空字符串 → 忽略，重绘提示符
    ├─ 以 / 开头 → 命令式
    ├─ 纯数字 → 检查是否为有效插件编号
    │   ├─ 是 → 显示插件详情（format_plugin_detail 7 区块）
    │   └─ 否 → 走对话式（LLM 处理）
    ├─ 厂商名快速切换（在 /models 面板后）
    │   ├─ 匹配 → 执行切换 + 自动刷新面板
    │   └─ 不匹配 → 走对话式
    └─ 其他 → 对话式（LLM 处理）
```

### 4.3 对话式（自然语言）

```
> 今天天气怎么样？                           ← 用户输入
[suri] 抱歉，我目前没有获取天气信息的能力...     ← LLM 响应（紫色）
>                                          ← 提示符恢复
```

**规则**：
- LLM 在线 → 发送给 LLM（通过 EventBus → user.input 事件）
- LLM 离线 → 提示：`⚠️ 当前 LLM 离线，无法处理自然语言。`

---

## 五、提示符管理

### 5.1 PromptManager 状态机

```python
STATE_IDLE = 0      默认，等待输入
STATE_INPUT = 1     用户正在输入（输入缓冲非空）
STATE_OUTPUT = 2    系统正在输出
STATE_MULTILINE = 3 多行模式
```

```
IDLE → 显示 "> "
    │
    ├─ 用户开始输入 → 进入 INPUT 状态
    │   └─ 输入完成 → 恢复 IDLE
    │
    ├─ 系统输出 → 清除当前行 → 输出内容
    │   └─ 输出完成 → 重绘提示符 + 恢复用户输入
    │
    └─ Ctrl+C → 换行 → 重绘提示符
```

### 5.2 输出渲染规则

```python
def on_output(self, text: str) -> None:
    """安全输出，不破坏用户输入。

    1. 保存用户正在输入的文本 (readline.get_line_buffer)
    2. 清除当前行，输出内容
    3. 恢复用户输入 + 提示符
    """
    saved_input = readline.get_line_buffer() if readline else ""
    clean_text = text.rstrip('\n')
    sys.stdout.write(f"\r\033[K{clean_text}\n{self._prompt}{saved_input}")
    sys.stdout.flush()
```

### 5.3 撤销/修正输入

| 按键 | 行为 |
|------|------|
| Ctrl+C | 取消当前输入，换行后重绘提示符 |
| Ctrl+U | 清除当前行内容 |
| Ctrl+L | 清屏（ANSI 清屏 + 重绘提示符） |
| 上/下箭头 | 历史导航（由 readline 原生支持） |

---

## 六、命令系统

### 6.1 内置命令完整列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/quit` / `/exit` | 退出程序 | `/quit` |
| `/status` | 查看系统运行状态 | `/status` |
| `/plugins` | 列出所有插件 | `/plugins` |
| `/plugin <N>` | 查看插件详情 | `/plugin 5` |
| `/plugin start <N>` | 启动插件 | `/plugin start 3` |
| `/plugin stop <N>` | 暂停插件 | `/plugin stop 3` |
| `/plugin restart <N>` | 重启插件 | `/plugin restart 3` |
| `/plugin upgrade <N>` | 升级插件 | `/plugin upgrade 3` |
| `/plugin remove <N>` | 删除插件 | `/plugin remove 3` |
| `/models` | 列出所有 LLM 厂商和模型 | `/models` |
| `/model` | 查看当前激活模型 | `/model` |
| `/switch <厂商> [模型]` | 切换 LLM 模型 | `/switch kimi` |
| `/setkey <厂商> [key]` | 修改 API Key | `/setkey deepseek sk-xxx` |
| `/reconfig` | 进入配置菜单 | `/reconfig` |
| `/config [key]` | 查看配置 | `/config` |
| `/reload` | 重载配置 | `/reload` |
| `/logs` | 查看日志路径 | `/logs` |
| `/sessions` | 查看会话统计 | `/sessions` |
| `/hotreload` | 热更新状态 | `/hotreload` |
| `/history` | 显示命令历史 | `/history 20` |
| `/clear` | 清屏 | `/clear` |

### 6.2 插件管理命令

所有插件管理命令都走 `/plugin` 子命令：

```
/plugin <N>                   查看插件详情（同直接输入编号）
/plugin start <N>             启动插件
/plugin stop <N>              暂停插件  
/plugin restart <N>           重启插件
/plugin upgrade <N>           升级插件
/plugin remove <N>            删除插件
```

### 6.3 命令优先级

> 命令注册与发现机制详见 → `prd/operations/command-system.md`

```
用户输入以 / 开头
    │
    ├─ 1. 内置命令（/help /plugins /switch 等）→ 本地处理
    ├─ 2. COMMAND_REGISTRY 注册命令 → EventBus 路由到对应插件
    └─ 3. 未知命令 → 提示 "未知命令，输入 /help 查看"
```

### 6.4 特殊命令（会话级）

| 命令 | 作用 | 示例 |
|------|------|------|
| `/exit` | 退出会话 | `/exit` |
| `/help` | 帮助 | `/help` |
| `/history` | 查看历史 | `/history 20` |
| `/session` | 查看会话信息 | `/session` |
| `/clear` | 清屏 | `/clear` |

---

## 七、插件列表面板

### 7.1 启动面板

用户 `python main.py` 后看到的完整启动界面：

```
═════════════════════════════════════════════════
  Suri Agent v1.0.0 已就绪
═════════════════════════════════════════════════

  #  │ 名称            │ 所属层     │ 状态     │ 说明
 ────┼─────────────────┼────────────┼──────────┼──────────────────
  1  │ suri_core       │ core       │ ✅ 运行中 │ 系统内核与健康检查
  2  │ access          │ access     │ ✅ 运行中 │ CLI/Telegram 多通道接入
  3  │ llm_gateway     │ service    │ ✅ 运行中 │ 5 家国产大模型路由与调度
  4  │ role_manager    │ role       │ ✅ 运行中 │ 多角色管理与切换
  5  │ agent_executor  │ execution  │ ✅ 运行中 │ 任务执行引擎
  6  │ agent_registry  │ execution  │ ✅ 运行中 │ Agent 注册与发现
  7  │ code_tool       │ execution  │ ✅ 运行中 │ 代码读写搜索执行
  8  │ interrupt_handler│execution  │ ✅ 运行中 │ 中断请求处理
  9  │ role_comm       │ execution  │ ✅ 运行中 │ 角色间通信协调
 10  │ task_planner    │ execution  │ ✅ 运行中 │ 任务分解与规划
 11  │ task_scheduler  │ execution  │ ✅ 运行中 │ 定时任务调度
 12  │ memory_service  │ service    │ ✅ 运行中 │ 记忆存储与检索
 13  │ config_service  │ service    │ ✅ 运行中 │ 集中配置管理
 14  │ log_service     │ service    │ ✅ 运行中 │ 日志收集与分析
 15  │ security_service│ service    │ ✅ 运行中 │ 权限审计安全管控

  输入编号查看插件详情，/help 查看更多命令

┌──────────────────────────────────────────────────┐
│  LLM 模型状态                                      │
├──────────────────────────────────────────────────┤
│  🔵 当前会话: deepseek / deepseek-chat            │
├─────────┬─────────┬────────────────────┬──────────┤
│ deepseek│ ✅ 在线 │ deepseek-chat ◀   │ /switch  │
│ kimi    │ ✅ 在线 │ moonshot-v1-8k    │ /switch  │
│ chatglm │ ❌ 离线 │ (未配置 API Key)  │ /setkey  │
└─────────┴─────────┴────────────────────┴──────────┘

>
```

### 7.2 `/plugins` 命令面板

```
> /plugins

┌───────────────────────────────────────────────┐
│  Suri Agent 插件列表   (共 15 个)              │
├─────┬───────────────────┬─────────┬───────────┤
│  #  │ 名称              │ 类型    │ 状态       │
├─────┼───────────────────┼─────────┼───────────┤
│  1  │ suri_core         │  核心   │ ✅ 运行中  │
│  2  │ access            │  接入   │ ✅ 运行中  │
│  3  │ llm_gateway       │  服务   │ ✅ 运行中  │
│  4  │ role_manager      │  能力   │ ✅ 运行中  │
│  5  │ agent_executor    │  执行   │ ✅ 运行中  │
│  6  │ agent_registry    │  执行   │ ✅ 运行中  │
│  7  │ code_tool         │  执行   │ ✅ 运行中  │
│  8  │ interrupt_handler │  执行   │ ✅ 运行中  │
│  9  │ role_comm         │  执行   │ ✅ 运行中  │
│ 10  │ task_planner      │  执行   │ ✅ 运行中  │
│ 11  │ task_scheduler    │  执行   │ ✅ 运行中  │
│ 12  │ memory_service    │  服务   │ ✅ 运行中  │
│ 13  │ config_service    │  服务   │ ✅ 运行中  │
│ 14  │ log_service       │  服务   │ ✅ 运行中  │
│ 15  │ security_service  │  服务   │ ✅ 运行中  │
└─────┴───────────────────┴─────────┴───────────┘

提示: 输入插件编号 (如 1) 查看详情
>
```

### 7.3 状态定义与图标

| 状态 | 图标 | 触发条件 | 恢复方式 |
|------|------|---------|---------|
| 运行中 | ✅ | 心跳 ≤ 10s | — |
| 响应延迟 | ⚠️ | 心跳 10-30s | 自动恢复 / 重启 |
| 无响应 | ❌ | 心跳 > 30s | `/plugin restart <N>` |
| 等待中 | ⏳ | 刚启动，首次心跳未到 | 正常启动后自动变 ✅ |
| 加载失败 | ❌ | 启动阶段报错 | `/plugin start <N>` |
| 已暂停 | ⏸ | 用户执行 `/plugin stop <N>` | `/plugin start <N>` |
| 升级中 | ❕ | 执行 `/plugin upgrade <N>` | 升级完成后自动重启 |
| 已卸载 | 🗑️ | 执行 `/plugin remove <N>` | 重新安装 |

### 7.4 实时刷新机制

当插件状态或数量发生变化时，终端根据当前显示状态自动处理：

| 当前显示 | 状态变化时的行为 |
|---------|----------------|
| 插件列表（启动面板或 `/plugins`） | **自动重绘** — 只更新变化的行 |
| 某个插件详情 | **闪烁更新** — 状态行闪烁 3 次后固定 |
| 空闲 `>` 提示符 | **通知** — 输出 "⚠️ [通知] llm_gateway 状态: ✅→⏸" 后恢复提示符 |

自动刷新的事件订阅：

```python
self._event_bus.subscribe("system.plugin_loaded", self._on_plugin_event)
self._event_bus.subscribe("system.plugin_unloaded", self._on_plugin_event)
self._event_bus.subscribe("plugin.status_changed", self._on_plugin_event)
self._event_bus.subscribe("plugin.manifest_updated", self._on_plugin_event)
```

---

## 八、插件详情面板

### 8.1 触发方式

| 方式 | 示例 | 说明 |
|------|------|------|
| 直接输入编号 | `5` | 在提示符后输入纯数字 + 回车 |
| 命令式 | `/plugin 5` | 显式命令 + 编号参数 |
| 名称式 | `/plugin llm_gateway` | 用插件名代替编号 |

### 8.2 完整面板示例（7 区块）

```
> 5

┌─ 5. llm_gateway ──────────────────────────────────────┐    ← 标题行：编号 + 名称
│  5 家国产大模型路由与调度                                 │    ← 简述行
│                                                        │
│  ── 基本信息 ──                                        │    ← 区块1
│  版本:    1.0.0                                        │
│  集层:    service (服务层)                              │
│  状态:    ✅ 运行中 (心跳: 1s前)                        │
│                                                        │
│  ── 依赖关系 ──                                        │    ← 区块2
│  依赖:    suri_core, config_service                    │
│  被依赖:  access, agent_executor                       │
│                                                        │
│  ── 能力边界 ──                                        │    ← 区块3
│  权限:    system.*                                     │
│  作用域:  全局，所有会话共享 LLM 连接                    │
│                                                        │
│  ── 提供的命令 ──                                      │    ← 区块4
│  /switch <厂商> [模型]  切换 LLM 厂商                   │
│  /setkey <厂商> [key]   修改 API Key                   │
│  /models                列出所有模型                    │
│  /model                 查看当前模型                    │
│                                                        │
│  ── 事件契约 ──                                        │    ← 区块5
│  订阅:  llm.request, user.command,                     │
│         system.config_changed                          │
│  发布:  llm.response, llm.error                        │
│                                                        │
│  ── 配置项 ──                                          │    ← 区块6
│  default_provider: deepseek    默认厂商                 │
│  已配置厂商: deepseek ✅, kimi ✅                       │
│                                                        │
│  ── 操作 ──                                            │    ← 区块7
│  /plugin start 3      启动插件                         │
│  /plugin stop 3       暂停插件                         │
│  /plugin restart 3    重启插件                         │
│  /plugin upgrade 3    升级插件                         │
│  /plugin remove 3     删除插件                         │
└────────────────────────────────────────────────────────┘
>

```

### 8.3 详情热更新

当插件能力发生变化（升级后新增命令/事件），详情面板数据会实时更新：

```
# 用户执行升级后，在详情页看到：
┌─ 5. llm_gateway ──────────────────────────────────────┐
│  版本:    1.1.0          ← 版本号从 1.0.0 变为 1.1.0     │
│  ── 提供的命令 ──                                      │
│  /switch /setkey /models /model /sse  ← 新增 /sse 命令  │
```

更新方式：
- `plugin.manifest_updated` 事件触发后，**清除该插件详情缓存**
- 下次查看详情时从 PluginManager 重新读取最新 manifest
- 如果当前已经在该插件详情页，自动刷新「基本信息」「提供的命令」「事件契约」「配置项」四个区块

### 8.4 数据来源总览

| 面板元素 | 数据来源 |
|---------|---------|
| 名称 | manifest.json `name` |
| 简述 | manifest.json `description` |
| 版本 | manifest.json `version` |
| 集层 | manifest.json `type` + 映射表 |
| 状态 | `plugin._status` / `plugin._running` + 心跳时间戳 |
| 依赖 | manifest.json `dependencies` |
| 被依赖 | 反向依赖分析（遍历所有插件） |
| 权限 | manifest.json `permissions` |
| 作用域 | 事件订阅推导 |
| 命令 | COMMAND_REGISTRY |
| 事件订阅 | manifest.json `event_subscriptions` |
| 发布事件 | manifest.json `published_events` |
| 配置项 | manifest.json `config_schema` |
| 操作 | manifest.json `operations` 字段枚举 |

---

## 九、模型状态面板

### 9.1 `/models` 完整面板

```
> /models

┌──────────────────────────────────────────────────┐
│  LLM 模型状态                                      │
├──────────────────────────────────────────────────┤
│  🔵 当前会话: deepseek / deepseek-chat            │
├──────┬─────────┬───────────────────┬─────────────┤
│  厂商 │ 状态    │ 可用模型           │ 快速切换    │
├──────┼─────────┼───────────────────┼─────────────┤
│deepseek│ ✅ 在线 │ deepseek-chat ◀   │ /switch    │
│        │        │ deepseek-v4-pro   │  deepseek  │
│        │        │ deepseek-v4-flash │             │
│kimi   │ ✅ 在线 │ moonshot-v1-8k    │ /switch    │
│        │        │ moonshot-v1-32k   │  kimi      │
│        │        │ moonshot-v1-128k  │             │
│chatglm│ ❌ 离线 │ (未配置 API Key)  │ /setkey    │
│        │        │                   │  chatglm   │
├──────┴─────────┴───────────────────┴─────────────┤
│  快速切换: 在提示符后输入厂商名即可，例如 kimi      │
└──────────────────────────────────────────────────┘
```

### 9.2 在线状态判断

| 条件 | 状态 | 图标 |
|------|------|------|
| 配置了 API Key + 最近一次调用成功 | 在线 | ✅ |
| 配置了 API Key + 最近一次调用失败 | 异常 | ⚠️ |
| 未配置 API Key | 离线 | ❌ |
| 从未测试过 | 未知 | ➖ |

### 9.3 快速切换

```
> /models          ← 显示面板
（面板内容...）
> kimi             ← 直接输入厂商名
✅ 已切换到 kimi
                  ← 重新显示更新后的面板
> 
```

### 9.4 `/model` 简版面板

```
> /model

当前模型: deepseek / deepseek-chat [在线]
```

---

## 十、Tab 补全规范

### 10.1 命令补全

```
> /[Tab]
/clear     /config    /help      /history   /logs
/model     /models    /plugin    /plugins   /quit
/reconfig  /reload    /setkey    /status    /switch
> /[用户继续输入]
```

### 10.2 厂商名补全

```
> /switch [Tab]
chatglm    deepseek   kimi       tongyi     wenxin
> /switch kimi
```

### 10.3 命令参数补全

```
> /switch kimi [Tab]
moonshot-v1-8k    moonshot-v1-32k
> /switch kimi moonshot-v1-8k
```

### 10.4 插件编号补全

```
> /plugin [Tab]
1          2          3          4          5
6          7          8          9          10
11         12         13         14         15
> /plugin 3
```

---

## 十一、流式输出

CLI 天然支持流式输出：

```
> 写个故事
[suri] 从前有一个...
                    ← 逐字符打印
```

---

## 十二、长消息分页

超过终端高度的消息自动分页：

```
# 输出末尾显示
-- 更多 (回车继续, q 退出) --
```

---

## 十三、启动与退出

### 13.1 启动方式

```bash
# 默认启动（main.py 自动启动 CLI）
python main.py

# 显式指定通道
python main.py --channel cli
```

### 13.2 完整启动展示

```
$ python main.py                              ← Shell 中执行
═════════════════════════════════════════════════
  Suri Agent v1.0.0 已就绪
═════════════════════════════════════════════════

  #  │ 名称            │ 所属层     │ 状态     │ 说明
 ────┼─────────────────┼────────────┼──────────┼──────────────────
  1  │ suri_core       │ core       │ ✅ 运行中 │ 系统内核与健康检查
  2  │ access          │ access     │ ✅ 运行中 │ CLI/Telegram 多通道接入
  3  │ llm_gateway     │ service    │ ✅ 运行中 │ 5 家国产大模型路由与调度
  4  │ role_manager    │ role       │ ✅ 运行中 │ 多角色管理与切换
  5  │ agent_executor  │ execution  │ ✅ 运行中 │ 任务执行引擎
  ..  │ ...            │ ...        │ ...       │ ...
 15  │ security_service│ service    │ ✅ 运行中 │ 权限审计安全管控

  输入编号查看插件详情，/help 查看更多命令

┌─ LLM 模型状态 ─────────────────────────────────┐
│ deepseek ✅ 在线  deepseek-chat ◀              │
│ kimi     ✅ 在线  moonshot-v1-8k               │
│ chatglm  ❌ 离线  (未配置 API Key)             │
└────────────────────────────────────────────────┘

>
```

### 13.3 退出方式

| 方式 | 命令 | 说明 |
|------|------|------|
| 命令退出 | `/quit` 或 `/exit` | 保存历史后退出 |
| Ctrl+C | 信号中断 | 触发主机关闭流程 |
| Ctrl+D | EOF | 空行输入 EOF 导致 `readline()` 返回空 |

退出时保存：
- readline 历史（默认 500 条）
- 当前会话状态（内存中）

---

## 十四、消息格式

```
# 输入：用户在 > 提示符后输入文本
# 纯文本 → user.input
# /命令  → user.command
# 数字   → 插件编号查询

# 输出：直接打印到终端
# 纯文本 → print()
# Markdown → ANSI 渲染
# 图片 → "📷 [图片名称.png]"
# 文件 → "📎 [文件名.pdf] (2.3MB)"
```

---

## 十五、插件生命周期

### 15.1 状态机

```
                    ┌──────────────────────┐
                    │     待加载 (pending)   │
                    └──────────┬───────────┘
                               │ 插件文件存在，EventBus 就绪
                               ▼
                    ┌──────────────────────┐
                    │ 初始化 (initialized)  │ ← 插件 init() 完成
                    └──────────┬───────────┘
                               │ plugin.start()
                               ▼
              ┌──────────────────────────────────┐
              │      ✅ 运行中 (running)           │
              │  心跳上报中，可正常提供服务          │
              └──┬──────────────┬──────────────┬──┘
                 │              │              │
          plugin.stop()  心跳超30s     plugin.upgrade()
                 ▼              ▼              ▼
        ┌────────────┐  ┌────────────┐  ┌──────────────┐
        │ ⏸ 已暂停    │  │ ❌ 无响应   │  │ ❕ 升级中     │
        │ (stopped)  │  │ (timeout) │  │ (upgrading) │
        └─────┬──────┘  └─────┬──────┘  └──────┬───────┘
              │              │              │ 升级完成
       plugin.start()  plugin.restart()   plugin.start()
              │              │              │
              └──────┬───────┘              │
                     ▼                      │
              ┌──────────────┐              │
              │ ✅ 运行中     │◀─────────────┘
              └──────────────┘

              ❌ 加载失败 (load_failed)
              插件 init() 或 start() 抛出异常
              → /plugin start <N> 重试

              🗑️ 已卸载 (removed)
              /plugin remove <N> 后从列表移除
              → 重新安装才能恢复
```

### 15.2 操作命令详细说明

| 命令 | 效果 | 状态变化 | 成功提示 | 失败提示 |
|------|------|---------|---------|---------|
| `/plugin start <N>` | 启动已暂停的插件 | ⏸ → ✅ | `✅ <名称> 已启动` | `❌ 启动失败: <原因>` |
| `/plugin stop <N>` | 暂停运行中的插件 | ✅ → ⏸ | `⏸ <名称> 已暂停` | `❌ 暂停失败: <原因>` |
| `/plugin restart <N>` | 重启运行中的插件 | ✅→⏸→✅ | `🔄 <名称> 已重启` | `❌ 重启失败: <原因>` |
| `/plugin upgrade <N>` | 升级插件 | ✅→❕→✅ | `⬆️ <名称> 已升级为 vX.Y.Z` | `❌ 升级失败: <原因>` |
| `/plugin upgrade <N> <版本>` | 升级到指定版本 | ✅→❕→✅ | `⬆️ <名称> v1.0.0 → vX.Y.Z` | `❌ 升级失败: <原因>` |
| `/plugin remove <N>` | 删除插件 | ✅→🗑️ | `🗑️ <名称> 已卸载` | `❌ 卸载失败: <原因>` |

### 15.3 操作示例

```
> /plugin stop 3
⏸ llm_gateway 已暂停

> /plugins                                    ← 自动刷新

  #  │ 名称            │ 所属层     │ 状态     │ 说明
 ────┼─────────────────┼────────────┼──────────┼──────────────────
  3  │ llm_gateway     │ service    │ ⏸ 已暂停 │ 5 家国产大模型路由与调度

> /plugin start 3
✅ llm_gateway 已启动

> /plugin upgrade 3
⬆️ llm_gateway 已升级为 v1.1.0

> /plugin remove 3
🗑️ llm_gateway 已卸载

> /plugins                                    ← 列表少一行
```

---

## 十六、状态同步与热更新

### 16.1 事件驱动刷新

终端展示不是静态快照，所有状态变化通过 EventBus 事件驱动刷新：

```
事件源                     发布的事件                    CLI 通道响应
──────────────────────────────────────────────────────────────────
PluginManager.load_plugin  → system.plugin_loaded     → 列表追加一行
PluginManager.unload_plugin→ system.plugin_unloaded   → 列表移除一行
插件实例.stop()            → plugin.status_changed    → 对应行状态 ⏸
插件实例.start()           → plugin.status_changed    → 对应行状态 ✅
插件实例.心跳超时           → plugin.status_changed    → 对应行状态 ❌
插件升级 (manifest 变化)    → plugin.manifest_updated  → 清除详情缓存
配置变更                   → system.config_changed    → 重载模型面板
```

### 16.2 实时刷新策略

```
CLIChannelPlugin._on_plugin_event(event)
    │
    ▼
判断当前显示状态
    │
    ├─ 当前显示的是「插件列表」(self._last_view == "plugins")
    │   └─ 重绘列表
    │       └─ 如果事件是 status_changed → 只更新对应行的状态图标
    │       └─ 如果事件是 loaded/unloaded → 完整重新渲染列表
    │
    ├─ 当前显示的是「该插件详情」(self._last_view == "detail:<id>")
    │   └─ 闪烁更新
    │       └─ 如果事件是 status_changed → 只更新状态行（闪烁 3 次）
    │       └─ 如果事件是 manifest_updated → 刷新基本信息/命令/事件/配置
    │
    └─ 当前是「空闲」(self._last_view == "idle")
        └─ 输出通知
            └─ "⚠️ [通知] llm_gateway 状态变更为: ⏸ 已暂停"
            └─ 恢复 > 提示符
```

通知输出不破坏用户输入（同 on_output 规则）：

```
> 我正在编辑这句话                      ← 用户没按回车
⚠️ [通知] llm_gateway 状态变更为: ⏸ 已暂停   ← 系统通知
> 我正在编辑这句话                      ← 恢复用户输入
```

### 16.3 热更新架构

> 热更新实现细节见 → `prd/operations/hot-reload.md`

```
┌─────────────────────────────────────────────────┐
│                  HotReloadManager                │
│                                                  │
│  FileWatcher (每 2s 轮询)                        │
│  ├─ 扫描 config.json 的 mtime                    │
│  ├─ 扫描 manifest.json 的 mtime                  │
│  └─ 扫描 plugin.py 的 mtime                      │
│       │                                          │
│       检测到变更                                  │
│       │                                          │
│       ▼                                          │
│  事件触发:                                       │
│  ┌─ config.updated         → 配置重载            │
│  ├─ manifest.updated       → 插件命令注册刷新    │
│  └─ code.changed           → 热重载 (reload)    │
│       │                                          │
│       ▼                                          │
│  EventBus.publish()                              │
│       │                                          │
│       ▼                                          │
│  CLIChannelPlugin._on_plugin_event()             │
│  └─ 根据 `16.2` 刷新策略实时更新终端             │
└─────────────────────────────────────────────────┘
```

### 16.4 详情缓存淘汰

详情面板的数据来自多个源，为了确保数据一致性，当以下事件发生时淘汰缓存：

```
缓存淘汰事件                   淘汰范围
──────────────────────────────────────────────────
plugin.manifest_updated      → 该插件详情缓存失效
system.plugin_loaded         → 全部插件列表缓存失效 + 新增详情缓存
system.plugin_unloaded       → 全部插件列表缓存失效 + 移除详情缓存
system.config_changed        → 模型状态面板缓存失效
```

缓存保存在 `CLIChannelPlugin._detail_cache: Dict[str, str]`（详情面板渲染后的字符串）。

### 16.5 数据一致性保证

```
所有终端展示的数据只有一条来源路径：

PluginManager._plugins
    → 插件实例
        → instance._status (实时状态)
        → instance._running (运行标志)
        → instance._manifest (元数据)
        → instance._heartbeat (心跳时间戳)
    ↓
CLIChannelPlugin._fetch_plugins() / _fetch_detail(id)
    ↓
MessageFormatter.format_plugin_list() / format_plugin_detail()
    ↓
终端输出

不存在第二条数据路径，避免不一致。
```

---

## 十七、实现参考

CLI 通道插件接口：

```python
class CliChannel(ChannelPlugin):
    async def start(self):
        """启动 CLI 读取循环"""
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, input, "> ")
            msg = SessionMessage(
                session_id=self.session_id,
                channel_type="cli",
                channel_id=self.channel_id,
                msg_type="command" if line.startswith("/") else "text",
                content=line,
            )
            await self.hub.handle_input(msg)

    async def send(self, output: SessionOutput):
        """输出到终端"""
        if output.streaming:
            await self._stream_output(output.content)
        else:
            rendered = self._render(output)
            print(rendered)
            if output.options:
                self._show_options(output.options)

    def _render(self, output: SessionOutput) -> str:
        """根据 content_type 格式化输出"""
        if output.content_type == "markdown":
            return self._ansi_markdown(output.content)
        elif output.content_type == "text":
            return output.content
        elif output.content_type == "image":
            return f"📷 [{output.attachments[0].name}]"
        else:
            return output.content
```

---

## 十八、已修复问题

以下是在实现过程中修复的交互问题，已稳定运行：

| # | 问题 | 表现 | 解决方案 |
|---|------|------|---------|
| 1 | **插件状态不准确** | `/plugins` 所有插件显示"已暂停" | `_get_status_icon()` 从插件实例的 `_status` / `_running` 属性读取真实状态，而非仅依赖默认值 |
| 2 | **用户输入重复行** | 输入内容在终端被打印两次 | 去掉手动回显，依靠终端天然回显 |
| 3 | **发言者区分不明显** | 用户输入和 suri 回复都是白色 | `format_response()` 输出加 `[suri]` 紫色 ANSI 前缀 |
| 4 | **提示符不显示** | 启动后没有 `>` 提示符 | 改为纯 asyncio StreamReader 输入循环，初始化时和每次输出后都写入 `> ` |
| 5 | **光标位置错乱** | LLM 回复到达时用户刚好在编辑输入，光标被带到回复内容末尾 | `on_output()` 中通过 `readline.get_line_buffer()` 保存用户正在编辑的内容，输出完提示符后恢复 |
| 6 | **输入线程与 async 冲突** | threading + asyncio 混合导致 stdin 竞争 | 统一为纯 asyncio StreamReader（`connect_read_pipe`），移除 `_start_input_thread()` |
| 7 | **启动面板缺少插件列表** | 启动后只显示模型面板，看不到有哪些插件 | `_show_startup_panel()` 改为展示全量插件表格 + 模型面板 |
| 8 | **状态变更不通知** | 插件被 stop/upgrade/remove 后终端不更新 | 增加 EventBus 事件订阅，实时刷新列表或输出通知 |