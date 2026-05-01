"""
文档同步服务

职责：
- 检测代码/目录变更
- 调用大模型生成文档更新建议
- 向用户汇报审核结果（模拟 document-review 角色）
- 用户确认后执行文档写入

使用方式：
    开发完成后，在 cli.py 或相关流程中调用：
    doc_sync = DocSyncService(model_manager)
    doc_sync.run_sync()
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class DocSyncService:
    """文档同步服务"""
    
    def __init__(self, model_manager, project_root: Path):
        self.model_manager = model_manager
        self.project_root = project_root
        self.core_memory_dir = project_root / "suri-agent" / "memory" / "ai-dev-memory"
        self.tracking_file = project_root / ".doc_sync_state.json"
        self._load_state()
    
    def _load_state(self) -> None:
        """加载上次同步状态（文件修改时间快照）"""
        self.state = {}
        if self.tracking_file.exists():
            try:
                self.state = json.loads(self.tracking_file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[DocSync] 加载状态文件失败: {e}")
                self.state = {}
    
    def _save_state(self) -> None:
        """保存同步状态"""
        self.tracking_file.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def _scan_files(self) -> Dict[str, float]:
        """扫描关键目录，获取文件修改时间"""
        snapshots = {}
        key_dirs = [
            self.project_root / "suri-agent",
            self.project_root / "group",
        ]
        for d in key_dirs:
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file() and not f.name.endswith(".db") and ".pyc" not in f.suffix:
                        try:
                            snapshots[str(f.relative_to(self.project_root))] = f.stat().st_mtime
                        except Exception as e:
                            print(f"[DocSync] 无法获取文件状态: {e}")
                            pass
        return snapshots
    
    def detect_changes(self) -> List[Dict]:
        """检测自上次同步以来的变更"""
        current = self._scan_files()
        changes = []
        
        for path, mtime in current.items():
            prev_mtime = self.state.get(path)
            if prev_mtime is None:
                changes.append({"type": "added", "path": path, "mtime": mtime})
            elif mtime > prev_mtime:
                changes.append({"type": "modified", "path": path, "mtime": mtime})
        
        for path in self.state:
            if path not in current:
                changes.append({"type": "deleted", "path": path, "mtime": 0})
        
        return changes
    
    def _generate_prompt(self, changes: List[Dict]) -> str:
        """生成调用大模型的 prompt"""
        change_list = "\n".join(
            f"- [{c['type']}] {c['path']}" for c in changes
        )
        
        # V2.0: 动态获取审核者角色显示名
        reviewer_name = "文档审核员"
        if hasattr(self, 'config') and self.config:
            reviewer_roles = self.config.get_roles_by_type("reviewer")
            if reviewer_roles:
                reviewer_name = self.config.get_role_nickname(reviewer_roles[0])
        
        prompt = f"""你是 suri 平台的文档审核员（{reviewer_name}）。

以下文件发生了变更：
{change_list}

请根据这些变更，生成对 AI 开发记忆库 `suri-agent/memory/ai-dev-memory/` 的更新建议。

AI 开发记忆库包含以下文件：
- `development-log.md`：开发日志，按时间线记录变更
- `module-index.md`：模块索引，记录所有目录/文件的功能和最新变更
- `architecture.md`：架构决策记录（如有重大架构变更）

请输出 JSON 格式的审核报告：
{{
  "development_log_updates": [
    {{"section": "标题", "content": "具体日志内容"}}
  ],
  "module_index_updates": [
    {{"path": "文件路径", "latest_change": "变更描述"}}
  ],
  "architecture_updates": [
    {{"title": "决策标题", "content": "ADR 内容"}}
  ],
  "missing_docs": [
    {{"path": "缺失文档的路径", "reason": "为什么需要它"}}
  ]
}}

