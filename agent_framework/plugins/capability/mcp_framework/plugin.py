"""mcp_framework — MCP 服务框架插件。

MCP（Model Context Protocol）服务框架，系统唯一的工具注册中心。

职责：
- MCP Server：接收 tool.call 事件，路由到对应工具服务
- Registry：工具注册、发现、查询
- 内置服务管理：filesystem、shell_exec、web_search 等
- 工具调用参数校验（JSON Schema）
- 权限检查（通过 security_service）
- 调用审计日志

架构：
mcp_framework (插件)
  ├── plugin.py        ← MCP Server + Registry
  └── services/
      ├── filesystem.py  ← 文件系统操作
      ├── shell_exec.py  ← 命令执行
      └── web_search.py  ← 网络搜索
"""

import asyncio
import json
import importlib
import inspect
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


# ── MCP 工具定义 ──

class MCPTool:
    """MCP 工具定义。"""

    def __init__(self, name: str, description: str, params_schema: Dict[str, Any],
                 handler: Callable, permission: str = "public",
                 service_id: str = "local"):
        self.name = name
        self.description = description
        self.params_schema = params_schema
        self.handler = handler
        self.permission = permission  # public | maintainer | role:{role_id}
        self.service_id = service_id  # "local" 或远程服务 ID
        self.registered_at = datetime.now(timezone.utc).isoformat()

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """校验参数是否符合 schema。返回错误信息或 None。"""
        schema = self.params_schema
        required = schema.get("required", [])
        props = schema.get("properties", {})

        # 检查必填字段
        for field in required:
            if field not in params or params[field] in (None, ""):
                return f"缺少必填参数: {field}"

        # 类型检查
        for field, value in params.items():
            if field not in props:
                continue
            field_schema = props[field]
            expected_type = field_schema.get("type")
            if expected_type and value is not None:
                if expected_type == "string" and not isinstance(value, str):
                    return f"参数 {field} 应为字符串，实际为 {type(value).__name__}"
                elif expected_type == "integer" and not isinstance(value, int):
                    return f"参数 {field} 应为整数，实际为 {type(value).__name__}"

        return None


