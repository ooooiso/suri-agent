"""
模型管理器

职责：
- 管理模型配置（名称、API Key、端点）
- 调用模型 API 生成回复
- 首次启动引导配置（两级菜单：品牌 → 型号）
- 模型自动降级切换

调用层特性：
- httpx 异步客户端（连接池复用）
- tenacity 自动重试（指数退避）
- SSE 流式输出支持
- 结构化错误信息
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, AsyncIterator
from dataclasses import dataclass, asdict

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import logging

logger = logging.getLogger(__name__)

# ========== 两级模型菜单定义 ==========
MODEL_MENU = {
    "1": {
        "brand": "智谱 AI (GLM)",
        "provider": "glm",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": {
            "1": ("GLM-4", "glm-4"),
            "2": ("GLM-4.7-Flash (免费)", "glm-4.7-flash"),
            "3": ("GLM-4V", "glm-4v"),
            "4": ("GLM-4-Flash", "glm-4-flash"),
        }
    },
    "2": {
        "brand": "OpenAI",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": {
            "1": ("GPT-4o", "gpt-4o"),
            "2": ("GPT-4o Mini", "gpt-4o-mini"),
            "3": ("GPT-4 Turbo", "gpt-4-turbo"),
        }
    },
    "3": {
        "brand": "Moonshot (Kimi)",
        "provider": "moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "models": {
            "1": ("Moonshot v1-8k", "moonshot-v1-8k"),
            "2": ("Moonshot v1-32k", "moonshot-v1-32k"),
            "3": ("Moonshot v1-128k", "moonshot-v1-128k"),
        }
    },
    "4": {
        "brand": "DeepSeek",
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "models": {
            "1": ("DeepSeek Chat", "deepseek-chat"),
            "2": ("DeepSeek Coder", "deepseek-coder"),
        }
    },
    "5": {
        "brand": "Anthropic (Claude)",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": {
            "1": ("Claude 3.5 Sonnet", "claude-3-5-sonnet"),
            "2": ("Claude 3 Opus", "claude-3-opus"),
            "3": ("Claude 3 Haiku", "claude-3-haiku"),
        }
    },
}


@dataclass
class ModelConfig:
    """单个模型配置"""
    name: str
    model_id: str
    api_key: str
    base_url: str
    provider: str
    is_default: bool = False
    priority: int = 0


class ModelManager:
    """模型管理器"""

    CONFIG_FILE = "model_config.json"

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_path = project_root / self.CONFIG_FILE
        self._models: Dict[str, ModelConfig] = {}
        self._load()
        # 复用连接池的异步 HTTP 客户端
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _load(self) -> None:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                for key, val in data.items():
                    self._models[key] = ModelConfig(**val)
            except Exception as e:
                print(f"[ModelManager] 加载配置失败: {e}")

    def _save(self) -> None:
        data = {k: asdict(v) for k, v in self._models.items()}
        self.config_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def is_first_run(self) -> bool:
        return len(self._models) == 0

    # ========== 首次运行引导 ==========

    def setup_wizard(self) -> bool:
        if not sys.stdin.isatty():
            print("[ModelManager] 非交互环境，跳过模型配置引导")
            return False

        print("")
        print("=" * 50)
        print("  欢迎使用 Suri 智能体平台")
        print("=" * 50)
        print("")
        print("请选择模型品牌：")
        print("")
        for key, info in MODEL_MENU.items():
            marker = " ← 推荐" if key == "1" else ""
            print(f"  {key}) {info['brand']}{marker}")
        print("  6) 自定义")
        print("")

        brand_choice = input("输入选项 [1-6]: ").strip()
        if brand_choice == "6":
            return self._setup_custom()

        brand_info = MODEL_MENU.get(brand_choice)
        if not brand_info:
            print("\n❌ 无效选项")
            return False

        print("")
        print(f"请选择 {brand_info['brand']} 型号：")
        print("")
        for key, (name, model_id) in brand_info["models"].items():
            print(f"  {key}) {name}")
        print("")

        model_choice = input("输入选项: ").strip()
        model_entry = brand_info["models"].get(model_choice)
        if not model_entry:
            print("\n❌ 无效选项")
            return False

        name, model_id = model_entry
        provider = brand_info["provider"]
        base_url = brand_info["base_url"]

        print(f"\n请输入您的 {name} API Key：")
        api_key = input("API Key: ").strip()
        if not api_key:
            print("\n❌ API Key 不能为空")
            return False

        self._persist_config(name, model_id, api_key, base_url, provider)
        print("\n✅ 模型配置完成！")
        print(f"   模型: {name} ({model_id})")
        print(f"   提供商: {provider}")
        print("")
        return True

    def _setup_custom(self) -> bool:
        print("")
        print("自定义模型配置：")
        name = input("显示名称: ").strip()
        model_id = input("模型 ID: ").strip()
        base_url = input("API 端点: ").strip()
        provider = input("提供商名称: ").strip() or "custom"
        api_key = input("API Key: ").strip()
        if not all([name, model_id, base_url, api_key]):
            print("\n❌ 所有字段必填")
            return False
        self._persist_config(name, model_id, api_key, base_url, provider)
        print("\n✅ 自定义模型配置完成！")
        return True

    def _persist_config(self, name: str, model_id: str, api_key: str,
                        base_url: str, provider: str) -> None:
        env_path = self.project_root / ".env"
        env_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        env_dict = {}
        for line in env_lines:
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_dict[k.strip()] = v.strip()
        env_dict["DEFAULT_MODEL"] = model_id
        env_dict["DEFAULT_MODEL_API_KEY"] = api_key
        env_dict["DEFAULT_MODEL_BASE_URL"] = base_url
        env_dict["DEFAULT_MODEL_PROVIDER"] = provider
        env_content = "\n".join(f"{k}={v}" for k, v in env_dict.items())
        env_path.write_text(env_content + "\n", encoding="utf-8")
        self.add_model(name, model_id, api_key, base_url, provider, is_default=True, priority=0)

    def add_model(self, name: str, model_id: str, api_key: str,
                  base_url: str, provider: str, is_default: bool = False,
                  priority: int = 0) -> None:
        if is_default:
            for m in self._models.values():
                m.is_default = False
        self._models[model_id] = ModelConfig(
            name=name, model_id=model_id, api_key=api_key,
            base_url=base_url, provider=provider,
            is_default=is_default, priority=priority,
        )
        self._save()

    def list_models(self) -> List[ModelConfig]:
        return list(self._models.values())

    def get_default_model(self) -> Optional[ModelConfig]:
        for m in self._models.values():
            if m.is_default:
                return m
        if self._models:
            return list(self._models.values())[0]
        return None

    def set_default(self, model_id: str) -> bool:
        if model_id not in self._models:
            return False
        for m in self._models.values():
            m.is_default = False
        self._models[model_id].is_default = True
        self._save()
        return True

    # ========== 模型调用（自动降级 + 重试） ==========

    async def chat(self, messages: List[Dict[str, str]],
                   model_id: Optional[str] = None) -> Optional[str]:
        """
        调用模型生成回复（带自动降级和重试）

        1. 先尝试指定/默认模型（3 次重试）
        2. 失败时按优先级自动尝试其他已配置模型
        """
        candidates = []
        primary = self._models.get(model_id) if model_id else self.get_default_model()
        if primary:
            candidates.append(primary)
        others = sorted(
            [m for m in self._models.values()
             if m.model_id != (primary.model_id if primary else None)],
            key=lambda m: m.priority,
        )
        candidates.extend(others)

        if not candidates:
            print("[ModelManager] 错误: 没有可用的模型配置")
            return None

        for model in candidates:
            print(f"[ModelManager] 尝试调用 {model.name} ({model.model_id})...")
            result = await self._call_single(model, messages)
            if result is not None:
                if primary and model.model_id != primary.model_id:
                    print(f"[ModelManager] ⚠️ 已自动降级到备用模型: {model.name}")
                return result

        print("[ModelManager] ❌ 所有模型均不可用，请检查 API Key 和网络连接")
        return None

    async def chat_stream(self, messages: List[Dict[str, str]],
                          model_id: Optional[str] = None) -> AsyncIterator[str]:
        """
        流式调用模型（SSE）

        Yields:
            每个 token 片段
        """
        model = self._models.get(model_id) if model_id else self.get_default_model()
        if not model:
            print("[ModelManager] 错误: 没有可用的模型配置")
            return

        if model.provider == "anthropic":
            async for chunk in self._stream_anthropic(model, messages):
                yield chunk
        else:
            async for chunk in self._stream_openai_compatible(model, messages):
                yield chunk

    async def _call_single(self, model: ModelConfig,
                           messages: List[Dict[str, str]]) -> Optional[str]:
        if model.provider == "anthropic":
            return await self._call_anthropic(model, messages)
        return await self._call_openai_compatible(model, messages)

    # ---------- OpenAI 兼容格式 ----------

    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _call_openai_compatible(self, model: ModelConfig,
                                       messages: List[Dict[str, str]]) -> Optional[str]:
        url = f"{model.base_url}/chat/completions"
        payload = {
            "model": model.model_id,
            "messages": messages,
            "temperature": 0.7,
        }
        try:
            resp = await self._client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {model.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [{}])
            if choices and isinstance(choices, list):
                return choices[0].get("message", {}).get("content")
            return None
        except httpx.HTTPStatusError as e:
            print(f"[ModelManager] {model.name} HTTP 错误 {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            print(f"[ModelManager] {model.name} 调用失败: {e}")
            return None

    async def _stream_openai_compatible(self, model: ModelConfig,
                                         messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        url = f"{model.base_url}/chat/completions"
        payload = {
            "model": model.model_id,
            "messages": messages,
            "temperature": 0.7,
            "stream": True,
        }
        try:
            async with self._client.stream(
                "POST", url,
                json=payload,
                headers={"Authorization": f"Bearer {model.api_key}"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"[ModelManager] {model.name} 流式调用失败: {e}")

    # ---------- Anthropic 格式 ----------

    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _call_anthropic(self, model: ModelConfig,
                               messages: List[Dict[str, str]]) -> Optional[str]:
        url = f"{model.base_url}/messages"
        payload = {
            "model": model.model_id,
            "messages": messages,
            "max_tokens": 4096,
        }
        try:
            resp = await self._client.post(
                url,
                json=payload,
                headers={
                    "x-api-key": model.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", [{}])
            if content and isinstance(content, list):
                return content[0].get("text")
            return None
        except httpx.HTTPStatusError as e:
            print(f"[ModelManager] {model.name} HTTP 错误 {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            print(f"[ModelManager] {model.name} 调用失败: {e}")
            return None

    async def _stream_anthropic(self, model: ModelConfig,
                                 messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        url = f"{model.base_url}/messages"
        payload = {
            "model": model.model_id,
            "messages": messages,
            "max_tokens": 4096,
            "stream": True,
        }
        try:
            async with self._client.stream(
                "POST", url,
                json=payload,
                headers={
                    "x-api-key": model.api_key,
                    "anthropic-version": "2023-06-01",
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "content_block_delta":
                                text = data.get("delta", {}).get("text", "")
                                if text:
                                    yield text
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"[ModelManager] {model.name} 流式调用失败: {e}")
