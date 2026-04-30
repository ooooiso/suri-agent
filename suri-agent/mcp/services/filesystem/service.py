"""
MCP 文件系统服务

提供跨角色的文件操作能力：
- 读取任意允许路径的文件
- 搜索文件内容
- 获取目录结构

此服务可被任何角色调用，用于补足文件处理能力。
"""

from pathlib import Path
from typing import Dict, Any, List
from mcp.base import BaseMCPService, MCPTool


class FilesystemMCPService(BaseMCPService):
    """文件系统 MCP 服务"""
    
    def __init__(self, project_root: Path):
        super().__init__('filesystem', '文件系统', '')
        self.project_root = project_root
        self._tools = {
            'fs_read': MCPTool('fs_read', 'filesystem', '读取文件', '读取指定路径的文件内容', {'path': 'string'}),
            'fs_list': MCPTool('fs_list', 'filesystem', '列出目录', '列出指定目录的内容', {'path': 'string'}),
            'fs_search': MCPTool('fs_search', 'filesystem', '搜索文件', '按名称搜索文件', {'pattern': 'string'}),
        }
    
    def discover_tools(self) -> List[MCPTool]:
        return list(self._tools.values())
    
    def execute(self, tool_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool_id == 'fs_read':
            return self._do_read(params.get('path', ''))
        elif tool_id == 'fs_list':
            return self._do_list(params.get('path', '.'))
        elif tool_id == 'fs_search':
            return self._do_search(params.get('pattern', ''))
        return {'success': False, 'error': f'未知工具: {tool_id}'}
    
    def _do_read(self, rel_path: str) -> Dict[str, Any]:
        path = self.project_root / rel_path
        if not path.exists():
            return {'success': False, 'error': '文件不存在'}
        return {'success': True, 'content': path.read_text(encoding='utf-8')}
    
    def _do_list(self, rel_path: str) -> Dict[str, Any]:
        path = self.project_root / rel_path
        if not path.is_dir():
            return {'success': False, 'error': '不是目录'}
        items = [{'name': p.name, 'type': 'dir' if p.is_dir() else 'file'} for p in path.iterdir()]
        return {'success': True, 'items': items}
    
    def _do_search(self, pattern: str) -> Dict[str, Any]:
        matches = list(self.project_root.rglob(pattern))
        return {'success': True, 'matches': [str(p.relative_to(self.project_root)) for p in matches[:20]]}
