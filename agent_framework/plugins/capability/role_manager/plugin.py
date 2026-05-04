"""role_manager 插件 — 角色管理与 suri 决策流。

系统请求处理流程：
  1. 接收 user.input 事件
  2. 构建完整的 role.context_ready 事件（含 soul_content, tool_descriptions, history）
  3. suri（agent_executor）接收 context_ready 后决策
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import datetime
from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event


# 内置角色创建模板
BUILTIN_SOUL_TEMPLATE = """# {role_name} - Soul 定义

## 身份
{identity}

## 职责
{responsibilities}

## 约束
{constraints}

## 技能
{skills}

## 记忆模式
{memory}
"""


class RoleManagerPlugin(PluginInterface):
    """角色管理插件。"""

    BUILTIN_SOUL_TEMPLATE = BUILTIN_SOUL_TEMPLATE
    EXTERNAL_SOUL_TEMPLATE_PATH = str(Path.home() / ".suri" / "config" / "soul_template.md")
    EXTERNAL_TOOL_DESC_PATH = str(Path.home() / ".suri" / "config" / "tool_descriptions.yaml")
    MAX_HISTORY_MESSAGES = 50

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._roles: Dict[str, dict] = {}
        self._roles_dir: Optional[Path] = None
        self._soul_template: str = BUILTIN_SOUL_TEMPLATE
        self._tool_descriptions: List[dict] = []
        self._session_contexts: Dict[str, List[dict]] = {}
        self._status = "stopped"

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config

        # 确定角色目录
        roles_dir = config.get("roles_dir", str(Path.cwd() / "roles"))
        self._roles_dir = Path(roles_dir)
        self._roles_dir.mkdir(parents=True, exist_ok=True)

        # 加载已有角色
        self._load_existing_roles()

        # 确保 suri 角色存在
        if "suri" not in self._roles:
            self._create_suri_role()

        # 加载模板
        self._reload_templates()

        self._status = "initialized"

    def _load_existing_roles(self) -> None:
        """从 roles_dir 加载已有角色。"""
        if not self._roles_dir or not self._roles_dir.exists():
            return
        for item in self._roles_dir.iterdir():
            if item.is_dir():
                meta_path = item / "meta.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        self._roles[item.name] = meta
                    except Exception:
                        pass

    def _create_suri_role(self) -> None:
        """创建默认 suri 角色。"""
        suri_dir = self._roles_dir / "suri"
        suri_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "type": "core",
            "name": "suri",
            "description": "核心 orchestrator 角色",
            "created_at": "2024-01-01",
        }
        with open(suri_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        soul_content = """# Suri - 核心协调者

## 身份
你是 Suri，一个智能 agent 系统的核心协调者。你负责理解用户需求，协调各个专业 agent 完成任务。

## 职责
1. 理解用户意图，制定任务计划
2. 根据需要创建和委派子 agent
3. 监控任务执行进度
4. 处理异常和中断

## 约束
- 始终以用户利益为先
- 在不确定时主动寻求用户确认
- 保护用户隐私和数据安全

## 技能
- 任务规划与分解
- 多 agent 协调
- 上下文管理
- 异常处理

