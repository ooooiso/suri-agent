"""suri_core 插件 — 系统内核。

职责：
- 启动序列（12 步分阶段加载）
- 目录初始化（Step 1.5）
- 启动自检（Pre-boot Healthcheck）
- 心跳检测（核心 5s / 普通 30s）
- 关闭流程（warm/cold + 状态持久化）
- 热重启
"""

import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from agent_framework.event_bus.bus import EventBus
from agent_framework.plugin_manager.manager import PluginManager
from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority

from agent_framework.core.suri_core.health import (
    run_healthcheck,
)


class SuriCorePlugin(PluginInterface):
    """系统内核插件。

    作为第一个启动的插件，负责任命任务、管理所有插件的生命周期。
    """

    # 核心插件列表（心跳间隔 5s，超时 30s）
    CORE_PLUGINS = {
        "config_service", "log_service", "security_service",
        "llm_gateway", "role_manager",
    }

    def __init__(self):
        self.name = "suri_core"
        self._event_bus: Optional[EventBus] = None
        self._plugin_manager: Optional[PluginManager] = None
        self._config: Dict[str, Any] = {}

        # 运行时路径
        self._project_root: Path = Path(__file__).parent.parent.parent.parent
        self._suri_home: Path = Path.home() / ".suri"
        self._runtime_dir: Path = self._suri_home / "runtime"
        self._config_path: Path = self._suri_home / "config.json"
        self._db_path: Path = self._suri_home / "suri.db"
        self._data_dir: Path = self._suri_home / "data"
        self._logs_dir: Path = self._suri_home / "runtime" / "logs"
        self._works_dir: Path = self._project_root / "works"
        self._tmp_dir: Path = Path("/tmp") / "suri-agent"

        # 插件心跳
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._plugin_heartbeats: Dict[str, float] = {}

        # 运行状态
        self._running = False
        self._shutdown_mode: str = "cold"
        self._started_at: Optional[str] = None

    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config.get("suri_core", {})

    def register_events(self) -> None:
        self._event_bus.subscribe("system.shutdown", self._on_shutdown)
        self._event_bus.subscribe("system.restart", self._on_restart)
        self._event_bus.subscribe("plugin.heartbeat", self._on_plugin_heartbeat)
        self._event_bus.subscribe("plugin.error", self._on_plugin_error)
        self._event_bus.subscribe("upgrade.requested", self._on_upgrade)

    async def start(self) -> None:
        pass

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._shutdown_mode == "warm":
            await self._warm_shutdown()
        else:
            await self._cold_shutdown()

    async def cleanup(self) -> None:
        self._plugin_heartbeats.clear()

    # ================================================================== #
    # Bootstrap
    # ================================================================== #
    async def bootstrap(self) -> None:
        """执行启动序列。"""
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._running = True

        print("[suri_core] 🚀 启动序列开始...")

        print("[suri_core] Step 1/12: 创建 EventBus...")
        self._event_bus = EventBus()
        await self._event_bus.start()

        print("[suri_core] Step 1.5/12: 初始化目录结构...")
        self._init_directories()

        print("[suri_core] Step 2/12: 创建 PluginManager...")
        scan_dirs = [
            str(self._project_root / "agent_framework" / "plugins"),
            str(self._project_root / "agent_framework" / "core"),
        ]
        self._plugin_manager = PluginManager(self._event_bus, scan_dirs)

        # 自注册
        self._plugin_manager._plugins["suri_core"] = self
        self._plugin_manager._manifests["suri_core"] = {
            "name": "suri_core", "version": "1.0.0", "type": "core",
            "description": "系统内核 — 启动序列、目录初始化、自检、心跳、关闭流程、热重启",
            "dependencies": [],
            "permissions": ["system.*"],
            "event_subscriptions": ["system.shutdown", "system.restart", "plugin.heartbeat", "plugin.error", "upgrade.requested"],
            "config_schema": {},
            "operations": ["restart", "stop"],
        }

        # 加载 Phase 1 — 基础服务
        print("[suri_core] Step 4/12: 加载基础服务插件...")
        await self._load_phase(["config_service", "log_service", "security_service"], "基础服务")

        # 加载 Phase 2 — 核心能力
        print("[suri_core] Step 5/12: 加载核心能力插件...")
        await self._load_phase(["llm_gateway", "role_manager", "mcp_framework"], "核心能力")

        # 加载 Phase 3 — 执行层
        print("[suri_core] Step 6/12: 加载执行层插件...")
        await self._load_phase(["agent_registry", "task_planner", "interrupt_handler", "role_comm"], "执行层")

        # 加载 Phase 4 — 接入层
        print("[suri_core] Step 7/12: 加载接入层插件...")
        await self._load_phase(["access"], "接入层")

        # 恢复角色状态
        print("[suri_core] Step 8/12: 恢复角色状态...")
        await self._restore_role_states()

        # 启动自检
        print("[suri_core] Step 11/12: 执行启动自检...")
        await self._run_healthcheck()

        # 心跳
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # 广播 system.started（CLI 通道收到此事件后才渲染面板和启动输入循环）
        print("[suri_core] Step 12/12: 🎉 系统就绪，广播 system.started...")
        await self._event_bus.publish(Event(
            event_type="system.started",
            source="suri_core",
            payload={
                "started_at": self._started_at,
                "pid": os.getpid(),
                "project_root": str(self._project_root),
            },
            priority=Priority.CRITICAL,
        ))
        print("[suri_core] ✅ 启动完成。")

    # ================================================================== #
    # 分阶段加载插件
    # ================================================================== #
    async def _load_phase(self, plugin_ids: List[str], phase_name: str) -> None:
        """按阶段加载插件列表。"""
        for pid in plugin_ids:
            try:
                manifests = list(self._project_root.rglob(f"**/{pid}/manifest.json"))
                if not manifests:
                    print(f"[suri_core]   ℹ️  '{pid}' not found, skip")
                    continue
                manifest_path = manifests[0]
                plugin_dir = manifest_path.parent
                plugin_file = plugin_dir / "plugin.py"
                if not plugin_file.exists():
                    print(f"[suri_core]   ℹ️  '{pid}' has no plugin.py, skip")
                    continue

                import importlib.util
                module_name = f"plugin_{pid}"
                spec = importlib.util.spec_from_file_location(module_name, str(plugin_file))
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                for attr in dir(module):
                    cls = getattr(module, attr)
                    if isinstance(cls, type) and issubclass(cls, PluginInterface) and cls is not PluginInterface:
                        instance = cls()
                        await instance.init(self._event_bus, self._config)
                        instance.register_events()

                        # 设置状态追踪属性（供 CLI 面板读取）
                        instance._status = "running"
                        instance._running = True

                        # 读取 manifest.json 存为 dict
                        try:
                            with open(manifest_path, "r", encoding="utf-8") as mf:
                                manifest_dict = json.load(mf)
                        except (json.JSONDecodeError, OSError):
                            manifest_dict = {"name": pid, "version": "?", "type": "unknown", "description": ""}
                        if not manifest_dict.get("type"):
                            manifest_dict["type"] = "unknown"
                        if not manifest_dict.get("operations"):
                            manifest_dict["operations"] = ["start", "stop", "restart"]
                        self._plugin_manager._manifests[pid] = manifest_dict
                        print(f"[suri_core]   📋 manifest for '{pid}': type={manifest_dict.get('type', '?')}")

                        # 给接入层注入 PluginManager（新 CLI 通道需要真实插件列表）
                        if pid == "access":
                            await instance.start(plugin_manager=self._plugin_manager)
                        else:
                            await instance.start()
                        self._plugin_manager._plugins[pid] = instance
                        print(f"[suri_core]   ✅ '{pid}' loaded")

                        # 【bootstrap 期间不发布 system.plugin_loaded】
                        # 原因：CLI 通道在 system.started 之后才订阅 plugin_loaded，
                        # bootstrap 期间发布的事件（NORMAL 优先级）会滞留在队列中，
                        # 在 system.started（CRITICAL）跳队处理后依次触发，导致 5 次重复面板刷新。
                        # 改为：只发布 system.started 一个事件，CLI 在收到后统一渲染全量面板。
                        break
            except Exception as e:
                print(f"[suri_core]   ❌ '{pid}' load failed: {e}")

    # ================================================================== #
    # 目录与数据库初始化
    # ================================================================== #
    def _init_directories(self) -> None:
        dirs = [self._suri_home, self._runtime_dir, self._logs_dir,
                self._data_dir, self._tmp_dir, self._works_dir]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        if not self._config_path.exists():
            default_config = {
                "llm_gateway": {
                    "default_provider": "",
                    "providers": {},
                },
                "access": {
                    "channels": {
                        "cli": {"enabled": True},
                        "telegram": {"enabled": False, "bot_token": ""},
                    }
                },
                "suri_core": {
                    "heartbeat_interval_core": 5,
                    "heartbeat_interval_normal": 30,
                    "heartbeat_timeout_core": 30,
                    "heartbeat_timeout_normal": 120,
                },
            }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"[suri_core]   Created default config: {self._config_path}")

        self._init_database()
        print(f"[suri_core]   Directory structure initialized at {self._suri_home}")

    def _init_database(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _schema_version (
                version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
            )
        """)
        cursor.execute("SELECT MAX(version) FROM _schema_version")
        row = cursor.fetchone()
        current_version = row[0] if row and row[0] else 0

        if current_version < 1:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY, task_id TEXT, task_name TEXT,
                    parent_agent_id TEXT, role_id TEXT, status TEXT DEFAULT 'pending',
                    user_id TEXT, plan_id TEXT, created_at TEXT, updated_at TEXT,
                    steps_json TEXT, metadata_json TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY, role_id TEXT,
                    context_json TEXT, created_at TEXT, updated_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    memory_id TEXT PRIMARY KEY, role_id TEXT, content TEXT,
                    memory_type TEXT, created_at TEXT, tags_json TEXT
                )
            """)
            cursor.execute(
                "INSERT INTO _schema_version (version, applied_at) VALUES (?, ?)",
                (1, datetime.now(timezone.utc).isoformat())
            )
            print("[suri_core]   Database schema initialized (version 1)")
        conn.commit()
        conn.close()

    # ================================================================== #
    # 恢复角色状态
    # ================================================================== #
    async def _restore_role_states(self) -> None:
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT agent_id, task_id, task_name, role_id, status FROM agents WHERE status IN ('running', 'paused')"
            )
            for row in cursor.fetchall():
                agent_id, task_id, task_name, role_id, status = row
                cursor.execute(
                    "UPDATE agents SET status = 'paused', updated_at = ? WHERE agent_id = ?",
                    (datetime.now(timezone.utc).isoformat(), agent_id),
                )
                await self._event_bus.publish(Event(
                    event_type="agent.recovered", source="suri_core",
                    payload={"agent_id": agent_id, "task_name": task_name, "role_id": role_id,
                             "previous_status": status, "message": "Agent 已恢复（已暂停）"},
                    priority=Priority.NORMAL,
                ))
            cursor.execute("SELECT session_id, role_id, context_json FROM sessions")
            recovered = 0
            for row in cursor.fetchall():
                session_id, role_id, context_json = row
                await self._event_bus.publish(Event(
                    event_type="session.recovered", source="suri_core",
                    payload={"session_id": session_id, "role_id": role_id,
                             "context": json.loads(context_json) if context_json else {}},
                    priority=Priority.NORMAL,
                ))
                recovered += 1
            conn.close()
            if recovered > 0:
                print(f"[suri_core]   ✅ Recovered {recovered} sessions")
        except Exception as e:
            print(f"[suri_core]   ⚠️ Role state restoration failed: {e}")

    # ================================================================== #
    # 自检
    # ================================================================== #
    async def _run_healthcheck(self) -> None:
        plugins_dir = self._project_root / "agent_framework" / "plugins"
        roles_dir = self._project_root / "roles"
        report = run_healthcheck(
            project_root=self._project_root, roles_dir=roles_dir,
            plugins_dir=plugins_dir, db_path=self._db_path,
            config_path=self._config_path,
        )
        report.print_report()
        await self._event_bus.publish(Event(
            event_type="system.healthcheck", source="suri_core",
            payload={"summary": report.summary(),
                     "items": [{"name": i.name, "status": i.status, "message": i.message} for i in report.items]},
            priority=Priority.HIGH,
        ))
        if report.has_fatal:
            print("[suri_core] ❌ 启动自检存在致命错误")
            sys.exit(1)

    # ================================================================== #
    # 心跳
    # ================================================================== #
    async def _heartbeat_loop(self) -> None:
        interval_core = self._config.get("heartbeat_interval_core", 5)
        while self._running:
            await asyncio.sleep(interval_core)
            await self._event_bus.publish(Event(
                event_type="system.heartbeat", source="suri_core",
                payload={"timestamp": datetime.now(timezone.utc).timestamp(),
                         "active_plugins": len(self._plugin_heartbeats)},
                priority=Priority.LOW,
            ))

    async def _on_plugin_heartbeat(self, event: Event) -> None:
        self._plugin_heartbeats[event.payload.get("plugin_id", event.source)] = (
            datetime.now(timezone.utc).timestamp()
        )

    async def _on_plugin_error(self, event: Event) -> None:
        print(f"[suri_core] ⚠️ Plugin error: {event.payload.get('plugin_id', event.source)} — {event.payload.get('error', 'Unknown')}")

    # ================================================================== #
    # 关闭
    # ================================================================== #
    async def _on_shutdown(self, event: Event) -> None:
        self._shutdown_mode = event.payload.get("mode", "cold")
        print(f"[suri_core] 🔴 系统关闭（{self._shutdown_mode}）...")
        await self._event_bus.publish(Event(
            event_type="system.shutting_down", source="suri_core",
            payload={"mode": self._shutdown_mode},
            priority=Priority.CRITICAL,
        ))
        await self.stop()

    async def _warm_shutdown(self) -> None:
        await self._persist_role_states()
        for pid, plugin in list(self._plugin_manager._plugins.items()):
            if pid != "suri_core":
                try:
                    await plugin.stop()
                    await plugin.cleanup()
                except Exception:
                    pass
        print("[suri_core] ✅ 热关闭完成")

    async def _cold_shutdown(self) -> None:
        for pid, plugin in list(self._plugin_manager._plugins.items()):
            if pid != "suri_core":
                try:
                    await plugin.stop()
                    await plugin.cleanup()
                except Exception:
                    pass
        print("[suri_core] ✅ 冷关闭完成")

    async def _persist_role_states(self) -> None:
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            role_manager = self._plugin_manager._plugins.get("role_manager")
            if role_manager and hasattr(role_manager, "_session_contexts"):
                now = datetime.now(timezone.utc).isoformat()
                for session_id, messages in role_manager._session_contexts.items():
                    cursor.execute(
                        "INSERT OR REPLACE INTO sessions (session_id, role_id, context_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (session_id, "suri", json.dumps(messages, ensure_ascii=False), now, now),
                    )
            conn.commit()
            conn.close()
        except Exception:
            pass

    async def _on_restart(self, event: Event) -> None:
        print("[suri_core] 🔄 热重启...")
        await self._persist_role_states()
        for pid, plugin in list(self._plugin_manager._plugins.items()):
            if pid != "suri_core":
                try:
                    await plugin.stop()
                    await plugin.cleanup()
                except Exception:
                    pass
        self._plugin_manager._plugins = {"suri_core": self}
        self._plugin_heartbeats.clear()
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except Exception:
                pass
        await self._load_phase(["config_service", "log_service", "security_service"], "基础服务")
        await self._load_phase(["llm_gateway", "role_manager", "mcp_framework"], "核心能力")
        await self._load_phase(["agent_registry", "task_planner", "interrupt_handler", "role_comm"], "执行层")
        await self._load_phase(["access"], "接入层")
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        print("[suri_core] ✅ 热重启完成")
        await self._event_bus.publish(Event(
            event_type="system.restarted", source="suri_core",
            payload={"restarted_at": datetime.now(timezone.utc).isoformat()},
            priority=Priority.CRITICAL,
        ))

    async def hot_restart(self) -> None:
        await self._event_bus.publish(Event(
            event_type="system.restart", source="suri_core",
            payload={}, priority=Priority.CRITICAL,
        ))

    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        return self._plugin_manager._plugins.get(plugin_id) if self._plugin_manager else None

    async def run(self) -> None:
        """保持运行。"""
        while self._running:
            await asyncio.sleep(0.5)

    async def _on_upgrade(self, event: Event) -> None:
        pass

    @property
    def event_bus(self) -> Optional[EventBus]:
        return self._event_bus

    @event_bus.setter
    def event_bus(self, value: EventBus) -> None:
        self._event_bus = value