#!/usr/bin/env python3
"""
suri-agent 入口

启动顺序：
1. 加载环境变量 (.env)
2. 初始化 ConfigService
3. 初始化 MemoryService（角色级独立 SQLite 存储）
4. 初始化 SecurityService
5. 初始化 FileService
6. 初始化 ModelManager（httpx 异步客户端）
7. 初始化 ModelService（委托 ModelManager 实际调用）
8. 初始化 ContextService
9. 初始化 CommService（Telegram，可选）
10. 初始化 ProjectionService
11. 初始化 ApprovalService
12. 初始化 ToolService
13. 初始化 TaskService
14. 启动消息监听循环

终端命令：
- /model    配置/添加模型
- /status   查看系统状态
- /test     运行连接测试
- /reload   重新加载配置
- /logs     查看今日日志
- /help     显示帮助

主循环架构：
- 消息队列 (asyncio.Queue) 解耦生产者和消费者
- 生产者：终端输入 / Telegram 消息 / Webhook
- 消费者：handle_user_message() → 调度 → 模型 → 结果回流
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
# 确保 suri-agent 目录在路径中（支持直接运行和通过 run.sh 运行）
SURI_AGENT_DIR = PROJECT_ROOT / "suri-agent"
if str(SURI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(SURI_AGENT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.filesystem import FileService
from model.manager import ModelManager
from core.model_router import ModelService
from core.context import ContextService
from access.telegram.bot import CommService
from access.projection import ProjectionService
from core.approval import ApprovalService
from core.tool_executor import ToolService
from core.task_dispatcher import TaskService
from mcp.registry import MCPRegistry


class SuriAgent:
    """Suri 平台主程序"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config: ConfigService = None
        self.memory: MemoryService = None
        self.security: SecurityService = None
        self.file_service: FileService = None
        self.model_manager: ModelManager = None
        self.model: ModelService = None
        self.context: ContextService = None
        self.comm: CommService = None
        self.projection: ProjectionService = None
        self.approval: ApprovalService = None
        self.tool: ToolService = None
        self.task: TaskService = None
        self.mcp: MCPRegistry = None
        self.learner = None
        self._message_queue: asyncio.Queue = None
        self._running = False

    async def initialize(self) -> bool:
        """初始化所有服务"""
        print("=" * 50)
        print("Suri Agent 启动中...")
        print("=" * 50)

        env_path = self.project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print("[OK] 环境变量已加载")

        self.config = ConfigService(self.project_root)
        self.config.load_all()
        print("[OK] 配置服务已启动")

        self.memory = MemoryService(self.project_root, self.config)
        print("[OK] 记忆服务已启动")

        self.security = SecurityService(self.project_root, self.config)
        print("[OK] 安全服务已启动")

        self.file_service = FileService(self.project_root, self.security)
        print("[OK] 文件服务已启动")

        self.model_manager = ModelManager(self.project_root)
        self.model = ModelService(self.config, self.model_manager)
        print("[OK] 模型服务已启动")

        self.context = ContextService(self.config, self.memory)
        print("[OK] 上下文服务已启动")

        self.comm = CommService(self.config)
        connected = await self.comm.connect()
        if not connected:
            print("[WARN] 通信服务未连接，将以终端模式运行")
        else:
            print("[OK] 通信服务已启动")

        # 初始化投影服务
        self.projection = ProjectionService(self.comm, self.config)
        print("[OK] 投影服务已启动")

        self.approval = ApprovalService(self.config, self.memory, self.security)
        print("[OK] 审批服务已启动")

        self.tool = ToolService(self.project_root, self.config)
        print("[OK] 工具服务已启动")

        # 初始化自学习引擎
        from learning import RoleLearner
        self.learner = RoleLearner(self.memory, self.model, self.logger)
        print("[OK] 自学习引擎已启动")

        self.task = TaskService(
            self.config, self.memory, self.context,
            self.model, self.comm, self.logger,
            learner=self.learner
        )
        print("[OK] 任务服务已启动")

        self.mcp = MCPRegistry()
        print("[OK] MCP 服务已启动（预留）")

        # 消息队列
        self._message_queue = asyncio.Queue()
        self._running = True

        # 注册通信回调
        self.comm.on_message(self._on_external_message)

        print("=" * 50)
        print("Suri Agent 启动完成")
        print(f"角色数: {len(self.config.list_roles())}")
        print(f"技能数: {len(self.config.list_skills())}")
        print("=" * 50)

        # 首次运行提示
        if self.model_manager.is_first_run():
            print("\n⚠️ 首次运行，尚未配置模型。")
            print("   请输入 /model 命令添加模型，或输入 /help 查看所有命令。\n")

        return True

    async def run(self) -> None:
        """主循环：消息队列消费者 + 生产者 + 超时检查"""
        print("\n等待用户消息...\n")

        await asyncio.gather(
            self._message_consumer(),
            self._timeout_checker(),
            self._terminal_producer(),
            return_exceptions=True,
        )

    async def _message_consumer(self):
        """消息消费者：从队列取出消息并处理"""
        while self._running:
            try:
                user_id, text = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0
                )
                await self.handle_user_message(user_id, text)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[Consumer] 处理消息时出错: {e}")

    async def _timeout_checker(self):
        """审批超时检查器"""
        while self._running:
            try:
                await asyncio.sleep(10)
                self.approval.check_timeout()
            except Exception as e:
                print(f"[TimeoutChecker] 检查超时出错: {e}")

    async def _terminal_producer(self):
        """终端输入生产者：从 stdin 读取用户输入并放入队列"""
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                # 在非阻塞的 executor 中运行 input()
                text = await loop.run_in_executor(
                    None, lambda: input("您 > ")
                )
                text = text.strip()
                if text:
                    await self._message_queue.put(("terminal_user", text))
            except (EOFError, KeyboardInterrupt):
                self._running = False
                print("\n正在关闭 Suri Agent...")
                break
            except Exception as e:
                print(f"[Terminal] 读取输入出错: {e}")

    def _on_external_message(self, msg):
        """外部消息回调（Telegram / Webhook）"""
        # 将 StandardMessage 放入队列
        user_id = msg.sender_role or "external_user"
        text = msg.body.get('content', '')
        asyncio.create_task(self._message_queue.put((user_id, text)))

    async def handle_user_message(self, user_id: str, text: str) -> None:
        """
        处理用户消息入口

        命令以 '/' 开头，直接处理不走任务调度。
        普通消息走任务调度闭环。
        """
        # 命令路由
        if text.startswith('/'):
            await self._handle_command(user_id, text)
            return

        # 普通消息：创建任务 → 调度分派 → 模型分析 → 结果回流
        task_id = self.task.receive_task(user_id, text)

        result = await self.task.dispatch(task_id)

        if not result['success']:
            await self._fallback_reply(user_id, text)
            return

        await self._fallback_reply(user_id, text)

    async def _handle_command(self, user_id: str, text: str) -> None:
        """处理终端命令"""
        parts = text.strip().split()
        cmd = parts[0].lower() if parts else ''
        args = parts[1:] if len(parts) > 1 else []

        handler = self._commands.get(cmd)
        if handler:
            try:
                await handler(args)
            except Exception as e:
                print(f"[Command] {cmd} 执行出错: {e}")
        else:
            print(f"未知命令: {cmd}\n输入 /help 查看可用命令。")

    @property
    def _commands(self) -> dict:
        """命令映射表"""
        return {
            '/model': self._cmd_model,
            '/models': self._cmd_models,
            '/status': self._cmd_status,
            '/test': self._cmd_test,
            '/reload': self._cmd_reload,
            '/logs': self._cmd_logs,
            '/help': self._cmd_help,
        }

    async def _cmd_model(self, args: list) -> None:
        """/model - 模型管理（wizard/add/set/del/list）"""
        loop = asyncio.get_event_loop()
        
        # 无子命令：启动向导
        if not args:
            print("\n>>> 启动模型配置向导...")
            success = await loop.run_in_executor(
                None, self.model_manager.setup_wizard
            )
            if success:
                print("✅ 模型配置已更新。新配置立即生效，无需重启。\n")
            else:
                print("⚠️ 配置未完成，当前模型设置保持不变。\n")
            return
        
        sub = args[0].lower()
        
        if sub == 'list':
            models = self.model_manager.list_models()
            if not models:
                print("\n未配置任何模型。\n")
                return
            print("\n已配置模型列表：")
            for m in models:
                marker = " ⭐默认" if m.is_default else ""
                caps = ", ".join(m.capabilities or [])
                type_desc = m.model_type
                print(f"  • {m.name} ({m.model_id}){marker}")
                print(f"    类型: {type_desc} | 提供商: {m.provider}")
                print(f"    能力: {caps} | 成本: {m.cost_tier}")
            print("")
        
        elif sub == 'add':
            from model.manager import MODEL_MENU
            
            def _interactive_add():
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
                        return False
                else:
                    brand_info = MODEL_MENU.get(choice)
                    if not brand_info:
                        print("❌ 无效选项")
                        return False
                    
                    print(f"\n请输入您的 {brand_info['brand']} API Key：")
                    api_key = input("API Key: ").strip()
                    if not api_key:
                        print("❌ API Key 不能为空")
                        return False
                    
                    # 自动测试并选择可用型号
                    print("\n正在验证 API Key 并测试可用型号...")
                    result = self.model_manager._test_api_key(brand_info, api_key)
                    
                    if result is None:
                        print("\n❌ API Key 无效或该品牌下所有型号均不可用。")
                        return False
                    
                    name, model_id = result
                    provider = brand_info["provider"]
                    base_url = brand_info["base_url"]
                
                # 询问是否设为默认
                is_default = False
                if not self.model_manager.list_models():
                    is_default = True
                    print(f"（首个模型，自动设为默认）")
                else:
                    choice = input("设为默认模型? [y/N]: ").strip().lower()
                    is_default = choice in ('y', 'yes')
                
                self.model_manager.add_model(
                    name, model_id, api_key, base_url, provider,
                    is_default=is_default
                )
                print(f"\n✅ 模型 {name} ({model_id}) 已添加{'并设为默认' if is_default else ''}")
                return True
            
            success = await loop.run_in_executor(None, _interactive_add)
        
        elif sub == 'set':
            if len(args) < 2:
                print("\n用法: /model set <model_id>")
                print("       /model set glm-4.7-flash\n")
                return
            model_id = args[1]
            ok = self.model_manager.set_default(model_id)
            if ok:
                print(f"✅ 默认模型已设置为: {model_id}\n")
            else:
                print(f"❌ 模型 '{model_id}' 不存在。用 /model list 查看。\n")
        
        elif sub == 'del':
            if len(args) < 2:
                print("\n用法: /model del <model_id>")
                print("       /model del glm-4.7-flash\n")
                return
            model_id = args[1]
            
            def _confirm_delete():
                m = self.model_manager._models.get(model_id)
                if not m:
                    return None
                confirm = input(f"确认删除模型 '{m.name}' ({model_id})? [y/N]: ").strip().lower()
                return confirm in ('y', 'yes')
            
            confirmed = await loop.run_in_executor(None, _confirm_delete)
            if confirmed is None:
                print(f"❌ 模型 '{model_id}' 不存在。\n")
            elif confirmed:
                ok = self.model_manager.delete_model(model_id)
                if ok:
                    print(f"✅ 模型 {model_id} 已删除。\n")
                else:
                    print(f"❌ 删除失败。\n")
            else:
                print("已取消删除。\n")
        
        else:
            print(f"\n未知子命令: {sub}")
            print("用法: /model [wizard|add|set|del|list]")
            print("  /model        启动交互式向导")
            print("  /model add    直接添加模型")
            print("  /model set    设置默认模型")
            print("  /model del    删除模型")
            print("  /model list   列出所有模型")
            print("  /models       交互式浏览并切换模型\n")

    async def _cmd_models(self, args: list) -> None:
        """/models - 交互式列出模型并切换默认模型"""
        loop = asyncio.get_event_loop()
        
        # 通过 ToolService 获取模型列表
        result = self.tool.execute('model_manager', {'action': 'list'})
        if not result['success']:
            print(f"\n❌ 获取模型列表失败: {result.get('error')}\n")
            return
        
        data = result['data']
        groups = data.get('groups', {})
        if not groups:
            print("\n  暂无配置模型\n")
            return
        
        def _interactive_switch():
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
                switch_result = self.tool.execute('model_manager', {
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
        
        await loop.run_in_executor(None, _interactive_switch)

    async def _cmd_status(self, args: list) -> None:
        """/status - 查看系统状态"""
        print("\n" + "=" * 40)
        print("📊 Suri 系统状态")
        print("=" * 40)

        models = self.model_manager.list_models()
        print(f"模型: {len(models)} 个")
        for m in models:
            marker = " ⭐默认" if m.is_default else ""
            print(f"  • {m.name} ({m.model_id}){marker}")

        print(f"\n角色: {len(self.config.list_roles())} 个")
        for role_id in self.config.list_roles():
            print(f"  • {role_id}")

        print(f"\n技能: {len(self.config.list_skills())} 个")
        print(f"工具: {len(self.config.list_tools())} 个")

        print(f"\n通信服务: {'已连接' if self.comm.is_connected else '未连接'}")
        print(f"投影服务: {'已启动' if self.projection else '未启动'}")
        print(f"自学习引擎: {'已启动' if self.learner else '未启动'}")

        if self.projection:
            groups = self.projection.get_bound_groups()
            print(f"\n已绑定 Telegram 群组: {len(groups)} 个")
            for dept, gid in groups.items():
                print(f"  • {dept} → {gid}")

        print("=" * 40 + "\n")

    async def _cmd_test(self, args: list) -> None:
        """/test - 运行连接测试"""
        print("\n>>> 运行连接测试...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/test_connections.py"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

    async def _cmd_reload(self, args: list) -> None:
        """/reload - 重新加载配置"""
        print("\n>>> 重新加载配置...")
        self.config.load_all()
        print("✅ 配置已重新加载。\n")

    async def _cmd_logs(self, args: list) -> None:
        """/logs - 查看今日日志"""
        print("\n>>> 今日日志路径:")
        logs = self.logger.get_today_logs()
        for category, path in logs.items():
            size = path.stat().st_size if path.exists() else 0
            print(f"  {category}: {path} ({size} bytes)")

        # 显示最近的 runtime 日志
        runtime_log = logs.get("runtime")
        if runtime_log and runtime_log.exists():
            print(f"\n--- 最近 20 条 runtime 日志 ---")
            lines = runtime_log.read_text(encoding="utf-8").splitlines()
            for line in lines[-20:]:
                print(f"  {line}")
            print("---\n")

    async def _cmd_help(self, args: list) -> None:
        """/help - 显示帮助"""
        print("""
📖 Suri 终端命令

普通消息:
  直接输入文字即可发起任务

可用命令:
  /model           启动模型配置向导
  /model add       直接添加模型（交互式）
  /model set       设置默认模型
  /model del       删除模型
  /model list      列出所有模型
  /models          交互式浏览模型（按类型分组，支持切换）
  /status          查看系统状态
  /test            运行连接测试
  /reload          重新加载配置
  /logs            查看今日日志
  /help            显示此帮助

首次使用:
  1. 输入 /model 配置模型
  2. 输入普通消息开始任务
        """)

    async def _fallback_reply(self, user_id: str, text: str):
        """回退回复：当调度失败时，suri 直接调用模型回复用户"""
        if not self.model_manager:
            print("[suri] ❌ 模型管理器未初始化，无法回复。")
            return

        if self.model_manager.is_first_run():
            print("[suri] ⚠️ 未配置模型，无法回复。")
            print("        请使用 /model 命令添加模型，或检查 .env 文件中的 API Key 配置。")
            return

        # 检查网络连接（简单探测）
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.get("https://httpbin.org/get")
        except Exception:
            print("[suri] ❌ 网络连接异常，无法调用模型 API。请检查网络连接。")
            return

        messages = [
            {"role": "system", "content": "你是 Suri，central 部门负责人。请简洁回复用户。"},
            {"role": "user", "content": text},
        ]

        try:
            result = await self.model_manager.chat_with_usage(messages)
            if result and result.get('content'):
                reply = result['content']
                total_tokens = result.get('total_tokens', 0)
                token_info = f" [Token: {total_tokens}]" if total_tokens > 0 else ""
                print(f"\n[suri] {reply}{token_info}\n")
            else:
                print("\n[suri] ⚠️ 模型调用失败：API 返回空或模型服务不可用。")
                print("        可能原因：API Key 错误、网络问题、模型服务限流或欠费。\n")
                await self._prompt_reconfigure_model()
        except httpx.ConnectError as e:
            print(f"\n[suri] ❌ 无法连接到模型服务器: {e}")
            print("        请检查网络连接和代理配置。\n")
            await self._prompt_reconfigure_model()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            print(f"\n[suri] ❌ 模型 API 返回错误: HTTP {status}")
            print(f"        响应: {e.response.text[:200]}\n")
            if status in (401, 403, 429, 503):
                await self._prompt_reconfigure_model()
        except Exception as e:
            print(f"\n[suri] ❌ 回复出错: {type(e).__name__}: {e}\n")

    async def _prompt_reconfigure_model(self):
        """模型调用失败后，引导用户重新配置模型"""
        loop = asyncio.get_event_loop()
        def _ask():
            return input("是否立即配置新模型？ [Y/n]: ").strip().lower()
        fix_now = await loop.run_in_executor(None, _ask)
        if fix_now in ('', 'y', 'yes'):
            print(">>> 启动模型配置向导...")
            success = await loop.run_in_executor(None, self.model_manager.setup_wizard)
            if success:
                print("✅ 新模型已配置，您可以重新输入刚才的问题。\n")
            else:
                print("⚠️ 配置未完成。您可以稍后输入 /model 重新配置。\n")
        else:
            print("[suri] 已跳过。输入 /model 可随时重新配置。\n")

    async def shutdown(self):
        """优雅关闭"""
        self._running = False
        if self.model_manager:
            await self.model_manager.close()
        if self.comm:
            await self.comm.disconnect()
        print("[OK] Suri Agent 已关闭")

    @property
    def logger(self):
        """懒加载 LoggerService"""
        if not hasattr(self, '_logger') or self._logger is None:
            from infrastructure.logger import LoggerService
            self._logger = LoggerService(self.project_root)
        return self._logger


async def main():
    project_root = Path(__file__).parent.parent
    agent = SuriAgent(project_root)

    try:
        await agent.initialize()
        await agent.run()
    except KeyboardInterrupt:
        print("\n收到中断信号...")
    finally:
        await agent.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
