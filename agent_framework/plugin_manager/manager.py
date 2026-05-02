"""PluginManager — 插件管理器。"""

import ast
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority


class PluginManager:
    """插件管理器。
    
    职责：扫描、加载、初始化、注册、卸载插件。
    按依赖顺序管理插件生命周期。
    """

    def __init__(self, event_bus: Any, scan_dirs: List[str]):
        self._event_bus = event_bus
        self._scan_dirs = scan_dirs
        self._plugins: Dict[str, PluginInterface] = {}
        self._manifests: Dict[str, Dict[str, Any]] = {}
        self._plugin_classes: Dict[str, Type[PluginInterface]] = {}

    async def load_all(self) -> None:
        """扫描并加载所有插件。"""
        manifests = self._scan_plugins()
        sorted_plugins = self._topological_sort(manifests)
        
        for plugin_name in sorted_plugins:
            manifest = manifests[plugin_name]
            try:
                await self._load_plugin(plugin_name, manifest)
            except Exception as e:
                print(f"[PluginManager] Failed to load {plugin_name}: {e}")
                error_event = Event(
                    event_type="error.plugin",
                    source="plugin_manager",
                    payload={
                        "plugin_id": plugin_name,
                        "error_type": "load_failed",
                        "message": str(e),
                    },
                    priority=Priority.HIGH,
                )
                await self._event_bus.publish(error_event)

    async def unload_all(self) -> None:
        """卸载所有插件（逆序）。"""
        for name in reversed(list(self._plugins.keys())):
            await self._unload_plugin(name)

    async def _load_plugin(self, name: str, manifest: Dict[str, Any]) -> None:
        """加载单个插件。"""
        # 1. 安全检查：AST 扫描
        plugin_path = manifest.get("_path", "")
        plugin_file = Path(plugin_path) / "plugin.py"
        if plugin_file.exists():
            if not self._ast_scan(plugin_file):
                raise SecurityError(f"AST scan failed for {name}")
        
        # 2. 动态导入
        plugin_class = self._import_plugin(plugin_file, name)
        
        # 3. 实例化
        instance = plugin_class()
        
        # 4. 初始化
        config = manifest.get("config_schema", {})
        await instance.init(self._event_bus, config)
        
        # 5. 注册事件
        instance.register_events()
        
        # 6. 启动
        await instance.start()
        
        # 7. 记录
        self._plugins[name] = instance
        self._manifests[name] = manifest
        self._plugin_classes[name] = plugin_class
        
        # 8. 发布事件
        load_event = Event(
            event_type="system.plugin_loaded",
            source="plugin_manager",
            payload={
                "plugin_id": name,
                "version": manifest.get("version", "0.0.0"),
                "type": manifest.get("type", "extension"),
            },
            priority=Priority.NORMAL,
        )
        await self._event_bus.publish(load_event)

    async def _unload_plugin(self, name: str) -> None:
        """卸载单个插件。"""
        if name not in self._plugins:
            return
        
        plugin = self._plugins[name]
        try:
            await plugin.stop()
            await plugin.cleanup()
        except Exception as e:
            print(f"[PluginManager] Error unloading {name}: {e}")
        
        del self._plugins[name]
        
        unload_event = Event(
            event_type="system.plugin_unloaded",
            source="plugin_manager",
            payload={"plugin_id": name},
            priority=Priority.NORMAL,
        )
        await self._event_bus.publish(unload_event)

    def _scan_plugins(self) -> Dict[str, Dict[str, Any]]:
        """扫描插件目录，读取 manifest.json。"""
        manifests = {}
        for scan_dir in self._scan_dirs:
            path = Path(scan_dir)
            if not path.exists():
                continue
            for plugin_dir in path.iterdir():
                if not plugin_dir.is_dir():
                    continue
                manifest_file = plugin_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                        manifest["_path"] = str(plugin_dir)
                        name = manifest.get("name", plugin_dir.name)
                        manifests[name] = manifest
                    except Exception as e:
                        print(f"[PluginManager] Failed to read manifest {manifest_file}: {e}")
        return manifests

    def _topological_sort(self, manifests: Dict[str, Dict[str, Any]]) -> List[str]:
        """按依赖关系拓扑排序插件加载顺序。"""
        # 构建依赖图
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}
        
        for name, manifest in manifests.items():
            deps = set(manifest.get("dependencies", []))
            graph[name] = deps
            in_degree[name] = in_degree.get(name, 0)
        
        # 计算入度
        for name, deps in graph.items():
            for dep in deps:
                if dep in manifests:
                    in_degree[name] = in_degree.get(name, 0) + 1
        
        # Kahn 算法
        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            for name, deps in graph.items():
                if node in deps:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)
        
        # 处理循环依赖：未排序的插件放到最后
        for name in manifests:
            if name not in result:
                result.append(name)
        
        return result

    def _ast_scan(self, file_path: Path) -> bool:
        """AST 安全扫描。"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            
            forbidden = {
                "socket", "subprocess", "os.system", "os.popen",
                "os.exec", "os.spawn", "eval", "exec", "compile",
                "__import__", "ctypes", "imp",
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = self._get_func_name(node.func)
                    if func_name and any(
                    func_name == f or func_name.endswith(f".{f}") for f in forbidden
                ):
                        print(f"[AST Scan] Forbidden API detected: {func_name}")
                        return False
            return True
        except Exception as e:
            print(f"[AST Scan] Error scanning {file_path}: {e}")
            return False

    def _get_func_name(self, node: ast.AST) -> Optional[str]:
        """获取函数调用的完整名称。"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self._get_func_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        return None

    def _import_plugin(self, file_path: Path, name: str) -> Type[PluginInterface]:
        """动态导入插件模块。"""
        module_name = f"plugin_{name}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Cannot load plugin from {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # 查找 PluginInterface 的子类
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, PluginInterface) and 
                attr is not PluginInterface):
                return attr
        
        raise ImportError(f"No PluginInterface subclass found in {file_path}")


class SecurityError(Exception):
    """安全异常。"""
    pass
