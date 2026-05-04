"""config_service 插件 — 统一配置中心。

支持：
- 加载/保存 ~/.suri/config.json
- 热重载（文件监听 + 命令触发）
- 配置变更通知事件
- 配置子树隔离
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


class ConfigServicePlugin(PluginInterface):
    """配置服务插件。

    职责：
    - 加载/保存 ~/.suri/config.json
    - 热重载监听（文件 watch + 事件触发）
    - 提供配置查询 API
    - 变更通知发布
    """

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._config_path: Path = None
        self._last_mtime: float = 0
        self._watch_task: Optional[asyncio.Task] = None
        self._running = False

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        path = config.get("config_path", "~/.suri/config.json")
        self._config_path = Path(path).expanduser()
        self._load_config()

    async def start(self) -> None:
        self._running = True
        # 启动文件监听协程
        self._watch_task = asyncio.create_task(
            self._file_watch_loop(),
            name="config_watch",
        )

    async def pause(self) -> None:
        self._running = False

    async def resume(self) -> None:
        self._running = True
        if not self._watch_task or self._watch_task.done():
            self._watch_task = asyncio.create_task(
                self._file_watch_loop(),
                name="config_watch",
            )

    async def stop(self) -> None:
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

    async def cleanup(self) -> None:
        pass

    def register_events(self) -> None:
        self._event_bus.subscribe("user.command", self._on_command)
        self._event_bus.subscribe("system.config_changed", self._on_config_changed)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项（点分隔路径）。"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件的配置子树。"""
        return self._config.get(plugin_name, {})

    def set(self, key: str, value: Any, notify: bool = True) -> None:
        """设置配置项并保存。"""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        old_value = config.get(keys[-1])
        config[keys[-1]] = value
        self._save_config()

        if notify and self._event_bus:
            asyncio.ensure_future(self._publish_change_event(key, old_value, value))

    def get_all(self) -> Dict[str, Any]:
        """获取全部配置。"""
        return self._config.copy()

    # --- 热重载机制 ---

    async def _file_watch_loop(self) -> None:
        """文件监听循环（每 3 秒检查 mtime 变化）。

        自动检测配置文件变更并热重载。
        """
        while self._running:
            try:
                await asyncio.sleep(3.0)
                if self._config_path.exists():
                    current_mtime = self._config_path.stat().st_mtime
                    if current_mtime > self._last_mtime:
                        old_config = self._config.copy()
                        self._load_config()
                        print(f"[ConfigService] 🔄 检测到配置变更，已热重载")
                        if self._event_bus:
                            # 计算变更的键
                            changed_keys = self._detect_changes(old_config, self._config)
                            await self._event_bus.publish(Event(
                                event_type="system.config_changed",
                                source="config_service",
                                payload={
                                    "reason": "file_change",
                                    "changed_keys": changed_keys,
                                    "file_path": str(self._config_path),
                                },
                                priority=Priority.NORMAL,
                            ))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ConfigService] File watch error: {e}")

    def _detect_changes(self, old: Dict, new: Dict, prefix: str = "") -> list:
        """递归检测新旧配置之间的差异，返回变更键列表。"""
        changes = []
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            if key not in old:
                changes.append(full_key)
            elif key not in new:
                changes.append(full_key)
            elif isinstance(old[key], dict) and isinstance(new[key], dict):
                changes.extend(self._detect_changes(old[key], new[key], full_key))
            elif old[key] != new[key]:
                changes.append(full_key)
        return changes

    async def reload(self) -> bool:
        """手动触发重新加载配置。"""
        if not self._config_path.exists():
            return False
        old_config = self._config.copy()
        self._load_config()
        changed_keys = self._detect_changes(old_config, self._config)
        if self._event_bus:
            await self._event_bus.publish(Event(
                event_type="system.config_changed",
                source="config_service",
                payload={
                    "reason": "manual_reload",
                    "changed_keys": changed_keys,
                },
                priority=Priority.NORMAL,
            ))
        return len(changed_keys) > 0

    async def _publish_change_event(self, key: str, old_value: Any, new_value: Any) -> None:
        """发布配置变更事件。"""
        if self._event_bus:
            await self._event_bus.publish(Event(
                event_type="system.config_changed",
                source="config_service",
                payload={
                    "reason": "api_set",
                    "key": key,
                    "old_value": old_value,
                    "new_value": new_value,
                },
                priority=Priority.NORMAL,
            ))

    # --- 内部方法 ---

    def _load_config(self) -> None:
        """从文件加载配置。"""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                self._last_mtime = self._config_path.stat().st_mtime
            except Exception as e:
                print(f"[ConfigService] ⚠️ 加载配置失败: {e}")
                self._config = {}
        else:
            self._config = {}

    def _save_config(self) -> None:
        """保存配置到文件。"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            self._last_mtime = self._config_path.stat().st_mtime
        except Exception as e:
            print(f"[ConfigService] ⚠️ 保存配置失败: {e}")

    async def _on_command(self, event: Event) -> None:
        """处理命令。"""
        cmd = event.payload.get("command", "")
        args = event.payload.get("args", [])

        if cmd == "reload":
            changed = await self.reload()
            print(f"[ConfigService] {'✅ 配置已重载' if changed else '⚠️ 配置无变化'}")
        elif cmd == "config":
            key = args[0] if args else None
            if key:
                value = self.get(key, "<not set>")
                print(f"  {key} = {value}")
            else:
                print(json.dumps(self._config, indent=2, ensure_ascii=False))

    async def _on_config_changed(self, event: Event) -> None:
        """配置变更时重新加载（从其他途径修改了文件）。"""
        self._load_config()