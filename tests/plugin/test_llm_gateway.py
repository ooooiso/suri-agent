"""llm_gateway 插件单元测试。"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_framework.plugins.llm_gateway.plugin import LLMGatewayPlugin
from agent_framework.shared.utils.event_types import Event, Priority


class TestLLMGatewayPlugin:
    """LLMGatewayPlugin 单元测试。"""

    @pytest.fixture(autouse=True)
    def _patch_config(self):
        """阻止 _load_from_config_file 从本地 ~/.suri/config.json 加载配置。"""
        with patch.object(LLMGatewayPlugin, '_load_from_config_file', return_value=None):
            yield

    @pytest.mark.asyncio
    async def test_init_defaults(self):
        """测试默认初始化。"""
        plugin = LLMGatewayPlugin()
        event_bus = MagicMock()
        await plugin.init(event_bus, {})
        assert plugin._active_provider == "deepseek"
        assert plugin._active_model == "deepseek-v4-pro"

    @pytest.mark.asyncio
    async def test_init_with_config(self):
        """测试带配置初始化。"""
        plugin = LLMGatewayPlugin()
        event_bus = MagicMock()
        config = {
            "default_provider": "kimi",
            "providers": {
                "kimi": {
                    "models": ["moonshot-v1-8k"],
                    "api_key": "sk-test-kimi",
                }
            }
        }
        await plugin.init(event_bus, config)
        assert plugin._active_provider == "kimi"
        assert plugin._api_keys.get("kimi") == "sk-test-kimi"

    def test_set_provider(self):
        """测试切换提供商。"""
        plugin = LLMGatewayPlugin()
        assert plugin.set_provider("kimi") is True
        assert plugin._active_provider == "kimi"
        assert plugin._active_model == "moonshot-v1-8k"

    def test_set_provider_invalid(self):
        """测试切换到不存在的提供商。"""
        plugin = LLMGatewayPlugin()
        assert plugin.set_provider("nonexistent") is False

    def test_set_provider_with_model(self):
        """测试切换提供商并指定模型。"""
        plugin = LLMGatewayPlugin()
        assert plugin.set_provider("deepseek", "deepseek-v4-flash") is True
        assert plugin._active_model == "deepseek-v4-flash"

    def test_set_provider_session(self):
        """测试会话级模型切换。"""
        plugin = LLMGatewayPlugin()
        assert plugin.set_provider("kimi", session_id="test_session") is True
        assert plugin._session_provider["test_session"] == "kimi"
        assert plugin._session_model["test_session"] == "moonshot-v1-8k"
        # 全局不受影响
        assert plugin._active_provider == "deepseek"

    def test_list_providers(self):
        """测试列出提供商。"""
        plugin = LLMGatewayPlugin()
        providers = plugin.list_providers()
        assert "deepseek" in providers
        assert "kimi" in providers
        assert "deepseek-chat" in providers["deepseek"]

    @pytest.mark.asyncio
    async def test_chat_no_api_key(self):
        """测试无 API Key 时返回错误。"""
        plugin = LLMGatewayPlugin()
        event_bus = MagicMock()
        await plugin.init(event_bus, {})
        result = await plugin.chat([{"role": "user", "content": "hi"}])
        assert result["success"] is False
        assert result["error_code"] == 3002

    @pytest.mark.asyncio
    async def test_chat_unknown_provider(self):
        """测试未知提供商。"""
        plugin = LLMGatewayPlugin()
        event_bus = MagicMock()
        await plugin.init(event_bus, {})
        result = await plugin.chat([{"role": "user", "content": "hi"}], provider="unknown")
        assert result["success"] is False
        assert result["error_code"] == 3001

    def test_inject_model_info_with_system(self):
        """测试在已有 system message 中注入模型信息。"""
        plugin = LLMGatewayPlugin()
        messages = [
            {"role": "system", "content": "You are Suri."},
            {"role": "user", "content": "hi"},
        ]
        plugin._inject_model_info(messages, "deepseek", "deepseek-chat")
        assert "deepseek/deepseek-chat" in messages[0]["content"]
        assert messages[0]["content"].startswith("You are Suri.")

    def test_inject_model_info_no_system(self):
        """测试无 system message 时插入。"""
        plugin = LLMGatewayPlugin()
        messages = [
            {"role": "user", "content": "hi"},
        ]
        plugin._inject_model_info(messages, "kimi", "moonshot-v1-8k")
        assert messages[0]["role"] == "system"
        assert "kimi/moonshot-v1-8k" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_on_llm_request_success(self):
        """测试 llm.request 事件处理成功。"""
        plugin = LLMGatewayPlugin()
        event_bus = AsyncMock()
        await plugin.init(event_bus, {"providers": {"deepseek": {"api_key": "sk-test"}}})
        
        event = Event(
            event_type="llm.request",
            source="test",
            payload={
                "messages": [{"role": "user", "content": "hi"}],
                "session_id": "test_session",
            },
        )
        
        # mock chat 返回成功
        with patch.object(plugin, 'chat', return_value={"success": True, "content": "Hello!"}):
            await plugin._on_llm_request(event)
            event_bus.publish.assert_called_once()
            call_args = event_bus.publish.call_args[0][0]
            assert call_args.event_type == "llm.response"
            assert call_args.payload["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_on_llm_request_error(self):
        """测试 llm.request 事件处理失败。"""
        plugin = LLMGatewayPlugin()
        event_bus = AsyncMock()
        await plugin.init(event_bus, {"providers": {"deepseek": {"api_key": "sk-test"}}})
        
        event = Event(
            event_type="llm.request",
            source="test",
            payload={
                "messages": [{"role": "user", "content": "hi"}],
                "session_id": "test_session",
            },
        )
        
        # mock chat 返回错误
        with patch.object(plugin, 'chat', return_value={
            "success": False, "error_code": 401, "error_message": "Unauthorized"
        }):
            await plugin._on_llm_request(event)
            event_bus.publish.assert_called_once()
            call_args = event_bus.publish.call_args[0][0]
            assert call_args.event_type == "llm.error"
            assert call_args.payload["error_code"] == 401

    @pytest.mark.asyncio
    async def test_on_command_models(self, capsys):
        """测试 models 命令。"""
        plugin = LLMGatewayPlugin()
        event_bus = MagicMock()
        await plugin.init(event_bus, {})
        
        event = Event(
            event_type="user.command",
            source="test",
            payload={"command": "models", "args": []},
        )
        await plugin._on_command(event)
        captured = capsys.readouterr()
        assert "deepseek" in captured.out
        assert "kimi" in captured.out

    @pytest.mark.asyncio
    async def test_on_command_switch(self, capsys):
        """测试 switch 命令。"""
        plugin = LLMGatewayPlugin()
        event_bus = MagicMock()
        await plugin.init(event_bus, {})
        
        event = Event(
            event_type="user.command",
            source="test",
            payload={"command": "switch", "args": ["kimi"]},
        )
        await plugin._on_command(event)
        assert plugin._active_provider == "kimi"
        captured = capsys.readouterr()
        assert "kimi" in captured.out
