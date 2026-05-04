"""消息格式化 — 所有通道共用。

各通道可重写特定方法以实现差异化渲染。
CLI 用 ANSI 文本、Telegram 用 Markdown、Web 用 HTML。
"""

from typing import Any, Dict, List, Optional


class MessageFormatter:
    """消息格式化器。

    提供静态方法，所有通道共用。
    子类可重写特定方法实现通道特有渲染。
    """

    @staticmethod
    def format_response(content: str) -> str:
        """格式化 LLM 响应。"""
        return f"Suri: {content}"

    @staticmethod
    def format_error(error_code: int, message: str, provider: str) -> str:
        """格式化错误消息。"""
        if error_code in (401, 403):
            return (
                f"⚠️  {message}  "
                f"提示: /setkey {provider} 修改Key 或 llm.switch <厂商> 切换"
            )
        elif error_code == 429:
            return (
                f"⚠️  {message}  "
                f"提示: 稍后重试 或 llm.switch <厂商> 切换"
            )
        elif error_code == 503:
            return (
                f"⚠️  {message}  "
                f"提示: llm.switch <厂商> 切换 或稍后重试"
            )
        elif error_code == 3002:
            return (
                f"⚠️  {message}  "
                f"提示: /setkey {provider} 添加Key 或 llm.switch <厂商> 切换"
            )
        return f"⚠️  {message}"

    @staticmethod
    def format_status(providers: Dict[str, Any],
                      active_provider: str,
                      active_model: str,
                      api_keys: Dict[str, str]) -> str:
        """格式化模型配置状态面板。"""
        lines = []
        lines.append("=" * 50)
        lines.append("  Suri Agent CLI 模式")
        lines.append("=" * 50)
        lines.append("")
        lines.append("📋 模型配置状态：")

        for name, info in providers.items():
            models = info.get("models", [])
            models_str = ", ".join(models[:2])
            if info.get("api_key") or api_keys.get(name):
                lines.append(f"  ✅ {name} ({models_str}) — 已配置，可用")
            else:
                lines.append(f"  ❌ {name} ({models_str}) — 未配置 API Key")

        lines.append("")
        lines.append(f"当前默认模型: {active_provider}/{active_model}")
        lines.append("")
        lines.append("常用命令:")
        lines.append("  /help     显示完整帮助")
        lines.append("  /status   查看系统状态")
        lines.append("  /model    查看当前模型")
        lines.append("  /setkey   修改 API Key")
        lines.append("  /reconfig 进入配置菜单")
        lines.append("  /logs     查看日志路径")
        lines.append("  /quit     退出程序")
        lines.append("")
        lines.append("直接输入文字开始对话，或输入命令。")
        lines.append("聊天记录在上方，输入框在下方，已完全分割。")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def format_decision(question: str, options: List[str]) -> str:
        """格式化决策菜单。"""
        lines = []
        lines.append("")
        lines.append("┌─────────────────────────────────────┐")
        lines.append(f"│  {question}")
        lines.append("│")
        for i, opt in enumerate(options, 1):
            lines.append(f"│  {i}. {opt}")
        lines.append("│")
        lines.append(f"│  请选择 [1-{len(options)}]:           │")
        lines.append("└─────────────────────────────────────┘")
        return "\n".join(lines)

    @staticmethod
    def format_system(msg: str) -> str:
        """格式化系统消息。"""
        return f"[Suri] {msg}"

    @staticmethod
    def format_success(msg: str) -> str:
        """格式化成功消息。"""
        return f"✅ {msg}"

    @staticmethod
    def format_model_switch(provider: str, model: str) -> str:
        """格式化模型切换成功消息。"""
        return f"✅ 已切换到 {provider}/{model}"
