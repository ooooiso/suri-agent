"""
配置加载服务

职责：
- 扫描并解析项目中的外部配置（角色、技能、流程等 .md 文件）
- 规则已迁移为代码（suri-agent/rules/），不再通过本服务加载
- 提供配置查询 API（按 role_id、process_id、skill_id 等查找）
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from infrastructure.utils import load_markdown_file, scan_markdown_files


@dataclass
class ConfigEntry:
    """单个配置条目"""
    rel_path: str
    meta: Dict[str, Any]
    body: str
    abs_path: Path


class ConfigService:
    """
    配置中心
    
    加载路径：
    - wiki/      平台配置（流程、通信、模型、记忆）
    - group/         角色实例
    - skills/        suri 技能库
    - suri-agent/tools/  公共工具
    
    规则已代码化，不再通过 .md 加载。规则查询请使用 rules.RuleEngine。
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._registry: Dict[str, ConfigEntry] = {}
        self._indexes: Dict[str, Dict[str, ConfigEntry]] = {
            'role_id': {},
            'process_id': {},
            'skill_id': {},
            'tool_id': {},
            'department_id': {},
        }
    
    def load_all(self) -> None:
        """加载所有外部配置到内存"""
        dirs = ["group", "skills", "suri-agent/tools"]
        for dirname in dirs:
            path = self.project_root / dirname
            if not path.exists():
                continue
            files = scan_markdown_files(path)
            for rel_path, (meta, body) in files.items():
                if '_archived' in rel_path:
                    continue
                full_rel = f"{dirname}/{rel_path}"
                entry = ConfigEntry(
                    rel_path=full_rel,
                    meta=meta,
                    body=body,
                    abs_path=path / rel_path
                )
                self._registry[full_rel] = entry
                self._index_entry(entry)
        
        print(f"[ConfigService] 已加载 {len(self._registry)} 个配置文件")
    
    def _index_entry(self, entry: ConfigEntry) -> None:
        """将条目加入索引"""
        meta = entry.meta
        for key in ['role_id', 'process_id', 'skill_id', 'tool_id']:
            value = meta.get(key)
            if value:
                self._indexes[key][value] = entry
        
        # 部门索引特殊处理（从 function_index.md 解析）
        if entry.rel_path.endswith('group_function.md'):
            self._index_departments(entry)
    
    def _index_departments(self, entry: ConfigEntry) -> None:
        """解析 group_function.md 中的部门信息"""
        departments = entry.meta.get('departments', [])
        for dept in departments:
            dept_id = dept.get('id')
            if dept_id:
                self._indexes['department_id'][dept_id] = entry
    
    # ---- 查询接口 ----
    
    def get_role_soul(self, role_id: str) -> Optional[ConfigEntry]:
        """获取角色 Soul 文件"""
        if role_id == 'suri':
            soul_path = self.project_root / 'group/central/suri/suri.md'
            if soul_path.exists():
                meta, body = load_markdown_file(soul_path)
                return ConfigEntry(
                    rel_path='group/central/suri/suri.md',
                    meta=meta, body=body, abs_path=soul_path
                )
            return None
        
        entry = self._indexes['role_id'].get(role_id)
        if entry:
            return entry
        
        # 兼容：从 group/ 下查找
        fallback_path = self.project_root / 'group' / role_id / f"{role_id}.md"
        if fallback_path.exists():
            meta, body = load_markdown_file(fallback_path)
            return ConfigEntry(
                rel_path=f"group/{role_id}/{role_id}.md",
                meta=meta, body=body, abs_path=fallback_path
            )
        return None
    
    def get_process(self, process_id: str) -> Optional[ConfigEntry]:
        """获取流程文件"""
        return self._indexes['process_id'].get(process_id)
    
    def get_skill(self, skill_id: str) -> Optional[ConfigEntry]:
        """获取技能定义文件"""
        return self._indexes['skill_id'].get(skill_id)
    
    def get_tool(self, tool_id: str) -> Optional[ConfigEntry]:
        """获取工具定义文件"""
        return self._indexes['tool_id'].get(tool_id)
    
    def get_function_index(self) -> Optional[ConfigEntry]:
        """获取部门职能索引"""
        return self._registry.get('group/group_function.md')
    
    def get_model_pool(self) -> Optional[ConfigEntry]:
        """获取模型池配置"""
        return self._registry.get('wiki/models/model_pool.md')
    
    def get_memory_config(self) -> Optional[ConfigEntry]:
        """获取记忆策略配置"""
        return self._registry.get('wiki/memory/memory_config.md')
    
    def get_telegram_config(self) -> Optional[ConfigEntry]:
        """获取 Telegram 配置"""
        return self._registry.get('wiki/communication/telegram.md')
    
    def list_roles(self) -> List[str]:
        """列出所有角色 ID"""
        return list(self._indexes['role_id'].keys())
    
    def list_skills(self) -> List[str]:
        """列出所有技能 ID"""
        return list(self._indexes['skill_id'].keys())
    
    def list_tools(self) -> List[str]:
        """列出所有工具 ID"""
        return list(self._indexes['tool_id'].keys())
    
    def get_file(self, rel_path: str) -> Optional[ConfigEntry]:
        """按相对路径获取任意配置"""
        return self._registry.get(rel_path)
