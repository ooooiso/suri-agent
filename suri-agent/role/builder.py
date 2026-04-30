"""
角色搭建规则执行器

职责：
- 执行角色创建规则
- 验证角色 Soul 文件格式
- 初始化角色目录结构
- 角色能力分析
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional


class RoleBuilder:
    """角色搭建规则执行器"""
    
    ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
    
    def create_role(self, role_id: str, name: str, department: str = "central",
                   role_type: str = "member") -> Dict[str, Any]:
        """
        创建新角色，初始化完整目录结构
        
        Args:
            role_id: 角色唯一标识（小写+下划线）
            name: 角色显示名称
            department: 所属部门
            role_type: 角色类型
            
        Returns:
            创建结果
        """
        if not self._validate_role_id(role_id):
            return {
                "success": False,
                "error": f"无效的角色 ID: {role_id}，必须为 lowercase + underscore",
            }
        
        role_dir = self.project_root / "group" / department / role_id
        
        if role_dir.exists():
            return {"success": False, "error": f"角色 {role_id} 已存在"}
        
        # 创建目录结构
        (role_dir / "memories").mkdir(parents=True)
        (role_dir / "reference").mkdir(parents=True)
        (role_dir / "skills").mkdir(parents=True)
        
        # 创建 Soul 文件
        soul_content = self._generate_soul(role_id, name, department, role_type)
        (role_dir / f"{role_id}.md").write_text(soul_content, encoding="utf-8")
        
        # 创建文件权限地图
        (role_dir / "reference" / "files_i_use.md").write_text(
            f"# {role_id} 的文件权限地图\n\n| 路径 | 权限 | 说明 |\n|------|------|------|\n",
            encoding="utf-8"
        )
        
        # 创建技能索引
        (role_dir / "skills" / "skills.md").write_text(
            f"---\nowner: {role_id}\n---\n\n# {name} 的技能索引\n\n| 技能 ID | 路径 | 状态 |\n|---------|------|------|\n",
            encoding="utf-8"
        )
        
        return {
            "success": True,
            "role_id": role_id,
            "path": str(role_dir.relative_to(self.project_root)),
            "created_files": [
                f"group/{department}/{role_id}/{role_id}.md",
                f"group/{department}/{role_id}/memories/",
                f"group/{department}/{role_id}/reference/files_i_use.md",
                f"group/{department}/{role_id}/skills/skills.md",
            ],
        }
    
    def analyze_capabilities(self, role_id: str, 
                            task_description: str) -> Dict[str, Any]:
        """
        分析角色应具备的能力
        
        Args:
            role_id: 角色标识
            task_description: 任务描述，用于推断所需能力
            
        Returns:
            能力分析结果
        """
        # 简化实现：基于关键词匹配推断能力
        keywords = {
            "设计": ["visual_design", "creative_thinking", "quality_review"],
            "开发": ["coding", "architecture_design", "code_review"],
            "运维": ["monitoring", "incident_response", "security_audit"],
            "管理": ["coordination", "planning", "decision_making"],
        }
        
        suggested_skills = []
        for kw, skills in keywords.items():
            if kw in task_description:
                suggested_skills.extend(skills)
        
        return {
            "role_id": role_id,
            "suggested_skills": list(set(suggested_skills)),
            "note": "能力分析由 suri-hr 完成，角色可自行调整",
        }
    
    def validate_soul(self, soul_path: Path) -> Dict[str, Any]:
        """
        验证 Soul 文件格式
        
        Args:
            soul_path: Soul 文件路径
            
        Returns:
            验证结果
        """
        if not soul_path.exists():
            return {"valid": False, "error": "文件不存在"}
        
        content = soul_path.read_text(encoding="utf-8")
        
        # 检查 YAML Frontmatter
        if not content.startswith("---"):
            return {"valid": False, "error": "缺少 YAML Frontmatter"}
        
        # 检查必需字段
        required_sections = ["## 人设", "## 职责", "## 能力边界"]
        missing = [s for s in required_sections if s not in content]
        
        if missing:
            return {"valid": False, "error": f"缺少必要章节: {missing}"}
        
        return {"valid": True, "error": None}
    
    def _validate_role_id(self, role_id: str) -> bool:
        """验证角色 ID 格式"""
        if not role_id or len(role_id) < 2:
            return False
        return bool(self.ROLE_ID_PATTERN.match(role_id))
    
    def _generate_soul(self, role_id: str, name: str, 
                      department: str, role_type: str) -> str:
        """生成 Soul 文件模板内容"""
        return f"""---
role_id: {role_id}
name: {role_id}
nickname: {name}
version: "1.0.0"
type: {role_type}
department: {department}
---

# {name}

## 人设

（请描述角色的性格、语气、工作风格）

## 职位

（角色在部门中的职位）

## 职责

- （职责 1）
- （职责 2）
- （职责 3）

## 能力边界

- **可以**：
  - （能力 1）
  - （能力 2）
- **不可以**：
  - （限制 1）
  - （限制 2）

## 输入输出格式

- 输入：（角色接收什么类型的输入）
- 输出：（角色产出什么类型的输出）

## 独立存储

- 记忆：group/{department}/{role_id}/memories/
- 会话：group/{department}/{role_id}/memories/role.db
- 技能：group/{department}/{role_id}/skills/
"""