## 记忆模式
- 会话级上下文
- 角色级长期记忆
"""
        with open(suri_dir / "soul.md", "w", encoding="utf-8") as f:
            f.write(soul_content)

        self._roles["suri"] = meta

    async def start(self) -> None:
        self._status = "running"

    async def pause(self) -> None:
        self._status = "paused"

    async def resume(self) -> None:
        self._status = "running"

    async def stop(self) -> None:
        self._status = "stopped"

    async def cleanup(self) -> None:
        self._status = "stopped"

    def register_events(self) -> None:
        self._event_bus.subscribe("user.input", self._on_user_input)
        self._event_bus.subscribe("role.create_requested", self._on_role_create)
        self._event_bus.subscribe("llm.response", self._on_llm_response)
        self._event_bus.subscribe("user.command", self._on_command)
        self._event_bus.subscribe("config.updated", self._on_config_updated)
        self._event_bus.subscribe("role_manager.templates_updated", self._on_templates_updated)

    # ── 公开 API ──

    def list_roles(self) -> List[dict]:
        """列出所有角色。"""
        return [{"name": name, "type": info.get("type", "unknown")}
                for name, info in self._roles.items()]

    def get_role(self, role_id: str) -> Optional[dict]:
        """获取角色信息。"""
        return self._roles.get(role_id)

    def get_soul(self, role_id: str) -> Optional[str]:
        """获取角色 Soul 内容。"""
        if not self._roles_dir:
            return None
        soul_path = self._roles_dir / role_id / "soul.md"
        if soul_path.exists():
            try:
                return soul_path.read_text(encoding="utf-8")
            except Exception:
                pass
        return None

    async def create_role(self, name: str, role_type: str = "custom",
                          identity: str = "", responsibilities: str = "",
                          constraints: str = "", skills: str = "",
                          memory: str = "") -> bool:
        """创建新角色。已存在返回 False。"""
        if name in self._roles:
            return False

        role_dir = self._roles_dir / name
        role_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "type": role_type,
            "name": name,
            "created_at": datetime.datetime.now().isoformat(),
        }
        with open(role_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # 生成 Soul 文件
        soul_content = self._soul_template.format(
            role_name=name,
            identity=identity or f"{name} 角色",
            responsibilities=responsibilities or "待定义",
            constraints=constraints or "无特殊约束",
            skills=skills or "待定义",
            memory=memory or "会话级上下文",
        )
        with open(role_dir / "soul.md", "w", encoding="utf-8") as f:
            f.write(soul_content)

        self._roles[name] = meta
        return True

    # ── 事件处理 ──

    async def _on_user_input(self, event: Event) -> None:
        """处理 user.input 事件 → 构建 context 并发布 role.context_ready。"""
        payload = event.payload if hasattr(event, 'payload') else event
        content = payload.get("content", "")
        session_id = payload.get("session_id", "")

        # 追加用户消息到上下文
        self._append_context(session_id, "user", content)

        # 获取 soul 内容
        soul = self.get_soul("suri") or ""

        # 构建历史
        history = list(self._session_contexts.get(session_id, []))

        # 发布 role.context_ready
        await self._event_bus.publish(Event(
            event_type="role.context_ready",
            source="role_manager",
            payload={
                "session_id": session_id,
                "role_id": "suri",
                "soul_content": soul,
                "tool_descriptions": self._tool_descriptions,
                "history": history,
                "original_event": {
                    "event_type": event.event_type if hasattr(event, 'event_type') else "user.input",
                    "payload": payload,
                },
            },
        ))

    async def _on_role_create(self, event: Event) -> None:
        """处理 role.create_requested 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        name = payload.get("name", "")
        role_type = payload.get("role_type", "custom")
        identity = payload.get("identity", "")

        await self.create_role(
            name=name,
            role_type=role_type,
            identity=identity,
        )

    async def _on_llm_response(self, event: Event) -> None:
        """处理 llm.response 事件 → 追加助手回复到上下文。"""
        payload = event.payload if hasattr(event, 'payload') else event
        content = payload.get("content", "")
        session_id = payload.get("session_id", "")

        if not content.strip():
            return

        self._append_context(session_id, "assistant", content)

    async def _on_command(self, event: Event) -> None:
        """处理 user.command 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        cmd = payload.get("command", "")
        session_id = payload.get("session_id", "")

        if cmd == "clear":
            if session_id in self._session_contexts:
                self._session_contexts[session_id] = []
                print("会话上下文已清空。")
            else:
                print("无上下文。")

    async def _on_config_updated(self, event: Event) -> None:
        """处理 config.updated 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        if payload.get("plugin_id") == "role_manager":
            self._reload_templates()

    async def _on_templates_updated(self, event: Event) -> None:
        """处理 templates_updated 事件。"""
        self._reload_templates()

    # ── 上下文管理 ──

    def _append_context(self, session_id: str, role: str, content: str) -> None:
        """追加消息到会话上下文。"""
        if session_id not in self._session_contexts:
            self._session_contexts[session_id] = []
        self._session_contexts[session_id].append({
            "role": role,
            "content": content,
        })
        # 裁剪到最大消息数
        if len(self._session_contexts[session_id]) > self.MAX_HISTORY_MESSAGES:
            cutoff = len(self._session_contexts[session_id]) - self.MAX_HISTORY_MESSAGES
            self._session_contexts[session_id] = self._session_contexts[session_id][cutoff:]

    def _get_system_prompt(self) -> str:
        """获取系统提示（包含 Soul 内容）。"""
        soul = self.get_soul("suri") or "Suri is the core orchestrator."
        return f"你是 Suri，一个智能 agent 系统的核心协调者。\n\n{soul}"

    # ── 工具说明 ──

    def _build_tool_descriptions_text(self) -> str:
        """将工具说明列表转换为文本。"""
        if not self._tool_descriptions:
            return ""
        lines = ["可用工具:"]
        for tool in self._tool_descriptions:
            name = tool.get("name", "未知")
            desc = tool.get("description", "")
            params = tool.get("parameters", [])
            param_str = ", ".join([f"{p.get('name', '?')}: {p.get('description', '')}"
                                   for p in params])
            example = tool.get("example", "")
            lines.append(f"  - {name}: {desc}")
            if param_str:
                lines.append(f"    参数: {param_str}")
            if example:
                lines.append(f"    示例: {example}")
        return "\n".join(lines)

    # ── 热更新 ──

    def _reload_templates(self) -> None:
        """重新加载模板。"""
        self._soul_template = self.BUILTIN_SOUL_TEMPLATE
        self._tool_descriptions = []

        # 加载外部 Soul 模板
        external_path = Path(self.EXTERNAL_SOUL_TEMPLATE_PATH)
        if external_path.exists():
            try:
                self._soul_template = external_path.read_text(encoding="utf-8")
            except Exception:
                pass

        # 加载外部工具说明
        tool_desc_path = Path(self.EXTERNAL_TOOL_DESC_PATH)
        if tool_desc_path.exists():
            try:
                import yaml
                with open(tool_desc_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and "tools" in data:
                    self._tool_descriptions = data["tools"]
            except Exception:
                pass