"""CLI 通道插件 — 独立通道插件，符合 PRD 通道规范。

PRD：
- prd/plugins/access/channels/cli.md（通道架构、输入循环、提示符管理）
- prd/operations/command-system.md（命令注册与发现体系）
- prd/plugins/access/formatter-spec.md（面板渲染规范）

架构：
- PromptManager 统一管理提示符状态
- 三种交互范式：命令式(/xxx)、浏览式(数字)、对话式(自然语言)
- 基于 COMMAND_REGISTRY 的路由（取代硬编码 if-else）
- 异步输入循环，线程安全输出
"""

import asyncio
import json
import os
import queue  # 线程安全队列
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent_framework.plugins.access.session_hub import (
    ChannelCapabilities, SessionMessage, SessionOutput,
    SESSION_ACTIVE,
)
from agent_framework.plugins.access.base import BaseChannel
from agent_framework.plugins.access.formatter import MessageFormatter
from agent_framework.shared.commands import (
    CommandInfo, get_command, list_commands,
    register_command, unregister_command, load_commands_from_manifests,
)
from agent_framework.shared.utils.event_types import Event, Priority


# ═══════════════════════════════════════════════════════════════════ #
# PromptManager — 提示符管理器
# ═══════════════════════════════════════════════════════════════════ #

class PromptManager:
    """集中管理终端提示符状态。

    职责：
    - 初始启动时显示 > 提示符
    - 输出内容后自动恢复提示符
    - 用户输入时隐藏提示符
    - 多行模式切换提示符样式
    - 输出时不破坏用户已输入内容
    """

    STATE_IDLE = 0
    STATE_INPUT = 1
    STATE_OUTPUT = 2
    STATE_MULTILINE = 3

    def __init__(self):
        self._state = self.STATE_IDLE
        self._prompt = "> "
        self._multiline_prompt = "... "
        self._input_buffer = ""
        self._last_panel = None  # "models" | "plugins" | None

    @property
    def state(self) -> int:
        return self._state

    @property
    def input_buffer(self) -> str:
        return self._input_buffer

    @input_buffer.setter
    def input_buffer(self, value: str):
        self._input_buffer = value

    @property
    def last_panel(self) -> Optional[str]:
        return self._last_panel

    @last_panel.setter
    def last_panel(self, value: Optional[str]):
        self._last_panel = value

    def show_prompt(self) -> None:
        """显示提示符（IDLE 状态）。"""
        sys.stdout.write(self._prompt)
        sys.stdout.flush()
        self._state = self.STATE_IDLE

    def show_multiline_prompt(self) -> None:
        """显示多行模式提示符。"""
        sys.stdout.write(self._multiline_prompt)
        sys.stdout.flush()
        self._state = self.STATE_MULTILINE

    def on_output(self, text: str) -> None:
        """【光标安全】输出内容，确保光标始终回到 > 提示符。

        关键行为：
        1. 保存 readline 中用户正在编辑的输入（没按回车那种）
        2. \r\033[K 清除当前行（无论用户正在输入什么）
        3. 输出回复文本（去除末尾多余换行避免双空行）
        4. 在新行打印 > 提示符
        5. 恢复用户之前正在编辑的输入（如果有）
        """
        saved_input = ""
        try:
            import readline as _rl
            buf = _rl.get_line_buffer()
            if buf:
                saved_input = buf
        except (ImportError, RuntimeError, AttributeError):
            pass
        # 如果 _input_buffer 有值（逐字符追踪），优先用这个
        if self._input_buffer and not saved_input:
            saved_input = self._input_buffer

        # 清除当前行 → 输出回复（去尾换行）→ 提示符 → 恢复用户输入
        clean_text = text.rstrip('\n')
        sys.stdout.write(f"\r\033[K{clean_text}\n{self._prompt}")
        if saved_input:
            sys.stdout.write(saved_input)
        sys.stdout.flush()
        self._state = self.STATE_IDLE

    def on_output_no_prompt(self, text: str) -> None:
        """输出内容但不重绘提示符（用于流式输出）。"""
        sys.stdout.write(f"\r\033[K{text}\n")
        sys.stdout.flush()

    def clear_line(self) -> None:
        """清除当前行内容。"""
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def on_cancel(self) -> None:
        """用户按 Ctrl+C 取消当前输入。"""
        self._input_buffer = ""
        sys.stdout.write("\n")
        self.show_prompt()

    def on_exit(self) -> None:
        """程序退出时清除提示符。"""
        self.clear_line()


# ═══════════════════════════════════════════════════════════════════ #
# CLIChannelPlugin — CLI 通道插件
# ═══════════════════════════════════════════════════════════════════ #

