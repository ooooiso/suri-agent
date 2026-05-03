"""access CLI 模块 — 终端交互逻辑。

核心设计：
- 独立线程读取 sys.stdin.readline()，通过 asyncio.Queue 传递给主事件循环
- 输出使用 ANSI 清行 (\r\033[K) + 重绘提示符
- 输入缓冲区保护：输出前保存当前输入行，输出后恢复
- 所有 input() 调用统一通过 _async_input() 方法，避免与主循环竞争 stdin
- 启动时显示模型配置状态面板
- LLM 异常时弹出交互式恢复菜单

双模式输入处理：
1. LLM 在线模式：用户输入自然语言 → 先尝试让 LLM 理解意图并自动执行命令
   → 如果 LLM 不理解则走对话
2. LLM 离线模式：LLM 不可用时 → 用户手动输入 /xxx 命令 → 本地处理
"""

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.utils.event_types import Event, Priority

from plugins.access.config_editor import ConfigEditor
from plugins.access.formatter import MessageFormatter


class CLISession:
    """终端 CLI 会话。

    使用独立线程读取 stdin，通过队列传递给主事件循环。
    所有输出使用 ANSI 清行，确保提示符始终在最底行。
    """

    def __init__(self, event_bus, session_id: Optional[str] = None):
        self._event_bus = event_bus
        self._session_id = session_id or f"cli_{os.getpid()}"
        self._running = False
        
        # 输入队列：独立线程读取 stdin，主循环消费
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._input_thread: Optional[threading.Thread] = None
        
        # 当前输入行缓冲区（用于输出保护）
        self._current_input_line = ""
        
        # LLM 连接状态：True=在线，False=离线
        self._llm_online = True
        
        # 启用 readline 支持行编辑和历史
        self._readline_available = False
        try:
            import readline
            self._readline_available = True
            history_file = os.path.expanduser("~/.suri/.cli_history")
            try:
                readline.read_history_file(history_file)
                readline.set_history_length(500)
            except (FileNotFoundError, OSError):
                pass
        except ImportError:
            pass

    # ------------------------------------------------------------------ #
    # 公开接口：供 access/plugin.py 调用
    # ------------------------------------------------------------------ #
    def print_output(self, text: str) -> None:
        """系统输出：清除当前行 → 保存输入缓冲区 → 打印内容 → 恢复提示符。

        即使用户正在输入，输出也不会和输入内容混在一起。
        """
        # 保存当前输入行
        input_buf = self._current_input_line
        
        # 清除当前行，打印输出
        sys.stdout.write(f"\r\033[K{text}\n")
        
        # 恢复提示符和输入缓冲区
        if input_buf:
            sys.stdout.write(f"> {input_buf}")
        else:
            sys.stdout.write("> ")
        sys.stdout.flush()

    def print_system(self, text: str) -> None:
        """系统消息（不需要重绘提示符的场合）。"""
        sys.stdout.write(f"\r\033[K{text}\n")
        sys.stdout.flush()

    def set_llm_online(self, online: bool) -> None:
        """设置 LLM 连接状态。"""
        self._llm_online = online

    # ------------------------------------------------------------------ #
    # 异步输入：统一通过此方法获取用户输入
    # ------------------------------------------------------------------ #
    async def _async_input(self, prompt: str = "") -> str:
        """异步获取用户输入。
        
        与主循环共享同一个 stdin 读取线程。
        适用于配置菜单等需要 input() 的场景。
        """
        if prompt:
            sys.stdout.write(f"\r\033[K{prompt}")
            sys.stdout.flush()
        
        # 从输入队列获取一行
        line = await self._input_queue.get()
        return line.strip()

    # ------------------------------------------------------------------ #
    # 主循环
    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        """启动终端输入循环。"""
        self._running = True
        
        # 启动 stdin 读取线程
        self._start_input_thread()
        
        # 显示欢迎信息和模型状态面板
        await self._show_status_panel()
        
        sys.stdout.write("> ")
        sys.stdout.flush()

        while self._running:
            try:
                # 从输入队列获取用户输入
                line = await self._input_queue.get()
                self._current_input_line = ""  # 清空输入缓冲区
                line = line.strip()

                if not line:
                    sys.stdout.write("> ")
                    sys.stdout.flush()
                    continue
                
                if line == "/quit":
                    self.print_system("Goodbye.")
                    self._running = False
                    self._save_history()
                    break
                
                if line == "/help":
                    self._print_help()
                    sys.stdout.write("> ")
                    sys.stdout.flush()
                    continue

                await self._handle_input(line)
                sys.stdout.write("> ")
                sys.stdout.flush()

            except EOFError:
                break
            except KeyboardInterrupt:
                self.print_system("Goodbye.")
                break

    async def _show_status_panel(self) -> None:
        """显示模型配置状态面板。"""
        # 从 config.json 读取配置
        config_path = Path.home() / ".suri" / "config.json"
        providers_info = {}
        active_provider = "deepseek"
        active_model = "deepseek-chat"
        api_keys = {}

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                llm_cfg = cfg.get("llm_gateway", {})
                active_provider = llm_cfg.get("default_provider", "deepseek")
                providers = llm_cfg.get("providers", {})

                # 标准 5 家厂商
                all_providers = {
                    "wenxin": {"models": ["ernie-4.0", "ernie-3.5"]},
                    "tongyi": {"models": ["qwen-max", "qwen-plus"]},
                    "chatglm": {"models": ["glm-4", "glm-3-turbo"]},
                    "kimi": {"models": ["moonshot-v1-8k", "moonshot-v1-32k"]},
                    "deepseek": {"models": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat"]},
                }

                for name, info in all_providers.items():
                    provider_cfg = providers.get(name, {})
                    has_key = bool(provider_cfg.get("api_key", ""))
                    models = provider_cfg.get("models", info["models"])
                    providers_info[name] = {
                        "models": models,
                        "api_key": has_key,
                    }
                    if has_key:
                        api_keys[name] = provider_cfg["api_key"]

                # 从环境变量补充
                for name in all_providers:
                    env_key = f"SURI_{name.upper()}_API_KEY"
                    env_val = os.environ.get(env_key, "")
                    if env_val and name not in api_keys:
                        api_keys[name] = env_val
                        if name in providers_info:
                            providers_info[name]["api_key"] = True

                # 确定 active_model
                if active_provider in providers:
                    default_model = providers[active_provider].get("default_model", "")
                    if default_model:
                        active_model = default_model
                    elif providers[active_provider].get("models"):
                        active_model = providers[active_provider]["models"][0]

            except Exception:
                pass

        # 如果 config.json 不存在，显示默认状态
        if not providers_info:
            all_providers = {
                "wenxin": {"models": ["ernie-4.0", "ernie-3.5"]},
                "tongyi": {"models": ["qwen-max", "qwen-plus"]},
                "chatglm": {"models": ["glm-4", "glm-3-turbo"]},
                "kimi": {"models": ["moonshot-v1-8k", "moonshot-v1-32k"]},
                "deepseek": {"models": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat"]},
            }
            for name, info in all_providers.items():
                env_key = f"SURI_{name.upper()}_API_KEY"
                has_key = bool(os.environ.get(env_key, ""))
                providers_info[name] = {
                    "models": info["models"],
                    "api_key": has_key,
                }
                if has_key:
                    api_keys[name] = os.environ.get(env_key, "")

        # 使用 formatter 生成状态面板
        panel = MessageFormatter.format_status(
            providers_info, active_provider, active_model, api_keys
        )
        self.print_system(panel)

    async def _show_recovery_menu(self, error_code: int, provider: str) -> None:
        """显示 LLM 异常恢复菜单。"""
        # 获取已配置的厂商列表
        config_path = Path.home() / ".suri" / "config.json"
        configured_providers = []
        all_providers = ["deepseek", "kimi", "chatglm", "tongyi", "wenxin"]

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                providers = cfg.get("llm_gateway", {}).get("providers", {})
                for name in all_providers:
                    if name in providers and providers[name].get("api_key"):
                        configured_providers.append(name)
            except Exception:
                pass

        # 从环境变量补充
        for name in all_providers:
            env_key = f"SURI_{name.upper()}_API_KEY"
            if os.environ.get(env_key, "") and name not in configured_providers:
                configured_providers.append(name)

        # 构建菜单选项
        options = [f"修改 {provider} 的 API Key"]
        other_providers = [p for p in configured_providers if p != provider]
        if other_providers:
            options.append(f"切换到其他已配置厂商 ({', '.join(other_providers)})")
        else:
            options.append("添加新厂商并切换")
        options.append("忽略，继续使用当前模型")

        # 显示菜单
        menu = MessageFormatter.format_decision("模型连接异常，请选择操作：", options)
        self.print_system(menu)

        # 获取用户选择
        choice = await self._async_input()
        
        if choice == "1":
            # 修改 API Key
            editor = ConfigEditor(self._event_bus, input_func=self._async_input)
            await editor.verify_and_set_key(provider)
        elif choice == "2":
            if other_providers:
                # 切换到其他已配置厂商
                self.print_system(f"可用厂商: {', '.join(other_providers)}")
                target = await self._async_input("输入要切换的厂商名: ")
                if target in other_providers:
                    await self._event_bus.publish(Event(
                        event_type="user.command",
                        source="access",
                        payload={
                            "command": "switch",
                            "args": [target],
                            "session_id": self._session_id,
                            "channel": "cli",
                            "user_id": "cli_user",
                        },
                        priority=Priority.NORMAL,
                    ))
                    self.print_output(MessageFormatter.format_system(
                        f"正在切换到 {target}..."
                    ))
                else:
                    self.print_output(f"❌ 无效厂商: {target}")
            else:
                # 添加新厂商
                self.print_system("可用厂商: deepseek, kimi, chatglm, tongyi, wenxin")
                target = await self._async_input("输入要添加的厂商名: ")
                if target in all_providers:
                    editor = ConfigEditor(self._event_bus, input_func=self._async_input)
                    await editor.verify_and_set_key(target)
                else:
                    self.print_output(f"❌ 无效厂商: {target}")
        else:
            self.print_output("已忽略，继续使用当前模型。")

    def _start_input_thread(self) -> None:
        """启动 stdin 读取线程。"""
        def read_stdin():
            """在独立线程中读取 stdin。"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            while self._running:
                try:
                    line = sys.stdin.readline()
                    if not line:  # EOF
                        break
                    # 更新当前输入缓冲区（用于输出保护）
                    self._current_input_line = line.rstrip('\n')
                    # 放入队列
                    loop.run_until_complete(
                        asyncio.ensure_future(self._input_queue.put(line.rstrip('\n')))
                    )
                except (EOFError, KeyboardInterrupt):
                    break
                except Exception:
                    break
        
        self._input_thread = threading.Thread(target=read_stdin, daemon=True)
        self._input_thread.start()

    def stop(self) -> None:
        self._running = False

    def _save_history(self) -> None:
        """保存 readline 历史。"""
        if self._readline_available:
            import readline
            history_file = os.path.expanduser("~/.suri/.cli_history")
            try:
                readline.write_history_file(history_file)
            except (FileNotFoundError, OSError):
                pass

    # ------------------------------------------------------------------ #
    # 命令处理 — 双模式设计
    # ------------------------------------------------------------------ #
    async def _handle_input(self, raw: str) -> None:
        """处理 CLI 输入。

        双模式设计：
        
        模式 1 — LLM 在线（_llm_online == True）：
          - /xxx 命令 → 本地处理（不依赖 LLM）
          - 自然语言 → 发送给 LLM，让 LLM 理解意图并自动执行命令
            （LLM 的 system prompt 中注入了命令说明，它知道如何响应）
        
        模式 2 — LLM 离线（_llm_online == False）：
          - /xxx 命令 → 本地处理
          - 自然语言 → 提示用户使用 /xxx 命令，显示帮助
        
        这样设计的好处：
        - LLM 在线时，用户不需要记忆命令，直接说"切换到 kimi"即可
        - LLM 离线时，用户仍然可以通过 /xxx 命令管理系统，解决突发问题
        - /xxx 命令始终本地处理，不依赖 LLM，确保关键操作永远可用
        """
        parts = raw.split()
        cmd = parts[0]
        args = parts[1:]

        # ========== 始终本地处理的命令（不依赖 LLM） ==========
        
        # /setkey 快速修改 API Key
        if cmd == "/setkey":
            await self._handle_setkey(args)
            return

        # /reconfig 进入配置菜单
        if cmd == "/reconfig":
            await self._handle_reconfig()
            return

        # /switch 切换模型（本地处理，不依赖 LLM）
        if cmd == "/switch":
            await self._handle_switch(args)
            return

        # /models 列出模型（本地处理，不依赖 LLM）
        if cmd == "/models":
            await self._handle_models()
            return

        # /config 查看配置（本地处理，不依赖 LLM）
        if cmd == "/config":
            await self._handle_config(args)
            return

        # /status 查看状态（本地处理，不依赖 LLM）
        if cmd == "/status":
            self.print_output("系统运行中。输入 /help 查看命令。")
            return

        # /model 查看当前模型（本地处理，不依赖 LLM）
        if cmd == "/model":
            await self._handle_model()
            return

        # /reload 重载配置（本地处理，不依赖 LLM）
        if cmd == "/reload":
            await self._handle_reload()
            return

        # /logs 查看日志路径（本地处理，不依赖 LLM）
        if cmd == "/logs":
            log_path = os.path.expanduser("~/.suri/runtime/logs")
            self.print_output(f"日志目录: {log_path}")
            return

        # /clear 清空上下文（本地处理，不依赖 LLM）
        if cmd == "/clear":
            await self._handle_clear()
            return

        # 其他 /xxx 命令 → 发布 user.command 事件
        if cmd.startswith("/"):
            await self._event_bus.publish(Event(
                event_type="user.command",
                source="access",
                payload={
                    "command": cmd.lstrip("/"),
                    "args": args,
                    "session_id": self._session_id,
                    "channel": "cli",
                    "user_id": "cli_user",
                },
                priority=Priority.NORMAL,
            ))
            return

        # ========== 自然语言处理 ==========
        if self._llm_online:
            # 模式 1：LLM 在线 → 发送给 LLM
            # LLM 的 system prompt 中注入了命令说明，
            # 它知道如何理解"切换到 kimi"这样的自然语言并自动执行
            await self._event_bus.publish(Event(
                event_type="user.input",
                source="access",
                payload={
                    "user_id": "cli_user",
                    "content": raw,
                    "channel": "cli",
                    "session_id": self._session_id,
                },
                priority=Priority.NORMAL,
            ))
        else:
            # 模式 2：LLM 离线 → 提示用户使用 /xxx 命令
            self.print_output(
                "⚠️ 当前 LLM 离线，无法处理自然语言。\n"
                "  请使用 /xxx 命令操作，输入 /help 查看可用命令。\n"
                "  例如: /switch kimi  切换模型\n"
                "        /setkey deepseek sk-xxx  修改 API Key\n"
                "        /reconfig  进入配置菜单"
            )

    # ------------------------------------------------------------------ #
    # 本地命令处理（不依赖 LLM）
    # ------------------------------------------------------------------ #
    async def _handle_setkey(self, args: list) -> None:
        """处理 /setkey 命令：/setkey <厂商> [key]"""
        if not args:
            self.print_output("用法: /setkey <厂商> [key]  例如: /setkey deepseek sk-xxx...")
            return

        provider = args[0]
        editor = ConfigEditor(self._event_bus, input_func=self._async_input)

        if len(args) >= 2:
            api_key = args[1]
            self.print_output(f"正在验证 {provider} 的 API Key...")
            wizard = editor._wizard
            models = []
            for k, (pid, name, mdl_list) in wizard.PROVIDERS.items():
                if pid == provider:
                    models = mdl_list
                    break
            if editor._wizard._verify_key(provider, api_key, models):
                self.print_output("✅ 验证通过。")
                await editor.set_provider_key(provider, api_key)
            else:
                self.print_output("❌ 验证失败，Key 可能无效。")
                retry = await self._async_input("  仍要保存? [y/N]: ")
                if retry.lower() in ("y", "yes"):
                    await editor.set_provider_key(provider, api_key)
                else:
                    self.print_output("已取消。")
        else:
            await editor.verify_and_set_key(provider)

    async def _handle_reconfig(self) -> None:
        """处理 /reconfig 命令：进入配置菜单。"""
        editor = ConfigEditor(self._event_bus, input_func=self._async_input)
        await editor.run_menu()

    async def _handle_switch(self, args: list) -> None:
        """处理 /switch 命令：/switch <厂商> [模型]"""
        if not args:
            self.print_output("用法: /switch <厂商> [模型]  例如: /switch kimi")
            return
        
        await self._event_bus.publish(Event(
            event_type="user.command",
            source="access",
            payload={
                "command": "switch",
                "args": args,
                "session_id": self._session_id,
                "channel": "cli",
                "user_id": "cli_user",
            },
            priority=Priority.NORMAL,
        ))

    async def _handle_models(self) -> None:
        """处理 /models 命令：列出所有厂商和模型。"""
        await self._event_bus.publish(Event(
            event_type="user.command",
            source="access",
            payload={
                "command": "models",
                "args": [],
                "session_id": self._session_id,
                "channel": "cli",
                "user_id": "cli_user",
            },
            priority=Priority.NORMAL,
        ))

    async def _handle_config(self, args: list) -> None:
        """处理 /config 命令：查看配置。"""
        await self._event_bus.publish(Event(
            event_type="user.command",
            source="access",
            payload={
                "command": "config",
                "args": args,
                "session_id": self._session_id,
                "channel": "cli",
                "user_id": "cli_user",
            },
            priority=Priority.NORMAL,
        ))

    async def _handle_model(self) -> None:
        """处理 /model 命令：查看当前模型。"""
        await self._event_bus.publish(Event(
            event_type="user.command",
            source="access",
            payload={
                "command": "model",
                "args": [],
                "session_id": self._session_id,
                "channel": "cli",
                "user_id": "cli_user",
            },
            priority=Priority.NORMAL,
        ))

    async def _handle_reload(self) -> None:
        """处理 /reload 命令：重载配置。"""
        await self._event_bus.publish(Event(
            event_type="user.command",
            source="access",
            payload={
                "command": "reload",
                "args": [],
                "session_id": self._session_id,
                "channel": "cli",
                "user_id": "cli_user",
            },
            priority=Priority.NORMAL,
        ))

    async def _handle_clear(self) -> None:
        """处理 /clear 命令：清空会话上下文。"""
        await self._event_bus.publish(Event(
            event_type="user.command",
            source="access",
            payload={
                "command": "clear",
                "args": [],
                "session_id": self._session_id,
                "channel": "cli",
                "user_id": "cli_user",
            },
            priority=Priority.NORMAL,
        ))

    def _print_help(self) -> None:
        """打印帮助信息。

        所有命令统一使用 /xxx 格式。
        """
        help_text = """
╔══════════════════════════════════════════════╗
║            Suri Agent CLI 命令手册            ║
╚══════════════════════════════════════════════╝

━━━ 基础命令 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  /help                显示本帮助
  /quit                退出程序
  /status              查看系统运行状态
  /model               查看当前使用的模型
  /clear               清空当前会话的对话历史

━━━ 模型配置 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  /models              列出所有可用厂商和模型
  /switch <厂商> [模型] 切换模型（/switch kimi）
  /setkey <厂商> [key]  修改厂商 API Key（/setkey deepseek sk-xxx）
  /reconfig            进入交互式配置菜单

━━━ 系统管理 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  /reload              重载配置文件
  /logs                查看日志文件路径
  /config [key]        查看配置（/config / config llm_gateway.default_provider）

━━━ 双模式说明 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  LLM 在线时：直接输入自然语言即可（如"切换到 kimi"）
  LLM 离线时：请使用 /xxx 命令操作
  所有 /xxx 命令不依赖 LLM，确保关键操作永远可用
"""
        self.print_system(help_text.strip())
