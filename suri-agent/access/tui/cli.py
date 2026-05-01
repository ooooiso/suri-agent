#!/usr/bin/env python3
"""
Suri 终端客户端

关联文档: suri-agent/access/tui/tui.md

简易的命令行交互界面，直接调用 suri-agent 核心服务。
无需启动 JSON-RPC 后端，直接在进程中与 suri 对话。

使用方式:
    python -m suri-agent.access.tui.cli
    或: python suri-agent/access/tui/cli.py
"""

import sys
import readline  # 改善终端输入体验（支持中文退格删除、光标移动）
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

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
from model.manager import ModelManager
from core.doc_sync import DocSyncService
from rules.doc_sync_rule import DocSyncRule
from hooks.doc_watcher import DocWatcher
from core.tool_executor import ToolService
from access.output import OutputRouter, OutputChannel


class CreationDialog:
    """
    创建对话状态机 — 管理部门/角色/技能的多轮对话创建流程
    
    状态流转：
    idle → creating(step 0: 确认) → creating(step N: 收集字段) → confirming → executing → idle
    """
    
    PROMPTS = {
        'create_dept': [
            "未找到处理该需求的部门。是否需要创建新部门？请回复：是 / 否",
            "请描述新部门的名称：",
            "请描述该部门的职责范围：",
            "请指定部门负责人（role_id，如 suri_hr）：",
        ],
        'create_role': [
            "[{dept}] 暂无处理此类需求的角色。是否需要创建新角色？请回复：是 / 否",
            "请描述新角色的名称：",
            "请描述该角色的工作内容/职责：",
        ],
        'add_skill': [
            "[{role}] 暂无匹配技能。是否需要为其增加新技能？请回复：是 / 否",
            "请描述新技能的名称：",
            "请描述该技能的功能和触发条件：",
        ],
    }
    
    def __init__(self, terminal: 'SuriTerminal'):
        self.terminal = terminal
        self.reset()
    
    def reset(self):
        self.state = 'idle'
        self.action = None
        self.data = {}
        self.step = 0
    
    def start(self, action: str, **context) -> str:
        """开始创建对话，返回第一个问题"""
        self.state = 'creating'
        self.action = action
        self.data = {'context': context}
        self.step = 0
        return self._get_prompt()
    
    def handle_input(self, text: str) -> str:
        """
        处理用户输入，返回下一步提示或状态标记。
        返回值格式：
        - 以 "[CREATION]" 开头表示需要继续对话
        - "[COMPLETE]" 表示对话完成，可以执行创建
        - "[CANCELLED]" 表示用户取消
        """
        text = text.strip()
        text_lower = text.lower()
        
        # 全局取消命令
        if text_lower in ('取消', 'cancel', '不', '否', 'no', 'n'):
            if self.step == 0:
                self.reset()
                return "[CANCELLED]"
            # 在后续步骤中，如果用户说取消，回到确认阶段或取消
            if '取消' in text or 'cancel' in text_lower:
                self.reset()
                return "[CANCELLED]"
        
        # 确认阶段
        if self.state == 'confirming':
            if text_lower in ('确认', '是', 'yes', 'y', 'ok', '好'):
                return "[COMPLETE]"
            elif text_lower in ('修改', 'change', '改'):
                self.step = 1
                self.state = 'creating'
                # 清除之前的数据，重新收集
                self.data = {'context': self.data.get('context', {})}
                return f"[CREATION]{self._get_prompt()}"
            else:
                self.reset()
                return "[CANCELLED]"
        
        # 创建阶段 — 第一步：确认是否创建
        if self.step == 0:
            if text_lower in ('是', 'yes', 'y', '好', '可以', 'ok'):
                self.step = 1
                return f"[CREATION]{self._get_prompt()}"
            else:
                self.reset()
                return "[CANCELLED]"
        
        # 创建阶段 — 收集字段
        self.data[f'field_{self.step}'] = text
        
        prompts = self.PROMPTS.get(self.action, [])
        if self.step + 1 < len(prompts):
            self.step += 1
            return f"[CREATION]{self._get_prompt()}"
        
        # 所有字段收集完成，进入确认阶段
        self.state = 'confirming'
        summary = self._build_summary()
        return f"[CREATION]{summary}\n\n请确认以上信息是否正确？回复：确认 / 修改 / 取消"
    
    def _get_prompt(self) -> str:
        prompts = self.PROMPTS.get(self.action, [])
        if self.step < len(prompts):
            prompt = prompts[self.step]
            ctx = self.data.get('context', {})
            prompt = prompt.replace('{dept}', ctx.get('dept', '未知部门'))
            prompt = prompt.replace('{role}', ctx.get('role', '未知角色'))
            return prompt
        return ""
    
    def _build_summary(self) -> str:
        if self.action == 'create_dept':
            return (
                f"【新建部门确认】\n"
                f"名称: {self.data.get('field_1', '')}\n"
                f"职责: {self.data.get('field_2', '')}\n"
                f"负责人: {self.data.get('field_3', '')}"
            )
        elif self.action == 'create_role':
            return (
                f"【新建角色确认】\n"
                f"名称: {self.data.get('field_1', '')}\n"
                f"职责: {self.data.get('field_2', '')}\n"
                f"所属部门: {self.data.get('context', {}).get('dept', 'central')}"
            )
        elif self.action == 'add_skill':
            return (
                f"【新增技能确认】\n"
                f"角色: {self.data.get('context', {}).get('role', '')}\n"
                f"技能名称: {self.data.get('field_1', '')}\n"
                f"功能描述: {self.data.get('field_2', '')}"
            )
        return ""
    
    def execute(self) -> str:
        """执行创建操作"""
        return self.terminal._execute_creation(self.action, self.data)


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
        self.tool_service = None
        self.output_router = None
        self.user_id = f"terminal_user_{datetime.now().strftime('%H%M%S')}"
        self._code_snapshot = None
        self._code_changed_notified = False
        self.creation_dialog = None  # V3.0: 创建对话状态机
        
    def initialize(self):
        """初始化服务"""
        # 日志服务（最先初始化，确保后续日志可记录）
        self.logger = LoggerService(self.project_root)
        self.logger.info("系统", "开始初始化服务...")
        
        # ==== 核心角色 suri 存在性检查（mandatory）====
        suri_soul = self.project_root / "group" / "central" / "suri" / "suri.md"
        if not suri_soul.exists():
            print("\n❌ [致命错误] 找不到核心角色 suri")
            print(f"   期望路径: {suri_soul}")
            print("   suri 是 central 部门负责人，也是所有部门的中枢。")
            print("   没有 suri，程序无法启动。\n")
            self.logger.error("系统", "suri 角色 Soul 文件缺失，程序终止")
            sys.exit(1)
        
        self.config = ConfigService(self.project_root)
        self.config.load_all()
        
        self.memory = MemoryService(self.project_root, self.config)
        self.security = SecurityService(self.project_root, self.config)
        self.filesystem = FileService(self.project_root, self.security)
        self.model = ModelService(self.config)
        self.context = ContextService(self.config, self.memory)
        # TaskService 需要 CommService 作为第5个参数，cli 模式下暂不连接 Telegram
        # 传 None 作为 comm，logger 作为第6个参数
        self.task = TaskService(self.config, self.memory, self.context, self.model, None, self.logger)
        
        # 模型管理器
        self.model_manager = ModelManager(self.project_root)
        
        # 文档同步服务
        self.doc_sync = DocSyncService(self.model_manager, self.project_root)
        
        # 文档同步规则引擎
        self.doc_sync_rule = DocSyncRule(self.project_root, self.model_manager)
        
        # 文档监控钩子
        self.doc_watcher = DocWatcher(self.project_root)
        
        # 工具服务
        self.tool_service = ToolService(self.project_root, self.config)
        
        # 输出框架 — 从 Soul 文件动态构建角色路由
        role_routes = self._build_dynamic_routes()
        self.output_router = OutputRouter(
            self.project_root, self.memory, self.security, self.logger,
            role_routes=role_routes, config=self.config
        )
        
        # ==== V3.0 任务管理与多Agent系统 ====
        from core.task_state import TaskStateService
        from core.task_plan import TaskPlanService
        from core.agent_registry import AgentRegistry
        from core.state_card import StateCardRenderer
        from core.message_bus import MessageBus
        from core.interrupt_handler import InterruptHandler
        from core.department_registry import DepartmentRegistry
        
        self.task_state = TaskStateService(self.project_root)
        self.task_plan = TaskPlanService(self.config)
        self.agent_registry = AgentRegistry(self.project_root, self.task_state, self.config)
        self.state_card = StateCardRenderer(self.task_state)
        self.message_bus = MessageBus(self.project_root)
        self.interrupt_handler = InterruptHandler(self.task_state, self.message_bus, self.config)
        self.department_registry = DepartmentRegistry(self.project_root)
        self.creation_dialog = CreationDialog(self)
        
        self.logger.info("系统", "V3.0 任务管理与多Agent系统初始化完成")
        
        # 首次运行引导 — 强制配置模型（无模型无法工作）
        if self.model_manager.is_first_run():
            import sys as _sys
            if not _sys.stdin.isatty():
                print("\n⚠️ 首次运行且非交互环境，无法自动配置模型。")
                print("   请手动运行 ./suri 在终端中配置，或使用 /model add 命令。")
                print("")
            else:
                while self.model_manager.is_first_run():
                    self.logger.info("配置", "首次运行，启动模型配置引导")
                    if self.model_manager.setup_wizard():
                        break
                    print("\n⚠️ 模型配置未完成，suri 无法调用外部模型。")
                    print("   您必须配置至少一个模型才能继续使用。")
                    print("")
        
        roles_count = len(self.config.list_roles())
        self.logger.log_startup(roles_count)
        print(f"[就绪] 已加载 {roles_count} 个角色")
        print(f"[就绪] 核心角色 suri (central 负责人) 已就绪")
        print("")
        
        # 记录代码快照
        self._code_snapshot = self._compute_code_snapshot()
        self._code_changed_notified = False
        
        # 启动文档监控
        self.doc_watcher.start()
        self.logger.info("系统", "文档监控已启动")
        
        # 启动时自动运行文档同步检查 — 强制提示未同步的文档
        try:
            violations = self.doc_sync_rule.scan()
            if violations:
                self.logger.warn("系统", f"启动检测到 {len(violations)} 个文档同步违规项")
                print(f"\n{'='*50}")
                print("⚠️  [文档同步警告] 检测到以下文档未同步更新：")
                print(f"{'='*50}")
                for v in violations[:5]:
                    marker = "❌ 缺失" if v.violation_type == "missing" else "⚠️ 过时"
                    print(f"  {marker} {v.doc_path} ← {v.code_path}")
                if len(violations) > 5:
                    print(f"  ... 还有 {len(violations) - 5} 项")
                print(f"\n  输入 /sync 查看详情并生成同步计划")
                print(f"  遵守规则：代码变更必须同步更新文档（suri-dev 绝对规则 #1）")
                print(f"{'='*50}\n")
        except Exception as e:
            self.logger.error("系统", f"启动时文档同步检查失败: {e}")
        
    # 命令注册表 — 新增命令只需在这里注册，/help 自动生成
    _COMMAND_REGISTRY = {
        '/help':        '显示此帮助',
        '/roles':       '列出所有角色',
        '/rules':       '列出所有规则',
        '/tasks':       '查看任务列表',
        '/status':      '查看平台状态',
        '/model':       '模型管理（添加/删除/配置向导）',
        '/models':      '交互式浏览模型并切换默认模型',
        '/sync':        '文档同步检查',
        '/clear':       '清屏',
        '/quit':        '退出',
    }
    
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
            for cmd, desc in self._COMMAND_REGISTRY.items():
                print(f"  {cmd:12s} - {desc}")
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
            # 无参数：直接启动配置向导
            print("\n>>> 启动模型配置向导...")
            success = self.model_manager.setup_wizard()
            if success:
                print("✅ 模型配置已更新。新配置立即生效，无需重启。\n")
            else:
                print("⚠️ 配置未完成，当前模型设置保持不变。\n")
            return True
            
        if text.startswith('/model add'):
            from model.manager import MODEL_MENU
            
            print("\n添加模型：")
            print("")
            print("请选择模型品牌：")
            print("")
            
            for key, info in MODEL_MENU.items():
                primary_name = info["primary"][0]
                print(f"  {key}) {info['brand']}（首选: {primary_name}）")
            print(f"  0) 自定义")
            print("")
            
            choice = input("输入选项 [0-5]: ").strip()
            if choice == "0":
                # 自定义模型
                print("\n自定义模型配置：")
                name = input("显示名称: ").strip()
                model_id = input("模型 ID: ").strip()
                base_url = input("API 端点: ").strip()
                provider = input("提供商名称: ").strip() or "custom"
                api_key = input("API Key: ").strip()
                if not all([name, model_id, base_url, api_key]):
                    print("❌ 所有字段必填")
                    print("")
                    return True
            else:
                brand_info = MODEL_MENU.get(choice)
                if not brand_info:
                    print("❌ 无效选项")
                    print("")
                    return True
                
                print(f"\n请输入您的 {brand_info['brand']} API Key：")
                api_key = input("API Key: ").strip()
                if not api_key:
                    print("❌ API Key 不能为空")
                    print("")
                    return True
                
                # 自动测试并选择可用型号
                print("\n正在验证 API Key 并测试可用型号...")
                result = self.model_manager._test_api_key(brand_info, api_key)
                
                if result is None:
                    print("\n❌ API Key 无效或该品牌下所有型号均不可用。")
                    print("   请检查 Key 是否正确，或更换品牌重试。\n")
                    return True
                
                name, model_id = result
                provider = brand_info["provider"]
                base_url = brand_info["base_url"]
            
            # 询问是否设为默认
            is_default = False
            if not self.model_manager.list_models():
                is_default = True
                print("（首个模型，自动设为默认）")
            else:
                choice = input("设为默认模型? [y/N]: ").strip().lower()
                is_default = choice in ('y', 'yes')
            
            self.model_manager.add_model(
                name, model_id, api_key, base_url, provider,
                is_default=is_default
            )
            print(f"\n✅ 模型 {name} ({model_id}) 已添加{'并设为默认' if is_default else ''}\n")
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
        
        if text == '/models':
            self.logger.log_command(self.user_id, "/models")
            # 通过 ToolService 调用 model_manager 工具
            result = self.tool_service.execute('model_manager', {'action': 'list'})
            if not result['success']:
                print(f"\n❌ 获取模型列表失败: {result.get('error')}\n")
                return True
            
            data = result['data']
            groups = data.get('groups', {})
            if not groups:
                print("\n  暂无配置模型\n")
                return True
            
            print("\n已配置模型：")
            idx = 1
            index_map = {}
            for type_key in sorted(groups.keys()):
                desc = data.get('type_descriptions', {}).get(type_key, type_key)
                print(f"\n  [{type_key}] {desc}")
                for m in groups[type_key]:
                    marker = " ⭐默认" if m['is_default'] else ""
                    caps = ", ".join(m.get('capabilities', []))
                    print(f"    {idx}) {m['name']} ({m['model_id']}){marker}")
                    print(f"       品牌: {m['provider']} | 能力: {caps} | 成本: {m['cost_tier']}")
                    index_map[str(idx)] = m['model_id']
                    idx += 1
            
            print("")
            choice = input("输入编号切换默认模型，或按回车取消: ").strip()
            if choice in index_map:
                model_id = index_map[choice]
                switch_result = self.tool_service.execute('model_manager', {
                    'action': 'switch',
                    'model_id': model_id
                })
                if switch_result['success']:
                    name = switch_result['data'].get('name', model_id)
                    print(f"\n✅ 已切换默认模型: {name} ({model_id})\n")
                else:
                    print(f"\n❌ 切换失败: {switch_result.get('error')}\n")
            else:
                print("\n已取消切换。\n")
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
            
            # 3. 自动生成 group_function.md（角色索引从 Soul 文件扫描）
            try:
                gf_content = self.config.sync_group_function()
                gf_path = self.project_root / "group" / "group_function.md"
                
                # 比较是否有变化
                old_content = gf_path.read_text(encoding="utf-8") if gf_path.exists() else ""
                if gf_content != old_content:
                    choice = input("检测到角色信息有变更，是否更新 group_function.md? [Y/n]: ").strip().lower()
                    if choice in ('', 'y', 'yes'):
                        gf_path.write_text(gf_content, encoding="utf-8")
                        print("✅ group_function.md 已更新\n")
                        self.logger.info("系统", "group_function.md 已自动生成")
                    else:
                        print("已跳过 group_function.md 更新\n")
                else:
                    print("✅ group_function.md 已是最新\n")
            except Exception as e:
                self.logger.error("系统", f"生成 group_function.md 失败: {e}")
            
            # 4. 执行传统 doc_sync（变更摘要生成）
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
            self._perform_reload(reason="用户手动触发")
            
    def _perform_reload(self, reason: str = "用户手动触发") -> None:
        """
        执行进程热重载
        
        使用 os.execv 重启当前进程，加载全新代码。
        角色记忆等持久化数据将保留（存储在 SQLite 中）。
        
        Args:
            reason: 触发原因，用于日志记录
        """
        print(f"\n[系统] 正在重新加载服务...（{reason}）")
        self.logger.info("系统", f"开始重新加载服务...（{reason}）")
        
        # 清理资源，确保重启前状态干净
        if self.doc_watcher:
            self.doc_watcher.stop()
        if self.model_manager:
            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(self.model_manager.close())
            except Exception:
                pass
        
        # 真正的热重载：用 os.execv 重启当前进程，加载全新代码
        import os, sys
        self.logger.info("系统", "执行进程热重载 (os.execv)")
        print("[系统] ✅ 进程已重启，新代码已加载\n")
        os.execv(sys.executable, [sys.executable] + sys.argv)
            
        if text == '/clear':
            print("\033[2J\033[H", end="")
            self.print_banner()
            return True
            
        return True
        
    async def handle_user_input(self, text: str):
        """
        处理用户输入
        
        终端(cli)是接入层，只负责接收输入和显示输出。
        所有业务逻辑交给 suri 角色处理（suri_process）。
        """
        if text.startswith('/'):
            return self.handle_command(text)
        
        # 未配置模型时阻止普通输入，引导用户配置
        default_model = self.model_manager.get_default_model()
        if not default_model:
            self.logger.warn("系统", "用户输入被阻止：未配置模型")
            self.output_router.deliver_alert(
                "⚠️ 未配置模型，无法处理您的输入。请先配置模型：1.重启程序按引导配置 2.输入 /model add 手动添加",
                role_id='suri',
                priority='high',
                target_channels=[OutputChannel.TERMINAL]
            )
            return True
        
        # 记录用户输入
        self.logger.log_user_input(self.user_id, text)
        
        # 交给 suri 角色处理
        try:
            await self.suri_process(text)
        except Exception as e:
            self.logger.error("suri_process", f"处理用户输入时出错: {e}")
            self.output_router.deliver_alert(
                f"❌ 处理出错: {e}。输入 /model 可重新配置模型，或稍后重试。",
                role_id='suri',
                priority='high',
                target_channels=[OutputChannel.TERMINAL]
            )
        return True
    
    async def suri_process(self, text: str, user_id: str = "") -> None:
        """
        suri 角色处理流程（支持多用户并发隔离）
        
        多用户场景下，通过 user_id 区分不同用户，各自维护独立的 session。
        每个用户的消息历史相互隔离，避免上下文混淆。
        
        调度链：
        用户 → suri → 部门总监 → 成员 → 结果回流 suri → 用户
        """
        effective_user_id = user_id or self.user_id
        
        # 1. 获取或创建会话（多用户隔离核心）
        session_id = self._get_or_create_session(effective_user_id)
        
        # 2. 创建任务
        task_id = self.task.receive_task(effective_user_id, text, session_id=session_id)
        self.logger.log_task_created(task_id, effective_user_id, text)
        
        # ==== V3.0: 创建 Agent + 生成任务规划 ====
        agent = self.agent_registry.create_agent(
            task_text=text,
            user_id=effective_user_id,
            task_id=task_id,
        )
        
        # 先检测调度目标，生成规划
        dispatch_targets = await self._detect_dispatch_target(text, "")
        plan = self.task_plan.generate_plan(text, dispatch_targets)
        
        # 更新 Agent 步骤
        self.agent_registry.update_agent_steps(agent.agent_id, plan.steps)
        self.agent_registry.update_step(agent.agent_id, "step_1", "in_progress")
        
        # V3.0: 显示任务规划（单任务时展示步骤分解）
        if plan.steps:
            plan_card = self.state_card.render_single_task(agent)
            self.output_router.deliver_text(
                plan_card,
                role_id='suri',
                task_id=task_id,
                user_id=effective_user_id,
                session_id=session_id,
                target_channels=[OutputChannel.TERMINAL]
            )
        
        # 3. suri 调用模型分析需求
        default_model = self.model_manager.get_default_model()
        self.logger.log_model_call(default_model.name, default_model.model_id, "开始", "suri 分析需求")
        
        # 构建 suri 的系统提示（注入学习经验、历史记忆、规则，按 session 隔离）
        current_task = {'task_id': task_id, 'requirement': text}
        model_info = {
            'name': default_model.name,
            'model_id': default_model.model_id,
            'provider': default_model.provider,
        }
        suri_base_prompt = self.context.build_context(
            'suri', current_task=current_task, model_info=model_info, session_id=session_id
        )
        
        # 动态生成调度规则（从所有角色的 Soul 读取 keywords，新增角色无需改代码）
        dispatch_rules = []
        all_roles = [rid for rid in self.config.list_roles() if rid != 'suri']
        for role_id in all_roles:
            kws = self.config.get_role_keywords(role_id)
            soul = self.config.get_role_soul(role_id)
            name = soul.meta.get('name', role_id) if soul else role_id
            if kws:
                kw_str = '、'.join(kws[:5])
                dispatch_rules.append(f"- 用户问'{kw_str}'等 → 由 {name}（{role_id}）处理，不要自己回答")
        
        dispatch_instructions = (
            "\n\n---\n\n"
            "调度规则（你必须遵守）：\n"
            "- 用户问关于你自身的问题（你是谁、用的什么模型、你能做什么）→ 直接回答，不要调度\n"
            "- 闲聊、问候、简单事实问答 → 直接回答，不要调度\n"
            + '\n'.join(dispatch_rules) +
            "\n- 如果需求涉及多个角色，请明确列出所有相关角色名（用逗号分隔）\n"
            "- 请用简洁的中文回复，直接给出结果\n"
            "- 你（suri）绝不直接查询数据库、调用工具、或生成统计数据。所有数据查询必须由对应角色执行"
        )
        suri_system_prompt = suri_base_prompt + dispatch_instructions
        
        messages = [
            {"role": "system", "content": suri_system_prompt},
            {"role": "user", "content": text},
        ]
        
        reply = None
        try:
            result = await self.model_manager.chat_with_usage(messages)
            if result:
                reply = result.get('content')
                if self.logger and default_model:
                    self.logger.log_token_usage(
                        model_id=default_model.model_id,
                        prompt_tokens=result.get('prompt_tokens', 0),
                        completion_tokens=result.get('completion_tokens', 0),
                        total_tokens=result.get('total_tokens', 0),
                        task_hint=f"suri分析:{text[:30]}",
                        role_id='suri'
                    )
        except Exception as e:
            self.logger.log_model_call_error(default_model.name, f"调用异常: {e}")
            self.output_router.deliver_alert(
                f"⚠️ 模型调用异常（{default_model.name}）: {e}",
                role_id='suri',
                priority='high',
                target_channels=[OutputChannel.TERMINAL]
            )
        
        if not reply:
            self.output_router.deliver_alert(
                f"⚠️ 模型调用失败（{default_model.name} 不可用）。可能原因：API Key 错误、网络问题、模型服务限流或欠费。",
                role_id='suri',
                priority='high',
                target_channels=[OutputChannel.TERMINAL]
            )
            
            fix_now = input("是否立即配置新模型？ [Y/n]: ").strip().lower()
            if fix_now in ('', 'y', 'yes'):
                print(">>> 启动模型配置向导...")
                success = self.model_manager.setup_wizard()
                if success:
                    print("✅ 新模型已配置，您可以重新输入刚才的问题。\n")
                else:
                    print("⚠️ 配置未完成。您可以稍后输入 /model 重新配置。\n")
            else:
                self.output_router.deliver_text(
                    "已跳过。输入 /model 可随时重新配置。",
                    role_id='suri',
                    target_channels=[OutputChannel.TERMINAL]
                )
            return
        
        self.logger.log_model_call(default_model.name, default_model.model_id, "成功", f"回复长度={len(reply)}")
        
        # 4. 输出对话内容（通过输出框架统一投递）
        # V3.0: suri 回复后追加状态卡片
        state_card = self.state_card.render(effective_user_id, compact=True)
        final_reply = reply
        if state_card:
            final_reply = f"{reply}\n\n{state_card}"
        
        self.output_router.deliver_text(
            final_reply,
            role_id='suri',
            task_id=task_id,
            user_id=effective_user_id,
            session_id=session_id,
            target_channels=[OutputChannel.TERMINAL]
        )
        
        # 5. 调度判断 + 创建流程检查点
        dispatch_targets = await self._detect_dispatch_target(text, reply)
        
        # 检查点1：部门匹配
        if not dispatch_targets:
            dept_match = self._check_department_match(text)
            if not dept_match:
                # 无匹配部门，触发创建部门对话
                question = self.creation_dialog.start('create_dept')
                print(f"\nSuri > {question}")
                return
            else:
                # 有部门但无匹配角色，触发创建角色对话
                question = self.creation_dialog.start('create_role', dept=dept_match)
                print(f"\nSuri > {question}")
                return
        
        # 检查点2：技能匹配
        for target_role in dispatch_targets:
            skills = self.config.list_role_skills(target_role)
            if not skills:
                # 角色无技能，触发增加技能对话
                question = self.creation_dialog.start('add_skill', role=target_role)
                print(f"\nSuri > {question}")
                return
            skill_details = [self.config.get_skill_detail(target_role, s) for s in skills]
            if not self._skill_matches(text, skill_details):
                # 技能不匹配，触发增加技能对话
                question = self.creation_dialog.start('add_skill', role=target_role)
                print(f"\nSuri > {question}")
                return
        
        if dispatch_targets:
            all_results = []
            for target_role in dispatch_targets:
                role_result = await self._execute_dispatch(
                    task_id, text, reply, target_role, session_id=session_id, 
                    agent_id=agent.agent_id if agent else ''
                )
                if role_result:
                    all_results.append((target_role, role_result))
            
            # 6. 结果回流
            if all_results:
                if len(all_results) == 1:
                    summary = await self._summarize_result(
                        task_id, text, all_results[0][0], all_results[0][1]
                    )
                else:
                    summary = await self._summarize_multi_result(task_id, text, all_results)
                if summary:
                    self.output_router.deliver_text(
                        summary,
                        role_id='suri',
                        task_id=task_id,
                        user_id=effective_user_id,
                        session_id=session_id,
                        target_channels=[OutputChannel.TERMINAL]
                    )
        
        # 7. 任务完成
        self.memory.update_task_status('suri', task_id, 'completed')
        task_duration = 0  # 简化：当前不追踪精确耗时
        self.logger.log_task_completed(task_id, 'suri', 'completed', task_duration)
        self.logger.log_task_dispatched(task_id, 'suri', effective_user_id, 'central')
        
        # V3.0: 更新 Agent 状态为 completed（所有步骤执行完成后自动更新）
        if agent:
            # 检查是否所有步骤已完成或阻塞
            all_done = True
            for s in agent.steps:
                if s.status not in ('completed', 'blocked'):
                    all_done = False
                    break
            if all_done:
                self.agent_registry.update_agent_status(agent.agent_id, "completed")
        
        # V3.0: 保存 suri 经验卡片
        try:
            self.memory.save_experience(
                role_id='suri',
                task_id=task_id,
                action=f"任务完成: {text[:50]}",
                result=reply[:200] if reply else "",
                feedback="success",
                tags="task,complete"
            )
        except Exception:
            pass  # 经验记录失败不应阻塞主流程
        
        # V3.0: 最终状态卡片（显示所有活跃 Agent 状态）
        final_state_card = self.state_card.render(effective_user_id, compact=True)
        if final_state_card:
            self.output_router.deliver_text(
                f"\n{final_state_card}",
                role_id='suri',
                task_id=task_id,
                user_id=effective_user_id,
                session_id=session_id,
                target_channels=[OutputChannel.TERMINAL]
            )
        
        # V3.0: 任务完成后检测代码变更，如有变更自动刷新
        if self._check_code_change():
            print("\n⚠️ [系统] 检测到核心代码已更新，正在自动刷新...")
            self._perform_reload(reason="任务完成后检测到代码变更")
    
    def _build_dynamic_routes(self) -> Dict[str, List[OutputChannel]]:
        """
        从所有角色的 Soul 文件动态构建输出路由映射
        
        新增角色只需在 Soul frontmatter 中声明 output_channels，
        无需修改此文件。
        """
        routes: Dict[str, List[OutputChannel]] = {}
        channel_map = {
            'terminal': OutputChannel.TERMINAL,
            'file': OutputChannel.FILE,
            'logger': OutputChannel.LOGGER,
            'memory': OutputChannel.MEMORY,
            'telegram': OutputChannel.TELEGRAM,
            'webhook': OutputChannel.WEBHOOK,
        }
        for role_id in self.config.list_roles():
            if role_id == 'suri':
                continue
            channels_cfg = self.config.get_role_output_channels(role_id)
            if channels_cfg:
                channels = []
                for ch_name in channels_cfg:
                    ch = channel_map.get(ch_name.lower())
                    if ch:
                        channels.append(ch)
                if channels:
                    routes[role_id] = channels
            # 如果 Soul 中未声明 output_channels，保持空（使用 OutputRouter 回退）
        return routes
    
    async def _detect_dispatch_target(self, text: str, suri_reply: str) -> List[str]:
        """
        检测应该调度到哪些角色（支持多角色协作）
        
        双层匹配策略：
        1. suri 回复中明确包含角色 ID（最高优先级）
        2. 关键词匹配用户输入（收集所有匹配角色）
        
        返回按优先级排序的角色 ID 列表，或空列表（不需要调度）
        """
        all_roles = [rid for rid in self.config.list_roles() if rid != 'suri']
        suri_reply_lower = suri_reply.lower()
        user_text_lower = text.lower()
        matched_roles: List[str] = []
        seen = set()
        
        # 第一层：suri 回复中明确包含角色 ID（最高优先级）
        for rid in all_roles:
            if rid in suri_reply_lower and rid not in seen:
                matched_roles.append(rid)
                seen.add(rid)
        
        # 第二层：关键词匹配用户输入（收集所有匹配角色）
        for role_id in all_roles:
            if role_id in seen:
                continue
            keywords = self.config.get_role_keywords(role_id)
            for kw in keywords:
                if kw.lower() in user_text_lower:
                    matched_roles.append(role_id)
                    seen.add(role_id)
                    break
        
        return matched_roles
    
    async def _execute_step(self, task_id: str, agent_id: str, step: 'TaskStep', session_id: str = '') -> bool:
        """
        执行单个步骤
        
        1. 更新步骤状态: pending → in_progress
        2. 构建步骤专用 prompt
        3. 调用模型执行该步骤
        4. 保存步骤结果
        5. 更新步骤状态: in_progress → completed / blocked
        
        Returns:
            True 如果步骤成功完成，False 如果步骤受阻
        """
        from core.task_state import TaskStep
        
        # 检查依赖是否满足
        if step.depends_on:
            agent = self.agent_registry.get_agent(agent_id)
            if agent:
                completed_steps = {s.step_id for s in agent.steps if s.status == 'completed'}
                for dep_id in step.depends_on:
                    if dep_id not in completed_steps:
                        self.agent_registry.update_step(agent_id, step.step_id, 'blocked', 
                                                        block_reason=f'依赖步骤 {dep_id} 未完成')
                        return False
        
        # 更新状态: pending → in_progress
        self.agent_registry.update_step(agent_id, step.step_id, 'in_progress')
        
        # 获取角色 Soul
        role_soul = self.config.get_role_soul(step.assignee)
        if not role_soul:
            self.agent_registry.update_step(agent_id, step.step_id, 'blocked',
                                            block_reason=f'角色 {step.assignee} 未配置')
            return False
        
        # 构建步骤专用 prompt
        default_model = self.model_manager.get_default_model()
        model_info = None
        if default_model:
            model_info = {
                'name': default_model.name,
                'model_id': default_model.model_id,
                'provider': default_model.provider,
            }
        
        current_task = {
            'task_id': task_id,
            'requirement': step.description,
        }
        
        role_prompt = self.context.build_context(step.assignee, current_task=current_task, 
                                                  model_info=model_info, session_id=session_id)
        
        # 注入步骤方法论
        step_prompt = (
            f"{role_prompt}\n\n---\n\n"
            f"当前步骤：{step.description}\n"
            f"请直接给出该步骤的专业处理结果，用简洁的中文回复。"
        )
        
        messages = [
            {"role": "system", "content": step_prompt},
            {"role": "user", "content": step.description},
        ]
        
        # 调用模型执行步骤
        try:
            model_result = await self.model_manager.chat_with_usage(messages)
            result = model_result.get('content') if model_result else None
        except Exception as e:
            self.logger.log_model_call_error(step.assignee, f"步骤执行异常: {e}")
            self.agent_registry.update_step(agent_id, step.step_id, 'blocked',
                                            block_reason=f'模型调用异常: {e}')
            return False
        
        if result:
            # 保存结果到步骤
            step.result = result[:500]  # 摘要保存
            self.agent_registry.update_step(agent_id, step.step_id, 'completed')
            
            # 投递结果到终端
            self.output_router.deliver_text(
                result,
                role_id=step.assignee,
                task_id=task_id,
                target_channels=[OutputChannel.TERMINAL]
            )
            
            # 广播状态更新
            self.message_bus.broadcast_status(
                sender=step.assignee,
                content=f"完成步骤 [{step.step_id}]: {step.description[:30]}",
                task_id=task_id,
            )
            
            # 实时状态卡片
            agent = self.agent_registry.get_agent(agent_id)
            if agent:
                plan_card = self.state_card.render_single_task(agent)
                if plan_card:
                    self.output_router.deliver_text(
                        f"\n{plan_card}",
                        role_id='suri',
                        task_id=task_id,
                        target_channels=[OutputChannel.TERMINAL]
                    )
            
            return True
        else:
            self.agent_registry.update_step(agent_id, step.step_id, 'blocked',
                                            block_reason='模型返回空结果')
            return False
    
    async def _execute_dispatch(self, task_id: str, text: str, suri_reply: str, matched: str, 
                                session_id: str = '', agent_id: str = '') -> Optional[str]:
        """
        执行调度：匹配目标角色 → 构建角色上下文 → 调用模型 → 返回结果
        
        Args:
            task_id: 任务 ID
            text: 用户原始输入
            suri_reply: suri 的初始回复
            matched: 已匹配的目标角色 ID
            
        Returns:
            角色执行结果文本，或 None（执行失败）
        """
        # 检查角色是否存在
        role_soul = self.config.get_role_soul(matched)
        if not role_soul:
            self.output_router.deliver_alert(
                f"⚠️ 角色 {matched} 尚未配置，无法执行调度。",
                role_id='suri',
                priority='normal',
                target_channels=[OutputChannel.TERMINAL]
            )
            return None
        
        print(f"[系统] 调度至 {matched}...")
        
        # V3.0: 如果有关联的 Agent，按 plan.steps 逐个执行
        if agent_id:
            agent = self.agent_registry.get_agent(agent_id)
            if agent and agent.steps:
                # 过滤出 assignee=matched 的步骤，按 step_id 排序
                role_steps = [s for s in agent.steps if s.assignee == matched]
                role_steps.sort(key=lambda s: s.step_id)
                
                step_results = []
                for step in role_steps:
                    success = await self._execute_step(task_id, agent_id, step, session_id)
                    if success and step.result:
                        step_results.append(f"[{step.step_id}] {step.result}")
                    else:
                        step_results.append(f"[{step.step_id}] 步骤执行受阻: {step.block_reason or '未知原因'}")
                
                # 汇总所有步骤结果
                if step_results:
                    summary = "\n\n".join(step_results)
                    
                    # 保存汇总结果到记忆
                    import time
                    ts_suffix = str(time.time_ns())[-6:]
                    self.memory.save_message(
                        matched,
                        message_id=f"msg_{task_id[:8]}_{matched}_{ts_suffix}",
                        task_id=task_id,
                        sender=matched,
                        receiver='user',
                        body={'type': 'response', 'content': summary}
                    )
                    
                    return summary
                return None
        
        # 降级：无 Agent/Steps 时，使用一次性调度模式（兼容旧逻辑）
        # 使用 ContextService 构建完整的角色上下文（注入模型信息）
        default_model = self.model_manager.get_default_model()
        model_info = None
        if default_model:
            model_info = {
                'name': default_model.name,
                'model_id': default_model.model_id,
                'provider': default_model.provider,
            }
        
        # 构建当前任务信息，注入角色上下文（使模型能访问任务历史和记忆）
        current_task = {
            'task_id': task_id,
            'requirement': text,
        }
        
        role_prompt = self.context.build_context(matched, current_task=current_task, model_info=model_info, session_id=session_id)
        
        # 追加任务特定要求
        role_prompt += (
            f"\n\n---\n\n"
            f"当前任务来自用户，请直接给出专业的处理结果。\n"
            f"任务内容：{text}\n\n"
            f"要求：用简洁的中文回复，直接输出结果，不要提及调度或转发。"
        )
        
        # 保存用户消息到角色的记忆（支持多轮对话上下文）
        import time
        ts_suffix = str(time.time_ns())[-6:]  # 纳秒时间戳后6位，确保唯一性
        self.memory.save_message(
            matched,
            message_id=f"msg_{task_id[:8]}_user_{ts_suffix}",
            task_id=task_id,
            sender='user',
            receiver=matched,
            body={'type': 'task', 'content': text}
        )
        
        messages = [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": text},
        ]
        
        # 调用模型执行角色任务
        try:
            model_result = await self.model_manager.chat_with_usage(messages)
            result = model_result.get('content') if model_result else None
        except Exception as e:
            self.logger.log_model_call_error(matched, f"调度执行异常: {e}")
            return None
        
        if result:
            self.logger.log_model_call(matched, "调度执行", "成功", f"回复长度={len(result)}")
            if self.logger and model_result:
                self.logger.log_token_usage(
                    model_id=matched,
                    prompt_tokens=model_result.get('prompt_tokens', 0),
                    completion_tokens=model_result.get('completion_tokens', 0),
                    total_tokens=model_result.get('total_tokens', 0),
                    task_hint=f"{matched}执行:{text[:30]}",
                    role_id=matched
                )
            # 保存角色回复到记忆（支持后续追问的上下文）
            ts_suffix = str(time.time_ns())[-6:]
            self.memory.save_message(
                matched,
                message_id=f"msg_{task_id[:8]}_{matched}_{ts_suffix}",
                task_id=task_id,
                sender=matched,
                receiver='user',
                body={'type': 'response', 'content': result}
            )
            self.output_router.deliver_text(
                result,
                role_id=matched,
                task_id=task_id,
                target_channels=[OutputChannel.TERMINAL]
            )
            
            # V3.0: 广播状态更新（内部消息总线）
            self.message_bus.broadcast_status(
                sender=matched,
                content=f"完成子步骤：{text[:30]}",
                task_id=task_id,
            )
            
            return result
        else:
            self.output_router.deliver_alert(
                f"{matched} 处理失败，请稍后重试。",
                role_id='suri',
                task_id=task_id,
                priority='normal',
                target_channels=[OutputChannel.TERMINAL]
            )
            return None
    
    async def _summarize_result(self, task_id: str, text: str, role_id: str, role_result: str) -> Optional[str]:
        """
        结果回流：将角色执行结果交给 suri 汇总
        
        当角色执行完成后，suri 作为中枢需要对结果进行审核、补充说明，
        确保用户收到的是完整、一致的回复。
        """
        default_model = self.model_manager.get_default_model()
        if not default_model:
            return None
        
        summarize_prompt = (
            "你是 Suri，中枢调度总监。你刚刚将用户的任务交给了一个专业角色处理，"
            "现在该角色已完成工作并返回了结果。你的任务是：\n"
            "1. 审阅角色的处理结果\n"
            "2. 用简洁的中文向用户汇报最终结果\n"
            "3. 如果角色结果需要补充或澄清，简要说明\n"
            "4. 不要重复角色的详细技术内容，只提炼关键结论和行动项\n\n"
            f"原始用户需求：{text}\n"
            f"执行角色：{role_id}\n"
            f"角色返回结果：{role_result[:800]}\n\n"
            f"请向用户汇报最终结果（2-3 句话）："
        )
        
        messages = [
            {"role": "system", "content": "你是 Suri，用简洁中文汇报任务结果。"},
            {"role": "user", "content": summarize_prompt},
        ]
        
        try:
            model_result = await self.model_manager.chat_with_usage(messages)
            summary = model_result.get('content') if model_result else None
            if self.logger and model_result:
                self.logger.log_token_usage(
                    model_id='suri',
                    prompt_tokens=model_result.get('prompt_tokens', 0),
                    completion_tokens=model_result.get('completion_tokens', 0),
                    total_tokens=model_result.get('total_tokens', 0),
                    task_hint=f"结果回流:{role_id}",
                    role_id='suri'
                )
            self.logger.log_task_dispatched(task_id, role_id, 'user', 'central')
            
            # V2.0: 保存角色经验卡片
            try:
                self.memory.save_experience(
                    role_id=role_id,
                    task_id=task_id,
                    action=f"执行用户任务: {text[:50]}",
                    result=role_result[:200] if role_result else "",
                    feedback="success" if summary else "partial",
                    tags="task,dispatch"
                )
            except Exception:
                pass  # 经验记录失败不应阻塞主流程
            
            return summary
        except Exception as e:
            self.logger.error("结果回流", f"汇总失败: {e}")
            # 汇总失败时，直接返回角色原始结果
            return f"{role_id} 已处理完成：{role_result[:200]}..." if len(role_result) > 200 else role_result
    
    async def _summarize_multi_result(self, task_id: str, text: str, all_results: List[tuple]) -> Optional[str]:
        """
        多角色结果汇总：将多个角色的执行结果交给 suri 统一汇总
        
        当复杂需求涉及多个角色协作时，suri 需要整合各角色的输出，
        形成一份完整、连贯的最终汇报。
        """
        default_model = self.model_manager.get_default_model()
        if not default_model:
            return None
        
        # 构建各角色结果摘要
        parts = []
        for role_id, result in all_results:
            parts.append(f"**{role_id}** 的输出:\n{result[:500]}")
        
        results_text = "\n\n---\n\n".join(parts)
        
        summarize_prompt = (
            "你是 Suri，中枢调度总监。你刚刚将一个复杂需求拆分给多个专业角色协作处理，"
            "现在所有角色都已完成各自的工作。你的任务是：\n"
            "1. 审阅各角色的处理结果\n"
            "2. 用简洁的中文向用户汇报整体进展\n"
            "3. 按角色分工组织汇报内容，清晰明了\n"
            "4. 不要重复详细技术内容，只提炼各角色的关键结论\n\n"
            f"原始用户需求：{text}\n"
            f"涉及角色数：{len(all_results)}\n\n"
            f"各角色结果：\n\n{results_text}\n\n"
            f"请向用户汇报整体结果（按角色分段，每段1-2句话）："
        )
        
        messages = [
            {"role": "system", "content": "你是 Suri，用简洁中文汇报多角色协作结果。"},
            {"role": "user", "content": summarize_prompt},
        ]
        
        try:
            model_result = await self.model_manager.chat_with_usage(messages)
            summary = model_result.get('content') if model_result else None
            if self.logger and model_result:
                self.logger.log_token_usage(
                    model_id='suri',
                    prompt_tokens=model_result.get('prompt_tokens', 0),
                    completion_tokens=model_result.get('completion_tokens', 0),
                    total_tokens=model_result.get('total_tokens', 0),
                    task_hint=f"多角色汇总:{len(all_results)}个",
                    role_id='suri'
                )
            # V3.0: 保存各角色经验卡片
            try:
                for role_id, result in all_results:
                    self.memory.save_experience(
                        role_id=role_id,
                        task_id=task_id,
                        action=f"协作任务: {text[:50]}",
                        result=result[:200] if result else "",
                        feedback="success" if summary else "partial",
                        tags="task,collaboration"
                    )
            except Exception:
                pass  # 经验记录失败不应阻塞主流程
            
            return summary
        except Exception as e:
            self.logger.error("多角色汇总", f"汇总失败: {e}")
            # 汇总失败时，返回各角色的简要摘要
            brief = " | ".join(f"{rid}: {res[:80]}..." for rid, res in all_results)
            return f"多角色协作完成：{brief}"
        
    def _get_or_create_session(self, user_id: str) -> str:
        """
        获取或创建用户的会话（多用户隔离核心）
        
        逻辑：
        1. 查找该用户最近 24 小时内的活跃会话
        2. 如有活跃会话，复用 session_id
        3. 如无活跃会话，创建新会话
        
        Returns:
            session_id
        """
        from datetime import datetime
        
        # 查找该用户最近的活跃会话
        sessions = self.memory.get_active_sessions('suri', user_id=user_id, since_hours=24)
        
        if sessions:
            # 复用最近的活跃会话
            session_id = sessions[0]['session_id']
            return session_id
        
        # 创建新会话
        session_id = f"session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.memory.create_session('suri', session_id, user_id)
        self.logger.info("会话管理", f"为用户 {user_id} 创建新会话 {session_id}")
        return session_id
    
    def _compute_code_snapshot(self) -> str:
        """计算 suri-agent/ 下所有 .py 文件的修改时间哈希，用于检测代码变更"""
        agent_dir = self.project_root / "suri-agent"
        if not agent_dir.exists():
            return ""
        mtime_sum = 0.0
        for f in agent_dir.rglob("*.py"):
            try:
                mtime_sum += f.stat().st_mtime
            except Exception as e:
                print(f"[CLI] 无法读取文件状态: {e}")
                pass
        return f"{mtime_sum:.6f}"
    
    def _check_code_change(self) -> bool:
        """检查代码是否发生变更"""
        current = self._compute_code_snapshot()
        return current != self._code_snapshot
    
    def _check_department_match(self, text: str) -> Optional[str]:
        """检查用户输入是否匹配现有部门，返回匹配的部门 ID 或 None"""
        departments = [d.dept_id for d in self.department_registry.list_departments()]
        if not departments:
            return None
        
        # 从所有角色 Soul 动态推导部门关键词
        dept_keywords: Dict[str, set] = {}
        for role_id in self.config.list_roles(include_aliases=False):
            soul = self.config.get_role_soul(role_id)
            if not soul:
                continue
            dept = soul.meta.get('department', 'central')
            if dept not in departments:
                continue
            keywords = soul.meta.get('keywords', [])
            if dept not in dept_keywords:
                dept_keywords[dept] = set()
            dept_keywords[dept].update(keywords)
            dept_keywords[dept].update(soul.meta.get('capabilities', []))
        
        for dept_id in departments:
            for kw in dept_keywords.get(dept_id, []):
                if kw in text:
                    return dept_id
        return None
    
    def _skill_matches(self, text: str, skill_details: List[Optional[dict]]) -> bool:
        """检查用户输入是否匹配任一技能的触发条件"""
        for detail in skill_details:
            if not detail:
                continue
            triggers = detail.get('triggers', [])
            for trigger in triggers:
                if trigger in text:
                    return True
        # 如果角色没有技能定义，视为不匹配（需要增加技能）
        return len([d for d in skill_details if d]) > 0 and any(
            any(t in text for t in (d.get('triggers', []) if d else []))
            for d in skill_details
        )
    
    def _execute_creation(self, action: str, data: dict) -> str:
        """执行创建操作（部门/角色/技能）"""
        try:
            if action == 'create_dept':
                dept_name = data.get('field_1', '').strip()
                dept_ability = data.get('field_2', '').strip()
                dept_lead = data.get('field_3', '').strip()
                if not dept_name:
                    return "❌ 部门名称不能为空"
                dept_id = dept_name.lower().replace(' ', '_').replace('-', '_')
                dept_dir = self.project_root / 'group' / dept_id
                dept_dir.mkdir(parents=True, exist_ok=True)
                (dept_dir / f"{dept_id}.md").write_text(
                    f"---\nname: {dept_name}\nability: {dept_ability}\n---\n\n# {dept_name}\n\n## 部门职责\n\n{dept_ability}\n",
                    encoding='utf-8'
                )
                self.department_registry._load_departments()
                return f"✅ 部门 [{dept_name}] 创建成功，负责人: {dept_lead or '待指定'}"
            
            elif action == 'create_role':
                role_name = data.get('field_1', '').strip()
                role_desc = data.get('field_2', '').strip()
                dept = data.get('context', {}).get('dept', 'central')
                if not role_name:
                    return "❌ 角色名称不能为空"
                role_id = role_name.lower().replace(' ', '_').replace('-', '_')
                role_dir = self.project_root / 'group' / dept / role_id
                role_dir.mkdir(parents=True, exist_ok=True)
                (role_dir / f"{role_id}.md").write_text(
                    f"---\nrole_id: {role_id}\nname: {role_name}\ndepartment: {dept}\nlevel: specialist\ntype: specialist\ncapabilities: []\nkeywords: []\noutput_channels: [terminal, logger, memory]\ntools: []\n---\n\n# {role_name}\n\n## 定位\n\n{role_desc}\n",
                    encoding='utf-8'
                )
                for subdir in ['memories', 'skills', 'scripts', 'reference', 'output']:
                    (role_dir / subdir).mkdir(exist_ok=True)
                self.config.load_all()
                self.department_registry._load_departments()
                return f"✅ 角色 [{role_name}] 创建成功，位于 group/{dept}/{role_id}/"
            
            elif action == 'add_skill':
                role_id = data.get('context', {}).get('role', '')
                skill_name = data.get('field_1', '').strip()
                skill_desc = data.get('field_2', '').strip()
                if not skill_name or not role_id:
                    return "❌ 技能名称或角色不能为空"
                soul = self.config.get_role_soul(role_id)
                dept = soul.meta.get('department', 'central') if soul else 'central'
                skill_id = skill_name.lower().replace(' ', '_').replace('-', '_')
                skill_dir = self.project_root / 'group' / dept / role_id / 'skills' / skill_id
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / 'skill.md').write_text(
                    f"---\nskill_id: {skill_id}\nname: {skill_name}\nowner: {role_id}\nversion: \"0.1.0\"\nstatus: active\ntriggers: []\ninputs: []\n---\n\n# {skill_name}\n\n## 功能概述\n\n{skill_desc}\n",
                    encoding='utf-8'
                )
                return f"✅ 技能 [{skill_name}] 已添加到角色 [{role_id}]"
            
            return "❌ 未知创建操作"
        except Exception as e:
            return f"❌ 创建失败: {e}"
    
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
                
                # V3.0: 创建对话模式
                if self.creation_dialog and self.creation_dialog.state != 'idle':
                    result = self.creation_dialog.handle_input(text)
                    if result.startswith("[CREATION]"):
                        print(f"\nSuri > {result[10:]}")
                        continue
                    elif result == "[COMPLETE]":
                        creation_result = self.creation_dialog.execute()
                        print(f"\nSuri > {creation_result}")
                        self.creation_dialog.reset()
                        continue
                    elif result == "[CANCELLED]":
                        print("\nSuri > 已取消创建。")
                        self.creation_dialog.reset()
                        continue
                
                running = await self.handle_user_input(text)
            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except EOFError:
                break
            except Exception as e:
                self.logger.error("主循环", f"未捕获的异常: {e}")
                self.output_router.deliver_alert(
                    f"❌ 发生错误: {e}。程序将继续运行，输入 /model 可重新配置。",
                    role_id='suri',
                    priority='high',
                    target_channels=[OutputChannel.TERMINAL]
                )
        
        # 退出时清理资源
        if self.doc_watcher:
            self.doc_watcher.stop()
            self.logger.info("系统", "文档监控已停止")
        if self.model_manager:
            import asyncio
            asyncio.get_event_loop().run_until_complete(self.model_manager.close())


async def main():
    terminal = SuriTerminal()
    await terminal.run()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
