"""
工具服务

关联文档: suri-agent/core/core.md, suri-agent/tools/tools.md

职责：
- 读取 tools/tool_registry.json（业务配置）
- 加载并执行公共工具（tools/<tool_id>/scripts/）
- 为角色技能提供工具调用接口
- 输入参数校验、执行隔离、输出标准化

原则：工具本身是外部内容，主程序只提供加载和执行能力。
"""

import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, List
from infrastructure.config import ConfigService


class ToolService:
    """
    工具执行中心
    
    流程：
    1. 技能声明依赖工具（通过 tool_id）
    2. 框架根据 tool_registry.json 鉴权
    3. 加载 tools/<tool_id>/scripts/ 中的脚本
    4. 执行并返回标准化结果
    """
    
    def __init__(self, project_root: Path, config: ConfigService):
        self.project_root = project_root
        self.config = config
        self._tool_cache: Dict[str, Any] = {}  # 已加载的工具模块
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有已注册工具（从 JSON 读取）"""
        import json
        registry_path = self.project_root / 'suri-agent' / 'tools' / 'tool_registry.json'
        if not registry_path.exists():
            return []
        try:
            data = json.loads(registry_path.read_text(encoding='utf-8'))
            return data.get('tools', [])
        except Exception:
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
    
    def execute(self, tool_id: str, params: Dict[str, Any], 
                caller_role: str = None) -> Dict[str, Any]:
        """
        执行指定工具
        
        Args:
            tool_id: 工具 ID
            params: 输入参数
            caller_role: 调用者角色 ID（用于权限检查和调用记录）
            
        Returns:
            {'success': bool, 'result': Any, 'error': str}
        """
        # 1. 检查工具是否注册
        info = self.get_tool_info(tool_id)
        if not info:
            return {'success': False, 'result': None, 'error': f'工具 {tool_id} 未注册'}
        
        # 2. 权限检查（如有调用者角色）
        if caller_role and not self._can_use(caller_role, tool_id):
            return {
                'success': False,
                'result': None,
                'error': f'角色 [{caller_role}] 无权使用工具 [{tool_id}]。'
                         f'如需此工具，请向平台管理员申请授权。'
            }
        
        # 3. 加载工具脚本
        tool_module = self._load_tool_module(tool_id)
        if not tool_module:
            return {'success': False, 'result': None, 'error': f'工具 {tool_id} 加载失败'}
        
        # 4. 执行（带异常捕获）
        try:
            # 约定：每个工具模块提供 execute(params) -> dict 函数
            if hasattr(tool_module, 'execute'):
                result = tool_module.execute(params)
                # 记录工具调用历史（供技能复盘使用）
                self._record_tool_call(caller_role, tool_id, params, result.get('success', True))
                return {'success': True, 'result': result, 'error': ''}
            else:
                return {'success': False, 'result': None, 'error': f'工具 {tool_id} 缺少 execute 函数'}
        except Exception as e:
            self._record_tool_call(caller_role, tool_id, params, False)
            return {'success': False, 'result': None, 'error': str(e)}
    
    def _record_tool_call(self, caller_role: Optional[str], tool_id: str, 
                          params: Dict[str, Any], success: bool) -> None:
        """
        记录工具调用历史
        
        供角色复盘时分析工具使用模式，形成技能。
        记录写入 logs/tool_calls/ 目录下的日期日志文件。
        """
        from datetime import datetime
        
        if not caller_role:
            return
        
        log_dir = self.project_root / "logs" / "tool_calls"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"tool_calls_{today}.log"
        
        now = datetime.now().isoformat()
        line = (
            f"[{now}] role={caller_role} tool={tool_id} "
            f"params={str(params)[:200]} success={success}\n"
        )
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
    
    def _can_use(self, role_id: str, tool_id: str) -> bool:
        """
        检查角色是否有权使用指定工具
        
        权限判定策略（优先级从高到低）：
        1. 角色 Soul 显式授权：tools 字段包含该工具 → 允许
        2. 工具注册表默认权限：public / maintainer / 特定角色 → 自动推导
        3. 都不匹配 → 拒绝
        """
        # 1. 角色 Soul 显式授权（白名单覆盖）
        soul = self.config.get_role_soul(role_id)
        if soul:
            allowed_tools = soul.meta.get('tools', [])
            if tool_id in allowed_tools:
                return True
        
        # 2. 从 tool_registry.json 读取默认权限
        permission = self._get_tool_permission(tool_id)
        if permission == 'public':
            return True
        if permission == 'maintainer' and soul and soul.meta.get('type') == 'maintainer':
            return True
        if permission == role_id:
            return True
        
        return False
    
    def _get_tool_permission(self, tool_id: str) -> str:
        """从 tool_registry.json 读取工具的默认权限级别"""
        registry_path = self.project_root / 'suri-agent' / 'tools' / 'tool_registry.json'
        if not registry_path.exists():
            return ''
        
        try:
            import json
            data = json.loads(registry_path.read_text(encoding='utf-8'))
            for tool in data.get('tools', []):
                if tool.get('tool_id') == tool_id:
                    return tool.get('permission', '')
        except Exception:
            pass
        return ''
    
    def _load_tool_module(self, tool_id: str) -> Optional[Any]:
        """动态加载工具模块"""
        if tool_id in self._tool_cache:
            return self._tool_cache[tool_id]
        
        script_dir = self.project_root / 'suri-agent' / 'tools' / tool_id / 'scripts'
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
        
        从 tool.md 中定义的 YAML frontmatter 解析参数定义，进行类型/必填校验。
        """
        info = self.get_tool_info(tool_id)
        if not info:
            return False, f'工具 {tool_id} 不存在'
        
        # 从 tool.md 解析参数定义
        tool_md = self.project_root / 'suri-agent' / 'tools' / tool_id / f'{tool_id}.md'
        if not tool_md.exists():
            return True, "参数校验通过（无参数定义文件）"
        
        content = tool_md.read_text(encoding='utf-8')
        param_defs = self._parse_param_defs(content)
        if not param_defs:
            return True, "参数校验通过（无参数定义）"
        
        for name, definition in param_defs.items():
            if definition.get('required', False) and name not in params:
                return False, f'缺少必填参数: {name}'
            
            if name in params:
                expected_type = definition.get('type', 'string')
                if not self._check_type(params[name], expected_type):
                    return False, f'参数 {name} 类型错误，期望 {expected_type}，实际 {type(params[name]).__name__}'
        
        return True, "参数校验通过"
    
    def _parse_param_defs(self, content: str) -> Dict[str, Dict]:
        """从 tool.md 内容解析参数定义（查找 frontmatter 中的 params 字段）"""
        param_defs = {}
        if not content.startswith('---'):
            return param_defs
        
        end = content.find('---', 3)
        if end == -1:
            return param_defs
        
        try:
            import yaml
            meta = yaml.safe_load(content[3:end]) or {}
            params = meta.get('params', [])
            for p in params:
                if isinstance(p, dict) and 'name' in p:
                    param_defs[p['name']] = p
        except Exception:
            pass
        
        return param_defs
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """类型检查"""
        type_map = {
            'string': str,
            'str': str,
            'int': int,
            'float': (int, float),
            'number': (int, float),
            'bool': bool,
            'boolean': bool,
            'list': list,
            'array': list,
            'dict': dict,
            'object': dict,
        }
        expected = type_map.get(expected_type, str)
        return isinstance(value, expected)
