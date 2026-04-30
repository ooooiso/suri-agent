"""
ModelManager 单元测试

覆盖范围：
- 配置加载/保存
- 模型 CRUD
- 默认模型切换
- chat() 自动降级逻辑（mock httpx）
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "suri-agent"))

import pytest
from model.manager import ModelManager, ModelConfig, MODEL_MENU


@pytest.fixture
def tmp_project(tmp_path):
    """创建一个临时项目目录"""
    return tmp_path


@pytest.fixture
def manager(tmp_project):
    """创建一个空的 ModelManager"""
    return ModelManager(tmp_project)


class TestModelConfig:
    def test_model_config_creation(self):
        m = ModelConfig(
            name="Test", model_id="test-1",
            api_key="sk-xxx", base_url="https://api.test.com",
            provider="test", is_default=True, priority=0
        )
        assert m.name == "Test"
        assert m.is_default is True


class TestModelManagerLifecycle:
    def test_is_first_run_empty(self, manager):
        """无配置时应返回 True"""
        assert manager.is_first_run() is True

    def test_is_first_run_with_model(self, manager):
        """有配置时应返回 False"""
        manager.add_model("Test", "test-1", "sk-xxx", "https://api.test.com", "test")
        assert manager.is_first_run() is False

    def test_add_and_list_models(self, manager):
        manager.add_model("A", "a-1", "key-a", "https://a.com", "test")
        manager.add_model("B", "b-1", "key-b", "https://b.com", "test")
        models = manager.list_models()
        assert len(models) == 2

    def test_default_model(self, manager):
        manager.add_model("A", "a-1", "key-a", "https://a.com", "test", is_default=True)
        manager.add_model("B", "b-1", "key-b", "https://b.com", "test")
        default = manager.get_default_model()
        assert default.model_id == "a-1"
        assert default.is_default is True

    def test_set_default(self, manager):
        manager.add_model("A", "a-1", "key-a", "https://a.com", "test", is_default=True)
        manager.add_model("B", "b-1", "key-b", "https://b.com", "test")
        assert manager.set_default("b-1") is True
        assert manager.get_default_model().model_id == "b-1"
        assert manager._models["a-1"].is_default is False

    def test_set_default_not_found(self, manager):
        assert manager.set_default("nonexistent") is False

    def test_persistence(self, tmp_project):
        """配置应能正确持久化到 model_config.json"""
        m1 = ModelManager(tmp_project)
        m1.add_model("Test", "test-1", "sk-xxx", "https://api.test.com", "test", is_default=True)

        # 重新加载
        m2 = ModelManager(tmp_project)
        assert m2.is_first_run() is False
        assert m2.get_default_model().model_id == "test-1"


class TestModelManagerChat:
    @pytest.mark.asyncio
    async def test_chat_single_model_success(self, manager):
        """单模型调用成功"""
        manager.add_model("Test", "test-1", "sk-xxx", "https://api.test.com", "test", is_default=True)

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Hello"}}]}
        mock_response.raise_for_status = MagicMock()

        manager._client.post = AsyncMock(return_value=mock_response)

        result = await manager.chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello"

    @pytest.mark.asyncio
    async def test_chat_auto_fallback(self, manager):
        """默认模型失败时自动降级到备用模型"""
        manager.add_model("Primary", "primary", "key1", "https://a.com", "test", is_default=True, priority=0)
        manager.add_model("Backup", "backup", "key2", "https://b.com", "test", priority=1)

        # Primary 失败
        fail_response = MagicMock()
        fail_response.raise_for_status.side_effect = Exception("Primary failed")
        manager._client.post = AsyncMock(side_effect=[
            fail_response,  # primary fails
            MagicMock(json=lambda: {"choices": [{"message": {"content": "Backup reply"}}]}, raise_for_status=MagicMock())
        ])

        result = await manager.chat([{"role": "user", "content": "Hi"}])
        assert result == "Backup reply"

    @pytest.mark.asyncio
    async def test_chat_all_models_fail(self, manager):
        """所有模型都失败时返回 None"""
        manager.add_model("Only", "only", "key", "https://a.com", "test", is_default=True)

        manager._client.post = AsyncMock(side_effect=Exception("Network error"))

        result = await manager.chat([{"role": "user", "content": "Hi"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_chat_no_models(self, manager):
        """无模型时返回 None"""
        result = await manager.chat([{"role": "user", "content": "Hi"}])
        assert result is None


class TestModelManagerStream:
    @pytest.mark.asyncio
    async def test_chat_stream(self, manager):
        """流式输出测试"""
        manager.add_model("Test", "test-1", "sk-xxx", "https://api.test.com", "test", is_default=True)

        async def mock_lines():
            yield "data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}"
            yield "data: {\"choices\":[{\"delta\":{\"content\":\" World\"}}]}"
            yield "data: [DONE]"

        mock_stream = MagicMock()
        mock_stream.aiter_lines = mock_lines
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.raise_for_status = MagicMock()

        manager._client.stream = MagicMock(return_value=mock_stream)

        result = ""
        async for token in manager.chat_stream([{"role": "user", "content": "Hi"}]):
            result += token
        assert result == "Hello World"


class TestModelMenu:
    def test_menu_structure(self):
        """MODEL_MENU 结构完整性"""
        assert "1" in MODEL_MENU  # 智谱 AI
        assert "2" in MODEL_MENU  # OpenAI
        assert "3" in MODEL_MENU  # Moonshot
        assert "4" in MODEL_MENU  # DeepSeek
        assert "5" in MODEL_MENU  # Anthropic

        for key, brand in MODEL_MENU.items():
            assert "brand" in brand
            assert "provider" in brand
            assert "base_url" in brand
            assert "models" in brand
            assert len(brand["models"]) > 0
