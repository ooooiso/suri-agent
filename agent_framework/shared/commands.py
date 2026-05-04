"""命令注册表 — 插件命令元数据注册与发现。

插件通过 manifest.json 的 commands 字段声明命令，
或通过 register_command API 动态注册。
终端自动发现命令，无需手动 if-else。

PRD: prd/operations/command-system.md
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agent_framework.shared.utils.event_types import Event


# ── 数据结构 ──

@dataclass
class CommandArg:
    """命令参数定义。"""
    name: str
    required: bool
    description: str = ""


@dataclass
class CommandInfo:
    """单条命令注册信息。"""
    name: str                    # 命令名（不含 /）
    plugin_id: str               # 归属插件
    usage: str                   # 用法说明
    description: str             # 简短描述
    args: List[CommandArg] = field(default_factory=list)
    handler: str = "event"       # "event" (通过 EventBus) / "builtin" (内置处理)


# ── 全局注册表 ──

_COMMAND_REGISTRY: Dict[str, CommandInfo] = {}
_PLUGIN_COMMANDS: Dict[str, List[str]] = {}  # plugin_id → [command_names]


def register_command(cmd_info: CommandInfo) -> None:
    """注册一个命令到全局注册表。

    Args:
        cmd_info: 命令信息对象

    插件可以在 start() 中调用此方法动态注册命令。
    如果命令已存在则覆盖（以最后注册者为准）。
    """
    _COMMAND_REGISTRY[cmd_info.name] = cmd_info
    if cmd_info.plugin_id not in _PLUGIN_COMMANDS:
        _PLUGIN_COMMANDS[cmd_info.plugin_id] = []
    _PLUGIN_COMMANDS[cmd_info.plugin_id].append(cmd_info.name)


def unregister_command(command_name: str, plugin_id: str) -> bool:
    """注销一个命令。

    Args:
        command_name: 命令名（不含 /）
        plugin_id: 归属插件 ID

    Returns:
        是否成功注销
    """
    cmd = _COMMAND_REGISTRY.get(command_name)
    if cmd and cmd.plugin_id == plugin_id:
        del _COMMAND_REGISTRY[command_name]
        if plugin_id in _PLUGIN_COMMANDS:
            try:
                _PLUGIN_COMMANDS[plugin_id].remove(command_name)
            except ValueError:
                pass
        return True
    return False


def get_command(name: str) -> Optional[CommandInfo]:
    """获取命令信息。

    Args:
        name: 命令名（不含 /）

    Returns:
        命令信息，不存在返回 None
    """
    return _COMMAND_REGISTRY.get(name)


def list_commands() -> Dict[str, CommandInfo]:
    """列出所有已注册命令。

    Returns:
        命令名 → CommandInfo 的字典
    """
    return dict(_COMMAND_REGISTRY)


def get_plugin_commands(plugin_id: str) -> List[CommandInfo]:
    """获取某个插件的所有命令。

    Args:
        plugin_id: 插件 ID

    Returns:
        命令列表
    """
    names = _PLUGIN_COMMANDS.get(plugin_id, [])
    return [_COMMAND_REGISTRY[n] for n in names if n in _COMMAND_REGISTRY]


def load_commands_from_manifests(manifests: Dict[str, Dict]) -> None:
    """从 manifest.json 字典批量加载命令。

    Args:
        manifests: { plugin_id: manifest_dict, ... }

    每个 manifest 的 commands 字段格式：
        [{"name": "switch", "usage": "/switch <厂商>", "desc": "...", "args": [...]}]
    """
    for plugin_id, manifest in manifests.items():
        for cmd_dict in manifest.get("commands", []):
            args = [
                CommandArg(name=a.get("name", ""),
                          required=a.get("required", False),
                          description=a.get("desc", ""))
                for a in cmd_dict.get("args", [])
            ]
            cmd_info = CommandInfo(
                name=cmd_dict["name"],
                plugin_id=plugin_id,
                usage=cmd_dict.get("usage", f"/{cmd_dict['name']}"),
                description=cmd_dict.get("desc", ""),
                args=args,
                handler=cmd_dict.get("handler", "event"),
            )
            register_command(cmd_info)


def get_completion_data() -> Dict[str, Any]:
    """生成 readline completer 所需的补全数据。

    Returns:
        补全数据结构：
        {
            "/switch": {
                "description": "切换 LLM 厂商",
                "next": {
                    "厂商": ["deepseek", "kimi", ...],
                    "模型": [...]
                }
            },
            ...
        }
    """
    result = {}
    for name, info in _COMMAND_REGISTRY.items():
        entry = {
            "description": info.description,
        }
        if info.args:
            entry["next"] = {
                a.name: [] if a.required else []
                for a in info.args
            }
        result[f"/{info.name}"] = entry
    return result