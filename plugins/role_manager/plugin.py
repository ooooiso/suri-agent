"""role_manager 插件 — 角色管理（迭代 2：解耦改造）。"""

import json
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority

from plugins.role_manager.soul_parser import build_system_prompt, parse_soul


class RoleManagerPlugin(PluginInterface):
    """角色管理插件。
    
    迭代 2（解耦改造）：
    - 创建核心角色 suri
    - Soul 文件管理（YAML frontmatter + Markdown）
    - 角色列表查询
    - **不再代理 suri** — 只提供角色数据，发布 role.context_ready 事件
    - 会话上下文管理（按 session_id 维护消息历史）
    - Soul 模板外部化到 YAML 文件，支持热更新
    - 工具说明外部化到 YAML 文件，支持热更新
    """

    # 每个 session 最大保留消息数（user + assistant 各一半）
    MAX_HISTORY_MESSAGES = 20

    # 外部模板文件路径
    EXTERNAL_SOUL_TEMPLATE_PATH = os.path.expanduser("~/.suri/data/templates/soul_template.md")
    EXTERNAL_TOOL_DESC_PATH = os.path.expanduser("~/.suri/data/templates/tool_descriptions.yaml")

    # 内置 Soul 模板（代码内 fallback）
    BUILTIN_SOUL_TEMPLATE = """---
role_id: "{role_id}"
nickname: "{nickname}"
role_type: "{role_type}"
version: "1.0.0"
created_at: "{created_at}"
updated_at: "{updated_at}"
capabilities:
  - general_problem_solving
  - communication
keywords:
  - assistant
skills:
  - general_problem_solving
  - communication
methodology: "优先理解用户意图，给出结构化回答。"
context_window: 8000
temperature: 0.7
---

# Soul — {nickname}

## Identity
{identity}

## Responsibilities
{responsibilities}

## Constraints
{constraints}

## Skills
{skills}

## Memory
{memory}
"""

    def __init__(self):
        self.name = "role_manager"
        self._event_bus = None
        self._roles_dir: Path = None
        self._roles: Dict[str, Dict[str, Any]] = {}
        # 会话上下文：session_id -> [{"role": ..., "content": ...}]
        self._session_contexts: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        # 外部模板缓存
        self._soul_template = self.BUILTIN_SOUL_TEMPLATE
        self._tool_descriptions: List[Dict[str, Any]] = []

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        # 角色数据全部在项目根目录 roles/ 下，纳入 Git 版本控制
        self._roles_dir = Path(
            config.get("roles_dir", "roles/")
        ).resolve()
        self._roles_dir.mkdir(parents=True, exist_ok=True)
        self._load_roles()
        
        # 加载外部模板
        self._reload_templates()
        
        # 确保核心角色 suri 存在
        if "suri" not in self._roles:
            await self._create_suri()

    async def start(self) -> None:
        pass

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    def register_events(self) -> None:
        self._event_bus.subscribe("role.create", self._on_role_create)
        self._event_bus.subscribe("user.command", self._on_command)
        # 解耦：不再代理 suri，改为发布 role.context_ready 事件
        self._event_bus.subscribe("user.input", self._on_user_input)
        self._event_bus.subscribe("llm.response", self._on_llm_response)
        # 热更新事件
        self._event_bus.subscribe("config.updated", self._on_config_updated)
        self._event_bus.subscribe("role_manager.templates_updated", self._on_templates_updated)

    def list_roles(self) -> List[Dict[str, Any]]:
        """列出所有角色。"""
        return [
            {"name": name, "type": data.get("type", "unknown")}
            for name, data in self._roles.items()
        ]

    def get_role(self, name: str) -> Optional[Dict[str, Any]]:
        """获取角色信息。"""
        return self._roles.get(name)

    def get_soul(self, name: str) -> Optional[str]:
        """获取角色的 Soul 内容。"""
        soul_path = self._roles_dir / name / "soul.md"
        if soul_path.exists():
            return soul_path.read_text(encoding="utf-8")
        return None

    async def create_role(self, name: str, role_type: str = "custom",
                          identity: str = "", responsibilities: str = "",
                          constraints: str = "", skills: str = "",
                          memory: str = "") -> bool:
        """创建新角色。"""
        if name in self._roles:
            return False
        
        role_dir = self._roles_dir / name
        role_dir.mkdir(exist_ok=True)
        
        now = datetime.now(timezone.utc).isoformat()
        soul_content = self._soul_template.format(
            role_id=name,
            nickname=name,
            role_type=role_type,
            created_at=now,
            updated_at=now,
            identity=identity or f"AI assistant named {name}",
            responsibilities=responsibilities or "Assist the user.",
            constraints=constraints or "Follow system rules and user instructions.",
            skills=skills or "General problem solving, communication.",
            memory=memory or "No prior memory.",
        )
        
        (role_dir / "soul.md").write_text(soul_content, encoding="utf-8")
        
        meta = {
            "type": role_type,
            "created_at": now,
        }
        (role_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        
        self._roles[name] = meta
        return True

    async def _create_suri(self) -> None:
        """创建核心角色 suri。
        
        角色数据直接保存在项目根目录 roles/suri/ 下，纳入 Git 版本控制。
        """
        template_path = Path(__file__).parent.parent.parent / "roles" / "suri" / "soul.md"
        role_dir = self._roles_dir / "suri"
        role_dir.mkdir(parents=True, exist_ok=True)
        
        if template_path.exists():
            # 从项目模板复制到角色目录
            shutil.copy2(template_path, role_dir / "soul.md")
        else:
            # fallback：使用模板生成
            await self.create_role(
                name="suri",
                role_type="core",
                identity="Suri 是 suri-agent 系统的全局核心角色，统筹系统运行。",
                responsibilities="""- 响应用户输入
- 协调各插件工作
- 管理系统状态
- 提供对话接口""",
                constraints="""- 不得泄露敏感配置（如 API Key）
- 所有代码修改需用户确认
- 遵守安全沙箱规则""",
                skills="""- 自然语言理解与生成
- 代码阅读与分析
- 项目结构理解
- 多模型 LLM 调用""",
                memory="系统初始化，等待用户交互。",
            )
            return
        
        meta = {
            "type": "core",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (role_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._roles["suri"] = meta
        print("[RoleManager] 核心角色 suri 已创建。")

    def _load_roles(self) -> None:
        """从运行时目录加载角色。"""
        self._roles = {}
        if not self._roles_dir.exists():
            return
        
        for item in self._roles_dir.iterdir():
            if item.is_dir() and (item / "meta.json").exists():
                try:
                    meta = json.loads((item / "meta.json").read_text(encoding="utf-8"))
                    self._roles[item.name] = meta
                except Exception:
                    pass

    # --- 外部模板加载 ---
    
    def _load_external_soul_template(self) -> str:
        """从外部文件加载 Soul 模板"""
        try:
            if os.path.exists(self.EXTERNAL_SOUL_TEMPLATE_PATH):
                with open(self.EXTERNAL_SOUL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"[role_manager] 加载外部 Soul 模板失败: {e}")
        return self.BUILTIN_SOUL_TEMPLATE
    
    def _load_external_tool_descriptions(self) -> List[Dict[str, Any]]:
        """从外部 YAML 文件加载工具说明"""
        try:
            if not os.path.exists(self.EXTERNAL_TOOL_DESC_PATH):
                return []
            
            import yaml
            with open(self.EXTERNAL_TOOL_DESC_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            return data.get("tools", [])
        except Exception as e:
            print(f"[role_manager] 加载外部工具说明失败: {e}")
            return []
    
    def _reload_templates(self) -> None:
        """重新加载所有外部模板，用于热更新"""
        self._soul_template = self._load_external_soul_template()
        self._tool_descriptions = self._load_external_tool_descriptions()
        print(f"[role_manager] 模板加载完成: Soul模板={'外部' if self._soul_template != self.BUILTIN_SOUL_TEMPLATE else '内置'}, 工具说明={len(self._tool_descriptions)} 个")
    
    def _build_tool_descriptions_text(self) -> str:
        """从外部工具说明构建文本"""
        if not self._tool_descriptions:
            return ""
        
        lines = ["\n## 工具调用能力", "", "你可以通过以下格式调用工具来帮助用户：", "", "### 可用工具", ""]
        
        for i, tool in enumerate(self._tool_descriptions, 1):
            name = tool.get("name", "")
            desc = tool.get("description", "")
            params = tool.get("parameters", [])
            example = tool.get("example", "")
            
            param_strs = []
            for p in params:
                p_name = p.get("name", "")
                p_desc = p.get("description", "")
                required = p.get("required", False)
                options = p.get("options", [])
                
                if options:
                    # 有子选项的命令
                    opt_strs = []
                    for opt in options:
                        opt_name = opt.get("name", "")
                        opt_desc = opt.get("description", "")
                        opt_example = opt.get("example", "")
                        opt_strs.append(f"    - `{opt_name}` — {opt_desc}")
                        if opt_example:
                            opt_strs.append(f"      示例: `{opt_example}`")
                    param_strs.append(f"  - {p_name} ({p_desc}):\n" + "\n".join(opt_strs))
                else:
                    req_str = "必填" if required else "可选"
                    param_strs.append(f"  - {p_name} ({p_desc}, {req_str})")
            
            note = tool.get("note", "")
            
            lines.append(f"{i}. **{name}** — {desc}")
            if param_strs:
                lines.extend(param_strs)
            if example:
                lines.append(f"  示例: `{example}`")
            if note:
                lines.append(f"  **注意**: {note}")
            lines.append("")
        
        lines.append("### 调用方式")
        lines.append("")
        lines.append("当用户提出需求时，优先使用工具来满足，而不是告诉用户手动操作。")
        lines.append("工具调用的结果会通过后续消息返回给你。注意：工具调用结果返回后，请基于结果继续回答用户的问题。")
        
        return "\n".join(lines)
    
    def _get_system_prompt(self) -> str:
        """读取 suri 的 Soul 构建 system prompt。"""
        soul_path = self._roles_dir / "suri" / "soul.md"
        system_prompt = build_system_prompt(soul_path)
        
        # 从外部文件注入工具调用说明
        tool_desc = self._build_tool_descriptions_text()
        
        return system_prompt + tool_desc

    def _append_context(self, session_id: str, role: str, content: str) -> None:
        """追加消息到会话上下文，并裁剪到最大长度。"""
        ctx = self._session_contexts[session_id]
        ctx.append({"role": role, "content": content})
        # 裁剪：保留最近的 MAX_HISTORY_MESSAGES 条消息
        # 注意：system prompt 不在历史中，每次由 _get_system_prompt 重新生成
        if len(ctx) > self.MAX_HISTORY_MESSAGES:
            self._session_contexts[session_id] = ctx[-self.MAX_HISTORY_MESSAGES:]

    def _build_messages(self, session_id: str) -> List[Dict[str, str]]:
        """构建发送给 LLM 的 messages 列表。
        
        结构：[system_prompt, ...历史上下文...]
        
        注意：用户消息已在 _on_user_input 中通过 _append_context 追加到上下文，
        所以这里不再重复追加。
        
        模型切换时上下文处理策略：
        - 切换模型后，历史消息仍然保留在上下文中
        - 因为 system prompt 中注入了当前模型信息（通过 _inject_model_info），
          LLM 知道自己在用哪个模型，不会混淆
        - 如果切换前后模型能力差异大（如从 deepseek 切到 kimi），
          历史消息中的工具调用结果仍然可用，只是新模型可能无法复现之前的工具调用
        - 用户如果发现新模型不理解历史上下文，可以手动清空上下文（/clear 命令）
        """
        messages = [{"role": "system", "content": self._get_system_prompt()}]
        # 追加历史上下文（不含 system prompt）
        messages.extend(self._session_contexts[session_id])
        return messages

    async def _on_user_input(self, event: Event) -> None:
        """处理 user.input 事件（解耦：不再代理 suri）。
        
        迭代 2 解耦改造：
        - 不再直接调用 llm_gateway
        - 改为发布 role.context_ready 事件
        - suri 角色自己订阅该事件，获取 Soul 数据后自行构建 system prompt
        """
        payload = event.payload
        content = payload.get("content", "")
        session_id = payload.get("session_id", "default")
        
        # 追加用户消息到上下文
        self._append_context(session_id, "user", content)
        
        # 获取 suri 的 Soul 数据
        soul_content = self.get_soul("suri")
        
        # 发布 role.context_ready 事件，让 suri 角色自己处理
        await self._event_bus.publish(Event(
            event_type="role.context_ready",
            source=self.name,
            payload={
                "role_id": "suri",
                "session_id": session_id,
                "soul_content": soul_content,
                "tool_descriptions": self._tool_descriptions,
                "history": self._session_contexts.get(session_id, []),
                "original_event": event.payload,
            },
            priority=Priority.NORMAL,
        ))

    async def _on_llm_response(self, event: Event) -> None:
        """处理 llm.response 事件（解耦：只管理上下文，不处理工具调用）。
        
        迭代 2 解耦改造：
        - 不再解析工具调用（由 suri 角色自己处理）
        - 只负责将助手回复追加到会话上下文
        """
        payload = event.payload
        session_id = payload.get("session_id", "default")
        content = payload.get("content", "")
        
        if not content:
            return
        
        # 只将助手回复追加到会话上下文
        self._append_context(session_id, "assistant", content)

    async def _on_role_create(self, event: Event) -> None:
        """处理 role.create 事件。"""
        payload = event.payload
        name = payload.get("name")
        if name:
            await self.create_role(
                name=name,
                role_type=payload.get("role_type", "custom"),
                identity=payload.get("identity", ""),
                responsibilities=payload.get("responsibilities", ""),
                constraints=payload.get("constraints", ""),
                skills=payload.get("skills", ""),
                memory=payload.get("memory", ""),
            )

    async def _on_command(self, event: Event) -> None:
        """处理命令。"""
        cmd = event.payload.get("command", "")
        args = event.payload.get("args", [])
        session_id = event.payload.get("session_id", "default")
        
        if cmd == "clear":
            """清空当前会话的上下文历史。"""
            if session_id in self._session_contexts:
                self._session_contexts[session_id].clear()
                print(f"[Suri] 会话上下文已清空。")
            else:
                print(f"[Suri] 当前会话无上下文。")
    
    # --- 热更新事件处理 ---
    
    async def _on_config_updated(self, event: Event) -> None:
        """处理配置变更事件（热更新）"""
        plugin_id = event.payload.get("plugin_id")
        if plugin_id and plugin_id != self.name:
            return
        
        print(f"[role_manager] 收到配置变更事件，重新加载模板...")
        self._reload_templates()
    
    async def _on_templates_updated(self, event: Event) -> None:
        """处理模板更新事件（热更新）"""
        print(f"[role_manager] 收到模板更新事件，重新加载模板...")
        self._reload_templates()