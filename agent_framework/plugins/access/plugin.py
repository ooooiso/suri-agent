"""access 插件 — 会话中枢 + 多通道插件体系（PRD 对齐版）。

架构变化（PRD: prd/plugins/access/README.md）：
  旧版：access 是单插件，CLI/Telegram 是内部功能
  新版：access = SessionHub（会话中枢）+ 独立通道插件体系
         - session_hub.py（会话控制中枢）
         - channels/cli/channel.py（CLI 通道插件）
         - channels/telegram/channel.py（Telegram 通道插件）
         - channels/web/channel.py（Web 通道插件）

向下兼容：保持旧版测试接口 _cli, _on_llm_response, _last_error_map 等。
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority
from agent_framework.shared.hot_reload import HotReloadManager

from agent_framework.plugins.access.session_hub import SessionHub, SessionOutput
from agent_framework.plugins.access.channels.cli import CLIChannelPlugin
from agent_framework.plugins.access.channels.telegram import TelegramChannelPlugin
from agent_framework.plugins.access.wizard import ConfigWizard
from agent_framework.plugins.access.config_editor import ConfigEditor
from agent_framework.plugins.access.formatter import MessageFormatter


class AccessPlugin(PluginInterface):
    """访问通道插件。

    整合 SessionHub + 多通道插件体系。
    - 初始化 SessionHub（会话中枢）
    - 启动 CLI/Telegram/Web 通道插件
    - 提供事件路由（llm.response → 通道 send）
    """

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._session_hub: Optional[SessionHub] = None
        self._cli: Optional[CLIChannelPlugin] = None
        self._telegram: Optional[TelegramChannelPlugin] = None
        self._hot_reload: Optional[HotReloadManager] = None
        # 向下兼容：错误去重映射
        self._last_error_map: Dict[str, tuple] = {}

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config

        # 初始化 SessionHub
        self._session_hub = SessionHub()
        self._session_hub.set_event_bus(event_bus)

    async def start(self, plugin_manager=None) -> None:
        """启动 access 插件。

        Args:
            plugin_manager: 可选的 PluginManager 实例，注入给 CLI 通道用于获取插件列表。
        """
        # 检查是否需要首次运行向导
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            wizard = ConfigWizard()
            new_config = wizard.run()
            if new_config:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(new_config, f, indent=2, ensure_ascii=False)
                await self._event_bus.publish(Event(
                    event_type="system.config_changed",
                    source="access",
                    payload={"reason": "first_run_wizard"},
                    priority=Priority.HIGH,
                ))
            else:
                print("\n[Suri] 配置未完成，使用默认配置启动。\n")

        # 启动 CLI 通道插件（注册到 SessionHub）
        # 关键修复：注入 plugin_manager 以便 _fetch_plugins() 能获取真实数据
        self._cli = CLIChannelPlugin(self._event_bus)
        if plugin_manager:
            self._cli._plugin_manager = plugin_manager
        await self._cli.start(session_hub=self._session_hub)

        # 启动热更新系统
        await self._start_hot_reload(plugin_manager)

        # 启动 Telegram 通道插件（如配置启用）
        await self._start_telegram()

    async def _start_hot_reload(self, plugin_manager=None) -> None:
        """启动文件监听热更新。

        监听 agent_framework/ 下的所有插件目录（plugins、core）。
        FileWatcher 每 2 秒轮询一次，检测到 .py/.json 变更后：
          L1: 配置变更 → 插件重载配置
          L2: manifest.json 变更 → 命令注册表刷新
          L3: Python 代码变更 → importlib.reload + 插件实例重启
        """
        try:
            agent_fw_dir = Path(__file__).parent.parent.parent  # agent_framework/
            scan_dirs = [
                str(agent_fw_dir / "plugins"),  # agent_framework/plugins/
                str(agent_fw_dir / "core"),     # agent_framework/core/
            ]
            self._hot_reload = HotReloadManager(
                self._event_bus,
                watch_dirs=scan_dirs,
                plugin_manager=plugin_manager,
            )
            await self._hot_reload.start()
            print("[Access] 🔥 热更新系统已启动")
        except Exception as e:
            print(f"[Access] 热更新启动失败: {e}")

    async def _start_telegram(self) -> None:
        """根据配置启动 Telegram 通道插件。"""
        try:
            config_path = Path.home() / ".suri" / "config.json"
            if not config_path.exists():
                return
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            access_cfg = cfg.get("access", {})
            tg_cfg = access_cfg.get("channels", {}).get("telegram", {})
            if tg_cfg.get("enabled"):
                token = tg_cfg.get("bot_token", "")
                if token:
                    self._telegram = TelegramChannelPlugin(self._event_bus, bot_token=token)
                    await self._telegram.start(session_hub=self._session_hub)
        except Exception as e:
            print(f"[Access] Telegram 启动失败: {e}")

    async def pause(self) -> None:
        if self._cli:
            self._cli.stop()
        if self._telegram:
            self._telegram.stop()

    async def resume(self) -> None:
        if self._cli:
            await self._cli.start(session_hub=self._session_hub)

    async def stop(self) -> None:
        if self._cli:
            self._cli.stop()
        if self._telegram:
            self._telegram.stop()
        # 清理过期会话
        if self._session_hub:
            self._session_hub.cleanup_stale_sessions()

    async def cleanup(self) -> None:
        pass

    def register_events(self) -> None:
        self._event_bus.subscribe("user.input", self._on_user_input)
        self._event_bus.subscribe("llm.response", self._on_llm_response)
        self._event_bus.subscribe("llm.stream_chunk", self._on_llm_stream)
        self._event_bus.subscribe("llm.error", self._on_llm_error)
        self._event_bus.subscribe("error.tool", self._on_error)
        self._event_bus.subscribe("system.ready", self._on_system_ready)
        self._event_bus.subscribe("user.command", self._on_user_command)
        self._event_bus.subscribe("system.notification", self._on_system_notification)

    # ── 事件处理 ──

    async def _on_user_input(self, event: Event) -> None:
        """用户输入 → 转为 llm.request 事件。

        中继层（之前缺失的关键环节）：
        channel.py 发送 user.input
        → access/plugin.py 接收 user.input（新增订阅）
        → 构造 messages 并发送 llm.request
        → llm_gateway 接收 llm.request（已有订阅）
        → 调真实 API → 发送 llm.response
        → access/plugin.py 接收 llm.response（已有订阅）
        → 路由到对应通道发回用户
        """
        payload = event.payload if hasattr(event, 'payload') else event
        content = payload.get("content", "")
        session_id = payload.get("session_id", "")
        channel_type = payload.get("channel", "cli")

        if not content:
            return

        # 获取会话上下文（role_manager 可能维护了历史消息）
        messages = [{"role": "user", "content": content}]

        # 发布 llm.request 让 llm_gateway 处理
        await self._event_bus.publish(Event(
            event_type="llm.request",
            source="access",
            payload={
                "messages": messages,
                "session_id": session_id,
                "channel": channel_type,
                "request_id": f"req_{session_id}_{int(time.time())}",
            },
            priority=Priority.NORMAL,
        ))

    async def _on_llm_response(self, event: Event) -> None:
        """LLM 响应 → 通过 SessionHub 路由到对应通道。"""
        content = event.payload.get("content", "")
        session_id = event.payload.get("session_id", "")

        # 标记 LLM 在线
        if self._cli:
            self._cli.set_llm_online(True)

        # 在内容前加上 > [suri] 发言标记（紫色高亮）
        # 格式对齐：所有对话都以 > 开头
        prefix = "\033[35m> [suri]\033[0m "
        marked_content = f"{prefix}{content}"

        if self._session_hub and session_id:
            # 通过 SessionHub 能力协商路由
            session = self._session_hub.get_session(session_id)
            if session:
                output = self._session_hub.negotiate_output(
                    session, "markdown", marked_content
                )
                channel = self._session_hub.get_channel(session.channel_type)
                if channel and channel.handler:
                    await channel.handler.send(output)
                    return

        # 降级：直接通过 CLI 输出
        if content.strip() and self._cli:
            self._cli.print_output(marked_content)

    async def _on_llm_stream(self, event: Event) -> None:
        """LLM 流式输出块 → 路由到通道。"""
        chunk = event.payload.get("chunk", "")
        session_id = event.payload.get("session_id", "")

        if chunk and self._cli:
            print(chunk, end="", flush=True)

    async def _on_llm_error(self, event: Event) -> None:
        """LLM 错误处理（含去重、LLM 离线标记、恢复菜单）。"""
        import time
        error = event.payload.get("message", "Unknown error")
        error_code = event.payload.get("error_code", 0)
        provider = event.payload.get("provider", "")
        session_id = event.payload.get("session_id", "")

        # LLM 离线标记
        if self._cli:
            self._cli.set_llm_online(False)

        # 去重检查（5 秒内同一错误码不重复显示）
        now = time.time()
        last = self._last_error_map.get(session_id)
        if last and last[0] == error_code and now - last[1] < 5:
            return
        self._last_error_map[session_id] = (error_code, now)

        # 格式化错误消息
        provider_name = provider or "当前厂商"
        formatted = MessageFormatter.format_error(error_code, error, provider_name)

        # 通过 SessionHub 路由
        if self._session_hub and session_id:
            session = self._session_hub.get_session(session_id)
            if session:
                output = self._session_hub.negotiate_output(
                    session, "text", formatted
                )
                channel = self._session_hub.get_channel(session.channel_type)
                if channel and channel.handler:
                    await channel.handler.send(output)
                    return

        # 降级：直接 CLI 输出
        if self._cli:
            self._cli.print_output(formatted)
            # 不可恢复错误弹出恢复菜单
            if error_code in (401, 403, 3002):
                asyncio.create_task(
                    self._show_recovery_menu(error_code, provider_name)
                )

    async def _show_recovery_menu(self, error_code: int, provider: str) -> None:
        """显示恢复菜单（向下兼容旧版 CLI 的恢复菜单逻辑）。"""
        if self._cli and hasattr(self._cli, '_async_input'):
            from agent_framework.plugins.access.config_editor import ConfigEditor
            editor = ConfigEditor(self._event_bus, input_func=self._cli._async_input)
            await editor.run_menu()

    async def _on_error(self, event: Event) -> None:
        """工具错误事件。"""
        error = event.payload.get("error_message", "Unknown error")
        if self._cli:
            self._cli.print_output(f"[Error] {error}")

    async def _on_system_ready(self, event: Event) -> None:
        """系统就绪提示。"""
        if self._cli:
            self._cli.print_system(MessageFormatter.format_system("系统已就绪。"))

    async def _on_system_notification(self, event: Event) -> None:
        """系统通知事件。"""
        title = event.payload.get("title", "")
        body = event.payload.get("body", "")
        message = f"[{title}] {body}" if title else body
        if self._cli:
            self._cli.print_system(message)

    async def _on_user_command(self, event: Event) -> None:
        """处理 access 层命令。"""
        cmd = event.payload.get("command", "")
        channel = event.payload.get("channel", "cli")
        session_id = event.payload.get("session_id", "")
        args = event.payload.get("args", [])

        if cmd == "status":
            msg = MessageFormatter.format_system("系统运行中。输入 /help 查看命令。")
            self._send_response(msg, session_id, channel)
        elif cmd == "model" or cmd == "models":
            # 查看当前模型配置
            config_path = Path.home() / ".suri" / "config.json"
            if config_path.exists():
                cfg = json.loads(config_path.read_text())
                llm_cfg = cfg.get("llm_gateway", {})
                default_prov = llm_cfg.get("default_provider", "未设置")
                providers = llm_cfg.get("providers", {})
                msg_lines = [f"当前默认厂商: {default_prov}"]
                for name, pcfg in providers.items():
                    has_key = "✅" if pcfg.get("api_key") else "❌"
                    models = pcfg.get("models", [])
                    default_model = pcfg.get("default_model", models[0] if models else "未设置")
                    msg_lines.append(f"  {has_key} {name} (模型: {default_model})")
                    if models:
                        msg_lines.append(f"     可用: {', '.join(models)}")
                self._send_response("\n".join(msg_lines), session_id, channel)
            else:
                self._send_response("未找到配置文件", session_id, channel)
        elif cmd == "reload":
            msg = MessageFormatter.format_system("配置已重载。")
            self._send_response(msg, session_id, channel)
        elif cmd == "reconfig":
            asyncio.create_task(self._run_config_editor(session_id, channel))
        elif cmd == "logs":
            import os
            log_path = os.path.expanduser("~/.suri/runtime/logs")
            msg = MessageFormatter.format_system(f"日志目录: {log_path}")
            self._send_response(msg, session_id, channel)
        elif cmd == "clear":
            msg = MessageFormatter.format_system("会话上下文已清空。")
            self._send_response(msg, session_id, channel)
        elif cmd == "setkey":
            # /setkey <provider> [key]
            if len(args) < 1:
                self._send_response("用法: /setkey <厂商> [key]", session_id, channel)
                return
            provider = args[0]
            if len(args) >= 2:
                api_key = args[1]
                self._send_response(f"正在设置 {provider} 的 API Key...", session_id, channel)
                editor = ConfigEditor(self._event_bus)
                success = await editor.set_provider_key(provider, api_key)
                if success:
                    self._send_response(f"✅ {provider} 的 API Key 已保存。", session_id, channel)
                else:
                    self._send_response(f"❌ 保存失败", session_id, channel)
            else:
                self._send_response(f"请提供 API Key: /setkey {provider} <key>", session_id, channel)
        elif cmd == "switch":
            # /switch <provider> [model]
            if len(args) < 1:
                self._send_response("用法: /switch <厂商> [模型]", session_id, channel)
                return
            provider = args[0]
            model = args[1] if len(args) >= 2 else None
            # 更新配置文件中的 default_model
            config_path = Path.home() / ".suri" / "config.json"
            if config_path.exists():
                cfg = json.loads(config_path.read_text())
                providers = cfg.get("llm_gateway", {}).get("providers", {})
                if provider in providers:
                    pcfg = providers[provider]
                    if model:
                        pcfg["default_model"] = model
                        cfg["llm_gateway"]["default_provider"] = provider
                        config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
                        self._send_response(f"✅ 已切换到 {provider} / {model}", session_id, channel)
                    else:
                        # 使用第一个可用模型
                        models = pcfg.get("models", [])
                        if models:
                            pcfg["default_model"] = models[0]
                            cfg["llm_gateway"]["default_provider"] = provider
                            config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
                            self._send_response(f"✅ 已切换到 {provider} / {models[0]}", session_id, channel)
                        else:
                            self._send_response(f"❌ {provider} 没有可用模型", session_id, channel)
                else:
                    self._send_response(f"❌ 未配置厂商 {provider}", session_id, channel)
            else:
                self._send_response("❌ 未找到配置文件", session_id, channel)
        elif cmd == "role":
            self._send_response("角色管理功能已启动", session_id, channel)
        elif cmd == "help":
            help_text = (
                "可用命令:\n"
                "  /status          查看系统状态\n"
                "  /model           查看当前模型\n"
                "  /models          列出所有可用厂商和模型\n"
                "  /setkey <厂商> [key]  修改 API Key\n"
                "  /switch <厂商> [模型] 切换模型\n"
                "  /reconfig        进入配置菜单\n"
                "  /reload          重载配置\n"
                "  /clear           清空会话\n"
                "  /logs            查看日志路径\n"
                "  /sessions        查看会话统计\n"
                "  /help            显示本帮助\n"
                "  /quit            退出程序"
            )
            self._send_response(help_text, session_id, channel)
        elif cmd == "sessions" or cmd == "session":
            # PRD: /session 查看会话状态
            if self._session_hub:
                stats = self._session_hub.get_stats()
                msg = (
                    f"会话统计:\n"
                    f"  总会话: {stats['total_sessions']}\n"
                    f"  活跃: {stats['active_sessions']}\n"
                    f"  通道: {stats['by_channel']}\n"
                    f"  隔离层: {stats['by_isolation_layer']}\n"
                    f"  已注册通道: {stats['registered_channels']}"
                )
                self._send_response(msg, session_id, channel)

    async def _run_config_editor(self, session_id: str, channel: str) -> None:
        """运行配置编辑器。"""
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            self._send_response("[Suri] 无配置，下次启动进入向导。", session_id, channel)
            return

        if channel == "telegram":
            self._send_response(
                "配置编辑功能在 Telegram 中暂不支持交互式菜单，"
                "请使用 CLI 或直接编辑 ~/.suri/config.json。",
                session_id, channel,
            )
            return

        if channel == "cli" and self._cli and hasattr(self._cli, '_async_input'):
            editor = ConfigEditor(self._event_bus, input_func=self._cli._async_input)
        elif channel == "cli" and self._cli and hasattr(self._cli, 'channel'):
            # 从 channel 属性中获取 _async_input
            ch = self._cli.channel if hasattr(self._cli, 'channel') else None
            if ch and hasattr(ch, '_async_input'):
                editor = ConfigEditor(self._event_bus, input_func=ch._async_input)
            else:
                editor = ConfigEditor(self._event_bus)
        else:
            editor = ConfigEditor(self._event_bus)

        await editor.run_menu()

    def _send_response(self, msg: str, session_id: str, channel: str) -> None:
        """发送响应到对应通道。"""
        if channel == "telegram" and self._telegram:
            asyncio.create_task(self._telegram.send_message(msg))
        else:
            if self._cli:
                self._cli.print_output(msg)
            else:
                print(msg)

    @property
    def session_hub(self) -> Optional[SessionHub]:
        """获取 SessionHub 实例（供外部访问）。"""
        return self._session_hub