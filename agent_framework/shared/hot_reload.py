"""热更新模块 — 文件监听 + 事件驱动热重载。

解决原始需求：
- "服务端改代码后为什么没有热更新？"
- "输入聊天程序发现已更新代码直接进行重载"

架构：
- FileWatcher: 监听 plugins/ 目录，检测 Python 文件变更
- 变更 → 通过 EventBus → 各模块订阅并刷新
- 支持 L1(配置)、L2(数据)、L3(代码) 三级热更新

PRD: prd/operations/hot-reload.md
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from agent_framework.shared.utils.event_types import Event, Priority


# ═══════════════════════════════════════════════════════════════════ #
# FileWatcher — 文件变更监听器
# ═══════════════════════════════════════════════════════════════════ #

class FileWatcher:
    """文件变更监听器 — 轮询实现，零依赖。

    每 2 秒轮询插件目录，比对 mtime。
    检测到变更则发布 xxx.updated 事件。

    用户需求:
    "比如输入聊天程序发现已更新代码直接进行重载"
    """

    def __init__(self, event_bus, watch_dirs: List[str], interval: float = 2.0):
        self._event_bus = event_bus
        self._watch_dirs = [Path(d) for d in watch_dirs]
        self._interval = interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # mtime 缓存: str_path → (mtime, file_size)
        self._file_cache: Dict[str, tuple] = {}

        # 扩展名过滤
        self._watch_extensions = {".py", ".json", ".yaml", ".yml", ".md", ".sql"}

        # 排除模式
        self._exclude_dirs = {"__pycache__", ".git", ".DS_Store", "node_modules"}

        # 回调注册
        self._callbacks: Dict[str, List[Callable]] = {
            "plugin_file": [],     # .py 文件变更
            "manifest": [],        # manifest.json 变更
            "config": [],          # .json/.yaml 配置变更
            "template": [],        # .md/.sql 模板变更
        }

    def on(self, event_type: str, callback: Callable) -> None:
        """注册文件变更回调。

        Args:
            event_type: plugin_file / manifest / config / template
            callback: async def callback(path: str) -> None
        """
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)

    async def start(self) -> None:
        """启动监听循环。"""
        self._running = True
        # 初始化缓存
        self._scan_all()
        # 启动轮询
        self._task = asyncio.create_task(self._poll_loop())

    def stop(self) -> None:
        """停止监听。"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    def _scan_all(self) -> None:
        """扫描所有受监视目录，建立初始缓存。"""
        for watch_dir in self._watch_dirs:
            if not watch_dir.exists():
                continue
            for file_path in watch_dir.rglob("*"):
                self._update_cache(file_path)

    def _update_cache(self, file_path: Path) -> None:
        """更新单个文件的缓存。"""
        if not file_path.is_file():
            return
        if file_path.suffix not in self._watch_extensions:
            return
        if any(excl in file_path.parts for excl in self._exclude_dirs):
            return

        try:
            stat = file_path.stat()
            self._file_cache[str(file_path)] = (stat.st_mtime, stat.st_size)
        except OSError:
            pass

    async def _poll_loop(self) -> None:
        """轮询循环。"""
        while self._running:
            await asyncio.sleep(self._interval)
            try:
                await self._poll_once()
            except Exception:
                pass

    async def _poll_once(self) -> None:
        """单次轮询。"""
        changed_files: Dict[str, List[Path]] = {
            "plugin_file": [],
            "manifest": [],
            "config": [],
            "template": [],
        }

        for watch_dir in self._watch_dirs:
            if not watch_dir.exists():
                continue
            for file_path in watch_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.suffix not in self._watch_extensions:
                    continue
                if any(excl in file_path.parts for excl in self._exclude_dirs):
                    continue

                path_str = str(file_path)
                try:
                    stat = file_path.stat()
                    new_mtime = stat.st_mtime
                    new_size = stat.st_size
                    old = self._file_cache.get(path_str)

                    if old is None:
                        # 新文件
                        self._file_cache[path_str] = (new_mtime, new_size)
                    elif old[0] != new_mtime or old[1] != new_size:
                        # 文件变更
                        self._file_cache[path_str] = (new_mtime, new_size)

                        # 分类
                        if file_path.name == "manifest.json":
                            changed_files["manifest"].append(file_path)
                        elif file_path.suffix == ".py":
                            changed_files["plugin_file"].append(file_path)
                        elif file_path.suffix in (".yaml", ".yml"):
                            changed_files["config"].append(file_path)
                        elif file_path.suffix == ".json":
                            changed_files["config"].append(file_path)
                        elif file_path.suffix in (".md", ".sql"):
                            changed_files["template"].append(file_path)

                except OSError:
                    # 文件被删除
                    if path_str in self._file_cache:
                        del self._file_cache[path_str]

        # 发布事件 + 触发回调
        for event_type, files in changed_files.items():
            if not files:
                continue

            # 去重：只触发每个分类一次
            # 发布事件
            await self._event_bus.publish(Event(
                event_type=f"file.{event_type}_changed",
                source="hot_reload",
                payload={
                    "files": [str(f) for f in files],
                    "count": len(files),
                },
                priority=Priority.LOW,
            ))

            # 触发注册的回调
            for callback in self._callbacks.get(event_type, []):
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(str(files[0]))
                    else:
                        callback(str(files[0]))
                except Exception:
                    pass


