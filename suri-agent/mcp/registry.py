"""
MCP 注册中心

职责：
- 管理所有已注册的 MCP 服务
- 为角色动态匹配和绑定 MCP 工具
- 将 MCP 能力注入角色上下文

原则：核心框架，受保护不可外部编辑。
具体服务在 mcp/services/ 下自增长。
"""

from typing import Dict, Any, List, Optional
from .base import BaseMCPService, MCPServer, MCPTool


class MCPRegistry:
    """
    MCP 服务注册中心
    
    运行时动态加载 mcp/services/ 下的所有服务模块。
    """
    
    def __init__(self, services_dir: Optional[Any] = None):
        self._services: Dict[str, BaseMCPService] = {}
        self._tools: Dict[str, MCPTool] = {}
        self._role_bindings: Dict[str, List[str]] = {}  # role_id -> [tool_id]
    
    def register(self, service: BaseMCPService) -> None:
        """注册 MCP 服务"""
        self._services[service.server_id] = service
        
        # 自动发现工具
        for tool in service.discover_tools():
            self._tools[tool.tool_id] = tool
        
        print(f"[MCPRegistry] 注册服务: {service.name} ({service.server_id})")
    
    def unregister(self, server_id: str) -> None:
        """注销 MCP 服务"""
        if server_id in self._services:
            service = self._services[server_id]
            for tool_id in list(self._tools.keys()):
                if self._tools[tool_id].server_id == server_id:
                    del self._tools[tool_id]
            del self._services[server_id]
            print(f"[MCPRegistry] 注销服务: {server_id}")
    
    def bind_tool_to_role(self, role_id: str, tool_id: str) -> bool:
        """将 MCP 工具绑定到角色"""
        if tool_id not in self._tools:
            return False
        
        if role_id not in self._role_bindings:
            self._role_bindings[role_id] = []
        
        if tool_id not in self._role_bindings[role_id]:
            self._role_bindings[role_id].append(tool_id)
        
        return True
    
    def get_role_tools(self, role_id: str) -> List[MCPTool]:
        """获取角色绑定的所有 MCP 工具"""
        tool_ids = self._role_bindings.get(role_id, [])
        return [self._tools[tid] for tid in tool_ids if tid in self._tools]
    
    def execute_tool(self, tool_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行 MCP 工具"""
        tool = self._tools.get(tool_id)
        if not tool:
            return {'success': False, 'result': None, 'error': f'MCP 工具 {tool_id} 不存在'}
        
        service = self._services.get(tool.server_id)
        if not service:
            return {'success': False, 'result': None, 'error': f'MCP 服务 {tool.server_id} 不可用'}
        
        return service.execute(tool_id, params)
    
    def auto_enhance_role(self, role_id: str, task_requirement: str) -> List[MCPTool]:
        """
        根据任务需求，自动为角色推荐并绑定合适的 MCP 工具
        
        自动补足 skill 的核心入口。
        """
        suggested = []
        for tool in self._tools.values():
            # 简单关键词匹配
            keywords = task_requirement.lower().split()
            tool_desc = tool.description.lower()
            if any(kw in tool_desc for kw in keywords):
                suggested.append(tool)
        
        for tool in suggested[:3]:
            self.bind_tool_to_role(role_id, tool.tool_id)
        
        return suggested
    
    def inject_context(self, role_id: str, base_context: str) -> str:
        """将 MCP 能力说明注入角色上下文"""
        tools = self.get_role_tools(role_id)
        if not tools:
            return base_context
        
        mcp_section = "\n\n## 你的扩展能力（MCP）\n\n"
        for tool in tools:
            mcp_section += f"- **{tool.name}** ({tool.tool_id}): {tool.description}\n"
        
        return base_context + mcp_section
    
    def list_services(self) -> List[MCPServer]:
        """列出所有已注册服务"""
        return [s.get_server_info() for s in self._services.values()]
    
    def list_tools(self) -> List[MCPTool]:
        """列出所有可用工具"""
        return list(self._tools.values())
