"""
MCP 服务基类

所有 MCP 服务必须继承 MCPServer，实现标准接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class MCPTool:
    tool_id: str
    server_id: str
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class MCPServer:
    server_id: str
    name: str
    endpoint: str
    capabilities: List[str]
    status: str  # active / inactive


class BaseMCPService(ABC):
    """
    MCP 服务基类
    
    所有具体 MCP 服务（文件系统、网络搜索、代码执行等）必须实现此接口。
    """
    
    def __init__(self, server_id: str, name: str, endpoint: str = ''):
        self.server_id = server_id
        self.name = name
        self.endpoint = endpoint
        self.status = 'active'
        self._tools: Dict[str, MCPTool] = {}
    
    @abstractmethod
    def discover_tools(self) -> List[MCPTool]:
        """发现本服务提供的所有工具"""
        pass
    
    @abstractmethod
    def execute(self, tool_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定工具"""
        pass
    
    def get_server_info(self) -> MCPServer:
        """获取服务器信息"""
        return MCPServer(
            server_id=self.server_id,
            name=self.name,
            endpoint=self.endpoint,
            capabilities=list(self._tools.keys()),
            status=self.status
        )
    
    def get_tool(self, tool_id: str) -> Optional[MCPTool]:
        """获取工具定义"""
        return self._tools.get(tool_id)
