"""role_manager 插件 — 角色管理（迭代 1：核心角色 suri）。"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority


class RoleManagerPlugin(PluginInterface):
    """角色管理插件。
    
    迭代 1：
    - 创建核心角色 suri
    - Soul 文件管理
    - 角色列表查询
    """

    SOUL_TEMPLATE = """# Soul — {role_name}

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
        self._event_bus = None
        self._roles_dir: Path = None
        self._roles: Dict[str, Dict[str, Any]] = {}

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._roles_dir = Path(
            config.get("roles_runtime_dir", "~/.suri/runtime/roles/")
        ).expanduser()
        self._roles_dir.mkdir(parents=True, exist_ok=True)
        self._load_roles()
        
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
        soul_path = self._roles_dir / name / "Soul.md"
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
        
        soul_content = self.SOUL_TEMPLATE.format(
            role_name=name,
            identity=identity or f"AI assistant named {name}",
            responsibilities=responsibilities or "Assist the user.",
            constraints=constraints or "Follow system rules and user instructions.",
            skills=skills or "General problem solving, communication.",
            memory=memory or "No prior memory.",
        )
        
        (role_dir / "Soul.md").write_text(soul_content, encoding="utf-8")
        
        meta = {
            "type": role_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (role_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        
        self._roles[name] = meta
        return True

    async def _create_suri(self) -> None:
        """创建核心角色 suri。"""
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
        
        if cmd == "role.list":
            roles = self.list_roles()
            print("Roles:")
            for r in roles:
                print(f"  {r['name']} ({r['type']})")
        elif cmd == "role.soul" and args:
            soul = self.get_soul(args[0])
            if soul:
                print(f"\n--- Soul: {args[0]} ---")
                print(soul[:2000] + ("..." if len(soul) > 2000 else ""))
            else:
                print(f"Role not found: {args[0]}")
