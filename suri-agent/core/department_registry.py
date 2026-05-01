"""
部门注册表

关联文档: suri-agent/core/core.md

职责：
- 读取 departments.yaml 扩展部门配置
- 维护部门-能力-负责人-成员映射
- 支持 suri 按能力匹配最合适的部门
- 支持 hr 动态创建/更新/删除部门

V3.0 新增模块
"""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class Department:
    """扩展部门"""
    dept_id: str
    name: str
    lead_role: str           # 部门负责人 role_id
    ability: str             # 部门能力描述
    members: List[str] = field(default_factory=list)  # 成员 role_id 列表
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.dept_id,
            "name": self.name,
            "lead": self.lead_role,
            "ability": self.ability,
            "members": self.members,
        }


class DepartmentRegistry:
    """
    部门注册表
    
    数据来源：
    - 中枢部门（suri, suri_dev, suri_hr, suri_review, suri_stats）硬编码
    - 扩展部门从 departments.yaml 动态加载
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.dept_file = project_root / "departments.yaml"
        self._departments: Dict[str, Department] = {}
        self._load_departments()
    
    def _load_departments(self) -> None:
        """加载所有部门（扫描 group/ 目录 + departments.yaml 扩展）"""
        self._departments = {}
        
        # 1. 扫描 group/ 下的一级目录作为部门
        group_dir = self.project_root / "group"
        if group_dir.exists():
            for dept_dir in group_dir.iterdir():
                if not dept_dir.is_dir() or dept_dir.name.startswith('.'):
                    continue
                
                dept_id = dept_dir.name
                dept_name = dept_id
                ability = ""
                members = []
                lead_role = ""
                
                # 读取部门说明文件 <dept>/<dept>.md
                dept_md = dept_dir / f"{dept_id}.md"
                if dept_md.exists():
                    content = dept_md.read_text(encoding='utf-8')
                    if content.startswith('---'):
                        end = content.find('---', 3)
                        if end != -1:
                            try:
                                frontmatter = yaml.safe_load(content[3:end])
                                if frontmatter:
                                    dept_name = frontmatter.get('name', dept_id)
                                    ability = frontmatter.get('ability', '')
                            except Exception:
                                pass
                
                # 扫描部门下的角色目录
                for role_dir in dept_dir.iterdir():
                    if not role_dir.is_dir() or role_dir.name.startswith('.'):
                        continue
                    role_id = role_dir.name
                    members.append(role_id)
                    
                    # 找负责人：scheduler 类型或 director 级别
                    if not lead_role:
                        soul_file = role_dir / f"{role_id}.md"
                        if soul_file.exists():
                            content = soul_file.read_text(encoding='utf-8')
                            if 'type: scheduler' in content or 'level: director' in content:
                                lead_role = role_id
                
                if not lead_role and members:
                    lead_role = members[0]
                
                self._departments[dept_id] = Department(
                    dept_id=dept_id,
                    name=dept_name,
                    lead_role=lead_role,
                    ability=ability,
                    members=members,
                )
        
        # 2. 从 departments.yaml 加载扩展部门（覆盖或补充）
        if self.dept_file.exists():
            try:
                data = yaml.safe_load(self.dept_file.read_text(encoding="utf-8"))
                for d in data.get("departments", []):
                    dept_id = d["id"]
                    dept = Department(
                        dept_id=dept_id,
                        name=d.get("name", dept_id),
                        lead_role=d.get("lead", ""),
                        ability=d.get("ability", ""),
                        members=d.get("members", []),
                    )
                    self._departments[dept_id] = dept
            except Exception as e:
                print(f"[DepartmentRegistry] 加载部门配置失败: {e}")
    
    def list_departments(self) -> List[Department]:
        """列出所有部门"""
        return list(self._departments.values())
    
    def get_department(self, dept_id: str) -> Optional[Department]:
        """获取部门"""
        return self._departments.get(dept_id)
    
    def find_department_by_ability(self, keywords: List[str]) -> Optional[Department]:
        """
        按能力关键词匹配最合适的部门
        
        Args:
            keywords: 能力关键词列表
            
        Returns:
            最匹配的部门，无匹配返回 None
        """
        best_match = None
        best_score = 0
        
        for dept in self._departments.values():
            if dept.dept_id == "central":
                continue  # 中枢部门不参与扩展任务匹配
            score = sum(1 for kw in keywords if kw.lower() in dept.ability.lower())
            if score > best_score:
                best_score = score
                best_match = dept
        
        return best_match
    
    def find_department_for_role(self, role_id: str) -> Optional[Department]:
        """查找角色所属的部门"""
        for dept in self._departments.values():
            if role_id in dept.members or role_id == dept.lead_role:
                return dept
        return None
    
    def create_department(self, dept_id: str, name: str, lead_role: str,
                          ability: str, members: List[str]) -> Department:
        """
        创建新部门（供 hr 调用）
        
        创建后自动：
        1. 更新 departments.yaml
        2. 为部门负责人生成 Soul 文件（部门经理模板）
        """
        dept = Department(
            dept_id=dept_id,
            name=name,
            lead_role=lead_role,
            ability=ability,
            members=members,
        )
        self._departments[dept_id] = dept
        self._save_departments()
        return dept
    
    def _save_departments(self) -> None:
        """保存到 departments.yaml"""
        data = {
            "departments": [
                d.to_dict() for d in self._departments.values()
                if d.dept_id != "central"  # 中枢部门不写入文件
            ]
        }
        self.dept_file.write_text(
            yaml.dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8"
        )
    
    def generate_lead_soul(self, dept_id: str) -> str:
        """
        生成部门经理的 Soul 文件模板
        
        供 hr 创建新部门时使用
        """
        dept = self.get_department(dept_id)
        if not dept:
            return ""
        
        return f"""---
role_id: {dept.lead_role}
name: {dept.name}负责人
department: {dept_id}
level: director
type: admin
capabilities: [task_decomposition, team_coordination, status_reporting]
keywords: [部门管理, 任务分配, 进度跟踪, 团队协调]
output_channels: [terminal, logger, memory]
---

# {dept.lead_role} — {dept.name}负责人

## 定位

{dept.name}的负责人，接收 suri 下发的任务，在部门内进行二次调度和分配。

## 职责

1. 理解部门能力范围，接收 suri 下发的任务
2. 进行部门级任务分解，指派给部门内具体角色
3. 同步部门内各角色步骤状态给 suri
4. 当部门内无法胜任时，向 suri 汇报并请求支援

## 任务分解方法论

1. 理解需求 → 复述任务目标，确认输入输出
2. 识别依赖 → 列出前置材料或工具
3. 确定子任务 → 分解为可独立执行的子任务
4. 估算与排序 → 标出资源、耗时，并行标记
5. 执行与更新 → 完成子任务后更新状态通知 suri
6. 闭环检查 → 自我审查是否符合原始需求
"""
    
    def get_department_lead_context(self, dept_id: str) -> str:
        """获取部门经理的上下文描述（注入到系统提示中）"""
        dept = self.get_department(dept_id)
        if not dept:
            return ""
        
        member_desc = "\n".join(f"- {m}" for m in dept.members)
        return f"""你是 {dept.name}的负责人。

部门能力：{dept.ability}
部门成员：
{member_desc}

你的职责：
1. 接收 suri 下发的任务
2. 在部门内分解任务并指派给成员
3. 跟踪各成员进度，汇总后上报 suri
4. 部门能力不足时向 suri 请求支援
"""
