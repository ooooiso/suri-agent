"""消息格式化 — 所有通道共用。

各通道可重写特定方法以实现差异化渲染。
CLI 用 ANSI 文本、Telegram 用 Markdown、Web 用 HTML。

PRD: prd/plugins/access/formatter-spec.md
"""

from typing import Any, Dict, List, Optional

from agent_framework.shared.commands import list_commands, get_plugin_commands


class MessageFormatter:
    """消息格式化器。

    提供静态方法，所有通道共用。
    子类可重写特定方法实现通道特有渲染。
    """

    # ── ANSI 颜色常量 ──
    C_CYAN = "\033[36m"
    C_GREEN = "\033[32m"
    C_YELLOW = "\033[33m"
    C_RED = "\033[31m"
    C_MAGENTA = "\033[35m"
    C_BLUE = "\033[34m"
    C_BOLD = "\033[1m"
    C_DIM = "\033[2m"
    C_RESET = "\033[0m"

    # ── 面板常量 ──
    PANEL_WIDTH = 75
    PANEL_STATUS_RUNNING = "✅ 运行中"
    PANEL_STATUS_DELAY = "⚠️ 响应延迟"
    PANEL_STATUS_DOWN = "❌ 无响应"
    PANEL_STATUS_WAITING = "⏳ 等待中"
    PANEL_STATUS_FAILED = "❌ 加载失败"
    PANEL_STATUS_STOPPED = "⏸ 已暂停"
    PANEL_STATUS_UPGRADING = "❕ 升级中"
    PANEL_STATUS_REMOVED = "🗑️ 已卸载"

    TYPE_MAP = {
        "core": ("核心", "系统内核"),
        "service": ("服务", "基础服务"),
        "capability": ("能力", "能力插件"),
        "execution": ("执行", "执行层"),
        "integration": ("接入", "接入层"),
        "extension": ("扩展", "扩展插件"),
    }

    LAYER_MAP = {
        "core": "core",
        "service": "service",
        "capability": "role",
        "execution": "execution",
        "integration": "access",
        "extension": "extension",
    }

    # ========== 基础方法 ==========

    @staticmethod
    def format_response(content: str) -> str:
        return f"Suri: {content}"

    @staticmethod
    def format_error(error_code: int, message: str, provider: str) -> str:
        if error_code in (401, 403):
            return f"⚠️  {message}  提示: /setkey {provider} 修改Key 或 llm.switch <厂商> 切换"
        elif error_code == 429:
            return f"⚠️  {message}  提示: 稍后重试 或 llm.switch <厂商> 切换"
        elif error_code == 503:
            return f"⚠️  {message}  提示: llm.switch <厂商> 切换 或稍后重试"
        elif error_code == 3002:
            return f"⚠️  {message}  提示: /setkey {provider} 添加Key 或 llm.switch <厂商> 切换"
        return f"⚠️  {message}"

    @staticmethod
    def format_status(providers: Dict[str, Any],
                      active_provider: str,
                      active_model: str,
                      api_keys: Dict[str, str]) -> str:
        lines = ["=" * 50, "  Suri Agent CLI 模式", "=" * 50, ""]
        lines.append("📋 模型配置状态：")
        for name, info in providers.items():
            models = info.get("models", [])
            models_str = ", ".join(models[:2])
            if info.get("api_key") or api_keys.get(name):
                lines.append(f"  ✅ {name} ({models_str}) — 已配置，可用")
            else:
                lines.append(f"  ❌ {name} ({models_str}) — 未配置 API Key")
        lines += ["", f"当前默认模型: {active_provider}/{active_model}", ""]
        lines += [
            "常用命令:",
            "  /help     显示完整帮助",
            "  /status   查看系统状态",
            "  /model    查看当前模型",
            "  /setkey   修改 API Key",
            "  /reconfig 进入配置菜单",
            "  /logs     查看日志路径",
            "  /quit     退出程序", "",
            "直接输入文字开始对话，或输入命令。",
            "聊天记录在上方，输入框在下方，已完全分割。", ""
        ]
        return "\n".join(lines)

    @staticmethod
    def format_decision(question: str, options: List[str]) -> str:
        lines = ["", "┌─────────────────────────────────────┐",
                 f"│  {question}", "│"]
        for i, opt in enumerate(options, 1):
            lines.append(f"│  {i}. {opt}")
        lines += ["│", f"│  请选择 [1-{len(options)}]:           │",
                  "└─────────────────────────────────────┘"]
        return "\n".join(lines)

    @staticmethod
    def format_system(msg: str) -> str:
        return f"[Suri] {msg}"

    @staticmethod
    def format_success(msg: str) -> str:
        return f"✅ {msg}"

    @staticmethod
    def format_model_switch(provider: str, model: str) -> str:
        return f"✅ 已切换到 {provider}/{model}"

    # ========== 工具方法 ==========

    @staticmethod
    def _get_status_icon(plugin: Dict[str, Any]) -> str:
        status = plugin.get("status", "unknown")
        heartbeat = plugin.get("heartbeat", None)

        if status == "upgrading":
            return MessageFormatter.PANEL_STATUS_UPGRADING
        if status == "removed":
            return MessageFormatter.PANEL_STATUS_REMOVED
        if status in ("load_failed", "failed"):
            return MessageFormatter.PANEL_STATUS_FAILED
        if status == "stopped":
            return MessageFormatter.PANEL_STATUS_STOPPED
        if status == "running":
            if heartbeat is None:
                return MessageFormatter.PANEL_STATUS_WAITING
            if heartbeat <= 10:
                return MessageFormatter.PANEL_STATUS_RUNNING
            elif heartbeat <= 30:
                return MessageFormatter.PANEL_STATUS_DELAY
            else:
                return MessageFormatter.PANEL_STATUS_DOWN
        return MessageFormatter.PANEL_STATUS_WAITING

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 1] + "…"

    # ========== /plugins 列表面板 ==========

    @staticmethod
    def format_plugin_list(plugins: List[Dict[str, Any]]) -> str:
        """渲染 /plugins 列表面板（类型分组）。"""
        if not plugins:
            return "📋 暂无已加载的插件。"

        W = MessageFormatter.PANEL_WIDTH
        lines = []

        title = " Suri Agent 插件列表 "
        padding = W - len(title) - 2
        lines.append(f"┌{'─' * (W - 2)}┐")
        lines.append(f"│{title}{' ' * padding}│")
        lines.append(f"├{'─' * (W - 2)}┤")
        header = " #  │ 名称              │ 类型    │ 状态"
        lines.append(f"│ {header}{' ' * (W - len(header) - 4)} │")
        lines.append(f"├─────┼───────────────────┼─────────┼─────────────┤")

        for i, p in enumerate(plugins, 1):
            num = f"{i:2d}"
            name = MessageFormatter._truncate(p.get("name", p.get("id", "?")), 15)
            ptype_raw = p.get("type", "")
            ptype_disp = MessageFormatter.TYPE_MAP.get(ptype_raw, (ptype_raw, ""))[0]
            ptype = f"{ptype_disp:>5s}"
            status = MessageFormatter._get_status_icon(p)
            status_short = MessageFormatter._truncate(status, 11)
            row = f" {num}  │ {name:<17s}│ {ptype} │ {status_short}"
            lines.append(f"│{row}{' ' * (W - len(row) - 2)} │")

        lines.append(f"└{'─' * (W - 2)}┘")
        lines.append("提示: 输入插件编号 (如 1) 查看详情")
        return "\n".join(lines)

    # ========== 启动面板 ==========

    @staticmethod
    def format_startup_panel(plugins: List[Dict[str, Any]],
                             providers: Dict[str, Dict],
                             active_provider: str,
                             active_model: str,
                             api_keys: Dict[str, str],
                             health: Optional[Dict[str, Dict]] = None) -> str:
        """渲染完整的启动面板（按层分组 + LLM 模型状态）。"""
        W = MessageFormatter.PANEL_WIDTH

        if not plugins:
            return "Suri Agent v1.0.0 已就绪\n暂无已加载的插件。\n"

        lines = []
        title = "  Suri Agent v1.0.0 已就绪 "
        lines.append(f"╔{'═' * (W - 2)}╗")
        lines.append(f"║{title}{' ' * (W - len(title) - 2)}║")
        lines.append(f"╚{'═' * (W - 2)}╝")
        lines.append("")

        header_line = "  #  │ 名称            │ 所属层     │ 状态     │ 说明"
        lines.append(header_line)
        sep_line = f" {'─' * 3} ┼{'─' * 17}┼{'─' * 12}┼{'─' * 10}┼{'─' * 18}"
        lines.append(sep_line)

        for i, p in enumerate(plugins, 1):
            name = MessageFormatter._truncate(p.get("name", p.get("id", "?")), 12)
            ptype = p.get("type", "unknown")
            layer = MessageFormatter.LAYER_MAP.get(ptype, ptype)
            status_icon = MessageFormatter._get_status_icon(p)
            desc = MessageFormatter._truncate(p.get("description", ""), 16)
            status_short = status_icon.split()[0] if " " in status_icon else status_icon
            if len(status_icon) <= 4:
                status_short = status_icon
            row = f"  {i:2d}  │ {name:<14s}│ {layer:<10s}│ {status_short:<8s}│ {desc}"
            lines.append(row)

        lines.append("")
        lines.append("  输入编号查看插件详情，/help 查看更多命令")
        lines.append("")

        if providers:
            lines.append(MessageFormatter.format_model_status(
                providers=providers,
                active_provider=active_provider,
                active_model=active_model,
                api_keys=api_keys,
                health=health or {},
            ))

        return "\n".join(lines)

    # ========== 插件详情面板 ==========

    @staticmethod
    def format_plugin_detail(plugin: Dict[str, Any],
                             dependents: Optional[List[str]] = None,
                             plugin_index: Optional[int] = None) -> str:
        """渲染插件详情面板（7 区块）。"""
        if not plugin:
            return "❌ 未找到插件信息。"

        W = MessageFormatter.PANEL_WIDTH
        lines = []

        plugin_id = plugin.get("id", plugin.get("name", "?"))
        plugin_name = plugin.get("name", plugin_id)
        description = plugin.get("description", "")
        version = plugin.get("version", "?")
        ptype_raw = plugin.get("type", "")
        ptype_display, ptype_desc = MessageFormatter.TYPE_MAP.get(ptype_raw, (ptype_raw, ""))
        status = MessageFormatter._get_status_icon(plugin)
        heartbeat = plugin.get("heartbeat")
        heartbeat_str = f" (心跳: {heartbeat}s前)" if heartbeat is not None else ""

        idx_str = f"{plugin_index}. " if plugin_index else ""
        title = f" {idx_str}{plugin_name} "
        lines.append(f"┌─{title}{'─' * (W - 4 - len(title))}┐")
        desc_trunc = MessageFormatter._truncate(description, W - 6)
        lines.append(f"│ {desc_trunc}{' ' * (W - len(desc_trunc) - 3)}│")
        lines.append(f"│{' ' * (W - 2)}│")

        # 区块1: 基本信息
        lines.append(f"│ ── 基本信息 ── {' ' * (W - 18)}│")
        lines.append(f"│  版本:    {version:<12s}{' ' * (W - 22 - len(version))}│")
        lines.append(f"│  集层:    {ptype_display:<10s} ({ptype_desc}){' ' * (W - 30 - len(ptype_desc))}│")
        lines.append(f"│  状态:    {status}{heartbeat_str}{' ' * (W - 20 - len(status) - len(heartbeat_str))}│")
        lines.append(f"│{' ' * (W - 2)}│")

        # 区块2: 依赖关系
        deps = plugin.get("dependencies", [])
        dep_str = ", ".join(deps) if deps else "无"
        dep_list = dependents or []
        dep_list_str = ", ".join(dep_list) if dep_list else "无"
        lines.append(f"│ ── 依赖关系 ── {' ' * (W - 18)}│")
        lines.append(f"│  依赖:    {MessageFormatter._truncate(dep_str, W - 16):<{W - 16}}│")
        lines.append(f"│  被依赖:  {MessageFormatter._truncate(dep_list_str, W - 18):<{W - 18}}│")
        lines.append(f"│{' ' * (W - 2)}│")

        # 区块3: 能力边界
        permissions = plugin.get("permissions", [])
        perm_str = ", ".join(permissions) if permissions else "无"
        events = plugin.get("event_subscriptions", [])
        scope = "未知"
        has_session = any("session." in e or "user." in e for e in events)
        has_system = any("system." in e for e in events)
        if has_session and has_system:
            scope = "全局 + 会话级"
        elif has_system:
            scope = "全局，所有会话共享"
        elif has_session:
            scope = "会话级"
        lines.append(f"│ ── 能力边界 ── {' ' * (W - 18)}│")
        lines.append(f"│  权限:    {MessageFormatter._truncate(perm_str, W - 16):<{W - 16}}│")
        lines.append(f"│  作用域:  {MessageFormatter._truncate(scope, W - 18):<{W - 18}}│")
        lines.append(f"│{' ' * (W - 2)}│")

        # 区块4: 提供的命令
        commands = get_plugin_commands(plugin_id)
        lines.append(f"│ ── 提供的命令 ── {' ' * (W - 20)}│")
        if commands:
            for cmd in commands:
                cmd_line = f"  /{cmd.name}  {cmd.usage}  {cmd.description}"
                cmd_line = MessageFormatter._truncate(cmd_line, W - 4)
                lines.append(f"│ {cmd_line}{' ' * (W - len(cmd_line) - 2)}│")
        else:
            nod_cmd = "（无直接 CLI 命令，通常由 LLM 代理调用）"
            lines.append(f"│ {nod_cmd}{' ' * (W - len(nod_cmd) - 2)}│")
        lines.append(f"│{' ' * (W - 2)}│")

        # 区块5: 事件契约
        sub_events = plugin.get("event_subscriptions", [])
        sub_str = ", ".join(sub_events) if sub_events else "无"
        sub_trunc = MessageFormatter._truncate(sub_str, W - 12)
        pub_events = plugin.get("published_events", [])
        pub_str = ", ".join(pub_events) if pub_events else "（暂无）"
        pub_trunc = MessageFormatter._truncate(pub_str, W - 12)
        lines.append(f"│ ── 事件契约 ── {' ' * (W - 18)}│")
        lines.append(f"│  订阅:  {sub_trunc}{' ' * (W - 14 - len(sub_trunc))}│")
        lines.append(f"│  发布:  {pub_trunc}{' ' * (W - 14 - len(pub_trunc))}│")
        lines.append(f"│{' ' * (W - 2)}│")

        # 区块6: 配置项
        config_schema = plugin.get("config_schema", {})
        lines.append(f"│ ── 配置项 ── {' ' * (W - 16)}│")
        if config_schema and isinstance(config_schema, dict):
            for key, val in config_schema.items():
                if isinstance(val, dict):
                    desc = val.get("description", "")
                    default = val.get("default", "")
                    cfg_line = f"  {key}: {default}  {desc}"
                else:
                    cfg_line = f"  {key}: {val}"
                cfg_line = MessageFormatter._truncate(cfg_line, W - 4)
                lines.append(f"│ {cfg_line}{' ' * (W - len(cfg_line) - 2)}│")
        else:
            nocfg = "（无配置项）"
            lines.append(f"│ {nocfg}{' ' * (W - len(nocfg) - 2)}│")
        lines.append(f"│{' ' * (W - 2)}│")

        # 区块7: 操作
        idx = plugin_index if plugin_index else 0
        operations = plugin.get("operations", ["start", "stop", "restart"])
        lines.append(f"│ ── 操作 ── {' ' * (W - 14)}│")
        op_commands = {
            "start":   f"  /plugin start {idx}      启动插件",
            "stop":    f"  /plugin stop {idx}       暂停插件",
            "restart": f"  /plugin restart {idx}    重启插件",
            "upgrade": f"  /plugin upgrade {idx}    升级插件",
            "remove":  f"  /plugin remove {idx}    删除插件",
        }
        for op in operations:
            if op in op_commands:
                cmd_line = op_commands[op]
                lines.append(f"│ {cmd_line}{' ' * (W - len(cmd_line) - 2)}│")
        if not operations:
            lines.append(f"│ （无可用操作）{' ' * (W - 14)}│")
        lines.append(f"└{'─' * (W - 2)}┘")
        return "\n".join(lines)

    # ========== 模型状态面板 ==========

    @staticmethod
    def format_model_status(providers: Dict[str, Dict],
                            active_provider: str,
                            active_model: str,
                            api_keys: Dict[str, str],
                            health: Optional[Dict[str, Dict]] = None) -> str:
        """渲染 /models 模型状态面板。"""
        W = MessageFormatter.PANEL_WIDTH

        if not providers:
            return "📋 未配置任何 LLM 厂商。使用 /setkey 或 /reconfig 配置。"

        health = health or {}
        lines = []

        lines.append(f"┌{'─' * (W - 2)}┐")
        title = " LLM 模型状态 "
        lines.append(f"│{title}{' ' * (W - len(title) - 2)}│")
        lines.append(f"├{'─' * (W - 2)}┤")

        active_provider_name = providers.get(active_provider, {}).get("name", active_provider)
        active_line = f"  🔵 当前会话: {active_provider_name} / {active_model}"
        lines.append(f"│ {active_line}{' ' * (W - len(active_line) - 3)}│")
        lines.append(f"├{'─' * (W - 2)}┤")

        header = " 厂商    │ 状态    │ 可用模型                     │ 快速切换"
        lines.append(f"│ {header}{' ' * (W - len(header) - 2)}│")
        lines.append(f"├─────────┼─────────┼──────────────────────────────┼──────────────┤")

        for pid, info in providers.items():
            models = info.get("models", [])
            has_key = pid in api_keys and bool(api_keys[pid])

            if has_key:
                provider_health = health.get(pid, {})
                last_success = provider_health.get("last_success_timestamp", 0)
                last_error = provider_health.get("last_error_timestamp", 0)
                if last_success == 0 and last_error == 0:
                    status_icon = "⏳ 待机"
                elif last_success > last_error:
                    status_icon = "✅ 在线"
                else:
                    status_icon = "⚠️ 异常"
            else:
                status_icon = "❌ 离线"

            is_active = (pid == active_provider)
            action = f"/switch {pid}"

            provider_line = f" {pid:<8s}"
            status_line = f" {status_icon:<8s}"
            first_model = models[0] if models else "（未配置）"
            model_cell = f" {first_model} {'◀' if is_active and first_model == active_model else ' '}"
            action_cell = f" {action}"
            row = f"{provider_line}│{status_line}│{model_cell:<30s}│{action_cell}"
            lines.append(f"│{row}{' ' * (W - len(row) - 2)}│")

            for m in models[1:]:
                model_cell = f" {m} {'◀' if is_active and m == active_model else ' '}"
                row = f" {'':8s}│ {'':8s}│{model_cell:<30s}│ {'':12s}"
                lines.append(f"│{row}{' ' * (W - len(row) - 2)}│")

            if not has_key:
                detail = "未配置 API Key"
                row = f" {'':8s}│ {'':8s}│ ({detail:<26s})│ {'':12s}"
                lines.append(f"│{row}{' ' * (W - len(row) - 2)}│")

        lines.append(f"├{'─' * (W - 2)}┤")
        tip = "快速切换: 在提示符后输入厂商名即可，例如 kimi"
        lines.append(f"│ {tip}{' ' * (W - len(tip) - 2)}│")
        lines.append(f"└{'─' * (W - 2)}┘")
        return "\n".join(lines)

    @staticmethod
    def format_current_model(provider: str, provider_name: str,
                             model: str, status: str) -> str:
        lines = ["─" * 40,
                 f"当前模型: {provider_name} / {model} [{status}]",
                 "─" * 40]
        return "\n".join(lines)