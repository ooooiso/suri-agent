"""
配置加载服务

关联文档: suri-agent/infrastructure/infrastructure.md

职责：
- 扫描并解析项目中的外部配置（角色、技能、流程等 .md 文件）
- 规则已迁移为代码（suri-agent/rules/），不再通过本服务加载
- 提供配置查询 API（按 role_id、process_id、skill_id 等查找）
"""

from datetime import datetime
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
    - group/              角色实例（Soul 文件）
    - skills/             suri 技能库
    - suri-agent/tools/   公共工具
    - wiki/               预留：LLM Wiki 资料（不用于业务逻辑）
    
    规则已代码化，不再通过 .md 加载。规则查询请使用 rules.RuleEngine。
    """
    
    # 角色标识别名映射（旧名称 → 新名称，支持平滑迁移）
    _ROLE_ALIASES = {
        'suri-dev': 'suri_dev',
        'suri-hr': 'suri_hr',
        'document-review': 'suri_review',
        'analyst': 'suri_stats',
    }
    
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
        
        # V2.0: 自动重建缺失的核心角色
        self.ensure_core_roles()
        
        # 配置加载完成，信息不打印到终端
    
    def ensure_core_roles(self) -> List[str]:
        """
        确保五大核心角色 Soul 文件存在，缺失则自动重建
        
        Returns:
            重建的角色 ID 列表（空列表表示全部存在）
        """
        rebuilt = []
        core_roles = {
            'suri': ('central', 'suri'),
            'suri_dev': ('central', 'suri_dev'),
            'suri_hr': ('central', 'suri_hr'),
            'suri_review': ('central', 'suri_review'),
            'suri_stats': ('central', 'suri_stats'),
        }
        
        for role_id, (dept, dir_name) in core_roles.items():
            soul_path = self.project_root / 'group' / dept / dir_name / f"{dir_name}.md"
            if not soul_path.exists():
                # 自动重建：创建目录和默认 Soul 文件
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                default_soul = self._generate_default_soul(role_id)
                soul_path.write_text(default_soul, encoding='utf-8')
                rebuilt.append(role_id)
                
                # 重新加载该角色到索引
                if soul_path.exists():
                    meta, body = load_markdown_file(soul_path)
                    entry = ConfigEntry(
                        rel_path=f"group/{dept}/{dir_name}/{dir_name}.md",
                        meta=meta, body=body, abs_path=soul_path
                    )
                    self._registry[entry.rel_path] = entry
                    self._index_entry(entry)
        
        return rebuilt
    
    def _generate_default_soul(self, role_id: str) -> str:
        """生成角色的默认 Soul 文件内容"""
        templates = {
            'suri': """---\nrole_id: suri\nname: Suri\ndepartment: central\nlevel: director\ntype: scheduler\ncapabilities: [task_analysis, dispatch, coordination, escalation]\noutput_channels: [terminal, logger, memory]\noutput_path: resources/sessions/output/\ntools: [file_write]\n---\n\n# Suri — 中枢调度总监\n\n## 定位\n\nSuri 是全局输入/输出枢纽，用户唯一交互出口。\n""",
            'suri_dev': """---\nrole_id: suri_dev\nname: suri_dev\nnickname: 码农老李\ndepartment: central\nlevel: maintainer\ntype: maintainer\ncapabilities: [coding, debugging, infrastructure, tool_dev, testing]\nkeywords: [程序维护, Bug修复, Bug, 代码, 升级, 性能优化, 性能, 优化, 内存, 缓存, 重构, 函数, 崩溃, 出错, Python, 开发, 模块, API, 规则, 框架维护, 基础设施, 修复]\noutput_channels: [terminal, file, logger, memory]\noutput_path: group/central/suri_dev/output/\ntools: []\n---\n\n# suri_dev — 开发维护者\n\n## 定位\n\n主程序及工具的唯一维护者。\n""",
            'suri_hr': """---\nrole_id: suri_hr\nname: suri_hr\nnickname: 人事大姐\ndepartment: central\nlevel: director\ntype: admin\ncapabilities: [role_creation, org_management, group_setup, skill_assignment]\nkeywords: [创建角色, 创建, 角色, 组织架构, 部门, 部门设置, 技能分配, 技能, 角色管理, 人事, 权限]\noutput_channels: [terminal, file, logger, memory]\noutput_path: group/suri_hr/output/\ntools: [file_write]\n---\n\n# suri_hr — 人力资源与行政总监\n\n## 定位\n\n部门划分、角色能力与协同管理。\n""",
            'suri_review': """---\nrole_id: suri_review\nname: suri_review\nnickname: 审查员\ndepartment: central\nlevel: specialist\ntype: reviewer\ncapabilities: [code_review, doc_review, change_audit, requirement_validation]\nkeywords: [审核, 文档审核, 文档, 代码审查, 变更审计, 变更, 审计, 质量检查, 质量, 检查, 风险, 验证, 评估, 格式]\noutput_channels: [terminal, file, logger, memory]\noutput_path: group/central/suri_review/reports/\ntools: []\n---\n\n# suri_review — 文档与变更审核专员\n\n## 定位\n\n项目逻辑一致性把关者。\n""",
            'suri_stats': """---\nrole_id: suri_stats\nname: suri_stats\nnickname: 数据小能手\ndepartment: central\nlevel: specialist\ntype: specialist\ncapabilities: [statistics, aggregation, reporting, monitoring]\nkeywords: [统计, 分析, 报告, 消耗, token, 用量, 日报, 周报, 月报, 文件, 任务, 监控]\noutput_channels: [terminal, logger, memory]\noutput_path: resources/temp/\ntools: [file_read, file_list]\n---\n\n# suri_stats — 统计分析师\n\n## 定位\n\n数据统计与项目指标持续优化。\n""",
        }
        return templates.get(role_id, f"---\nrole_id: {role_id}\n---\n\n# {role_id}\n")
    
    def _index_entry(self, entry: ConfigEntry) -> None:
        """将条目加入索引"""
        meta = entry.meta
        for key in ['role_id', 'process_id', 'skill_id', 'tool_id']:
            value = meta.get(key)
            if value:
                self._indexes[key][value] = entry
    
    # ---- 查询接口 ----
    
    def get_role_soul(self, role_id: str) -> Optional[ConfigEntry]:
        """获取角色 Soul 文件（支持别名自动解析）"""
        # V2.0: 统一解析别名（如 'analyst' → 'suri_stats'）
        resolved_id = self.resolve_role_id(role_id)
        
        if resolved_id == 'suri':
            soul_path = self.project_root / 'group/central/suri/suri.md'
            if soul_path.exists():
                meta, body = load_markdown_file(soul_path)
                return ConfigEntry(
                    rel_path='group/central/suri/suri.md',
                    meta=meta, body=body, abs_path=soul_path
                )
            return None
        
        entry = self._indexes['role_id'].get(resolved_id)
        if entry:
            return entry
        
        # 兼容：从 group/ 下查找
        fallback_path = self.project_root / 'group' / resolved_id / f"{resolved_id}.md"
        if fallback_path.exists():
            meta, body = load_markdown_file(fallback_path)
            return ConfigEntry(
                rel_path=f"group/{resolved_id}/{resolved_id}.md",
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
    
    def list_departments(self) -> List[str]:
        """列出所有部门 ID（从 Soul 文件扫描）"""
        depts = set()
        for role_id in self.list_roles():
            soul = self.get_role_soul(role_id)
            if soul:
                dept = soul.meta.get('department', '')
                if dept:
                    depts.add(dept)
        return sorted(depts)
    
    def get_department_lead(self, dept_id: str) -> Optional[str]:
        """获取部门的 lead_role（该部门第一个 director/admin 类型角色，或第一个角色）"""
        candidates = []
        for role_id in self.list_roles():
            soul = self.get_role_soul(role_id)
            if not soul:
                continue
            if soul.meta.get('department', '') == dept_id:
                candidates.append((role_id, soul.meta.get('type', '')))
        
        if not candidates:
            return None
        
        # 优先 director/admin/scheduler 类型
        for rid, rtype in candidates:
            if rtype in ('director', 'admin', 'scheduler'):
                return rid
        
        return candidates[0][0]
    
    def get_function_index(self) -> Optional[ConfigEntry]:
        """
        [已废弃] 部门职能索引。
        
        业务逻辑不应使用此方法。请改用 list_departments() 和 get_department_lead()。
        保留此方法仅用于兼容旧代码。
        """
        return None
    
    def _load_yaml(self, rel_path: str) -> Optional[Dict[str, Any]]:
        """从 YAML 文件加载配置"""
        import yaml
        path = self.project_root / rel_path
        if not path.exists():
            return None
        try:
            return yaml.safe_load(path.read_text(encoding='utf-8'))
        except Exception:
            return None

    def get_model_pool(self) -> Optional[Dict[str, Any]]:
        """获取模型池配置（从 pool.yaml）"""
        return self._load_yaml('suri-agent/model/pool.yaml')

    def get_memory_config(self) -> Optional[Dict[str, Any]]:
        """获取记忆策略配置（从 config.yaml）"""
        return self._load_yaml('suri-agent/memory/config.yaml')

    def get_telegram_config(self) -> Optional[Dict[str, Any]]:
        """获取 Telegram 配置（从 groups.yaml）"""
        return self._load_yaml('suri-agent/access/telegram/groups.yaml')
    
    def list_roles(self, include_aliases: bool = False) -> List[str]:
        """
        列出所有角色 ID
        
        Args:
            include_aliases: 为 True 时同时返回旧版别名（如 'analyst', 'suri-dev'）
        
        Returns:
            角色标识列表
        """
        base = list(self._indexes['role_id'].keys())
        if include_aliases:
            # 添加反向别名映射（旧名 → 新名中的旧名键）
            for alias, canonical in self._ROLE_ALIASES.items():
                if canonical in base and alias not in base:
                    base.append(alias)
        return base
    
    def get_role_keywords(self, role_id: str) -> List[str]:
        """
        从角色 Soul 文件中提取调度关键词
        
        优先级：
        1. frontmatter 中的 keywords 字段
        2. frontmatter 中的 capabilities 字段
        3. body 中 ## 职责 或 ## 能力 段落的关键词提取
        """
        soul = self.get_role_soul(role_id)
        if not soul:
            return []
        
        # 1. 优先使用 frontmatter 中的 keywords
        keywords = soul.meta.get('keywords', [])
        if keywords:
            return keywords
        
        # 2. 回退到 capabilities
        capabilities = soul.meta.get('capabilities', [])
        if capabilities:
            return capabilities
        
        # 3. 从 body 提取（简单启发式：匹配 can/cannot 列表附近的关键词）
        body = soul.body
        extracted = []
        # 匹配 "- can: ..." 或 "keywords: [...]" 之类的列表
        import re
        for line in body.split('\n'):
            if line.strip().startswith('- ') and ':' in line:
                kw = line.split(':')[0].replace('- ', '').strip()
                if kw and kw not in extracted:
                    extracted.append(kw)
        return extracted
    
    def get_role_capabilities(self, role_id: str) -> List[str]:
        """
        获取角色的能力列表（从 Soul 文件 frontmatter 的 capabilities 字段）
        
        Returns:
            角色能力标签列表，如 ['coding', 'statistics', 'review']
        """
        soul = self.get_role_soul(role_id)
        if not soul:
            return []
        return soul.meta.get('capabilities', [])
    
    def get_role_output_channels(self, role_id: str) -> List[str]:
        """
        获取角色的输出渠道列表（从 Soul 文件 frontmatter 的 output_channels 字段）
        
        Returns:
            渠道标识列表，如 ['terminal', 'file', 'logger', 'memory']
            如果 Soul 中未声明，返回空列表（由调用方决定回退策略）
        """
        soul = self.get_role_soul(role_id)
        if not soul:
            return []
        return soul.meta.get('output_channels', [])
    
    def get_role_output_path(self, role_id: str) -> Optional[str]:
        """
        获取角色的默认文件输出路径（从 Soul 文件 frontmatter 的 output_path 字段）
        
        Returns:
            相对路径字符串，如 'group/my-role/output/'
            如果 Soul 中未声明，返回 None（由调用方决定回退策略）
        """
        soul = self.get_role_soul(role_id)
        if not soul:
            return None
        return soul.meta.get('output_path', None)
    
    # ---- V2.0 角色类型与别名系统 ----
    
    @classmethod
    def resolve_role_id(cls, raw_role_id: str) -> str:
        """
        统一解析角色标识（支持新旧别名兼容）
        
        Args:
            raw_role_id: 原始角色标识（可能包含旧名称，如 'suri-dev'）
            
        Returns:
            标准化后的角色标识（如 'suri_dev'）
        """
        return cls._ROLE_ALIASES.get(raw_role_id, raw_role_id)
    
    def get_role_type(self, role_id: str) -> Optional[str]:
        """
        获取角色的类型标签（从 Soul 文件 frontmatter 的 type 字段）
        
        Returns:
            角色类型，如 'maintainer', 'reviewer', 'admin', 'specialist'
        """
        soul = self.get_role_soul(role_id)
        if not soul:
            return None
        return soul.meta.get('type', None)
    
    def get_roles_by_type(self, role_type: str) -> List[str]:
        """
        获取指定类型的所有角色实例
        
        Args:
            role_type: 角色类型标签，如 'maintainer'
            
        Returns:
            角色 ID 列表
        """
        result = []
        for role_id in self.list_roles():
            if self.get_role_type(role_id) == role_type:
                result.append(role_id)
        return result
    
    def get_role_nickname(self, role_id: str) -> str:
        """
        获取角色的昵称（从 Soul 文件 frontmatter 的 nickname 字段）
        
        Returns:
            昵称字符串，如 '码农老李'。未设置时回退到 name 或 role_id
        """
        soul = self.get_role_soul(role_id)
        if not soul:
            return role_id
        return soul.meta.get('nickname') or soul.meta.get('name') or role_id
    
    def list_role_skills(self, role_id: str) -> List[str]:
        """列出指定角色的所有技能 ID（扫描 group/<dept>/<role>/skills/ 目录）"""
        soul = self.get_role_soul(role_id)
        dept = soul.meta.get('department', 'central') if soul else 'central'
        
        skills_dir = self.project_root / 'group' / dept / role_id / 'skills'
        if not skills_dir.exists():
            return []
        
        skills = []
        for item in skills_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                skills.append(item.name)
        return sorted(skills)
    
    def get_skill_detail(self, role_id: str, skill_id: str) -> Optional[Dict[str, Any]]:
        """获取技能的详细定义（解析 skill.md 的 frontmatter + body）"""
        soul = self.get_role_soul(role_id)
        dept = soul.meta.get('department', 'central') if soul else 'central'
        
        skill_md = self.project_root / 'group' / dept / role_id / 'skills' / skill_id / 'skill.md'
        if not skill_md.exists():
            return None
        
        content = skill_md.read_text(encoding='utf-8')
        meta = {}
        body = content
        if content.startswith('---'):
            end = content.find('---', 3)
            if end != -1:
                try:
                    meta = yaml.safe_load(content[3:end]) or {}
                    body = content[end+3:].strip()
                except Exception:
                    pass
        
        return {
            'skill_id': skill_id,
            'name': meta.get('name', skill_id),
            'owner': meta.get('owner', role_id),
            'version': meta.get('version', '0.1.0'),
            'status': meta.get('status', 'active'),
            'triggers': meta.get('triggers', []),
            'inputs': meta.get('inputs', []),
            'body': body,
        }
    
    def list_skills(self) -> List[str]:
        """列出所有技能 ID（全局）"""
        return list(self._indexes['skill_id'].keys())
    
    def list_tools(self) -> List[str]:
        """列出所有工具 ID"""
        return list(self._indexes['tool_id'].keys())
    
    def sync_group_function(self) -> str:
        """
        自动生成 group/group_function.md 内容
        
        从 group/central/ 目录下所有角色 Soul 文件扫描，
        生成角色列表和角色能力速查表格。
        保留手动编写的快速匹配指南部分。
        
        Returns:
            生成的 Markdown 内容
        """
        lines = [
            "---",
            'version: "1.0.0"',
            "description: 部门职能索引与角色能力速查，用于需求匹配与调度决策",
            f"last_updated: {datetime.now().strftime('%Y-%m-%d')}",
            "# ⚠️ 注意：roles 列表和角色能力速查表格由程序自动生成",
            "# 新增/修改角色后，运行 ConfigService.sync_group_function() 或 /sync 命令即可更新",
            "",
            "departments:",
        ]
        
        # 收集部门信息（按 department 分组）
        dept_roles: Dict[str, List[Dict]] = {}
        for role_id in sorted(self.list_roles()):
            soul = self.get_role_soul(role_id)
            if not soul:
                continue
            dept = soul.meta.get('department', 'unknown')
            if dept not in dept_roles:
                dept_roles[dept] = []
            dept_roles[dept].append({
                'id': role_id,
                'name': soul.meta.get('name', role_id),
                'type': soul.meta.get('type', ''),
                'level': soul.meta.get('level', ''),
                'keywords': soul.meta.get('keywords', soul.meta.get('capabilities', [])),
                'skills': self.list_role_skills(role_id),
            })
        
        # 生成 departments YAML
        for dept_id, roles in sorted(dept_roles.items()):
            lines.append(f"  - id: {dept_id}")
            lines.append(f"    name: {dept_id}部门")
            lines.append(f"    lead_role: {roles[0]['id'] if roles else ''}")
            lines.append("    members:")
            for r in roles:
                lines.append(f"      - {r['id']}")
            lines.append("    collaboration: []")
            lines.append("")
        
        lines.append("roles:")
        for dept_id, roles in sorted(dept_roles.items()):
            for r in roles:
                lines.append(f"  - id: {r['id']}")
                lines.append(f"    name: {r['name']}")
                lines.append(f"    type: {r['type'] or 'unknown'}")
                lines.append(f"    keywords: {r['keywords']}")
                skills_str = ', '.join(r['skills']) if r['skills'] else '无'
                lines.append(f"    skills: [{skills_str}]")
                lines.append("")
        
        lines.append("---")
        lines.append("")
        lines.append("# 角色能力速查")
        lines.append("")
        lines.append("| 角色 ID | 类型 | 核心能力关键词 | 技能 | 调度匹配场景 |")
        lines.append("|---------|------|---------------|------|-------------|")
        
        for dept_id, roles in sorted(dept_roles.items()):
            for r in roles:
                keywords = ', '.join(r['keywords'][:5]) if r['keywords'] else '-'
                skills = ', '.join(r['skills'][:3]) if r['skills'] else '-'
                lines.append(f"| {r['id']} | {r['type'] or '-'} | {keywords} | {skills} | 由角色 Soul 中 keywords 自动推导 |")
        
        lines.append("")
        lines.append("## 快速匹配指南")
        lines.append("")
        lines.append("**用户需求包含以下关键词时，系统自动调度给对应角色：**")
        lines.append("")
        
        for dept_id, roles in sorted(dept_roles.items()):
            for r in roles:
                if r['keywords']:
                    kw_examples = ' / '.join(r['keywords'][:3])
                    lines.append(f'- "{kw_examples}" → **{r["id"]}**')
        
        lines.append("- 其他所有业务需求 → **suri**（由 suri 进一步分派）")
        lines.append("")
        lines.append("> 本文档由 ConfigService.sync_group_function() 自动生成。")
        lines.append("> 如需调整角色关键词或能力，修改对应角色的 Soul 文件后重新生成即可。")
        
        return "\n".join(lines)
    
    def get_file(self, rel_path: str) -> Optional[ConfigEntry]:
        """按相对路径获取任意配置"""
        return self._registry.get(rel_path)
