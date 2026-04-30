"""
文档同步规则（代码化）

核心规则：
1. suri-agent/ 下任何目录发生代码变更时，必须同步更新该目录的同名 .md 文件
2. group/ 下任何角色目录发生变更时，必须同步更新该角色的 Soul 文件和技能文档
3. wiki/ 下任何目录发生变更时，必须同步更新该目录的同名 .md 文件
4. 同步流程：检测变更 → 大模型生成更新建议 → document-review 审核 → 用户确认 → 写入

职责：
- 建立代码文件 ↔ 文档文件的映射关系
- 检测"代码已更新但文档未更新"的违规项
- 驱动同步执行流程
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, asdict


@dataclass
class SyncViolation:
    """文档同步违规项"""
    doc_path: str           # 文档路径
    code_path: str          # 对应的代码/目录路径
    last_code_mtime: float  # 代码最后修改时间
    last_doc_mtime: float   # 文档最后修改时间（可能为0表示缺失）
    violation_type: str     # "missing" 缺失 / "stale" 过时
    suggestion: str = ""    # 更新建议


class DocSyncRule:
    """
    文档同步规则引擎
    
    使用方式：
        rule = DocSyncRule(project_root)
        violations = rule.scan()          # 扫描所有违规项
        rule.generate_sync_plan()          # 生成同步计划
    """
    
    STATE_FILE = ".doc_sync_rule_state.json"
    
    def __init__(self, project_root: Path, model_manager=None):
        self.project_root = project_root
        self.model_manager = model_manager
        self.state_path = project_root / self.STATE_FILE
        self._state = self._load_state()
        
        # 定义需要监控的目录映射
        self.watch_paths = [
            ("suri-agent", ".py"),    # suri-agent/ 下的 .py 变更 → 触发同名 .md 检查
            ("group", ".md"),         # group/ 下的变更 → 检查角色 Soul 文件
            ("wiki", ".md"),          # wiki/ 下的变更 → 检查同名 .md
        ]
    
    def _load_state(self) -> dict:
        """加载上次扫描状态"""
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[DocSyncRule] 加载状态失败: {e}")
                pass
        return {"last_scan": "", "violations": []}
    
    def _save_state(self) -> None:
        """保存扫描状态"""
        self._state["last_scan"] = datetime.now().isoformat()
        self.state_path.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _get_doc_for_dir(self, dir_path: Path) -> Optional[Path]:
        """
        获取目录对应的同名 .md 文档路径
        
        规则：
        - 目录名就是 .md 文件名（如 model/ → model.md）
        - 特殊情况：tools/ 子目录用 tool.md，角色目录用 <role_id>.md
        """
        name = dir_path.name
        parent = dir_path.parent
        
        # 工具子目录使用 tool.md
        if "tools" in str(parent) and name != "tools":
            return dir_path / "tool.md"
        
        # 角色目录（group/ 下）使用角色 Soul 文件
        if "group" in str(parent) and name not in ("central", "_archived"):
            return dir_path / f"{name}.md"
        
        # 默认：同名 .md
        return dir_path / f"{name}.md"
    
    def _scan_dir(self, base_dir: Path, code_ext: str) -> List[SyncViolation]:
        """扫描单个基目录下的违规项"""
        violations = []
        
        for subdir in base_dir.rglob("*"):
            if not subdir.is_dir():
                continue
            
            # 跳过 __pycache__、.git 等
            if any(part.startswith(".") or part == "__pycache__" for part in subdir.parts):
                continue
            
            doc_file = self._get_doc_for_dir(subdir)
            if not doc_file:
                continue
            
            # 检查该目录下是否有代码文件
            code_files = list(subdir.glob(f"*{code_ext}"))
            if not code_files and code_ext == ".py":
                # 如果是 Python 目录但无 .py 文件，跳过
                continue
            
            # 获取代码最新修改时间
            last_code_mtime = 0.0
            if code_files:
                last_code_mtime = max(f.stat().st_mtime for f in code_files)
            
            # 检查文档
            if not doc_file.exists():
                violations.append(SyncViolation(
                    doc_path=str(doc_file.relative_to(self.project_root)),
                    code_path=str(subdir.relative_to(self.project_root)),
                    last_code_mtime=last_code_mtime,
                    last_doc_mtime=0.0,
                    violation_type="missing",
                    suggestion=f"目录 {subdir.name} 缺少同名文档 {doc_file.name}"
                ))
            else:
                doc_mtime = doc_file.stat().st_mtime
                # 如果代码比文档新超过 60 秒，认为文档过时
                if last_code_mtime > doc_mtime + 60:
                    violations.append(SyncViolation(
                        doc_path=str(doc_file.relative_to(self.project_root)),
                        code_path=str(subdir.relative_to(self.project_root)),
                        last_code_mtime=last_code_mtime,
                        last_doc_mtime=doc_mtime,
                        violation_type="stale",
                        suggestion=f"目录 {subdir.name} 的代码已更新，但 {doc_file.name} 未同步更新"
                    ))
        
        return violations
    
    def scan(self) -> List[SyncViolation]:
        """
        全面扫描所有监控目录，返回违规项列表
        """
        all_violations = []
        
        for rel_path, ext in self.watch_paths:
            base = self.project_root / rel_path
            if base.exists():
                all_violations.extend(self._scan_dir(base, ext))
        
        # 保存状态
        self._state["violations"] = [asdict(v) for v in all_violations]
        self._save_state()
        
        return all_violations
    
    def quick_check(self, changed_file: Path) -> Optional[SyncViolation]:
        """
        快速检查单个文件变更是否触发文档同步需求
        
        用于文件保存后的即时检测
        """
        # 找到该文件所属目录
        parent_dir = changed_file.parent
        doc_file = self._get_doc_for_dir(parent_dir)
        
        if not doc_file or not doc_file.exists():
            return SyncViolation(
                doc_path=str(doc_file.relative_to(self.project_root)) if doc_file else "",
                code_path=str(parent_dir.relative_to(self.project_root)),
                last_code_mtime=changed_file.stat().st_mtime,
                last_doc_mtime=doc_file.stat().st_mtime if doc_file and doc_file.exists() else 0,
                violation_type="missing" if not (doc_file and doc_file.exists()) else "stale"
            )
        
        doc_mtime = doc_file.stat().st_mtime
        code_mtime = changed_file.stat().st_mtime
        
        if code_mtime > doc_mtime + 60:
            return SyncViolation(
                doc_path=str(doc_file.relative_to(self.project_root)),
                code_path=str(parent_dir.relative_to(self.project_root)),
                last_code_mtime=code_mtime,
                last_doc_mtime=doc_mtime,
                violation_type="stale",
                suggestion=f"{changed_file.name} 已更新，请同步更新 {doc_file.name}"
            )
        
        return None
    
    def generate_sync_plan(self, violations: List[SyncViolation]) -> str:
        """
        生成同步计划报告（供大模型或 document-review 使用）
        """
        if not violations:
            return "✅ 所有文档已同步，未发现违规项"
        
        lines = [
            "📋 文档同步检测报告",
            f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"发现违规项: {len(violations)} 个",
            "",
            "| 类型 | 文档路径 | 对应代码 | 状态 |",
            "|------|---------|---------|------|"
        ]
        
        for v in violations:
            type_label = "❌ 缺失" if v.violation_type == "missing" else "⚠️ 过时"
            lines.append(f"| {type_label} | `{v.doc_path}` | `{v.code_path}` | {v.suggestion} |")
        
        lines.extend([
            "",
            "**同步流程**:",
            "1. 调用大模型生成文档更新建议",
            "2. document-review 审核",
            "3. 用户确认",
            "4. 执行写入",
        ])
        
        return "\n".join(lines)
    
    def is_compliant(self) -> bool:
        """检查当前是否全部合规（无违规项）"""
        return len(self.scan()) == 0
    
    def get_unsynced_dirs(self) -> List[str]:
        """获取所有未同步的目录路径列表"""
        violations = self.scan()
        return list(set(v.code_path for v in violations))