class CLIChannelPlugin(BaseChannel):
    """CLI 通道插件。

    作为独立通道插件注册到 SessionHub。
    使用 asyncio 实现非阻塞标准输入读取，支持三种交互范式。
    """

    def __init__(self, event_bus=None, session_id: str = ""):
        super().__init__(event_bus, session_id)
        self._running = False
        self._llm_online = True
        self._task: Optional[asyncio.Task] = None
        self._session_id = session_id
        self._session_hub = None
        self._input_queue: asyncio.Queue = asyncio.Queue()
        self._input_thread: Optional[threading.Thread] = None
        self._readline_available = False
        self._pm = PromptManager()

        # 内置命令处理器（不依赖 EventBus，本地处理）
        # 包含所有旧版 cli.py 中的命令 + 新增的插件和模型命令
        self._builtin_commands = {
            # 基础
            "help": self._handle_help,
            "quit": self._handle_quit,
            "exit": self._handle_quit,
            "status": self._handle_status,
            "history": self._handle_history,
            "clear": self._handle_clear,
            # 插件
            "plugins": self._handle_plugins,
            "plugin": self._handle_plugin_detail,
            # 模型
            "models": self._handle_models,
            "model": self._handle_model,
            "switch": self._handle_switch,
            "setkey": self._handle_setkey,
            # 系统
            "reconfig": self._handle_reconfig,
            "config": self._handle_config,
            "reload": self._handle_reload,
            "logs": self._handle_logs,
            "sessions": self._handle_sessions,
            # 热更新
            "hotreload": self._handle_hotreload,
        }

        # 插件元数据缓存
        self._plugins_cache: List[Dict] = []
        self._providers_cache: Dict[str, Dict] = {}
        self._api_keys_cache: Dict[str, str] = {}
        self._active_provider_cache: str = ""
        self._active_model_cache: str = ""
        self._health_cache: Dict[str, Dict] = {}

        # 初始化命令行补全
        self._init_readline()

        # 系统就绪标志（启动完成前忽略插件事件）
        self._started = False

    def _init_readline(self) -> None:
        """初始化 readline 支持。"""
        try:
            import readline
            self._readline_available = True
            history_file = os.path.expanduser("~/.suri/.cli_history")
            try:
                readline.read_history_file(history_file)
            except (FileNotFoundError, OSError):
                pass
            readline.set_history_length(500)

            # 注册自定义补全器
            try:
                readline.set_completer(self._completer)
                readline.parse_and_bind("tab: complete")
            except Exception:
                pass
        except ImportError:
            self._readline_available = False

    def _completer(self, text: str, state: int) -> Optional[str]:
        """readline 补全回调。"""
        import readline
        try:
            # 获取当前输入行
            line = readline.get_line_buffer()
            if not line:
                return None

            # 获取所有补全项
            if line.startswith("/"):
                # 命令补全
                commands = list_commands()
                candidates = [f"/{name}" for name in commands
                             if f"/{name}".startswith(line)]
                # 加上内置命令
                for cmd_name in self._builtin_commands:
                    if f"/{cmd_name}".startswith(line) and f"/{cmd_name}" not in candidates:
                        candidates.append(f"/{cmd_name}")
            else:
                # 如果是 /models 面板后，补全厂商名
                if self._pm.last_panel == "models":
                    candidates = [p for p in self._providers_cache
                                 if p.startswith(line)]
                else:
                    return None

            if not candidates:
                return None

            if state < len(candidates):
                return sorted(candidates)[state] + " "
            return None
        except Exception:
            return None

    # ── 属性 ──

    @property
    def channel_type(self) -> str:
        return "cli"

    @property
    def capabilities(self) -> ChannelCapabilities:
        """CLI 通道能力矩阵。"""
        return ChannelCapabilities(
            text=True,
            markdown=True,
            html=False,
            commands=True,
            images=False,
            video=False,
            audio=False,
            files=False,
            file_max_size_mb=0,
            buttons=False,
            forms=False,
            sliders=False,
            text_stream=True,
            file_stream=False,
            rich_ui=False,
            notifications=False,
            dynamic_content=False,
            offline_mode=False,
            local_storage=False,
            clipboard=False,
            voice=False,
            location=False,
            identity=False,
            degrade_chain={
                "rich": ["markdown", "text"],
                "video": ["image", "text"],
                "file": ["text"],
                "html": ["markdown", "text"],
                "image": ["text"],
            },
        )

    # ── 生命周期 ──

    async def start(self, session_hub=None) -> None:
        """启动 CLI 通道。
        
        启动期间只做准备工作（注册 SessionHub、加载命令、加载配置），
        不在启动完成前显示面板或启动输入循环。
        面板渲染和输入循环在收到 system.started 事件后触发。
        """
        self._session_hub = session_hub
        self._running = True

        # 注册到 SessionHub
        if session_hub:
            await session_hub.register_channel(
                name="channel.cli",
                channel_type="cli",
                capabilities=self.capabilities,
                handler=self,
                manifest={
                    "version": "1.0.0",
                    "description": "终端 CLI 交互通道",
                },
            )
            session = session_hub.create_session(
                channel_type="cli",
                channel_id="terminal",
                capabilities=self.capabilities,
                isolation_layer="adhoc",
            )
            self._session_id = session.session_id

        # 加载插件命令（从 self._plugin_manager 获取 manifest）
        if hasattr(self, '_plugin_manager') and self._plugin_manager:
            pm = self._plugin_manager
            manifests_dict = {}
            for pid, plugin in pm._plugins.items():
                manifest = getattr(plugin, '_manifest_path', None) or pm._manifests.get(pid)
                if isinstance(manifest, dict):
                    manifests_dict[pid] = manifest
                elif manifest and isinstance(manifest, (str, Path)):
                    manifest_path = Path(manifest)
                    if manifest_path.exists():
                        try:
                            with open(manifest_path, 'r') as f:
                                manifests_dict[pid] = json.load(f)
                        except (json.JSONDecodeError, OSError):
                            pass
            if manifests_dict:
                load_commands_from_manifests(manifests_dict)
        else:
            # 降级：使用默认 manifest 数据
            manifests_dict = {
                "llm_gateway": {
                    "commands": [
                        {"name": "switch", "usage": "/switch <厂商> [模型]", "desc": "切换 LLM 厂商",
                         "args": [{"name": "厂商", "required": True, "desc": "厂商名"},
                                  {"name": "模型", "required": False, "desc": "模型名"}]},
                        {"name": "setkey", "usage": "/setkey <厂商> [key]", "desc": "修改 API Key",
                         "args": [{"name": "厂商", "required": True, "desc": "厂商名"},
                                  {"name": "key", "required": False, "desc": "API Key"}]},
                        {"name": "models", "usage": "/models", "desc": "列出所有可用模型", "args": []},
                        {"name": "model", "usage": "/model", "desc": "查看当前模型", "args": []},
                    ]
                }
            }
            load_commands_from_manifests(manifests_dict)

        # 注册内置命令
        for cmd_name in self._builtin_commands:
            register_command(CommandInfo(
                name=cmd_name,
                plugin_id="cli",
                usage=f"/{cmd_name}",
                description=f"内置命令: {cmd_name}",
                handler="builtin",
            ))

        # 从 config.json 加载配置
        self._load_config()

        # 订阅系统就绪事件（收到此事件后才开始渲染面板、订阅插件事件、启动输入循环）
        if self._event_bus:
            self._event_bus.subscribe("system.started", self._on_system_started)

    def start_sync(self, session_hub=None) -> None:
        """同步启动（用于旧版兼容）。"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.start(session_hub))
        loop.run_until_complete(self._run_input_loop())

    def _load_config(self) -> None:
        """从 config.json 加载配置。"""
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            llm_cfg = cfg.get("llm_gateway", {})
            providers = llm_cfg.get("providers", {})

            self._providers_cache = {}
            self._api_keys_cache = {}
            self._active_provider_cache = llm_cfg.get("default_provider", "deepseek")

            for pid, pcfg in providers.items():
                self._providers_cache[pid] = {
                    "name": pcfg.get("name", pid),
                    "models": pcfg.get("models", []),
                    "default_model": pcfg.get("default_model", ""),
                }
                if pcfg.get("api_key"):
                    self._api_keys_cache[pid] = pcfg["api_key"]

            # 确定活跃模型
            active_pcfg = providers.get(self._active_provider_cache, {})
            active_models = active_pcfg.get("models", [])
            default = active_pcfg.get("default_model", "")
            self._active_model_cache = default or (active_models[0] if active_models else "")

            # 刷新缓存
            self._refresh_providers_from_config()

        except Exception:
            pass

    def _refresh_providers_from_config(self) -> None:
        """从配置文件刷新提供商缓存。"""
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            return
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            llm_cfg = cfg.get("llm_gateway", {})
            providers = llm_cfg.get("providers", {})
            for pid, pcfg in providers.items():
                if pid not in self._providers_cache:
                    self._providers_cache[pid] = {
                        "name": pcfg.get("name", pid),
                        "models": pcfg.get("models", []),
                        "default_model": pcfg.get("default_model", ""),
                    }
                if pcfg.get("api_key") and pid not in self._api_keys_cache:
                    self._api_keys_cache[pid] = pcfg["api_key"]
        except Exception:
            pass

    async def _show_startup_panel(self) -> None:
        """显示完整的启动面板（全量插件列表 + LLM 模型状态 + 真实健康数据）。"""
        # 获取插件列表
        self._plugins_cache = await self._fetch_plugins()

        # 从 llm_gateway 获取真实健康数据
        if hasattr(self, '_plugin_manager') and self._plugin_manager:
            llm_gw = self._plugin_manager._plugins.get('llm_gateway')
            if llm_gw and hasattr(llm_gw, 'get_health'):
                self._health_cache = llm_gw.get_health()

        # 渲染完整启动面板
        panel = MessageFormatter.format_startup_panel(
            plugins=self._plugins_cache,
            providers=self._providers_cache,
            active_provider=self._active_provider_cache,
            active_model=self._active_model_cache,
            api_keys=self._api_keys_cache,
            health=self._health_cache,
        )
        self._pm.last_panel = "plugins"
        self.print_system(panel)

    # ── 系统就绪事件 ──

    async def _on_system_started(self, event: Event) -> None:
        """收到 system.started 事件后，启动 CLI 通道的完整功能。

        这是启动时序的关键：bootstrap 的 Step 12 广播 system.started，
        此时所有 14 个插件已加载完毕。CLI 在此处：
        1. 渲染启动面板（全量插件列表 + LLM 模型状态）
        2. 订阅插件状态变化事件（启动后不会有回放）
        3. 启动纯 asyncio 输入循环（显示 > 提示符）
        """
        # 标记系统已就绪
        self._started = True

        # 订阅插件状态变化事件（现在订阅，不会收到启动期间的回放事件）
        if self._event_bus:
            self._event_bus.subscribe("system.plugin_loaded", self._on_plugin_event)
            self._event_bus.subscribe("system.plugin_unloaded", self._on_plugin_event)
            self._event_bus.subscribe("plugin.status_changed", self._on_plugin_event)
            self._event_bus.subscribe("plugin.manifest_updated", self._on_plugin_event)

        # 显示启动面板
        await self._show_startup_panel()

        # 启动纯 asyncio 输入循环（自动显示 > 提示符）
        self._task = asyncio.create_task(self._input_loop())

    # ── 输入循环（纯 asyncio 版）──
    #
    # 使用 asyncio.StreamReader 连接系统标准输入，
    # 避免 threading 和 input() 的各种兼容性问题。
    # 不再需要 \r\033[K 清除行——所有输出前加 \n。

    async def _start_input_async(self) -> None:
        """启动 asyncio 标准输入读取。
        
        非 TTY 环境（测试/管道）安全跳过，不阻塞。
        """
        if not sys.stdin.isatty():
            # 非 TTY 环境（自动化测试、管道模式），
            # connect_read_pipe 会永久等待输入，
            # 这里静默跳过，让调用方自行处理
            return
        loop = asyncio.get_event_loop()
        self._stdin_reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._stdin_reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    async def _input_loop(self) -> None:
        """纯 asyncio 输入循环。

        流程：
        1. 显示 > 提示符
        2. 异步读取一行（按 Enter 结束）
        3. 处理用户输入（发送给 LLM 或执行命令）
        4. 回到步骤 1

        终端自然回显用户输入，所以用户看到：
        > hello
        > [suri] Hi!
        """
        await self._start_input_async()

        # 显示初始提示符
        sys.stdout.write("> ")
        sys.stdout.flush()

        # 非 TTY 环境：跳过输入循环（测试模式）
        if not sys.stdin.isatty():
            self._running = False
            return

        while self._running:
            line = await self._stdin_reader.readline()
            if not line:
                break
            text = line.decode('utf-8', errors='replace').rstrip('\n').rstrip('\r')
            if text:
                await self._on_user_input(text)
            # 显示下一个提示符
            sys.stdout.write("> ")
            sys.stdout.flush()

    async def _run_input_loop(self) -> None:
        """运行输入循环（同步启动使用）。"""
        await self._input_loop()

    # ═══════════════════════════════════════════════════════════════ #
    # 输入路由 — 三种交互范式
    # ═══════════════════════════════════════════════════════════════ #

    async def _on_user_input(self, text: str) -> None:
        """处理用户输入。

        三种交互范式：
        1. 命令式 (/xxx) → 本地处理 或 EventBus 路由
        2. 浏览式 (纯数字) → 插件详情查看
        3. 对话式 (自然语言) → LLM 处理

        格式说明：
        - 先打印 `> 用户输入` 标记用户发言
        - 再打印 LLM 回复
        - 用户能清晰区分"我说的"和"suri 说的"
        """
        raw = text.strip()
        if not raw:
            return

        # === 路由判断 ===
        # 不打印 "> {raw}" — 终端 readline 已显示输入行
        # 由 [suri] 前缀区分发言者
        # 1. 命令式
        if raw.startswith("/"):
            cmd_name = raw[1:].split()[0]
            args = raw[1:].split()[1:]
            await self._handle_command(cmd_name, args)
            return

        # 2. 浏览式 — 纯数字，检查是否为有效插件编号
        if raw.isdigit():
            num = int(raw)
            if 1 <= num <= len(self._plugins_cache):
                plugin = self._plugins_cache[num - 1]
                detail = MessageFormatter.format_plugin_detail(
                    plugin,
                    dependents=self._get_dependents(plugin.get("id", "")),
                    plugin_index=num,
                )
                self.print_output(detail)
                self._pm.last_panel = f"detail:{plugin.get('id', '')}"
                return

        # 3. 厂商名快速切换（在 /models 面板后）
        if self._pm.last_panel == "models" and raw.lower() in self._providers_cache:
            provider_id = raw.lower()
            await self._execute_switch(provider_id)
            # 重新显示面板
            panel = MessageFormatter.format_model_status(
                providers=self._providers_cache,
                active_provider=self._active_provider_cache,
                active_model=self._active_model_cache,
                api_keys=self._api_keys_cache,
                health=self._health_cache,
            )
            self.print_output(panel)
            self._pm.last_panel = "models"
            return

        # 4. 对话式 — 自然语言
        if self._llm_online:
            await self._send_to_llm(raw)
        else:
            self.print_output(
                "⚠️ 当前 LLM 离线，无法处理自然语言。\n"
                "  请使用 /xxx 命令操作，输入 /help 查看可用命令。"
            )

    # ── 命令路由 ──

    async def _handle_command(self, cmd_name: str, args: List[str]) -> None:
        """路由命令到对应的处理器。"""
        # 1. 检查内置命令
        if cmd_name in self._builtin_commands:
            await self._builtin_commands[cmd_name](args)
            return

        # 2. 检查 COMMAND_REGISTRY
        cmd_info = get_command(cmd_name)
        if cmd_info:
            if cmd_info.handler == "builtin":
                # 理论上不会到这里，内置命令已在上一步处理
                return
            else:
                # 通过 EventBus 发布到对应插件
                await self._event_bus.publish(Event(
                    event_type="user.command",
                    source="cli",
                    payload={
                        "command": cmd_info.name,
                        "args": args,
                        "session_id": self._session_id,
                        "channel": "cli",
                        "user_id": "cli_user",
                    },
                    priority=Priority.NORMAL,
                ))
                return

        # 3. 未知命令
        self.print_output(
            f"⚠️ 未知命令 /{cmd_name}，输入 /help 查看可用命令"
        )

    # ═══════════════════════════════════════════════════════════════ #
    # 内置命令处理器
    # ═══════════════════════════════════════════════════════════════ #

    async def _handle_help(self, args: List[str]) -> None:
        """显示帮助信息。"""
        lines = []
        lines.append("━" * 50)
        lines.append("  Suri Agent CLI 命令手册")
        lines.append("━" * 50)
        lines.append("")
        lines.append("━━━ 基础命令 ━━━━━━━━━━━━━━━━━━━")
        lines.append("  /help                显示本帮助")
        lines.append("  /quit                退出程序")
        lines.append("  /status              查看系统状态")
        lines.append("  /model               查看当前模型")
        lines.append("  /clear               清空会话")
        lines.append("  /history             显示命令历史")
        lines.append("")
        lines.append("━━━ 插件管理 ━━━━━━━━━━━━━━━━━━━")
        lines.append("  /plugins             列出所有插件")
        lines.append("  输入编号 (如 1)       查看插件详情")
        lines.append("")
        lines.append("━━━ 模型配置 ━━━━━━━━━━━━━━━━━━━")
        lines.append("  /models              列出所有厂商和模型")
        lines.append("  /switch <厂商> [模型] 切换模型")
        lines.append("  /setkey <厂商> [key]  修改 API Key")
        lines.append("  /model               查看当前模型")
        lines.append("")
        lines.append("━━━ 系统管理 ━━━━━━━━━━━━━━━━━━━")
        lines.append("  /reload              重载配置")
        lines.append("  /logs                查看日志路径")
        lines.append("  /config [key]        查看配置")
        lines.append("  /reconfig            进入配置菜单")
        lines.append("  /sessions            查看会话统计")
        lines.append("")
        # 显示所有已注册命令
        all_cmds = list_commands()
        if all_cmds:
            lines.append("━━━ 插件注册命令 ━━━━━━━━━━━━━━━━")
            for name, info in all_cmds.items():
                if name in self._builtin_commands:
                    continue
                lines.append(f"  /{name:<15s} {info.description}")
        lines.append("")
        lines.append("提示: 按 Tab 键可自动补全命令")
        self.print_output("\n".join(lines))

    async def _handle_quit(self, args: List[str]) -> None:
        """退出程序。"""
        self.print_system("Goodbye.")
        self._save_history()
        self._running = False
        # 延迟退出，让输出显示
        asyncio.create_task(self._delayed_exit())

    async def _delayed_exit(self) -> None:
        """延迟退出。"""
        await asyncio.sleep(0.5)
        os._exit(0)

    async def _handle_plugins(self, args: List[str]) -> None:
        """显示插件列表。"""
        self._plugins_cache = await self._fetch_plugins()
        panel = MessageFormatter.format_plugin_list(self._plugins_cache)
        self.print_output(panel)
        self._pm.last_panel = "plugins"

    async def _handle_plugin_detail(self, args: List[str]) -> None:
        """显示插件详情或执行管理操作（/plugin 5 或 /plugin llm_gateway）。

        子命令：
        /plugin 5                   查看 5 号插件详情
        /plugin stop 3              暂停 3 号插件
        /plugin start 3             启动 3 号插件
        /plugin restart 3           重启 3 号插件
        /plugin upgrade 3           升级 3 号插件
        /plugin remove 3            删除 3 号插件
        """
        if not args:
            self.print_output("用法: /plugin <操作> [参数]\n"
                              "  查看: /plugin <编号或名称>\n"
                              "  管理: /plugin start|stop|restart|upgrade|remove <编号>")
            return

        # 检查是否为管理操作
        manage_ops = {"start", "stop", "restart", "upgrade", "remove"}
        if args[0].lower() in manage_ops:
            await self._handle_plugin_manage(args)
            return

        query = args[0]

        # 按编号查找
        if query.isdigit():
            num = int(query)
            if 1 <= num <= len(self._plugins_cache):
                plugin = self._plugins_cache[num - 1]
                idx = num
            else:
                self.print_output(f"❌ 无效编号: {query}")
                return
        else:
            # 按名称查找
            matched = [p for p in self._plugins_cache if p.get("id") == query or p.get("name") == query]
            if not matched:
                self.print_output(f"❌ 未找到插件: {query}")
                return
            plugin = matched[0]
            idx = None
            for i, p in enumerate(self._plugins_cache, 1):
                if p.get("id") == plugin.get("id"):
                    idx = i
                    break

        detail = MessageFormatter.format_plugin_detail(
            plugin,
            dependents=self._get_dependents(plugin.get("id", "")),
            plugin_index=idx,
        )
        self.print_output(detail)
        # 设置 last_panel 为 detail:plugin_id 以便事件刷新
        self._pm.last_panel = f"detail:{plugin.get('id', '')}"

    async def _handle_models(self, args: List[str]) -> None:
        """显示模型状态面板（含真实健康数据）。"""
        # 刷新配置
        self._refresh_providers_from_config()

        # 从 llm_gateway 获取真实健康数据
        if hasattr(self, '_plugin_manager') and self._plugin_manager:
            llm_gw = self._plugin_manager._plugins.get('llm_gateway')
            if llm_gw and hasattr(llm_gw, 'get_health'):
                self._health_cache = llm_gw.get_health()

        panel = MessageFormatter.format_model_status(
            providers=self._providers_cache,
            active_provider=self._active_provider_cache,
            active_model=self._active_model_cache,
            api_keys=self._api_keys_cache,
            health=self._health_cache,
        )
        self.print_output(panel)
        self._pm.last_panel = "models"

    async def _handle_model(self, args: List[str]) -> None:
        """显示当前模型。"""
        provider_name = self._providers_cache.get(
            self._active_provider_cache, {}
        ).get("name", self._active_provider_cache)
        has_key = self._active_provider_cache in self._api_keys_cache
        status = "在线" if has_key else "离线"
        panel = MessageFormatter.format_current_model(
            self._active_provider_cache, provider_name,
            self._active_model_cache, status,
        )
        self.print_output(panel)

    async def _handle_history(self, args: List[str]) -> None:
        """显示命令历史。"""
        if not self._readline_available:
            self.print_output("readline 不可用，无法显示历史记录。")
            return

        import readline
        hist_len = readline.get_current_history_length()
        if hist_len == 0:
            self.print_output("暂无历史记录。")
            return

        start = max(0, hist_len - 20)
        lines = ["━━━ 最近命令历史 ━━━━━"]
        for i in range(start, hist_len):
            item = readline.get_history_item(i)
            if item:
                lines.append(f"  {i:3d}. {item}")
        self.print_output("\n".join(lines))

    async def _handle_clear(self, args: List[str]) -> None:
        """清屏。"""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    # ═══════════════════════════════════════════════════════════════ #
    # 新增命令：/status, /switch, /setkey, /reconfig, /config,
    #           /reload, /logs, /sessions, /hotreload
    # ═══════════════════════════════════════════════════════════════ #

    async def _handle_status(self, args: List[str]) -> None:
        """显示系统运行状态。"""
        online = "✅ 在线" if self._llm_online else "❌ 离线"
        provider_name = self._providers_cache.get(
            self._active_provider_cache, {}
        ).get("name", self._active_provider_cache)
        lines = [
            "━━━ 系统状态 ━━━━━━━━━━━━━━━━━━━━━",
            f"  LLM 状态:    {online}",
            f"  当前厂商:    {provider_name}",
            f"  当前模型:    {self._active_model_cache}",
            f"  插件数量:    {len(self._plugins_cache) or '未加载'}",
            f"  会话 ID:     {self._session_id}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        self.print_output("\n".join(lines))

    async def _handle_switch(self, args: List[str]) -> None:
        """处理 /switch 命令。"""
        if not args:
            self.print_output("用法: /switch <厂商> [模型]  例如: /switch kimi")
            return

        provider_id = args[0].lower()

        if provider_id not in self._providers_cache:
            self.print_output(f"❌ 未知厂商: {provider_id}")
            self.print_output(f"   可用: {', '.join(self._providers_cache.keys())}")
            return

        model = args[1] if len(args) >= 2 else None

        if model:
            # 检查模型是否在可用列表中
            available_models = self._providers_cache[provider_id].get("models", [])
            if model not in available_models:
                self.print_output(f"⚠️ 模型 {model} 不在 {provider_id} 的可用列表中")
                self.print_output(f"   可用: {', '.join(available_models)}")
        
        # 通过 EventBus 执行切换
        await self._execute_switch(provider_id, model)

    async def _execute_switch(self, provider_id: str, model: Optional[str] = None) -> None:
        """执行模型切换（内部实现）。"""
        if provider_id not in self._providers_cache:
            self.print_output(f"❌ 未知厂商: {provider_id}")
            return

        # 发布切换事件到 LLM Gateway
        switch_args = [provider_id]
        if model:
            switch_args.append(model)

        await self._event_bus.publish(Event(
            event_type="user.command",
            source="cli",
            payload={
                "command": "switch",
                "args": switch_args,
                "session_id": self._session_id,
                "channel": "cli",
                "user_id": "cli_user",
            },
            priority=Priority.NORMAL,
        ))

        # 更新本地缓存
        self._active_provider_cache = provider_id
        models = self._providers_cache[provider_id].get("models", [])
        default = self._providers_cache[provider_id].get("default_model", "")
        self._active_model_cache = model or default or (models[0] if models else "")

        provider_name = self._providers_cache[provider_id].get("name", provider_id)
        self.print_output(f"✅ 已切换到 {provider_name} / {self._active_model_cache}")

        # 更新配置文件
        await self._update_config_switch(provider_id, self._active_model_cache)

    async def _update_config_switch(self, provider_id: str, model: str) -> None:
        """更新配置文件中的默认厂商和模型。"""
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            return
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            llm = cfg.setdefault("llm_gateway", {})
            llm["default_provider"] = provider_id
            providers = llm.setdefault("providers", {})
            if provider_id in providers:
                providers[provider_id]["default_model"] = model
            with open(config_path, "w") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    async def _handle_setkey(self, args: List[str]) -> None:
        """处理 /setkey 命令。"""
        if not args:
            self.print_output("用法: /setkey <厂商> [key]  例如: /setkey deepseek sk-xxx...")
            return

        provider = args[0].lower()
        if provider not in self._providers_cache:
            self.print_output(f"❌ 未知厂商: {provider}")
            self.print_output(f"   可用: {', '.join(self._providers_cache.keys())}")
            return

        if len(args) >= 2:
            api_key = args[1]
            # 保存到配置文件
            config_path = Path.home() / ".suri" / "config.json"
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                cfg = {"llm_gateway": {"providers": {}}}

            llm = cfg.setdefault("llm_gateway", {})
            providers = llm.setdefault("providers", {})
            pcfg = providers.setdefault(provider, {})
            pcfg["api_key"] = api_key

            # 设置默认模型（如果有）
            if not pcfg.get("models"):
                pcfg["models"] = self._providers_cache[provider].get("models", [])

            with open(config_path, "w") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)

            # 更新缓存
            self._api_keys_cache[provider] = api_key
            self.print_output(f"✅ {provider} 的 API Key 已保存。")

            # 发布配置变更事件
            await self._event_bus.publish(Event(
                event_type="config.updated",
                source="cli",
                payload={
                    "plugin_id": "llm_gateway",
                    "config_key": "providers",
                    "file_path": str(config_path),
                },
                priority=Priority.NORMAL,
            ))
        else:
            self.print_output(f"请提供 Key: /setkey {provider} <api_key>")

    async def _handle_reconfig(self, args: List[str]) -> None:
        """进入配置菜单。"""
        from agent_framework.plugins.access.config_editor import ConfigEditor
        editor = ConfigEditor(self._event_bus, input_func=self._async_input)
        await editor.run_menu()

    async def _handle_config(self, args: List[str]) -> None:
        """查看配置。"""
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            self.print_output("❌ 未找到配置文件 (~/.suri/config.json)")
            return

        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)

            if args:
                # 按 key 路径查找配置
                key = args[0]
                keys = key.split(".")
                val = cfg
                for k in keys:
                    if isinstance(val, dict):
                        val = val.get(k, "N/A")
                    else:
                        val = "N/A"
                        break
                import json as _json
                self.print_output(f"  {key} = {_json.dumps(val, ensure_ascii=False, indent=2)}")
            else:
                # 显示概要
                llm = cfg.get("llm_gateway", {})
                access = cfg.get("access", {})
                lines = [
                    "━━━ 配置概要 ━━━━━━━━━━━━━━━",
                    f"  默认厂商:   {llm.get('default_provider', '未设置')}",
                    f"  已配置厂商: {len(llm.get('providers', {}))} 个",
                    f"  Telegram:   {'✅ 已启用' if access.get('channels', {}).get('telegram', {}).get('enabled') else '❌ 未启用'}",
                    f"  配置文件:   {config_path}",
                ]
                self.print_output("\n".join(lines))

        except json.JSONDecodeError:
            self.print_output("❌ 配置文件格式错误")

    async def _handle_reload(self, args: List[str]) -> None:
        """重载配置。"""
        self._load_config()
        self.print_output("✅ 配置已重载。")

        # 发布重载事件
        await self._event_bus.publish(Event(
            event_type="system.config_changed",
            source="cli",
            payload={"reason": "user_reload"},
            priority=Priority.NORMAL,
        ))

    async def _handle_logs(self, args: List[str]) -> None:
        """查看日志路径。"""
        log_path = os.path.expanduser("~/.suri/runtime/logs")
        self.print_output(f"日志目录: {log_path}")

        # 列出最近的日志文件
        if os.path.exists(log_path):
            log_files = sorted(Path(log_path).iterdir(), key=os.path.getmtime, reverse=True)[:5]
            if log_files:
                lines = ["最近日志文件:"]
                for f in log_files:
                    size = os.path.getsize(f)
                    lines.append(f"  {f.name} ({size} bytes)")
                self.print_output("\n".join(lines))

    async def _handle_sessions(self, args: List[str]) -> None:
        """查看会话统计。"""
        if self._session_hub:
            stats = self._session_hub.get_stats()
            lines = [
                "━━━ 会话统计 ━━━━━━━━━━━━━━━━━━━",
                f"  总会话:       {stats['total_sessions']}",
                f"  活跃:         {stats['active_sessions']}",
                f"  内存缓存:     {stats['memory_cache']}",
                f"  注册通道数:   {stats['registered_channels']}",
                f"  当前会话:     {self._session_id}",
            ]
            if stats.get('by_channel'):
                lines.append(f"  通道分布:     {stats['by_channel']}")
            self.print_output("\n".join(lines))
        else:
            self.print_output("SessionHub 未初始化。")

    async def _handle_hotreload(self, args: List[str]) -> None:
        """手动触发热更新。"""
        if not self._event_bus:
            self.print_output("❌ 事件总线未初始化。")
            return

        # 通知用户机制
        self.print_output("🔄 热更新功能已就绪。")
        self.print_output("")
        self.print_output("  支持的自动热更新场景：")
        self.print_output("  L1 - 配置文件变更（~/.suri/config.json）")
        self.print_output("  L2 - manifest.json 变更 → 命令自动刷新")
        self.print_output("  L3 - Python 代码变更 → importlib.reload")
        self.print_output("")
        self.print_output("  FileWatcher 每 2 秒轮询一次变更。")

        # 从 access/plugin.py 获取 HotReloadManager 状态
        hr_active = False
        if hasattr(self, '_plugin_manager') and self._plugin_manager:
            access_plugin = self._plugin_manager._plugins.get('access')
            if access_plugin and hasattr(access_plugin, '_hot_reload') and access_plugin._hot_reload:
                hr_active = True
        self.print_output("")
        self.print_output(f"  热更新系统: {'✅ 运行中' if hr_active else 'ℹ️ 未激活'}")

    # ═══════════════════════════════════════════════════════════════ #
    # 注意：_execute_switch / _update_config_switch 已在上方定义
    # （新定义支持 model 参数，覆盖了旧定义）
    # ═══════════════════════════════════════════════════════════════ #

    # ═══════════════════════════════════════════════════════════════ #
    # 插件数据获取
    # ═══════════════════════════════════════════════════════════════ #

    async def _fetch_plugins(self) -> List[Dict]:
        """从 PluginManager 获取所有插件元数据。

        注意：只从 PluginManager 获取真实插件，不包含 SessionHub 通道子模块。
        通道（cli、tg 等）是 access 插件内部的子模块，不应该出现在全局插件列表中。
        """
        plugins = []

        # 从 PluginManager 获取所有已注册插件（核心数据源）
        if hasattr(self, '_plugin_manager') and self._plugin_manager:
            pm = self._plugin_manager
            for pid, plugin in pm._plugins.items():
                # 从 _manifests 读取真实 dict（suri_core 已确保存为 dict 而非 Path）
                manifest = pm._manifests.get(pid, {})
                if isinstance(manifest, dict):
                    manifest_dict = manifest
                else:
                    # 降级：如果是 Path，尝试读取
                    if isinstance(manifest, (str, Path)):
                        try:
                            with open(manifest, "r", encoding="utf-8") as mf:
                                manifest_dict = json.load(mf)
                        except Exception:
                            manifest_dict = {"name": pid, "type": "unknown", "description": ""}
                    else:
                        manifest_dict = {"name": pid, "type": "unknown", "description": ""}
                
                # 判断运行状态
                status = "running"
                if hasattr(plugin, '_status'):
                    s = plugin._status
                    if s in ("running", "initialized", "paused", "stopped"):
                        status = s
                elif hasattr(plugin, '_running'):
                    status = "running" if plugin._running else "stopped"
                
                plugins.append({
                    "id": pid,
                    "name": manifest_dict.get("name", pid),
                    "version": manifest_dict.get("version", "?"),
                    "type": manifest_dict.get("type", "unknown"),
                    "description": manifest_dict.get("description", ""),
                    "status": status,
                    "heartbeat": 1,
                    "dependencies": manifest_dict.get("dependencies", []),
                    "permissions": manifest_dict.get("permissions", []),
                    "event_subscriptions": manifest_dict.get("event_subscriptions", []),
                    "config_schema": manifest_dict.get("config_schema", {}),
                    "operations": manifest_dict.get("operations", ["start", "stop", "restart"]),
                })

        if not plugins:
            # 降级：返回默认数据
            plugins = self._get_default_plugins()

        return plugins

    def _get_default_plugins(self) -> List[Dict]:
        """返回默认插件数据（当 PluginManager 不可用时）。"""
        return [
            {"id": "suri_core", "name": "suri_core", "version": "1.0.0",
             "type": "core", "description": "系统内核与健康检查",
             "status": "running", "heartbeat": 1, "dependencies": [],
             "permissions": ["system.*"], "event_subscriptions": ["system.*"],
             "config_schema": {}},
            {"id": "access", "name": "access", "version": "1.0.0",
             "type": "integration", "description": "CLI/Telegram 多通道访问",
             "status": "running", "heartbeat": 1, "dependencies": ["suri_core"],
             "permissions": ["system.*", "user.*"], "event_subscriptions": ["system.*", "user.*", "llm.*"],
             "config_schema": {}},
            {"id": "llm_gateway", "name": "llm_gateway", "version": "1.0.0",
             "type": "service", "description": "5 家国产大模型路由",
             "status": "running", "heartbeat": 1, "dependencies": ["suri_core", "config_service"],
             "permissions": ["system.*"], "event_subscriptions": ["llm.request", "user.command", "system.config_changed"],
             "config_schema": {"default_provider": "deepseek"}},
            {"id": "role_manager", "name": "role_manager", "version": "1.0.0",
             "type": "capability", "description": "多角色管理",
             "status": "running", "heartbeat": 2, "dependencies": ["suri_core"],
             "permissions": ["user.*"], "event_subscriptions": ["user.*"],
             "config_schema": {}},
            {"id": "agent_executor", "name": "agent_executor", "version": "1.0.0",
             "type": "execution", "description": "任务执行引擎",
             "status": "running", "heartbeat": 3, "dependencies": ["suri_core"],
             "permissions": ["system.*", "user.*"], "event_subscriptions": ["task.*", "user.*"],
             "config_schema": {}},
        ]

    def _get_dependents(self, plugin_id: str) -> List[str]:
        """获取依赖此插件的插件 ID 列表。"""
        dependents = []
        for p in self._plugins_cache:
            deps = p.get("dependencies", [])
            if plugin_id in deps:
                dependents.append(p.get("id", ""))
        return dependents

    # ═══════════════════════════════════════════════════════════════ #
    # 事件订阅 — 状态刷新（系统就绪后才生效）
    # ═══════════════════════════════════════════════════════════════ #

    async def _on_plugin_event(self, event: Event) -> None:
        """处理插件状态变化事件，根据当前显示状态实时刷新终端。

        事件类型：
        - system.plugin_loaded: 新插件加载
        - system.plugin_unloaded: 插件卸载
        - plugin.status_changed: 插件状态变化（stop/start/timeout）
        - plugin.manifest_updated: 插件 manifest 更新（升级后）

        刷新策略：
        - 当前在插件列表 → 自动重绘
        - 当前在该插件详情 → 刷新状态行或区块
        - 当前空闲 → 输出通知，不破坏输入
        
        安全守卫：启动完成（_started=True）之前忽略所有插件事件，
        避免 bootstrap 期间的回放事件触发重复面板刷新。
        """
        if not self._started:
            return

        event_type = event.event_type
        payload = event.payload or {}
        plugin_id = payload.get("plugin_id", "")

        # 刷新插件缓存
        self._plugins_cache = await self._fetch_plugins()

        # 根据当前视图状态决定刷新方式
        last_view = self._pm.last_panel

        if last_view == "plugins":
            # 当前在插件列表 → 自动重绘
            panel = MessageFormatter.format_plugin_list(self._plugins_cache)
            self.print_output(panel)

        elif last_view and last_view.startswith("detail:"):
            # 当前在详情页 → 刷新对应的插件详情
            viewing_id = last_view.split(":", 1)[1]
            matched = [p for p in self._plugins_cache
                       if p.get("id") == viewing_id or p.get("name") == viewing_id]
            if matched:
                idx = None
                for i, p in enumerate(self._plugins_cache, 1):
                    if p.get("id") == matched[0].get("id"):
                        idx = i
                        break
                detail = MessageFormatter.format_plugin_detail(
                    matched[0],
                    dependents=self._get_dependents(matched[0].get("id", "")),
                    plugin_index=idx,
                )
                self.print_output(detail)

        else:
            # 当前是空闲提示符 → 输出通知
            evt_labels = {
                "system.plugin_loaded": "📦 新插件加载",
                "system.plugin_unloaded": "🗑️ 插件卸载",
                "plugin.status_changed": "🔄 插件状态变更",
                "plugin.manifest_updated": "⬆️ 插件升级",
            }
            label = evt_labels.get(event_type, f"📢 {event_type}")

            # 获取状态内容
            if event_type == "plugin.status_changed":
                old_status = payload.get("old_status", "")
                new_status = payload.get("new_status", "")
                status_text = f" {old_status} → {new_status}"
            elif event_type == "plugin.manifest_updated":
                new_version = payload.get("new_version", "")
                status_text = f" 升级至 v{new_version}"
            else:
                status_text = ""

            notification = f"⚠️ [{label}] {plugin_id}{status_text}"
            self._pm.on_output(notification)

    async def _handle_plugin_manage(self, args: List[str]) -> None:
        """处理插件管理命令: /plugin start|stop|restart|upgrade|remove <编号>。

        Args:
            args: ["start", "3"] 或 ["stop", "5"] 等
        """
        if len(args) < 2:
            self.print_output(
                "用法: /plugin <操作> <编号>\n"
                "  操作: start, stop, restart, upgrade, remove\n"
                "  编号: 插件在列表中的数字编号\n"
                "  示例: /plugin stop 3  暂停 3 号插件"
            )
            return

        operation = args[0].lower()
        query = args[1]

        # 解析插件编号或名称
        plugin = None
        idx = 0
        if query.isdigit():
            num = int(query)
            if 1 <= num <= len(self._plugins_cache):
                plugin = self._plugins_cache[num - 1]
                idx = num
            else:
                self.print_output(f"❌ 无效编号: {query} (有效范围 1-{len(self._plugins_cache)})")
                return
        else:
            matched = [p for p in self._plugins_cache
                       if p.get("id") == query or p.get("name") == query]
            if not matched:
                self.print_output(f"❌ 未找到插件: {query}")
                return
            plugin = matched[0]
            for i, p in enumerate(self._plugins_cache, 1):
                if p.get("id") == plugin.get("id"):
                    idx = i
                    break

        plugin_name = plugin.get("name", plugin.get("id", "?"))
        plugin_id = plugin.get("id", plugin_name)

        # 检查 operation 是否在插件支持的 operations 中
        supported = plugin.get("operations", ["start", "stop", "restart"])
        if operation not in supported:
            self.print_output(f"⚠️ {plugin_name} 不支持 {operation} 操作")
            self.print_output(f"   支持: {', '.join(supported)}")
            return

        # 当前状态
        current_status = plugin.get("status", "running")

        # 状态转换校验
        status_check = {
            "start":   [("stopped",), "⏸ 已暂停 → ✅ 运行中"],
            "stop":    [("running", "delayed"), "✅ 运行中 → ⏸ 已暂停"],
            "restart": [("running", "stopped", "delayed", "timeout"), "🔄 重启"],
            "upgrade": [("running",), "✅ 运行中 → ❕ 升级中 → ✅ 运行中"],
            "remove":  [("running", "stopped"), "🗑️ 永久移除"],
        }

        if operation in status_check:
            allowed, desc = status_check[operation]
            if current_status not in allowed:
                self.print_output(
                    f"⚠️ 插件 {plugin_name} 当前状态为「{current_status}」\n"
                    f"   操作 {operation} 需要状态: {', '.join(allowed)}\n"
                    f"   操作说明: {desc}"
                )
                return

        # 执行操作
        if operation == "start":
            await self._execute_plugin_action(plugin_id, "start")
            self.print_output(f"✅ {plugin_name} 已启动")

        elif operation == "stop":
            await self._execute_plugin_action(plugin_id, "stop")
            self.print_output(f"⏸ {plugin_name} 已暂停")

        elif operation == "restart":
            await self._execute_plugin_action(plugin_id, "restart")
            self.print_output(f"🔄 {plugin_name} 已重启")

        elif operation == "upgrade":
            # 升级（可指定版本）
            target_version = args[2] if len(args) >= 3 else None
            await self._execute_plugin_action(plugin_id, "upgrade", target_version)
            if target_version:
                self.print_output(f"⬆️ {plugin_name} 已升级至 v{target_version}")
            else:
                self.print_output(f"⬆️ {plugin_name} 已升级")

        elif operation == "remove":
            # 确认后删除
            await self._execute_plugin_action(plugin_id, "remove")
            self.print_output(f"🗑️ {plugin_name} 已卸载")

        # 刷新插件缓存
        self._plugins_cache = await self._fetch_plugins()

        # 如果当前在插件列表视图，自动重绘
        if self._pm.last_panel == "plugins":
            panel = MessageFormatter.format_plugin_list(self._plugins_cache)
            self.print_output(panel)

    async def _execute_plugin_action(self, plugin_id: str, action: str,
                                     target_version: Optional[str] = None) -> None:
        """通过 EventBus 执行插件操作。

        向 PluginManager 发布操作事件，由 PluginManager 执行实际操作。
        """
        if not self._event_bus:
            self.print_output("❌ 事件总线未初始化，无法执行操作。")
            return

        payload = {
            "plugin_id": plugin_id,
            "action": action,
            "source": "cli",
        }
        if target_version:
            payload["target_version"] = target_version

        await self._event_bus.publish(Event(
            event_type="plugin.manage",
            source="cli",
            payload=payload,
            priority=Priority.HIGH,
        ))

    # ═══════════════════════════════════════════════════════════════ #
    # LLM 通信
    # ═══════════════════════════════════════════════════════════════ #

    async def _send_to_llm(self, text: str) -> None:
        """发送用户输入到 LLM。"""
        await self._event_bus.publish(Event(
            event_type="user.input",
            source="access",
            payload={
                "user_id": "cli_user",
                "content": text,
                "channel": "cli",
                "session_id": self._session_id,
            },
            priority=Priority.NORMAL,
        ))

    # ═══════════════════════════════════════════════════════════════ #
    # 输出方法
    # ═══════════════════════════════════════════════════════════════ #

    def print_output(self, content: str) -> None:
        """输出内容到终端，自动管理提示符。"""
        if content:
            self._pm.on_output(content)
        else:
            self._pm.show_prompt()

    def print_system(self, content: str) -> None:
        """输出系统消息到终端，自动管理提示符。"""
        if content:
            self._pm.on_output(content)
        else:
            self._pm.show_prompt()

    async def send(self, output: SessionOutput) -> None:
        """发送输出到 CLI（SessionHub 调用的 send 接口）。"""
        content = output.content
        if output.content_type == "markdown":
            # CLI 简化处理 markdown
            content = content.replace("**", "").replace("*", "")
        self.print_output(content)

    async def send_message(self, content: str, msg_type: str = "text") -> None:
        """发送消息到终端。"""
        self.print_output(content)

    async def send_decision(self, decision_id: str, question: str,
                            options: List[str]) -> None:
        """发送决策菜单。"""
        self.print_output(f"\n[决策] {question}")
        for i, opt in enumerate(options, 1):
            self.print_output(f"  {i}. {opt}")

    async def send_status(self, status: Dict[str, Any]) -> None:
        """发送状态信息。"""
        for k, v in status.items():
            self.print_output(f"  {k}: {v}")

    # ── 异步输入（供配置编辑器使用）──

    async def _async_input(self, prompt: str = "") -> str:
        """异步获取用户输入，用于配置菜单等需要 input() 的场景。"""
        if prompt:
            self._pm.clear_line()
            sys.stdout.write(prompt)
            sys.stdout.flush()

        line = await self._input_queue.get()
        return line.strip()

    # ── LLM 状态 ──

    def set_llm_online(self, online: bool) -> None:
        """设置 LLM 在线状态。"""
        self._llm_online = online

    # ── 历史记录 ──

    def _save_history(self) -> None:
        """保存 readline 历史。"""
        if self._readline_available:
            import readline
            history_file = os.path.expanduser("~/.suri/.cli_history")
            try:
                readline.write_history_file(history_file)
            except (FileNotFoundError, OSError):
                pass

    # ── 生命周期 ──

    def stop(self) -> None:
        """停止 CLI 通道。"""
        self._running = False
        self._save_history()
        if self._task and not self._task.done():
            self._task.cancel()
        self._pm.on_exit()