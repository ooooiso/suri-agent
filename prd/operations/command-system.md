# 命令系统

> 插件的 CLI 命令注册与发现体系，取代手动 if-else 路由。

---

## 一、定位

```python
# agent_framework/shared/commands.py  →  命令注册表
# CLIChannelPlugin._on_user_input()   →  命令发现与路由
# manifest.json commands 字段         →  命令声明
```

**核心角色**：插件无需在 CLI 通道中写 if-else，只需在 manifest.json 声明命令，或在 `start()` 中动态注册。终端自动发现。

## 二、关键数据结构

### CommandInfo

```python
@dataclass
class CommandInfo:
    name: str                    # 命令名（不含 /）
    plugin_id: str               # 归属插件
    usage: str                   # 用法说明
    description: str             # 简短描述
    args: List[CommandArg]       # 参数列表
    handler: str = "event"       # "event" (EventBus) / "builtin" (本地)
```

### CommandArg

```python
@dataclass
class CommandArg:
    name: str
    required: bool
    description: str = ""
```

## 三、命令声明方式

### 3.1 manifest.json 声明

```json
{
  "name": "llm_gateway",
  "commands": [
    {
      "name": "switch",
      "usage": "/switch <厂商> [模型]",
      "desc": "切换 LLM 厂商",
      "args": [
        {"name": "厂商", "required": true, "desc": "厂商名"},
        {"name": "模型", "required": false, "desc": "模型名"}
      ],
      "handler": "event"
    },
    {
      "name": "models",
      "usage": "/models",
      "desc": "列出所有模型",
      "args": []
    }
  ]
}
```

启动时通过 `load_commands_from_manifests()` 批量加载。

### 3.2 代码动态注册

```python
from agent_framework.shared.commands import register_command, CommandInfo

class MyPlugin(PluginInterface):
    async def start(self):
        register_command(CommandInfo(
            name="mycmd",
            plugin_id="myplugin",
            usage="/mycmd <arg>",
            description="我的命令",
            args=[CommandArg(name="arg", required=True)],
            handler="event",
        ))
```

### 3.3 内置命令（CLIChannelPlugin）

```python
self._builtin_commands = {
    "help": self._handle_help,
    "quit": self._handle_quit,
    "plugins": self._handle_plugins,
    "plugin": self._handle_plugin_detail,
    "models": self._handle_models,
    "switch": self._handle_switch,
    ...
}
```

## 四、路由优先级

```
用户输入 /xxx
    │
    ├─ 1. 内置命令匹配 → 本地处理
    ├─ 2. COMMAND_REGISTRY 匹配 → EventBus 发布 user.command
    └─ 3. 未匹配 → 输出 "未知命令，输入 /help 查看"
```

## 五、命令补全

```python
def get_completion_data() -> Dict[str, Any]:
    """生成 readline completer 所需的补全数据。"""
```

返回结构：

```json
{
  "/switch": {
    "description": "切换 LLM 厂商",
    "next": {
      "厂商": ["deepseek", "kimi"],
      "模型": ["deepseek-chat", "deepseek-v4-pro"]
    }
  }
}
```

## 六、相关文档

- [cli.md §6.3 命令优先级](../plugins/access/channels/cli.md) — 命令在终端中的路由和执行流程
- [plugin-development.md](./plugin-development.md) — 插件开发指南
- [program-flow.md](./program-flow.md) — 系统启动流程

---

## 七、API 总览

| 函数 | 说明 |
|------|------|
| `register_command(cmd_info)` | 注册命令 |
| `unregister_command(name, plugin_id)` | 注销命令 |
| `get_command(name)` | 查询命令 |
| `list_commands()` | 列出所有命令 |
| `get_plugin_commands(plugin_id)` | 获取插件全部命令 |
| `load_commands_from_manifests(manifests)` | 从 manifest 批量加载 |
| `get_completion_data()` | 补全数据 |