只输出 JSON，不要其他内容。"""
        return prompt
    
    def generate_update_summary(self, changes: List[Dict]) -> Optional[Dict]:
        """调用大模型生成更新摘要"""
        if not changes:
            return None
        
        default_model = self.model_manager.get_default_model()
        if not default_model:
            print("[DocSync] 未配置模型，无法生成更新摘要")
            return None
        
        prompt = self._generate_prompt(changes)
        messages = [
            {"role": "system", "content": "你是一个严谨的文档审核员，负责审核代码变更并生成文档更新建议。只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]
        
        print("[DocSync] 正在调用模型生成文档更新建议...")
        reply = self.model_manager.chat(messages)
        if not reply:
            return None
        
        try:
            # 提取 JSON
            json_str = reply
            if "```json" in reply:
                json_str = reply.split("```json")[1].split("```")[0].strip()
            elif "```" in reply:
                json_str = reply.split("```")[1].split("```")[0].strip()
            return json.loads(json_str)
        except Exception as e:
            print(f"[DocSync] 解析模型输出失败: {e}")
            print(f"[DocSync] 原始输出: {reply[:500]}")
            return None
    
    def prompt_user_approval(self, report: Dict) -> bool:
        """向用户汇报审核结果，请求确认"""
        import sys
        # 非交互环境自动跳过，避免阻塞
        if not sys.stdin.isatty():
            print("[DocSync] 非交互环境，跳过文档更新确认")
            return False
        
        print("\n" + "=" * 50)
        print("  [document-review] 文档更新审核报告")
        print("=" * 50)
        
        if report.get("development_log_updates"):
            print("\n📋 development-log.md 建议更新:")
            for u in report["development_log_updates"]:
                print(f"  • [{u.get('section', '')}] {u.get('content', '')[:80]}...")
        
        if report.get("module_index_updates"):
            print("\n📋 module-index.md 建议更新:")
            for u in report["module_index_updates"]:
                print(f"  • {u.get('path', '')}: {u.get('latest_change', '')[:80]}...")
        
        if report.get("architecture_updates"):
            print("\n📋 architecture.md 建议更新:")
            for u in report["architecture_updates"]:
                print(f"  • {u.get('title', '')}")
        
        if report.get("missing_docs"):
            print("\n⚠️ 缺失文档:")
            for m in report["missing_docs"]:
                print(f"  • {m.get('path', '')}: {m.get('reason', '')}")
        
        print("\n" + "-" * 50)
        choice = input("是否应用以上文档更新？输入 '是' 确认，其他则跳过: ").strip()
        return choice == "是"
    
    def apply_updates(self, report: Dict) -> None:
        """应用更新到核心记忆库"""
        now = datetime.now().strftime("%Y-%m-%d")
        
        # 更新 development-log.md
        if report.get("development_log_updates"):
            log_path = self.core_memory_dir / "development-log.md"
            if log_path.exists():
                content = log_path.read_text(encoding="utf-8")
                # 在 ## 日期 下追加内容
                new_section = f"\n### {now}\n\n"
                for u in report["development_log_updates"]:
                    new_section += f"**{u.get('section', '更新')}**:\n{u.get('content', '')}\n\n"
                
                # 插入到第一个 ## 日期 之后
                if "## " in content:
                    first_header = content.find("## ")
                    insert_pos = content.find("\n", first_header) + 1
                    content = content[:insert_pos] + new_section + content[insert_pos:]
                else:
                    content += new_section
                
                log_path.write_text(content, encoding="utf-8")
                print(f"[DocSync] 已更新 {log_path}")
        
        # 更新 module-index.md
        if report.get("module_index_updates"):
            idx_path = self.core_memory_dir / "module-index.md"
            if idx_path.exists():
                content = idx_path.read_text(encoding="utf-8")
                # 简化处理：追加更新记录到文件末尾
                content += f"\n\n## 更新记录 ({now})\n\n"
                for u in report["module_index_updates"]:
                    content += f"- `{u.get('path', '')}`: {u.get('latest_change', '')}\n"
                idx_path.write_text(content, encoding="utf-8")
                print(f"[DocSync] 已更新 {idx_path}")
        
        # 更新 architecture.md
        if report.get("architecture_updates"):
            arch_path = self.core_memory_dir / "architecture.md"
            if arch_path.exists():
                content = arch_path.read_text(encoding="utf-8")
                for u in report["architecture_updates"]:
                    title = u.get("title", "")
                    body = u.get("content", "")
                    new_adr = f"\n## {title}\n\n- **日期**: {now}\n- **内容**: {body}\n"
                    content += new_adr
                arch_path.write_text(content, encoding="utf-8")
                print(f"[DocSync] 已更新 {arch_path}")
        
        # 提醒缺失文档
        if report.get("missing_docs"):
            print("\n[DocSync] ⚠️ 以下文档缺失，请手动创建:")
            for m in report["missing_docs"]:
                print(f"  • {m.get('path', '')}: {m.get('reason', '')}")
    
    def run_sync(self) -> None:
        """执行完整同步流程"""
        changes = self.detect_changes()
        if not changes:
            print("[DocSync] 未检测到变更")
            return
        
        print(f"[DocSync] 检测到 {len(changes)} 个文件变更")
        report = self.generate_update_summary(changes)
        if not report:
            return
        
        if self.prompt_user_approval(report):
            self.apply_updates(report)
            # 更新状态快照
            self.state = self._scan_files()
            self._save_state()
            print("[DocSync] 文档同步完成")
        else:
            print("[DocSync] 用户跳过更新")
