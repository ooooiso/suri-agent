"""SuriCorePlugin — 内核插件。

自举注册，提供 EventBus + PluginManager。
启动时由 main.py 实例化，不由 PluginManager 加载。
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict

from agent_framework.event_bus.bus import EventBus
from agent_framework.plugin_manager.manager import PluginManager
from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority


class SuriCorePlugin(PluginInterface):
    """内核插件。
    
    特殊属性：
    - type: core
    - self_registration: true
    - runtime_mutable: false
    """

    def __init__(self):
        self._event_bus: EventBus = None
        self._plugin_manager: PluginManager = None
        self._running = False
        self._shutdown_event = None

    async def bootstrap(self) -> None:
        """启动流程。
        
        1. 初始化 EventBus
        2. 初始化 PluginManager
        3. 自注册
        4. 加载其他插件
        5. 发布 system.start
        """
        # 确保运行时目录存在
        runtime_dir = Path.home() / ".suri" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        
        db_path = str(runtime_dir / "suri.db")
        
        # 初始化数据库
        self._init_db(db_path)
        
        # 1. 创建 EventBus
        self._event_bus = EventBus(db_path=db_path)
        await self._event_bus.start()
        
        # 2. 创建 PluginManager
        project_root = Path(__file__).parent.parent.parent
        scan_dirs = [
            str(project_root / "plugins"),
            str(runtime_dir / "plugins"),
        ]
        self._plugin_manager = PluginManager(self._event_bus, scan_dirs)
        
        # 3. 自注册（将自己注册到 PluginManager 的管理中，但不重新加载）
        self._self_register()
        
        # 4. 加载其他插件
        await self._plugin_manager.load_all()
        
        # 5. 发布 system.start
        start_event = Event(
            event_type="system.start",
            source="suri_core",
            payload={
                "version": "1.0.0",
                "loaded_plugins": list(self._plugin_manager._plugins.keys()),
            },
            priority=Priority.CRITICAL,
        )
        await self._event_bus.publish(start_event)
        
        self._running = True
        self._shutdown_event = __import__("asyncio").Event()

    async def run(self) -> None:
        """保持运行，等待关闭信号。"""
        if self._shutdown_event:
            await self._shutdown_event.wait()

    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        """初始化（接口要求，内核插件自身不需要）。"""
        pass

    async def start(self) -> None:
        """启动（接口要求）。"""
        pass

    async def pause(self) -> None:
        """暂停。"""
        pass

    async def resume(self) -> None:
        """恢复。"""
        pass

    async def stop(self) -> None:
        """停止。
        
        1. 停止接收新输入
        2. 卸载插件（逆序）
        3. 停止 EventBus
        4. 发布 system.shutdown
        """
        if not self._running:
            return
        
        self._running = False
        
        # 发布关闭事件
        shutdown_event = Event(
            event_type="system.shutdown",
            source="suri_core",
            payload={"reason": "user_request"},
            priority=Priority.CRITICAL,
        )
        await self._event_bus.publish(shutdown_event)
        
        # 卸载插件
        await self._plugin_manager.unload_all()
        
        # 停止 EventBus
        await self._event_bus.stop()
        
        # 唤醒等待中的 run()
        if self._shutdown_event:
            self._shutdown_event.set()

    async def cleanup(self) -> None:
        """清理资源。"""
        pass

    def register_events(self) -> None:
        """注册事件订阅。"""
        self._event_bus.subscribe("system.shutdown", self._on_shutdown)
        self._event_bus.subscribe("plugin.upgrade_proposed", self._on_upgrade)

    def _self_register(self) -> None:
        """自注册到数据库。"""
        runtime_dir = Path.home() / ".suri" / "runtime"
        db_path = str(runtime_dir / "suri.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                """INSERT OR REPLACE INTO plugins 
                   (plugin_id, name, version, type, path, status, capabilities)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("suri_core", "suri_core", "1.0.0", "core", 
                 "agent_framework/suri_core_plugin", "active", "[event_bus, plugin_manager]"),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SuriCore] Self-register warning: {e}")

    def _init_db(self, db_path: str) -> None:
        """初始化数据库。"""
        if not Path(db_path).exists():
            # 从迁移脚本创建
            migrations_dir = Path(__file__).parent.parent / "migrations"
            if migrations_dir.exists():
                for sql_file in sorted(migrations_dir.glob("*.sql")):
                    with open(sql_file, "r", encoding="utf-8") as f:
                        sql = f.read()
                    conn = sqlite3.connect(db_path)
                    conn.executescript(sql)
                    conn.commit()
                    conn.close()

    async def _on_shutdown(self, event: Event) -> None:
        """处理关闭事件。"""
        await self.stop()

    async def _on_upgrade(self, event: Event) -> None:
        """处理升级提案。"""
        pass
