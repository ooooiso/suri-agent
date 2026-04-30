"""
文件所有权规则

职责：
- 定义每个路径的控制角色
- 校验角色是否有权操作目标文件
- 跨角色操作需授权验证
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from rules.base import BaseRule


class FileOwnershipRule(BaseRule):
    """文件所有权映射与校验"""
    
    rule_id = "file_ownership"
    name = "文件所有权映射"
    owner = "security_admin"
    
    # 路径 → 控制角色
    _ownership: Dict[str, str] = {
        "group/<role>/": "role_self",
        "group/<role>/memories/": "role_self",
        "group/<role>/skills/": "role_self",
        "group/<role>/reference/": "role_self",
        "group/_archived/": "file_admin",
        "skills/": "suri",
        "suri-agent/tools/": "suri-dev",
        "suri-agent/tools/tool_registry.md": "suri-dev",
        "suri-agent/rules/": "security_admin",
        "suri-agent/": "suri-dev",
        "suri-agent/access/": "suri-dev",
        "suri-agent/mcp/base.py": "suri-dev",
        "suri-agent/mcp/registry.py": "suri-dev",
        "suri-agent/mcp/services/": "service_dev",
        "suri-agent/hooks/": "ops_admin",
        "config.yaml": "suri-dev",
        ".env": "suri-dev",
        "group/central/suri/suri.md": "suri-dev",
        "state.db": "suri",
        "resources/logs/": "file_admin",
        "resources/sessions/": "suri",
        "resources/memories/": "suri",
        "resources/cache/": "file_admin",
        "resources/temp/": "file_admin",
        "cron/": "ops_admin",
    }
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
    
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
        """获取路径的控制角色"""
        path = path.lstrip("/")
        
        # 精确匹配
        if path in self._ownership:
            return self._ownership[path]
        
        # 前缀匹配（取最长匹配）
        matches = []
        for pattern, owner in self._ownership.items():
            if pattern.endswith("/") and path.startswith(pattern.rstrip("/")):
                matches.append((len(pattern), owner))
            elif pattern.endswith("/<role>/") and "/" in path:
                prefix = pattern.replace("<role>/", "")
                if path.startswith(prefix):
                    matches.append((len(pattern), "role_self"))
        
        if matches:
            matches.sort(reverse=True)
            return matches[0][1]
        
        return None
    
    def can_modify(self, role_id: str, path: str) -> bool:
        """检查角色是否有权修改目标文件"""
        owner = self.get_owner(path)
        if owner is None:
            return False
        
        # 角色自身管理的文件
        if owner == "role_self":
            # 检查路径是否属于该角色
            parts = path.strip("/").split("/")
            if len(parts) >= 2 and parts[1] == role_id:
                return True
            return False
        
        # suri-hr 可管理所有角色目录
        if role_id == "suri-hr" and path.startswith("group/"):
            return True
        
        # 精确匹配控制角色
        return owner == role_id
    
    def list_monitored_paths(self) -> List[str]:
        """返回所有受监控的路径"""
        return list(self._ownership.keys())
