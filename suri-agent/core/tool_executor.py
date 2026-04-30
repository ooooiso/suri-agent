"""
工具服务

职责：
- 读取 tools/tool_registry.md
- 加载并执行公共工具（tools/<tool_id>/scripts/）
- 为角色技能提供工具调用接口
- 输入参数校验、执行隔离、输出标准化

原则：工具本身是外部内容，主程序只提供加载和执行能力。
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from infrastructure.config import ConfigService


class ToolService:
    """
    工具执行中心
    
    流程：
    1. 技能声明依赖工具（通过 tool_id）
    2. 框架根据 tool_registry.md 鉴权
    3. 加载 tools/<tool_id>/scripts/ 中的脚本
    4. 执行并返回标准化结果
    """
    
    def __init__(self, project_root: Path, config: ConfigService):
        self.project_root = project_root
        self.config = config
        self._tool_cache: Dict[str, Any] = {}  # 已加载的工具模块
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有已注册工具"""
        registry = self.config.get_file('tools/tool_registry.md')
        if not registry:
            return []
        # TODO: 解析 Markdown 表格提取工具列表
        return []
    
    def get_tool_info(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """获取工具描述"""
        entry = self.config.get_tool(tool_id)
        if not entry:
            return None
        return {
            'tool_id': tool_id,
            'meta': entry.meta,
            'description': entry.body[:500]
        }
    
    def execute(self, tool_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行指定工具
        
        Args:
            tool_id: 工具 ID
            params: 输入参数
            
        Returns:
            {'success': bool, 'result': Any, 'error': str}
        """
        # 1. 检查工具是否注册
        info = self.get_tool_info(tool_id)
        if not info:
            return {'success': False, 'result': None, 'error': f'工具 {tool_id} 未注册'}
        
        # 2. 加载工具脚本
        tool_module = self._load_tool_module(tool_id)
        if not tool_module:
            return {'success': False, 'result': None, 'error': f'工具 {tool_id} 加载失败'}
        
        # 3. 执行（带异常捕获）
        try:
            # 约定：每个工具模块提供 execute(params) -> dict 函数
            if hasattr(tool_module, 'execute'):
                result = tool_module.execute(params)
                return {'success': True, 'result': result, 'error': ''}
            else:
                return {'success': False, 'result': None, 'error': f'工具 {tool_id} 缺少 execute 函数'}
        except Exception as e:
            return {'success': False, 'result': None, 'error': str(e)}
    
    def _load_tool_module(self, tool_id: str) -> Optional[Any]:
        """动态加载工具模块"""
        if tool_id in self._tool_cache:
            return self._tool_cache[tool_id]
        
        script_dir = self.project_root / 'tools' / tool_id / 'scripts'
        if not script_dir.exists():
            return None
        
        # 查找入口脚本（优先 __init__.py，然后是 tool_id.py）
        entry_candidates = [
            script_dir / '__init__.py',
            script_dir / f'{tool_id}.py',
            script_dir / 'main.py',
        ]
        
        for entry in entry_candidates:
            if entry.exists():
                spec = importlib.util.spec_from_file_location(tool_id, entry)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._tool_cache[tool_id] = module
                    return module
        
        return None
    
    def validate_params(self, tool_id: str, params: Dict[str, Any]) -> tuple[bool, str]:
        """
        校验工具参数
        
        根据 tool.md 中定义的参数表进行校验。
        参数 params 预留用于未来扩展参数校验逻辑。
        """
        info = self.get_tool_info(tool_id)
        if not info:
            return False, f'工具 {tool_id} 不存在'
        
        # TODO: 从 tool.md 解析参数定义，进行类型/必填校验
        return True, "参数校验通过"
