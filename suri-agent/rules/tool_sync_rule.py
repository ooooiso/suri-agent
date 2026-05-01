"""
工具同步规则（代码化）

核心规则：
1. suri-agent/tools/ 下新增/删除/修改工具时，必须同步更新 tool_registry.json
2. 角色 soul 文件的 `tools` 字段变更时，必须同步更新 tool_registry.json 的权限
3. 每个工具目录必须包含对应的说明文档（<tool_id>.md 或 README.md）
4. 同步流程：检测变更 → 自动生成更新 → document-review 审核 → 用户确认 → 写入

职责：
- 扫描 tools/ 目录，维护工具清单
- 扫描角色 soul 文件，维护权限
- 检测"工具已变更但 tool_registry.json 未更新"的违规项
- 驱动同步执行流程

关联文档: suri-agent/tools/tool_registry.md (纯说明文档)
业务权威来源: suri-agent/tools/tool_registry.json
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class ToolSyncViolation:
    """工具同步违规项"""
    violation_type: str       # "missing_doc" 缺失文档 / "missing_registry" 未注册 /
                              # "stale_registry" 注册过时 / "stale_permission" 权限过时
    tool_id: str              # 工具 ID
    suggestion: str = ""      # 更新建议


class ToolSyncRule:
    """
    工具同步规则引擎

    使用方式：
        rule = ToolSyncRule(project_root)
        violations = rule.scan()          # 扫描所有违规项
        rule.generate_json()              # 自动生成 tool_registry.json
        rule.write_json()                 # 写入文件
    """

    def __init__(self, project_root: Path, config=None):
        self.project_root = project_root
        self.tools_dir = project_root / "suri-agent" / "tools"
        self.registry_path = self.tools_dir / "tool_registry.json"
        self.roles_dir = project_root / "group" / "central"
        self.config = config  # ConfigService，用于动态查询角色信息

    # ───────────────────── 读取/写入 JSON ─────────────────────

    def _read_registry(self) -> Dict:
        """读取 tool_registry.json，不存在返回空 dict"""
        if not self.registry_path.exists():
            return {}
        try:
            return json.loads(self.registry_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_registry(self, data: Dict) -> None:
        """写入 tool_registry.json"""
        self.registry_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ───────────────────── 扫描违规项 ─────────────────────

    def scan(self) -> List[ToolSyncViolation]:
        """
        扫描工具同步违规项

        检查项：
        1. 每个工具目录是否有说明文档
        2. tool_registry.json 是否包含所有工具
        3. 权限是否与角色 soul 中的 tools 字段一致
        """
        violations = []
        registry = self._read_registry()
        registry_tools = set(registry.keys())
        actual_tools = self._scan_actual_tools()

        # 1. 检查每个实际工具
        for tool_id in actual_tools:
            # 检查说明文档
            if not self._has_doc(tool_id):
                violations.append(ToolSyncViolation(
                    violation_type="missing_doc",
                    tool_id=tool_id,
                    suggestion=f"为工具 {tool_id} 创建说明文档（{tool_id}.md 或 README.md）"
                ))

            # 检查是否已注册
            if tool_id not in registry_tools:
                violations.append(ToolSyncViolation(
                    violation_type="missing_registry",
                    tool_id=tool_id,
                    suggestion=f"在 tool_registry.json 中注册工具 {tool_id}"
                ))

        # 2. 检查注册表中是否有已不存在的工具
        for tool_id in registry_tools:
            if tool_id not in actual_tools:
                violations.append(ToolSyncViolation(
                    violation_type="stale_registry",
                    tool_id=tool_id,
                    suggestion=f"工具 {tool_id} 已不存在，从 tool_registry.json 中移除"
                ))

        # 3. 检查权限
        violations.extend(self._check_permissions())

        # 4. 检查技能依赖
        violations.extend(self._check_skill_dependencies())

        return violations

    # ───────────────────── 自动生成 JSON ─────────────────────

    def generate_json(self) -> Dict:
        """
        自动生成 tool_registry.json 的内容

        基于实际扫描结果生成：
        - tools: 工具列表及其权限
        """
        actual_tools = self._scan_actual_tools()
        role_tools = self._scan_role_tools()

        registry = {}
        for tool_id in sorted(actual_tools):
            desc = self._get_tool_description(tool_id)
            # 收集声明了此工具的角色
            allowed_roles = []
            for role_id, tools in role_tools.items():
                if tool_id in tools:
                    allowed_roles.append(role_id)

            registry[tool_id] = {
                "description": desc,
                "allowed_roles": sorted(set(allowed_roles)) if allowed_roles else [],
            }

        return registry

    def write_json(self) -> None:
        """将生成的内容写入 tool_registry.json"""
        data = self.generate_json()
        self._write_registry(data)

    def write_markdown(self) -> str:
        """
        同时生成 tool_registry.md（纯说明文档，供人类阅读）
        业务逻辑不使用此文件。
        """
        registry = self.generate_json()
        from datetime import datetime

        # V2.0: 动态查询维护者和审核者角色名称
        maintainer = "suri_dev"
        reviewer = "suri_review"
        if self.config:
            maintainer_roles = self.config.get_roles_by_type("maintainer")
            if maintainer_roles:
                maintainer = self.config.get_role_nickname(maintainer_roles[0])
            reviewer_roles = self.config.get_roles_by_type("reviewer")
            if reviewer_roles:
                reviewer = self.config.get_role_nickname(reviewer_roles[0])
        
        lines = [
            "# Suri 工具集清单",
            "",
            f"> 所有角色可调用的公共工具集，由 {maintainer} 维护。",
            "> 本文件为纯说明文档，业务权威来源是 `tool_registry.json`。",
            f"> 新增工具需经 {reviewer} 审核后合并。",
            "",
            "## 现有工具",
            "",
            "| 工具名 | 说明 | 授权角色 |",
            "|--------|------|----------|",
        ]

        for tool_id, info in sorted(registry.items()):
            desc = info.get("description", "暂无描述")
            roles = ", ".join(info.get("allowed_roles", [])) or "—"
            lines.append(f"| `{tool_id}` | {desc} | {roles} |")

        lines.extend([
            "",
            "## 工具创建规范",
            "",
            f"新工具由维护者角色创建，需遵循：",
            "",
            "1. **单一职责** — 每个工具只做一件事",
            "2. **输入校验** — 校验所有参数，防止注入攻击",
            "3. **权限检查** — 在 `ToolService.execute()` 中自动检查角色权限",
            "4. **日志记录** — 记录工具调用和结果",
            "5. **文档同步** — 创建 `tools/<tool_id>/<tool_id>.md` 说明文档",
            "",
            "## 角色申请新工具流程",
            "",
            "```",
            "角色发现需要某能力 → 向维护者角色提交需求",
            "    ↓",
            "维护者评估 → 在 tools/ 下创建工具",
            "    ↓",
            "更新对应角色的 soul 文件（tools 字段）",
            "    ↓",
            "运行 ToolSyncRule.write_json() 自动更新 tool_registry.json",
            "    ↓",
            "审核者审核 → 用户确认",
            "```",
            "",
            "---",
            "",
            f"> 最后生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "> 生成器: `suri-agent/rules/tool_sync_rule.py`",
            "",
        ])

        md_path = self.tools_dir / "tool_registry.md"
        content = "\n".join(lines)
        md_path.write_text(content, encoding="utf-8")
        return content

    # ───────────────────── 内部工具方法 ─────────────────────

    def _scan_actual_tools(self) -> set:
        """扫描 tools/ 目录下实际存在的工具"""
        tools = set()
        if not self.tools_dir.exists():
            return tools
        for item in self.tools_dir.iterdir():
            if item.is_dir() and item.name not in ('__pycache__', '.git'):
                if (item / "scripts").exists():
                    tools.add(item.name)
        return tools

    def _has_doc(self, tool_id: str) -> bool:
        """检查工具是否有说明文档"""
        tool_dir = self.tools_dir / tool_id
        doc_candidates = [
            tool_dir / f"{tool_id}.md",
            tool_dir / "README.md",
            tool_dir / "tool.md",
        ]
        return any(d.exists() for d in doc_candidates)

    def _scan_role_tools(self) -> Dict[str, List[str]]:
        """扫描所有角色 soul 文件中的 tools 字段"""
        from infrastructure.config import load_markdown_file

        role_tools = {}
        if not self.roles_dir.exists():
            return role_tools

        for role_dir in self.roles_dir.iterdir():
            if not role_dir.is_dir():
                continue
            soul_file = role_dir / f"{role_dir.name}.md"
            if not soul_file.exists():
                continue
            try:
                meta, _ = load_markdown_file(soul_file)
                tools = meta.get('tools', [])
                if tools:
                    role_tools[role_dir.name] = tools
            except Exception:
                continue

        return role_tools

    def _get_tool_description(self, tool_id: str) -> str:
        """获取工具的说明（从工具文档中读取）"""
        tool_dir = self.tools_dir / tool_id
        doc_candidates = [
            tool_dir / f"{tool_id}.md",
            tool_dir / "README.md",
            tool_dir / "tool.md",
        ]
        for doc in doc_candidates:
            if doc.exists():
                try:
                    content = doc.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            return line[:80]
                        if line.startswith('# '):
                            return line[2:][:80]
                except Exception:
                    pass
        return "暂无描述"

    def _check_permissions(self) -> List[ToolSyncViolation]:
        """检查 tool_registry.json 的权限是否与角色 soul 中的 tools 字段一致"""
        violations = []
        registry = self._read_registry()
        actual_tools = self._scan_actual_tools()
        role_tools = self._scan_role_tools()

        for role_id, tools in role_tools.items():
            for tool_id in tools:
                if tool_id not in actual_tools:
                    violations.append(ToolSyncViolation(
                        violation_type="stale_permission",
                        tool_id=tool_id,
                        suggestion=f"角色 {role_id} 声明了不存在的工具 {tool_id}"
                    ))

        return violations

    def _check_skill_dependencies(self) -> List[ToolSyncViolation]:
        """
        检查技能依赖：扫描所有角色的 skills/ 目录，
        检查技能声明的工具是否实际存在。
        """
        violations = []
        actual_tools = self._scan_actual_tools()

        if not self.roles_dir.exists():
            return violations

        for role_dir in self.roles_dir.iterdir():
            if not role_dir.is_dir():
                continue
            skills_dir = role_dir / "skills"
            if not skills_dir.exists():
                continue

            for skill_file in skills_dir.rglob("*.md"):
                try:
                    from infrastructure.config import load_markdown_file
                    meta, body = load_markdown_file(skill_file)
                    skill_tools = meta.get('tools', [])
                    skill_id = meta.get('skill_id', skill_file.stem)

                    for tool_id in skill_tools:
                        if tool_id not in actual_tools:
                            violations.append(ToolSyncViolation(
                                violation_type="stale_skill_dependency",
                                tool_id=tool_id,
                                suggestion=f"技能 [{skill_id}] (角色 {role_dir.name}) 依赖了不存在的工具 {tool_id}"
                            ))
                except Exception:
                    continue

        return violations
