"""role_manager 插件单元测试。"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_framework.plugins.role_manager.plugin import RoleManagerPlugin
from agent_framework.shared.utils.event_types import Event, Priority


class TestRoleManagerPlugin:
    """RoleManagerPlugin 单元测试。"""

    @pytest.mark.asyncio
    async def test_init_creates_suri(self):
        """测试初始化时自动创建 suri 角色。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = RoleManagerPlugin()
            event_bus = MagicMock()
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            assert "suri" in plugin._roles
            assert plugin._roles["suri"]["type"] == "core"
            # 验证 soul.md 文件存在
            soul_path = Path(tmpdir) / "suri" / "soul.md"
            assert soul_path.exists()

    @pytest.mark.asyncio
    async def test_init_loads_existing_roles(self):
        """测试初始化时加载已有角色。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 先创建一个角色
            role_dir = Path(tmpdir) / "test_role"
            role_dir.mkdir()
            meta = {"type": "custom", "created_at": "2024-01-01"}
            (role_dir / "meta.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (role_dir / "soul.md").write_text("# Test Soul", encoding="utf-8")
            
            plugin = RoleManagerPlugin()
            event_bus = MagicMock()
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            assert "test_role" in plugin._roles
            assert plugin._roles["test_role"]["type"] == "custom"

    def test_list_roles(self):
        """测试列出角色。"""
        plugin = RoleManagerPlugin()
        plugin._roles = {
            "suri": {"type": "core"},
            "test": {"type": "custom"},
        }
        roles = plugin.list_roles()
        assert len(roles) == 2
        assert {"name": "suri", "type": "core"} in roles
        assert {"name": "test", "type": "custom"} in roles

    def test_get_role(self):
        """测试获取角色信息。"""
        plugin = RoleManagerPlugin()
        plugin._roles = {"suri": {"type": "core"}}
        role = plugin.get_role("suri")
        assert role == {"type": "core"}
        assert plugin.get_role("nonexistent") is None

    def test_get_soul(self):
        """测试获取 Soul 内容。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = RoleManagerPlugin()
            plugin._roles_dir = Path(tmpdir)
            soul_path = Path(tmpdir) / "suri" / "soul.md"
            soul_path.parent.mkdir()
            soul_path.write_text("# Suri Soul", encoding="utf-8")
            
            soul = plugin.get_soul("suri")
            assert soul == "# Suri Soul"
            assert plugin.get_soul("nonexistent") is None

    @pytest.mark.asyncio
    async def test_create_role(self):
        """测试创建新角色。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = RoleManagerPlugin()
            plugin._roles_dir = Path(tmpdir)
            plugin._roles = {}
            
            result = await plugin.create_role(
                name="test_role",
                role_type="custom",
                identity="Test assistant",
                responsibilities="Help with testing",
                constraints="None",
                skills="Testing",
                memory="No memory",
            )
            assert result is True
            assert "test_role" in plugin._roles
            assert plugin._roles["test_role"]["type"] == "custom"
            
            # 验证文件
            soul_path = Path(tmpdir) / "test_role" / "soul.md"
            assert soul_path.exists()
            content = soul_path.read_text(encoding="utf-8")
            assert "Test assistant" in content

    @pytest.mark.asyncio
    async def test_create_role_duplicate(self):
        """测试创建重复角色返回 False。"""
        plugin = RoleManagerPlugin()
        plugin._roles = {"existing": {"type": "core"}}
        result = await plugin.create_role(name="existing")
        assert result is False

    @pytest.mark.asyncio
    async def test_on_user_input_publishes_context_ready(self):
        """测试 user.input 事件发布 role.context_ready（解耦后不再直接调用 llm_gateway）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = RoleManagerPlugin()
            event_bus = AsyncMock()
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            event = Event(
                event_type="user.input",
                source="access",
                payload={
                    "content": "Hello Suri!",
                    "session_id": "test_session",
                },
            )
            await plugin._on_user_input(event)
            
            event_bus.publish.assert_called_once()
            call_args = event_bus.publish.call_args[0][0]
            assert call_args.event_type == "role.context_ready"
            assert call_args.source == "role_manager"
            assert call_args.payload["session_id"] == "test_session"
            assert call_args.payload["role_id"] == "suri"
            
            # 验证 payload 包含 soul_content 和 tool_descriptions
            assert "soul_content" in call_args.payload
            assert "tool_descriptions" in call_args.payload
            assert "history" in call_args.payload
            assert "original_event" in call_args.payload
            
            # 验证上下文已追加用户消息
            history = call_args.payload["history"]
            assert len(history) >= 1
            assert history[-1]["role"] == "user"
            assert history[-1]["content"] == "Hello Suri!"

    @pytest.mark.asyncio
    async def test_on_user_input_includes_tool_desc(self):
        """测试 user.input 的 role.context_ready 事件包含工具说明。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = RoleManagerPlugin()
            event_bus = AsyncMock()
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            event = Event(
                event_type="user.input",
                source="access",
                payload={
                    "content": "Show me the code",
                    "session_id": "test_session",
                },
            )
            await plugin._on_user_input(event)
            
            call_args = event_bus.publish.call_args[0][0]
            tool_descriptions = call_args.payload["tool_descriptions"]
            # 默认没有外部文件时，tool_descriptions 为空列表
            assert isinstance(tool_descriptions, list)

    @pytest.mark.asyncio
    async def test_on_role_create(self):
        """测试 role.create 事件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = RoleManagerPlugin()
            plugin._roles_dir = Path(tmpdir)
            plugin._roles = {}
            
            event = Event(
                event_type="role.create",
                source="test",
                payload={
                    "name": "new_role",
                    "role_type": "custom",
                    "identity": "New assistant",
                },
            )
            await plugin._on_role_create(event)
            assert "new_role" in plugin._roles

    @pytest.mark.asyncio
    async def test_on_command_clear(self, capsys):
        """测试 /clear 命令清空会话上下文。"""
        plugin = RoleManagerPlugin()
        plugin._session_contexts["test_session"] = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        
        event = Event(
            event_type="user.command",
            source="test",
            payload={"command": "clear", "args": [], "session_id": "test_session"},
        )
        await plugin._on_command(event)
        captured = capsys.readouterr()
        assert "会话上下文已清空" in captured.out
        assert plugin._session_contexts["test_session"] == []

    @pytest.mark.asyncio
    async def test_on_command_clear_empty(self, capsys):
        """测试清空不存在的会话。"""
        plugin = RoleManagerPlugin()
        
        event = Event(
            event_type="user.command",
            source="test",
            payload={"command": "clear", "args": [], "session_id": "nonexistent"},
        )
        await plugin._on_command(event)
        captured = capsys.readouterr()
        assert "无上下文" in captured.out
    
    # --- 热更新测试 ---
    
    @pytest.mark.asyncio
    async def test_reload_templates_keeps_builtin(self):
        """测试重新加载模板时内置模板保留"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            # 修改模板
            plugin._soul_template = "被修改的模板"
            
            # 重新加载
            plugin._reload_templates()
            
            # 内置模板恢复（因为没有外部文件）
            assert plugin._soul_template == plugin.BUILTIN_SOUL_TEMPLATE
    
    @pytest.mark.asyncio
    async def test_reload_templates_external_overrides_builtin(self):
        """测试外部模板覆盖内置模板"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            # 模拟外部 Soul 模板文件
            import os
            external_path = plugin.EXTERNAL_SOUL_TEMPLATE_PATH
            os.makedirs(os.path.dirname(external_path), exist_ok=True)
            with open(external_path, "w", encoding="utf-8") as f:
                f.write("外部模板内容")
            
            # 重新加载
            plugin._reload_templates()
            
            # 外部模板生效
            assert plugin._soul_template == "外部模板内容"
            
            # 清理
            os.remove(external_path)
    
    @pytest.mark.asyncio
    async def test_reload_templates_external_tool_desc(self):
        """测试外部工具说明加载"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            # 模拟外部工具说明 YAML 文件
            import os
            import yaml
            external_path = plugin.EXTERNAL_TOOL_DESC_PATH
            os.makedirs(os.path.dirname(external_path), exist_ok=True)
            with open(external_path, "w", encoding="utf-8") as f:
                yaml.dump({"tools": [{"name": "test_tool", "description": "测试工具"}]}, f)
            
            # 重新加载
            plugin._reload_templates()
            
            # 外部工具说明生效
            assert len(plugin._tool_descriptions) == 1
            assert plugin._tool_descriptions[0]["name"] == "test_tool"
            
            # 清理
            os.remove(external_path)
    
    @pytest.mark.asyncio
    async def test_on_config_updated_ignores_other_plugin(self):
        """测试 config.updated 事件只响应自身插件"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            # 修改模板
            plugin._soul_template = "被修改"
            
            # 其他插件的配置变更
            event = Event(
                event_type="config.updated",
                source="other_plugin",
                payload={"plugin_id": "other_plugin"},
            )
            await plugin._on_config_updated(event)
            
            # 模板不应被恢复
            assert plugin._soul_template == "被修改"
    
    @pytest.mark.asyncio
    async def test_on_config_updated_self(self):
        """测试 config.updated 事件响应自身插件"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            # 修改模板
            plugin._soul_template = "被修改"
            
            # 自身配置变更
            event = Event(
                event_type="config.updated",
                source="role_manager",
                payload={"plugin_id": "role_manager"},
            )
            await plugin._on_config_updated(event)
            
            # 模板被恢复
            assert plugin._soul_template == plugin.BUILTIN_SOUL_TEMPLATE
    
    @pytest.mark.asyncio
    async def test_on_templates_updated(self):
        """测试 templates_updated 事件触发重新加载"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            # 修改模板
            plugin._soul_template = "被修改"
            
            event = Event(
                event_type="role_manager.templates_updated",
                source="upgrade_manager",
                payload={},
            )
            await plugin._on_templates_updated(event)
            
            # 模板被恢复
            assert plugin._soul_template == plugin.BUILTIN_SOUL_TEMPLATE
    
    @pytest.mark.asyncio
    async def test_build_tool_descriptions_text_empty(self):
        """测试工具说明为空时返回空字符串"""
        plugin = RoleManagerPlugin()
        plugin._tool_descriptions = []
        text = plugin._build_tool_descriptions_text()
        assert text == ""
    
    @pytest.mark.asyncio
    async def test_build_tool_descriptions_text_with_tools(self):
        """测试工具说明非空时生成文本"""
        plugin = RoleManagerPlugin()
        plugin._tool_descriptions = [
            {
                "name": "test_tool",
                "description": "测试工具",
                "parameters": [{"name": "param1", "description": "参数1", "required": True}],
                "example": "test_tool(param1=value)",
            }
        ]
        text = plugin._build_tool_descriptions_text()
        assert "test_tool" in text
        assert "测试工具" in text
        assert "param1" in text
        assert "test_tool(param1=value)" in text
    
    @pytest.mark.asyncio
    async def test_on_llm_response_appends_context(self):
        """测试 llm.response 事件追加助手回复到上下文"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            # 先添加用户消息
            plugin._append_context("session_1", "user", "你好")
            
            # 模拟 LLM 响应
            event = Event(
                event_type="llm.response",
                source="llm_gateway",
                payload={
                    "session_id": "session_1",
                    "content": "你好！有什么可以帮助你的？",
                },
            )
            await plugin._on_llm_response(event)
            
            # 验证上下文
            ctx = plugin._session_contexts["session_1"]
            assert len(ctx) == 2
            assert ctx[0]["role"] == "user"
            assert ctx[0]["content"] == "你好"
            assert ctx[1]["role"] == "assistant"
            assert ctx[1]["content"] == "你好！有什么可以帮助你的？"
    
    @pytest.mark.asyncio
    async def test_on_llm_response_empty_content(self):
        """测试 llm.response 空内容不追加上下文"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            plugin._append_context("session_1", "user", "你好")
            
            event = Event(
                event_type="llm.response",
                source="llm_gateway",
                payload={
                    "session_id": "session_1",
                    "content": "",
                },
            )
            await plugin._on_llm_response(event)
            
            # 上下文不变
            ctx = plugin._session_contexts["session_1"]
            assert len(ctx) == 1
    
    @pytest.mark.asyncio
    async def test_context_cutoff(self):
        """测试上下文裁剪到最大消息数"""
        plugin = RoleManagerPlugin()
        plugin.MAX_HISTORY_MESSAGES = 4  # 缩小限制便于测试
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            # 添加 6 条消息（超过限制）
            for i in range(6):
                plugin._append_context("session_1", "user", f"消息{i}")
            
            # 裁剪后只保留最近 4 条
            ctx = plugin._session_contexts["session_1"]
            assert len(ctx) == 4
            assert ctx[0]["content"] == "消息2"
            assert ctx[-1]["content"] == "消息5"
    
    @pytest.mark.asyncio
    async def test_get_system_prompt_contains_soul(self):
        """测试 system prompt 包含 Soul 内容"""
        plugin = RoleManagerPlugin()
        event_bus = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            await plugin.init(event_bus, {"roles_dir": tmpdir})
            
            prompt = plugin._get_system_prompt()
            assert "suri" in prompt.lower() or "Suri" in prompt