#!/usr/bin/env python3
"""
Suri 终端客户端

简易的命令行交互界面，直接调用 suri-agent 核心服务。
无需启动 JSON-RPC 后端，直接在进程中与 suri 对话。

使用方式:
    python -m suri-agent.access.tui.cli
    或: python suri-agent/access/tui/cli.py
"""

import sys
import uuid
import readline  # 改善终端输入体验（支持中文退格删除、光标移动）
from pathlib import Path
from datetime import datetime

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.filesystem import FileService
from infrastructure.logger import LoggerService
from core.context import ContextService
from core.model_router import ModelService
from core.task_dispatcher import TaskService
from core.approval import ApprovalService
from core.tool_executor import ToolService
from mcp.registry import MCPRegistry
from model.manager import ModelManager
from core.doc_sync import DocSyncService


class SuriTerminal:
    """终端交互界面"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.config = None
        self.memory = None
        self.security = None
        self.filesystem = None
        self.context = None
        self.model = None
        self.task = None
        self.model_manager = None
        self.doc_sync = None
        self.logger = None
        self.doc_sync_rule = None
        self.doc_watcher = None
        self.user_id = f"terminal_user_{datetime.now().strftime('%H%M%S')}"
        self._code_snapshot = None
        self._code_changed_notified = False
        
    def initialize(self):
        """初始化服务"""
        # 日志服务（最先初始化，确保后续日志可记录）
        self.logger = LoggerService(self.project_root)
        self.logger.info("系统", "开始初始化服务...")
        
        self.config = ConfigService(self.project_root)
        self.config.load_all()
        
        self.memory = MemoryService(self.project_root, self.config)
        self.security = SecurityService(self.project_root, self.config)
        self.filesystem = FileService(self.project_root, self.security)
        self.model = ModelService(self.config)
        self.context = ContextService(self.config, self.memory)
        self.task = TaskService(self.config, self.memory, self.context, self.model, self.logger)
        
        # 模型管理器
        self.model_manager = ModelManager(self.project_root)
        
        # 文档同步服务
        self.doc_sync = DocSyncService(self.model_manager, self.project_root)
        
        # 文档同步规则引擎
        self.doc_sync_rule = DocSyncRule(self.project_root, self.model_manager)
        
        # 文档监控钩子
        self.doc_watcher = DocWatcher(self.project_root)
        
        # 首次运行引导
        if self.model_manager.is_first_run():
            self.logger.info("配置", "首次运行，启动模型配置引导")
            if not self.model_manager.setup_wizard():
                self.logger.warn("配置", "用户未完成模型配置")
                print("\n⚠️ 未配置模型，suri 将无法调用外部模型进行对话。")
                print("可在之后使用 /model 命令添加模型。")
                print("")
        
        roles_count = len(self.config.list_roles())
        self.logger.log_startup(roles_count)
        print(f"[就绪] 已加载 {roles_count} 个角色")
        print("")
        
        # 记录代码快照
        self._code_snapshot = self._compute_code_snapshot()
        self._code_changed_notified = False
        
        # 启动文档监控
        self.doc_watcher.start()
        self.logger.info("系统", "文档监控已启动")
        
    def print_banner(self):
        """打印欢迎信息"""
        print("╔══════════════════════════════════════╗")
        print("║         Suri 智能体平台              ║")
        print("║     终端交互界面 (CLI Mode)          ║")
        print("╠══════════════════════════════════════╣")
        print("║  输入需求，suri 将为您调度          ║")
        print("║  输入 /help 查看命令                ║")
        print("║  输入 /quit 退出                    ║")
        print("╚══════════════════════════════════════╝")
        print("")
        
    def handle_command(self, text: str) -> bool:
        """处理斜杠命令，返回是否继续运行"""
        text = text.strip().lower()
        
        if text in ['/quit', '/exit', 'quit', 'exit']:
            self.logger.log_shutdown()
            print("\n再见！")
            return False
            
        if text == '/help':
            print("")
            print("可用命令:")
            print("  /roles      - 列出所有角色")
            print("  /rules      - 列出所有规则")
            print("  /tasks      - 查看任务列表")
            print("  /status     - 查看平台状态")
            print("  /model      - 模型管理")
            print("  /clear      - 清屏")
            print("  /help       - 显示此帮助")
            print("  /quit       - 退出")
            print("")
            return True
            
        if text == '/roles':
            roles = self.config.list_roles()
            print(f"\n共 {len(roles)} 个角色:")
            for role_id in roles:
                entry = self.config.get_role_soul(role_id)
                if entry:
                    print(f"  • {role_id:20s} | {entry.meta.get('nickname', ''):10s} | {entry.meta.get('department', '')}")
            print("")
            return True
            
        if text == '/rules':
            rules = self.config.list_rules()
            print(f"\n共 {len(rules)} 条规则:")
            for rule_id in rules:
                entry = self.config.get_rule(rule_id)
                if entry:
                    print(f"  • {rule_id:25s} | {entry.meta.get('name', '')}")
            print("")
            return True
            
        if text == '/tasks':
            print("\n[任务列表] 功能待实现（需要查询 state.db）")
            print("")
            return True
            
        if text == '/status':
            print("\n平台状态:")
            print(f"  角色数: {len(self.config.list_roles())}")
            print(f"  规则数: {len(self.config.list_rules())}")
            print(f"  用户ID: {self.user_id}")
            default = self.model_manager.get_default_model()
            if default:
                print(f"  默认模型: {default.name} ({default.model_id})")
            else:
                print(f"  默认模型: 未配置")
            print("")
            return True
            
        if text == '/model':
            self.logger.log_command(self.user_id, "/model")
            print("\n模型管理:")
            models = self.model_manager.list_models()
            if not models:
                print("  暂无配置模型")
            else:
                print(f"  共 {len(models)} 个模型:")
                for m in models:
                    marker = " [默认]" if m.is_default else ""
                    print(f"  • {m.name} ({m.model_id}){marker} — {m.provider}")
            print("")
            print("子命令:")
            print("  /model add    - 添加模型")
            print("  /model set    - 设置默认模型")
            print("  /model del    - 删除模型")
            print("")
            return True
            
        if text.startswith('/model add'):
            print("\n添加模型:")
            name = input("显示名称: ").strip()
            model_id = input("模型 ID: ").strip()
            api_key = input("API Key: ").strip()
            base_url = input("API 端点 (如 https://api.openai.com/v1): ").strip()
            provider = input("提供商 (openai/moonshot/deepseek/anthropic): ").strip()
            is_default = input("设为默认? [y/N]: ").strip().lower() == 'y'
            
            if not all([name, model_id, api_key, base_url, provider]):
                print("❌ 所有字段必填")
            else:
                self.model_manager.add_model(name, model_id, api_key, base_url, provider, is_default)
                print(f"✅ 已添加模型: {name}")
            print("")
            return True
            
        if text.startswith('/model set'):
            self.logger.log_command(self.user_id, "/model set")
            print("\n设置默认模型:")
            models = self.model_manager.list_models()
            for i, m in enumerate(models, 1):
                marker = " [默认]" if m.is_default else ""
                print(f"  {i}) {m.model_id}{marker}")
            choice = input("输入模型编号或 ID: ").strip()
            try:
                idx = int(choice) - 1
                model_id = models[idx].model_id
            except (ValueError, IndexError):
                model_id = choice
            if self.model_manager.set_default(model_id):
                self.logger.log_config("设置默认模型", f"ID={model_id}")
                print(f"✅ 已设置默认模型: {model_id}")
            else:
                self.logger.warn("配置", f"设置默认模型失败，未找到: {model_id}")
                print(f"❌ 未找到模型: {model_id}")
            print("")
            return True
            
        if text.startswith('/model del'):
            self.logger.log_command(self.user_id, "/model del")
            print("\n删除模型:")
            model_id = input("模型 ID: ").strip()
            if model_id in self.model_manager._models:
                del self.model_manager._models[model_id]
                self.model_manager._save()
                self.logger.log_config("删除模型", f"ID={model_id}")
                print(f"✅ 已删除模型: {model_id}")
            else:
                self.logger.warn("配置", f"删除模型失败，未找到: {model_id}")
                print(f"❌ 未找到模型: {model_id}")
            print("")
            return True
            
        if text == '/sync':
            self.logger.log_command(self.user_id, "/sync")
            print("\n[document-review] 启动文档同步...")
            
            # 1. 执行 DocSyncRule 扫描
            violations = self.doc_sync_rule.scan()
            if violations:
                print(f"\n⚠️ 检测到 {len(violations)} 个文档同步违规项：")
                for v in violations:
                    marker = "❌ 缺失" if v.violation_type == "missing" else "⚠️ 过时"
                    print(f"  {marker} {v.doc_path}")
                    print(f"     对应代码: {v.code_path}")
                    print(f"     建议: {v.suggestion}")
                print("")
                
                # 2. 调用大模型生成更新建议
                if self.model_manager.get_default_model():
                    plan = self.doc_sync_rule.generate_sync_plan(violations)
                    print("=" * 50)
                    print(plan)
                    print("=" * 50)
                    print("")
            else:
                print("\n✅ 所有文档已同步，未发现违规项\n")
            
            # 3. 执行传统 doc_sync（变更摘要生成）
            if self.doc_sync:
                self.doc_sync.run_sync()
                self.logger.log_doc_sync("文档同步完成")
            
            print("")
            return True
            
        if text == '/logs':
            self.logger.log_command(self.user_id, "/logs")
            print("\n📄 今日日志文件:")
            logs = self.logger.get_today_logs()
            total = 0
            for cat, path in logs.items():
                if path.exists():
                    lines = path.read_text(encoding="utf-8").strip().split("\n")
                    count = len(lines) if lines[0] else 0
                    total += count
                    print(f"  • [{cat:8s}] {path} ({count} 条)")
                else:
                    print(f"  • [{cat:8s}] {path} (0 条)")
            print(f"\n   总计: {total} 条记录")
            print("\n   可用子命令:")
            print("     /logs runtime  — 查看运行日志")
            print("     /logs error    — 查看错误日志")
            print("     /logs schedule — 查看调度日志")
            print("     /logs role     — 查看角色通信日志")
            print("     /logs system   — 查看系统日志\n")
            return True
            
        if text.startswith('/logs '):
            cat = text.split()[1].strip()
            self.logger.log_command(self.user_id, f"/logs {cat}")
            logs = self.logger.get_today_logs(cat)
            path = logs.get(cat)
            if path and path.exists():
                print(f"\n📄 [{cat}] 今日日志 ({path}):\n")
                lines = path.read_text(encoding="utf-8").strip().split("\n")
                for line in lines[-20:]:
                    print(f"   {line}")
                print("")
            else:
                print(f"\n📄 [{cat}] 暂无记录\n")
            return True
            
        if text == '/reload':
            self.logger.log_command(self.user_id, "/reload")
            print("\n[系统] 正在重新加载服务...")
            self.logger.info("系统", "开始重新加载服务...")
            self.initialize()
            self.logger.log_service_reload()
            print("\n[系统] ✅ 服务已重新加载，角色记忆已保留")
            print("   各角色 role.db 独立存储，新会话自动继承\n")
            self._code_changed_notified = False
            return True
            
        if text == '/clear':
            print("\033[2J\033[H", end="")
            self.print_banner()
            return True
            
        return True
        
    async def handle_user_input(self, text: str):
        """处理用户输入"""
        if text.startswith('/'):
            return self.handle_command(text)
        
        # 未配置模型时阻止普通输入，引导用户配置
        default_model = self.model_manager.get_default_model()
        if not default_model:
            self.logger.warn("系统", "用户输入被阻止：未配置模型")
            print(f"\n[suri] ⚠️ 未配置模型，无法处理您的输入。")
            print(f"[suri] 请先配置模型，两种方式：")
            print(f"  1. 重启程序，按引导配置（推荐）")
            print(f"  2. 输入 /model add 手动添加\n")
            return True
            
        # 记录用户输入
        self.logger.log_user_input(self.user_id, text)
        
        # 创建任务
        task_id = self.task.receive_task(self.user_id, text)
        self.logger.log_task_created(task_id, self.user_id, text)
        print(f"\n[suri] 已接收任务 {task_id}")
        print(f"[suri] 正在分析需求: {text[:60]}...")
        
        # 调用外部模型生成回复
        self.logger.log_model_call(default_model.name, default_model.model_id, "开始")
        messages = [
            {"role": "system", "content": (
                "你是 Suri，一个智能体平台的中枢调度助手。"
                "你负责理解用户需求，分配任务给合适的角色，并给出清晰的回复。"
                "当前平台有 suri（中枢）、suri-hr（人力资源）、suri-dev（开发）三个核心角色。"
            )},
            {"role": "user", "content": text},
        ]
        print(f"[suri] 正在调用模型 ({default_model.name}) 生成回复...")
        reply = self.model_manager.chat(messages)
        if reply:
            self.logger.log_model_call(default_model.name, default_model.model_id, "成功", f"回复长度={len(reply)}")
            print(f"\n[suri] {reply}\n")
        else:
            self.logger.log_model_call_error(default_model.name, "API 返回空或无网络")
            print(f"\n[suri] 模型调用失败，请检查 API Key 和网络连接。\n")
        
        return True
        
    def _compute_code_snapshot(self) -> str:
        """计算 suri-agent/ 下所有 .py 文件的修改时间哈希，用于检测代码变更"""
        agent_dir = self.project_root / "suri-agent"
        if not agent_dir.exists():
            return ""
        mtime_sum = 0.0
        for f in agent_dir.rglob("*.py"):
            try:
                mtime_sum += f.stat().st_mtime
            except Exception:
                pass
        return f"{mtime_sum:.6f}"
    
    def _check_code_change(self) -> bool:
        """检查代码是否发生变更"""
        current = self._compute_code_snapshot()
        return current != self._code_snapshot
    
    async def run(self):
        """主循环"""
        self.initialize()
        self.print_banner()
        
        running = True
        while running:
            try:
                # 代码变更检测
                if self._check_code_change() and not self._code_changed_notified:
                    self.logger.log_code_change_detected()
                    print("\n⚠️ [系统] 检测到核心代码已变更")
                    print("   输入 /reload 重新加载服务，角色记忆将保留")
                    print("")
                    self._code_changed_notified = True
                
                text = input("您 > ").strip()
                if not text:
                    continue
                running = await self.handle_user_input(text)
            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except EOFError:
                break
        
        # 退出时停止文档监控
        if self.doc_watcher:
            self.doc_watcher.stop()
            self.logger.info("系统", "文档监控已停止")


async def main():
    terminal = SuriTerminal()
    await terminal.run()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
