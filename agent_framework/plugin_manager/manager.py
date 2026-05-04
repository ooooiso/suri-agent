"""PluginManager — 插件管理器。"""

import ast
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


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
        """扫描插件目录，读取 manifest.json。
        
        递归扫描所有子目录（支持 capability/、execution/、service/、extension/ 等层级）。
        """
        manifests = {}
        for scan_dir in self._scan_dirs:
            path = Path(scan_dir)
            if not path.exists():
                continue
            # 递归遍历所有子目录，查找 manifest.json
            for manifest_file in path.rglob("manifest.json"):
                plugin_dir = manifest_file.parent
                try:
                    with open(manifest_file, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    manifest["_path"] = str(plugin_dir)
                    name = manifest.get("name", plugin_dir.name)
                    manifests[name] = manifest
                except Exception as e:
                    print(f"[PluginManager] Failed to read manifest {manifest_file}: {e}")
        return manifests

    def _detect_circular_deps(self, manifests: Dict[str, Dict[str, Any]]) -> List[str]:
        """检测循环依赖，返回参与循环的插件名称列表。
        
        使用 Kahn 算法检测剩余节点（入度 > 0 的节点即为循环部分）。
        """
        from collections import defaultdict, deque
        
        graph = defaultdict(set)
        in_degree = defaultdict(int)
        
        for name, manifest in manifests.items():
            deps = set(manifest.get("dependencies", []))
            graph[name]
            for dep in deps:
                if dep in manifests:
                    graph[name].add(dep)
                    in_degree[dep] += 1
        
        # Kahn 算法
        queue = deque([n for n in graph if in_degree[n] == 0])
        sorted_count = 0
        while queue:
            node = queue.popleft()
            sorted_count += 1
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if sorted_count != len(graph):
            cycled = [n for n in graph if in_degree[n] > 0]
            return cycled
        return []

    def _topological_sort(self, manifests: Dict[str, Dict[str, Any]]) -> List[str]:
        """按依赖关系拓扑排序插件加载顺序。
        
        使用 Kahn 算法，检测循环依赖和缺失依赖并发出警告。
        
        返回拓扑排序后的插件名称列表。
        """
        from collections import deque
        
        # Step 1: 检测缺失依赖并警告
        for name, manifest in manifests.items():
            deps = set(manifest.get("dependencies", []))
            for dep in deps:
                if dep not in manifests:
                    print(f"[PluginManager] WARNING: {name} depends on {dep}, but {dep} is not installed")
        
        # Step 2: 检测循环依赖
        cycled = self._detect_circular_deps(manifests)
        if cycled:
            print(f"[PluginManager] WARNING: Circular dependency detected among: {', '.join(cycled)}")
        
        # 构建依赖图
        # graph[name] = 依赖 name 的节点集合（反向图）
        graph: Dict[str, Set[str]] = {name: set() for name in manifests}
        # in_degree[name] = name 依赖的节点数
        in_degree: Dict[str, int] = {name: 0 for name in manifests}
        
        for name, manifest in manifests.items():
            deps = set(manifest.get("dependencies", []))
            for dep in deps:
                if dep in manifests:
                    # dep 被 name 依赖
                    graph[dep].add(name)
                    # name 依赖 dep
                    in_degree[name] += 1
        
        # Kahn 算法：先加载入度为 0 的节点（不依赖任何其他节点）
        queue = deque([n for n, d in in_degree.items() if d == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            # node 已加载，所有依赖 node 的节点入度减 1
            for dependent in graph[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # 处理循环依赖节点：强制追加到最后
        for name in manifests:
            if name not in result:
                result.append(name)
                print(f"[PluginManager] WARNING: {name} has circular dependency, loaded at end")
        
        return result

    def _ast_scan(self, file_path: Path) -> bool:
        """AST 安全扫描。
        
        检查内容：
        1. 禁止的 API 调用（精确匹配，避免 run_in_executor 被 exec 误杀）
        2. 禁止的 import 语句
        3. 禁止的模块导入
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            
            # 禁止调用的 API（精确匹配）
            forbidden_calls = {
                "socket", "subprocess", "os.system", "os.popen",
                "os.exec", "os.spawn", "eval", "exec", "compile",
                "__import__", "ctypes", "imp",
            }
            
            # 禁止导入的模块
            forbidden_imports = {
                "socket", "subprocess", "ctypes", "imp", "pickle",
            }
            
            for node in ast.walk(tree):
                # 检查 API 调用
                if isinstance(node, ast.Call):
                    func_name = self._get_func_name(node.func)
                    if func_name:
                        # 精确匹配：func_name == f 或 func_name.endswith(f".{f}")
                        # 避免 run_in_executor 被 exec 误杀
                        for f in forbidden_calls:
                            if func_name == f or func_name.endswith(f".{f}"):
                                print(f"[AST Scan] ❌ 禁止 API 调用: {func_name} (文件: {file_path.name})")
                                return False
                
                # 检查 import 语句
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        if module_name in forbidden_imports:
                            print(f"[AST Scan] ❌ 禁止导入: {alias.name} (文件: {file_path.name})")
                            return False
                
                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_top = node.module.split('.')[0]
                        if module_top in forbidden_imports:
                            print(f"[AST Scan] ❌ 禁止导入: {node.module} (文件: {file_path.name})")
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