# ═══════════════════════════════════════════════════════════════════ #
# HotReloadManager — 热更新管理
# ═══════════════════════════════════════════════════════════════════ #

class HotReloadManager:
    """热更新管理器。

    整合文件监听 + 事件订阅 + 重载执行。
    通过 EventBus 接收文件变更事件，执行对应热更新策略。

    支持的热更新场景：
    - manifest.json 变更 → 刷新 COMMAND_REGISTRY
    - 配置文件变更 → 通知对应插件重载配置
    - Python 文件变更 → 执行模块级热重载
    """

    def __init__(self, event_bus, watch_dirs: List[str], plugin_manager=None):
        self._event_bus = event_bus
        self._plugin_manager = plugin_manager
        self._watcher = FileWatcher(event_bus, watch_dirs, interval=2.0)
        self._running = False

        # 已注册的插件热更新处理器
        self._reload_handlers: Dict[str, Callable] = {}

    @staticmethod
    def _safe_print(text: str) -> None:
        """安全写入 stderr（不受 stdin non-blocking 影响）。"""
        try:
            sys.stderr.write(text + "\n")
            sys.stderr.flush()
        except (OSError, BlockingIOError):
            pass

    def register_plugin_reloader(self, plugin_id: str, handler: Callable) -> None:
        """注册插件的热更新处理器。

        Args:
            plugin_id: 插件 ID
            handler: async def handler(file_path: str) -> None
        """
        self._reload_handlers[plugin_id] = handler

    async def start(self) -> None:
        """启动热更新系统。"""
        self._running = True

        # 注册文件变更回调
        self._watcher.on("manifest", self._on_manifest_changed)
        self._watcher.on("config", self._on_config_changed)
        self._watcher.on("plugin_file", self._on_plugin_file_changed)

        # 订阅事件
        self._event_bus.subscribe("file.plugin_file_changed", self._on_file_event)
        self._event_bus.subscribe("file.manifest_changed", self._on_file_event)
        self._event_bus.subscribe("file.config_changed", self._on_file_event)

        # 启动文件监听
        await self._watcher.start()

    def stop(self) -> None:
        """停止热更新系统。"""
        self._running = False
        self._watcher.stop()

    async def _on_file_event(self, event: Event) -> None:
        """处理文件变更事件（由 FileWatcher 触发）。"""
        event_type = event.event_type
        files = event.payload.get("files", [])

        if event_type == "file.plugin_file_changed":
            for f in files:
                await self._hot_reload_plugin_file(f)
        elif event_type == "file.manifest_changed":
            for f in files:
                await self._reload_manifest(f)
        elif event_type == "file.config_changed":
            for f in files:
                await self._reload_config(f)

    async def _on_manifest_changed(self, file_path: str) -> None:
        """处理 manifest.json 变更。"""
        await self._reload_manifest(file_path)

    async def _on_config_changed(self, file_path: str) -> None:
        """处理配置文件变更。"""
        await self._reload_config(file_path)

    async def _on_plugin_file_changed(self, file_path: str) -> None:
        """处理 Python 文件变更。"""
        await self._hot_reload_plugin_file(file_path)

    async def _reload_manifest(self, file_path: str) -> None:
        """重载 manifest.json。

        提取 commands 并刷新 COMMAND_REGISTRY。
        """
        try:
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            plugin_id = manifest.get("name", Path(file_path).parent.name)

            # 通知 CLI 刷新命令注册表
            from agent_framework.shared.commands import load_commands_from_manifests
            load_commands_from_manifests({plugin_id: manifest})

            await self._event_bus.publish(Event(
                event_type="plugin.commands_refreshed",
                source="hot_reload",
                payload={
                    "plugin_id": plugin_id,
                    "commands": manifest.get("commands", []),
                },
                priority=Priority.LOW,
            ))

        except Exception:
            pass

    async def _reload_config(self, file_path: str) -> None:
        """处理配置文件变更。

        识别归属插件，发布 config.updated 事件。
        """
        path = Path(file_path)
        plugin_id = path.parent.name if path.parent.name != "configs" else "unknown"

        await self._event_bus.publish(Event(
            event_type="config.updated",
            source="hot_reload",
            payload={
                "plugin_id": plugin_id,
                "config_key": path.stem,
                "file_path": file_path,
            },
            priority=Priority.LOW,
        ))

    async def _hot_reload_plugin_file(self, file_path: str) -> None:
        """热重载插件 Python 文件 — L3 级热更新。

        用户需求："比如输入聊天程序发现已更新代码直接进行重载"

        执行流程：
        1. 识别插件 ID 和模块名
        2. 执行 importlib.reload() 重载模块内存
        3. 如果有 PluginManager，执行插件完整重启：
           stop() → cleanup() → 重新创建实例 → init() → register_events() → start()
        4. 发布重载通知
        """
        try:
            import importlib
            import inspect

            path = Path(file_path)
            plugin_id = path.parent.name

            # 构建完整模块名
            # agent_framework/plugins/access/formatter.py
            # → agent_framework.plugins.access.formatter
            parts = []
            found_framework = False
            for parent in path.parents:
                if parent.name == "agent_framework":
                    found_framework = True
                    break
                parts.insert(0, parent.name)

            prefix = "agent_framework." if found_framework else ""
            module_name = f"{prefix}{'.'.join(parts)}.{path.stem}"

            # Step 1: 模块重载
            if module_name in sys.modules:
                old_module = sys.modules[module_name]
                importlib.reload(old_module)
            else:
                importlib.import_module(module_name)
                old_module = sys.modules.get(module_name)

            self._safe_print(f"[HotReload] ✅ 模块重载: {module_name}")

            # Step 2: 插件实例完整重启（如果有 PluginManager）
            if self._plugin_manager and old_module:
                pm = self._plugin_manager
                old_plugin = pm._plugins.get(plugin_id)

                if old_plugin:
                    # 停止旧插件
                    try:
                        await old_plugin.stop()
                        await old_plugin.cleanup()
                    except Exception as e:
                        self._safe_print(f"[HotReload] ⚠️ 旧插件停止失败: {e}")

                    # 从新模块创建新实例
                    for attr in dir(old_module):
                        cls = getattr(old_module, attr)
                        if isinstance(cls, type) and issubclass(cls, type(old_plugin)) and cls is not type(old_plugin):
                            new_instance = cls()
                            # 初始化
                            if hasattr(new_instance, 'init') and callable(new_instance.init):
                                # 获取旧插件的 config（如果有）
                                old_config = getattr(old_plugin, '_config', {})
                                await new_instance.init(pm._event_bus, old_config)

                            # 重新注册事件
                            if hasattr(new_instance, 'register_events') and callable(new_instance.register_events):
                                new_instance.register_events()

                            # 标记运行状态（使用 _is_running 避免覆盖 task_scheduler._running 字典）
                            new_instance._status = "running"
                            new_instance._is_running = True

                            # 启动新实例（如果是 access 插件需要传 plugin_manager）
                            if plugin_id == "access":
                                await new_instance.start(plugin_manager=pm)
                            else:
                                await new_instance.start()

                            # 替换 PluginManager 中的实例
                            pm._plugins[plugin_id] = new_instance

                            self._safe_print(f"[HotReload] ✅ 插件 {plugin_id} 已重启为新实例")
                            break

            # Step 3: 发布通知
            await self._event_bus.publish(Event(
                event_type="system.notification",
                source="hot_reload",
                payload={
                    "title": "热更新",
                    "body": f"✅ {plugin_id} 已重载",
                },
                priority=Priority.LOW,
            ))

            # Step 4: 发布热重载完成事件（通知 CLI 通道刷新面板）
            await self._event_bus.publish(Event(
                event_type="system.hot_reload_completed",
                source="hot_reload",
                payload={
                    "plugin_id": plugin_id,
                    "file_path": file_path,
                    "reloaded_modules": [module_name],
                },
                priority=Priority.HIGH,
            ))

            self._safe_print(f"[HotReload] ✅ 热重载成功: {file_path}")

        except Exception as e:
            self._safe_print(f"[HotReload] ❌ 热重载失败 {file_path}: {e}")