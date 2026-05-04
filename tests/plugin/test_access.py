"""access 插件单元测试。"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_framework.plugins.access.cli import CLISession
from agent_framework.plugins.access.config_editor import ConfigEditor
from agent_framework.plugins.access.wizard import ConfigWizard
from agent_framework.shared.utils.event_types import Event, Priority


class TestCLISession:
    """CLISession 单元测试。"""

    @pytest.mark.asyncio
    async def test_init(self):
        """测试初始化。"""
        event_bus = MagicMock()
        session = CLISession(event_bus)
        assert session._session_id.startswith("cli_")
        assert session._running is False

    @pytest.mark.asyncio
    async def test_print_output(self):
        """测试 print_output 不抛出异常。"""
        event_bus = MagicMock()
        session = CLISession(event_bus)
        session.print_output("test message")
        session.print_system("test system message")

    @pytest.mark.asyncio
    async def test_stop(self):
        """测试 stop 方法。"""
        event_bus = MagicMock()
        session = CLISession(event_bus)
        session._running = True
        session.stop()
        assert session._running is False


class TestConfigEditor:
    """ConfigEditor 单元测试。"""

    @pytest.mark.asyncio
    async def test_init(self):
        """测试初始化。"""
        editor = ConfigEditor()
        assert editor._input_func is not None

    @pytest.mark.asyncio
    async def test_load_config_no_file(self):
        """测试无配置文件时返回空字典。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(ConfigEditor, 'CONFIG_PATH', Path(tmpdir) / "config.json"):
                editor = ConfigEditor()
                config = editor.load_config()
                assert config == {}

    @pytest.mark.asyncio
    async def test_save_and_load_config(self):
        """测试保存和加载配置。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            with patch.object(ConfigEditor, 'CONFIG_PATH', config_path):
                editor = ConfigEditor()
                test_config = {"llm_gateway": {"default_provider": "deepseek"}}
                assert editor.save_config(test_config) is True
                loaded = editor.load_config()
                assert loaded == test_config

    @pytest.mark.asyncio
    async def test_set_provider_key(self):
        """测试设置厂商 Key。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            with patch.object(ConfigEditor, 'CONFIG_PATH', config_path):
                event_bus = AsyncMock()
                editor = ConfigEditor(event_bus)
                result = await editor.set_provider_key("deepseek", "sk-test-key")
                assert result is True
                config = editor.load_config()
                assert config["llm_gateway"]["providers"]["deepseek"]["api_key"] == "sk-test-key"
                assert config["llm_gateway"]["default_provider"] == "deepseek"

    @pytest.mark.asyncio
    async def test_set_provider_key_notify(self):
        """测试设置 Key 后发布事件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            with patch.object(ConfigEditor, 'CONFIG_PATH', config_path):
                event_bus = AsyncMock()
                editor = ConfigEditor(event_bus)
                await editor.set_provider_key("deepseek", "sk-test")
                event_bus.publish.assert_called_once()
                call_args = event_bus.publish.call_args[0][0]
                assert call_args.event_type == "system.config_changed"
                assert call_args.payload["reason"] == "runtime_edit"


class TestConfigWizard:
    """ConfigWizard 单元测试。"""

    def test_providers_defined(self):
        """测试厂商定义完整。"""
        wizard = ConfigWizard()
        assert len(wizard.PROVIDERS) == 5
        assert "deepseek" in [v[0] for v in wizard.PROVIDERS.values()]
        assert "kimi" in [v[0] for v in wizard.PROVIDERS.values()]

    def test_get_base_url(self):
        """测试 base_url 映射。"""
        wizard = ConfigWizard()
        assert wizard._get_base_url("deepseek") == "https://api.deepseek.com"
        assert wizard._get_base_url("kimi") == "https://api.moonshot.cn"
        assert wizard._get_base_url("wenxin") == "https://aip.baidubce.com"

    def test_verify_key_invalid_chars(self):
        """测试非法字符 Key 验证。"""
        wizard = ConfigWizard()
        result = wizard._verify_key("deepseek", "中文key", ["deepseek-chat"])
        assert result is False

    @patch('urllib.request.urlopen')
    def test_verify_key_401(self, mock_urlopen):
        """测试 401 返回 False。"""
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            "http://example.com", 401, "Unauthorized", {}, None
        )
        wizard = ConfigWizard()
        result = wizard._verify_key("deepseek", "sk-invalid", ["deepseek-chat"])
        assert result is False

    @patch('urllib.request.urlopen')
    def test_verify_key_network_error(self, mock_urlopen):
        """测试网络错误返回 False。"""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network error")
        wizard = ConfigWizard()
        result = wizard._verify_key("deepseek", "sk-test", ["deepseek-chat"])
        assert result is False

    def test_verify_telegram_token_invalid_chars(self):
        """测试非法字符 Telegram Token。"""
        wizard = ConfigWizard()
        result = wizard._verify_telegram_token("中文token")
        assert result is False
