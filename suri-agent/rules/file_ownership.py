"""
文件所有权规则

关联文档: suri-agent/rules/rules.md

职责：
- 定义每个路径的控制角色类型
- 校验角色是否有权操作目标文件
- 跨角色操作需授权验证

V2.0 改造说明：
- 所有权映射绑定到 role_type（如 type:maintainer）而非具体 role_id
- 新增角色只需在 Soul 中声明 type，无需修改此文件
- 保留 _resolve_type_owner() 动态解析角色实例
"""

from pathlib import Path
from typing import Dict, List, Optional
from rules.base import BaseRule


class FileOwnershipRule(BaseRule):
    """文件所有权映射与校验"""
    
    rule_id = "file_ownership"
    name = "文件所有权映射"
    owner = "security_admin"
    
    # 路径 → 控制角色类型（或特殊标记）
    # 使用 "type:<role_type>" 格式绑定到角色类型，而非具体角色名
    _ownership: Dict[str, str] = {
        "group/<role>/": "role_self",
        "group/<role>/memories/": "role_self",
        "group/<role>/skills/": "role_self",
        "group/<role>/reference/": "role_self",
        "group/_archived/": "file_admin",
        "skills/": "type:scheduler",           # 调度者类型角色
        "suri-agent/tools/": "type:maintainer",  # 维护者类型角色
        "suri-agent/tools/tool_registry.json": "type:maintainer",
        "suri-agent/tools/tool_registry.md": "type:maintainer",
        "suri-agent/rules/": "security_admin",
        "suri-agent/": "type:maintainer",
        "suri-agent/access/": "type:maintainer",
        "suri-agent/mcp/base.py": "type:maintainer",
        "suri-agent/mcp/registry.py": "type:maintainer",
        "suri-agent/mcp/services/": "service_dev",
        "suri-agent/hooks/": "ops_admin",
        "config.yaml": "type:maintainer",
        ".env": "type:maintainer",
        # Soul 文件由 admin 专属管理（见 get_owner() 中的 Soul 文件检测逻辑）
        "state.db": "type:scheduler",
        "resources/logs/": "file_admin",
        "resources/sessions/": "type:scheduler",
        "resources/memories/": "type:scheduler",
        "resources/cache/": "file_admin",
        "resources/temp/": "file_admin",
        "cron/": "ops_admin",
    }
    
    # 需要特殊权限的角色类型（对 group/ 下所有路径有管理权）
    _ADMIN_TYPES = {"admin"}
    
    def __init__(self, project_root: Path, config=None):
        self.project_root = project_root
        self.config = config  # ConfigService，用于动态解析 type → role_id
    
    def _resolve_type_owner(self, owner_marker: str) -> Optional[str]:
        """
        将类型标记解析为具体角色 ID
        
        如 "type:maintainer" → 查询 ConfigService 返回当前 maintainer 角色
        """
        if not owner_marker.startswith("type:"):
            return owner_marker
        
        role_type = owner_marker.replace("type:", "")
        if self.config:
            roles = self.config.get_roles_by_type(role_type)
            if roles:
                return roles[0]  # 返回第一个匹配的角色
        
        # 无 config 时的硬编码回退（仅用于测试场景）
        fallback = {
            "maintainer": "suri_dev",
            "reviewer": "suri_review",
            "admin": "suri_hr",
            "specialist": "suri_stats",
            "scheduler": "suri",
        }
        return fallback.get(role_type, owner_marker)
    
    def _resolve_role_id(self, raw_role_id: str) -> str:
        """解析角色标识（支持别名兼容）"""
        if self.config:
            return self.config.resolve_role_id(raw_role_id)
        # 无 config 时的硬编码回退（仅用于测试场景）
        aliases = {
            'suri-dev': 'suri_dev',
            'suri-hr': 'suri_hr',
            'document-review': 'suri_review',
            'analyst': 'suri_stats',
        }
        return aliases.get(raw_role_id, raw_role_id)
    
    def _is_admin_type(self, role_id: str) -> bool:
        """检查角色是否为 admin 类型（对 group/ 有管理权限）"""
        if self.config:
            role_type = self.config.get_role_type(role_id)
            return role_type in self._ADMIN_TYPES
        # 硬编码回退
        return role_id in ("suri_hr", "suri-hr")
    
    def validate(self, context: Dict) -> bool:
        role_id = context.get("role_id")
        target_path = context.get("target_path")
        if not role_id or not target_path:
            return False
        return self.can_modify(role_id, target_path)
    
    def execute(self, context: Dict) -> Dict:
        role_id = context.get("role_id")
        target_path = context.get("target_path")
        return {
            "allowed": self.can_modify(role_id, target_path),
            "owner": self.get_owner(target_path),
            "role_id": role_id,
            "target_path": target_path,
        }
    
    def get_owner(self, path: str) -> Optional[str]:
        """获取路径的控制角色（返回具体角色 ID）"""
        path = path.lstrip("/")
        
        # 精确匹配
        if path in self._ownership:
            return self._resolve_type_owner(self._ownership[path])
        
        # Soul 文件专属规则：group/<dept>/<role>/<role>.md 由 admin 管理
        # 角色定义（Soul）只有 hr 可以修改
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "group" and path.endswith(".md"):
            # 格式：group/<dept>/<role>/<role>.md
            if len(parts) == 4 and parts[3] == f"{parts[2]}.md":
                return self._resolve_type_owner("type:admin")
            # 兼容旧格式：group/<role>/<role>.md
            if len(parts) == 3 and parts[2] == f"{parts[1]}.md":
                return self._resolve_type_owner("type:admin")
        
        # 前缀匹配（取最长匹配）
        matches = []
        for pattern, owner in self._ownership.items():
            if pattern.endswith("/") and path.startswith(pattern.rstrip("/")):
                resolved = self._resolve_type_owner(owner)
                matches.append((len(pattern), resolved))
            elif pattern.endswith("/<role>/") and "/" in path:
                prefix = pattern.replace("<role>/", "")
                if path.startswith(prefix):
                    matches.append((len(pattern), "role_self"))
        
        if matches:
            matches.sort(reverse=True)
            return matches[0][1]
        
        return None
    
    def can_modify(self, role_id: str, path: str) -> bool:
        """检查角色是否有权修改目标文件（支持别名自动解析）"""
        # V2.0: 统一解析角色标识（兼容旧名如 'suri-dev'）
        resolved_role = self._resolve_role_id(role_id)
        
        owner = self.get_owner(path)
        if owner is None:
            return False
        
        # admin 类型角色可管理所有角色目录（优先级最高）
        if self._is_admin_type(resolved_role) and path.startswith("group/"):
            return True
        
        # 角色自身管理的文件
        if owner == "role_self":
            # 检查路径是否属于该角色（支持 group/<dept>/<role>/ 格式）
            parts = path.strip("/").split("/")
            # parts = ['group', '<dept>', '<role>', ...]
            if len(parts) >= 3:
                path_role = self._resolve_role_id(parts[2])
                if path_role == resolved_role:
                    return True
            # 兼容旧格式 group/<role>/（无部门层）
            if len(parts) >= 2:
                path_role = self._resolve_role_id(parts[1])
                if path_role == resolved_role:
                    return True
            return False
        
        # 精确匹配控制角色（比较解析后的名称）
        return owner == resolved_role
    
    def list_monitored_paths(self) -> List[str]:
        """返回所有受监控的路径"""
        return list(self._ownership.keys())