class MCPRegistry:
    """MCP 工具注册中心。

    管理所有工具的注册、发现、查询。
    """

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._services: Dict[str, Any] = {}  # service_id → service module

    def register_tool(self, tool: MCPTool) -> None:
        """注册一个工具。"""
        self._tools[tool.name] = tool

    def register_service(self, service_id: str, service_module: Any,
                         tool_definitions: Dict[str, Dict]) -> None:
        """注册一个服务及其所有工具。

        Args:
            service_id: 服务标识（如 "filesystem"）
            service_module: 服务模块（包含 handle_tool_call 函数）
            tool_definitions: 工具定义字典
        """
        self._services[service_id] = service_module
        for tool_name, tool_def in tool_definitions.items():
            # 为每个工具定义创建一个 MCPTool，handler 委托给 service_module.handle_tool_call
            self._tools[tool_name] = MCPTool(
                name=tool_name,
                description=tool_def.get("description", ""),
                params_schema=tool_def.get("params_schema", {}),
                handler=self._make_service_handler(service_module, tool_name),
                permission=tool_def.get("permission", "public"),
                service_id=service_id,
            )

    def _make_service_handler(self, service_module: Any,
                              tool_name: str) -> Callable:
        """为服务模块创建工具调用 handler。"""
        async def handler(params: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
            return await service_module.handle_tool_call(tool_name, params, project_root)
        return handler

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取工具定义。"""
        return self._tools.get(name)

    def list_tools(self, permission: Optional[str] = None) -> List[Dict]:
        """列出所有工具（可选按权限过滤）。"""
        tools = []
        for name, tool in self._tools.items():
            if permission and tool.permission != permission and not tool.permission.startswith("role:"):
                if permission != "maintainer":
                    continue
            tools.append({
                "name": name,
                "description": tool.description,
                "params_schema": tool.params_schema,
                "permission": tool.permission,
                "service_id": tool.service_id,
            })
        return sorted(tools, key=lambda x: x["name"])

    def unregister_tool(self, name: str) -> bool:
        """注销工具。"""
        return self._tools.pop(name, None) is not None

    def unregister_service(self, service_id: str) -> List[str]:
        """注销服务及其所有工具。"""
        removed = []
        for name, tool in list(self._tools.items()):
            if tool.service_id == service_id:
                self._tools.pop(name)
                removed.append(name)
        self._services.pop(service_id, None)
        return removed

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def service_count(self) -> int:
        return len(self._services)


class MCPFrameworkPlugin(PluginInterface):
    """MCP 服务框架插件。

    作为系统唯一的工具注册中心，统一管理所有工具。
    """

    def __init__(self):
        self.name = "mcp_framework"
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._registry = MCPRegistry()
        self._project_root: Path = Path(__file__).parent.parent.parent.parent.parent
        self._services_dir: Path = Path(__file__).parent / "services"
        self._running = False

        # 审计日志
        self._call_log: List[Dict] = []
        self._max_log_size = 1000

    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config.get("mcp_framework", {})

    async def start(self) -> None:
        """启动 MCP Framework，注册内置服务。"""
        self._running = True

        # 注册所有内置服务
        await self._register_builtin_services()

        print(f"[MCP] 🔧 已注册 {self._registry.tool_count} 个工具 "
              f"（{self._registry.service_count} 个服务）")

    async def _register_builtin_services(self) -> None:
        """扫描 services/ 目录并注册所有内置服务。"""
        services_dir = self._services_dir
        if not services_dir.exists():
            print(f"[MCP] ⚠️ services 目录不存在: {services_dir}")
            return

        for entry in sorted(services_dir.iterdir()):
            if entry.is_file() and entry.suffix == ".py" and not entry.name.startswith("_"):
                service_id = entry.stem
                try:
                    # 动态导入服务模块
                    spec = importlib.util.spec_from_file_location(
                        f"mcp_service_{service_id}", str(entry)
                    )
                    if not spec or not spec.loader:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # 检查是否有 TOOL_DEFINITIONS 和 handle_tool_call
                    if not hasattr(module, "TOOL_DEFINITIONS"):
                        print(f"[MCP]   ⏭️  {service_id}: 无 TOOL_DEFINITIONS，跳过")
                        continue
                    if not hasattr(module, "handle_tool_call"):
                        print(f"[MCP]   ⏭️  {service_id}: 无 handle_tool_call，跳过")
                        continue

                    # 注册服务
                    self._registry.register_service(
                        service_id=service_id,
                        service_module=module,
                        tool_definitions=module.TOOL_DEFINITIONS,
                    )
                    tool_names = list(module.TOOL_DEFINITIONS.keys())
                    print(f"[MCP]   ✅ {service_id}: {', '.join(tool_names)}")
                except Exception as e:
                    print(f"[MCP]   ❌ {service_id} 注册失败: {e}")

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        self._running = False

    async def cleanup(self) -> None:
        self._registry._tools.clear()
        self._registry._services.clear()
        self._call_log.clear()

    def register_events(self) -> None:
        """注册事件订阅。"""
        self._event_bus.subscribe("tool.call", self._on_tool_call)
        self._event_bus.subscribe("system.config_changed", self._on_config_changed)

    async def _on_tool_call(self, event: Event) -> None:
        """处理 tool.call 事件 — MCP Server 核心路由。

        流程：
        1. 查找工具定义
        2. 参数校验（JSON Schema）
        3. 权限检查
        4. 执行工具
        5. 返回结果
        6. 记录审计日志
        """
        tool_name = event.payload.get("tool_name", "")
        params = event.payload.get("params", {})
        caller_role = event.payload.get("caller_role", "unknown")
        request_id = event.payload.get("request_id", "")
        task_id = event.payload.get("task_id", "")

        # 1. 查找工具
        tool = self._registry.get_tool(tool_name)
        if not tool:
            await self._publish_error(
                tool_name, request_id, 4001,
                f"未知工具: {tool_name}", retryable=False
            )
            return

        # 2. 参数校验
        validation_error = tool.validate_params(params)
        if validation_error:
            await self._publish_error(
                tool_name, request_id, 4002,
                validation_error, retryable=False
            )
            return

        # 3. 权限检查（TODO: 集成 security_service）
        if tool.permission == "maintainer" and caller_role not in ("suri", "maintainer"):
            await self._publish_error(
                tool_name, request_id, 4003,
                f"权限不足: {tool_name} 需要 maintainer 权限",
                retryable=False
            )
            return

        # 4. 执行工具
        start_time = datetime.now(timezone.utc)
        try:
            result = await tool.handler(params, self._project_root)
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )

            # 5. 返回结果
            if self._event_bus:
                await self._event_bus.publish(Event(
                    event_type="tool.result",
                    source="mcp_framework",
                    target=event.source,
                    payload={
                        "tool_name": tool_name,
                        "result": result,
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                    },
                    priority=Priority.NORMAL,
                ))

            # 6. 审计日志
            self._log_call(tool_name, params, result, duration_ms,
                          caller_role, task_id, success=True)

        except Exception as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            await self._publish_error(
                tool_name, request_id, 5000, str(e), retryable=True
            )
            self._log_call(tool_name, params, {"error": str(e)}, duration_ms,
                          caller_role, task_id, success=False)

    async def _publish_error(self, tool_name: str, request_id: str,
                             error_code: int, error_message: str,
                             retryable: bool = False) -> None:
        """发布工具调用错误。"""
        if self._event_bus:
            await self._event_bus.publish(Event(
                event_type="tool.error",
                source="mcp_framework",
                payload={
                    "tool_name": tool_name,
                    "request_id": request_id,
                    "error_code": error_code,
                    "error_message": error_message,
                    "retryable": retryable,
                },
                priority=Priority.HIGH,
            ))

    def _log_call(self, tool_name: str, params: Dict, result: Any,
                  duration_ms: int, caller_role: str, task_id: str,
                  success: bool) -> None:
        """记录工具调用审计日志。"""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "params": params,
            "duration_ms": duration_ms,
            "caller_role": caller_role,
            "task_id": task_id,
            "success": success,
        }
        self._call_log.append(log_entry)
        if len(self._call_log) > self._max_log_size:
            self._call_log.pop(0)

    async def _on_config_changed(self, event: Event) -> None:
        """配置变更后重新注册服务。"""
        # 重新加载配置
        self._config = event.payload.get("config", {}).get("mcp_framework", {})
        # 重新注册内置服务
        self._registry._tools.clear()
        self._registry._services.clear()
        await self._register_builtin_services()

    # ── 公开 API ──

    def list_tools(self, permission: Optional[str] = None) -> List[Dict]:
        """列出可用工具。"""
        return self._registry.list_tools(permission)

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取工具定义。"""
        return self._registry.get_tool(name)

    def register_external_tool(self, name: str, description: str,
                               params_schema: Dict, handler: Callable,
                               permission: str = "public") -> None:
        """注册外部工具（由其他插件或远程 Server 调用）。"""
        tool = MCPTool(name, description, params_schema, handler,
                      permission=permission, service_id="external")
        self._registry.register_tool(tool)

    def unregister_external_tool(self, name: str) -> bool:
        """注销外部工具。"""
        return self._registry.unregister_tool(name)

    @property
    def tool_count(self) -> int:
        return self._registry.tool_count

    @property
    def call_log(self) -> List[Dict]:
        return list(self._call_log[-50:])  # 返回最近 50 条