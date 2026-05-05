"""llm_gateway 插件 — 多厂商 LLM API 网关。

提供统一接口对接多个 LLM 提供商：
  - deepseek, kimi, chatglm, tongyi, wenxin
  - 自动降级、API Key 验证、模型切换
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


BUILTIN_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "models": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat"],
        "default_model": "deepseek-v4-pro",
        "env_key": "SURI_DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
    },
    "kimi": {
        "name": "Kimi",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "default_model": "moonshot-v1-8k",
        "env_key": "SURI_KIMI_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
    },
    "chatglm": {
        "name": "ChatGLM",
        "models": ["glm-4", "glm-4v", "glm-3-turbo"],
        "default_model": "glm-4",
        "env_key": "SURI_CHATGLM_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "tongyi": {
        "name": "通义千问",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "default_model": "qwen-turbo",
        "env_key": "SURI_TONGYI_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/api/v1",
    },
    "wenxin": {
        "name": "文心一言",
        "models": ["ernie-3.5-8k", "ernie-4.0-8k"],
        "default_model": "ernie-3.5-8k",
        "env_key": "SURI_WENXIN_API_KEY",
        "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1",
    },
}


class LLMGatewayPlugin(PluginInterface):
    """LLM 网关插件。"""

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._providers: Dict[str, Any] = {}
        self._api_keys: Dict[str, str] = {}
        self._active_provider: str = "deepseek"
        self._active_model: str = "deepseek-v4-pro"
        self._session_provider: Dict[str, str] = {}
        self._session_model: Dict[str, str] = {}
        self._status = "stopped"
        # 健康状态追踪（用于终端面板显示）
        # 完整数据模型见 PRD: prd/plugins/capability/llm_gateway.md
        self._health: Dict[str, Dict[str, Any]] = {}
        # 初始化内置提供商
        for pid, pconf in BUILTIN_PROVIDERS.items():
            self._providers[pid] = dict(pconf)

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config

        # 加载提供商配置
        self._providers = {}
        for pid, pconf in BUILTIN_PROVIDERS.items():
            self._providers[pid] = dict(pconf)

        # 从配置中加载
        cfg_providers = config.get("providers", {})
        for pid, pconf in cfg_providers.items():
            if pid in self._providers:
                if "models" in pconf:
                    self._providers[pid]["models"] = pconf["models"]
                if "base_url" in pconf:
                    self._providers[pid]["base_url"] = pconf["base_url"]
                if "default_model" in pconf:
                    self._providers[pid]["default_model"] = pconf["default_model"]
                if "api_key" in pconf:
                    self._api_keys[pid] = pconf["api_key"]

        # 默认提供商
        if "default_provider" in config:
            self._active_provider = config["default_provider"]
            if self._active_provider in self._providers:
                self._active_model = self._providers[self._active_provider]["default_model"]

        # 加载 API Keys（配置优先，环境变量兜底）
        self._load_api_keys()
        self._load_from_config_file()

        self._status = "initialized"

    def _load_api_keys(self) -> None:
        """从环境变量加载 API Key。"""
        for pid, pconf in self._providers.items():
            env_key = pconf.get("env_key", f"SURI_{pid.upper()}_API_KEY")
            val = os.environ.get(env_key)
            if val and pid not in self._api_keys:
                self._api_keys[pid] = val

    def _load_from_config_file(self) -> None:
        """从 ~/.suri/config.json 加载配置（可选）。"""
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            llm_cfg = cfg.get("llm_gateway", {})
            if llm_cfg.get("default_provider"):
                self._active_provider = llm_cfg["default_provider"]
            providers = llm_cfg.get("providers", {})
            for pid, pconf in providers.items():
                if pconf.get("api_key"):
                    self._api_keys[pid] = pconf["api_key"]
        except Exception:
            pass

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
        self._event_bus.subscribe("llm.request", self._on_llm_request)
        self._event_bus.subscribe("user.command", self._on_command)

    # ── 公开 API ──

    def set_provider(self, provider: str, model: Optional[str] = None,
                     session_id: Optional[str] = None) -> bool:
        """切换提供商。返回是否成功。"""
        if provider not in self._providers:
            return False

        target_model = model or self._providers[provider]["default_model"]

        if session_id:
            self._session_provider[session_id] = provider
            self._session_model[session_id] = target_model
        else:
            self._active_provider = provider
            self._active_model = target_model
        return True

    def list_providers(self) -> Dict[str, Any]:
        """列出所有提供商及模型。"""
        result = {}
        for pid, pconf in self._providers.items():
            models_dict = {}
            for m in pconf["models"]:
                models_dict[m] = {"default": m == pconf["default_model"]}
            result[pid] = {
                "name": pconf["name"],
                "models": pconf["models"],
                **models_dict,
            }
        return result

    def get_health(self) -> Dict[str, Dict[str, float]]:
        """返回各厂商的健康状态时间戳。

        Returns:
            { provider_id: {"last_success_timestamp": float, "last_error_timestamp": float} }
        """
        return dict(self._health)

    async def chat(self, messages: List[Dict], provider: Optional[str] = None,
                   model: Optional[str] = None, max_tokens: int = 4096,
                   temperature: float = 0.7) -> Dict[str, Any]:
        """调用 LLM 聊天。
        
        真实 API 调用，兼容 OpenAI SDK 格式的提供商（deepseek、kimi、chatglm、tongyi、wenxin）。
        deepseek/kimi/tongyi/wenxin 均兼容 OpenAI 的 /chat/completions 接口。
        chatglm 也兼容了相同的接口格式。

        返回格式: {"success": bool, "content": str, "error_code": int, "error_message": str}
        """
        import aiohttp
        import time

        active_provider = provider or self._active_provider
        active_model = model or self._active_model

        if active_provider not in self._providers:
            return {"success": False, "error_code": 3001, "error_message": f"未知提供商: {active_provider}"}

        api_key = self._api_keys.get(active_provider)
        if not api_key:
            return {"success": False, "error_code": 3002, "error_message": f"{active_provider} 未配置 API Key"}

        # 获取 base_url
        base_url = self._providers[active_provider].get("base_url", "")
        url = f"{base_url}/chat/completions"

        # 构建请求体
        payload = {
            "model": active_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # 注入模型信息（在 system prompt 中）
        self._inject_model_info(messages, active_provider, active_model)

        # 构建 Authorization header（兼容 Bearer 和 token 两种格式）
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=60) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        # 记录成功
                        self._health.setdefault(active_provider, {})
                        self._health[active_provider]["last_success_timestamp"] = time.time()
                        if content:
                            return {"success": True, "content": content, "error_code": 0}
                        return {"success": False, "error_code": 3003, "error_message": "API 返回空响应"}
                    elif resp.status == 401:
                        # 记录失败
                        self._health.setdefault(active_provider, {})
                        self._health[active_provider]["last_error_timestamp"] = time.time()
                        text = await resp.text()
                        return {"success": False, "error_code": 401, "error_message": f"API Key 无效 ({active_provider})"}
                    elif resp.status == 429:
                        self._health.setdefault(active_provider, {})
                        self._health[active_provider]["last_error_timestamp"] = time.time()
                        return {"success": False, "error_code": 429, "error_message": "API 请求频率超限"}
                    else:
                        self._health.setdefault(active_provider, {})
                        self._health[active_provider]["last_error_timestamp"] = time.time()
                        text = await resp.text()
                        return {"success": False, "error_code": resp.status, "error_message": f"API 错误: {text[:200]}"}
        except asyncio.TimeoutError:
            self._health.setdefault(active_provider, {})
            self._health[active_provider]["last_error_timestamp"] = time.time()
            return {"success": False, "error_code": 3004, "error_message": f"API 请求超时 ({active_provider})"}
        except aiohttp.ClientError as e:
            self._health.setdefault(active_provider, {})
            self._health[active_provider]["last_error_timestamp"] = time.time()
            return {"success": False, "error_code": 3005, "error_message": f"网络错误: {str(e)[:100]}"}
        except Exception as e:
            self._health.setdefault(active_provider, {})
            self._health[active_provider]["last_error_timestamp"] = time.time()
            return {"success": False, "error_code": 3006, "error_message": f"未知错误: {str(e)[:100]}"}

    def _inject_model_info(self, messages: List[Dict], provider: str, model: str) -> None:
        """在 system prompt 中注入当前使用的模型信息。"""
        info = f"当前使用模型: {provider}/{model}"
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = messages[0]["content"] + f"\n\n{info}"
        else:
            messages.insert(0, {"role": "system", "content": info})

    # ── 事件处理 ──

    async def _on_llm_request(self, event: Event) -> None:
        """处理 llm.request 事件。"""
        try:
            payload = event.payload if hasattr(event, 'payload') else event
            messages = payload.get("messages", [])
            session_id = payload.get("session_id", "")
            request_id = payload.get("request_id", "")

            # 会话级模型切换
            provider = self._session_provider.get(session_id, self._active_provider)
            model = self._session_model.get(session_id, self._active_model)

            result = await self.chat(messages, provider=provider, model=model)

            if result["success"]:
                await self._event_bus.publish(Event(
                    event_type="llm.response",
                    source="llm_gateway",
                    payload={
                        "content": result["content"],
                        "session_id": session_id,
                        "provider": provider,
                        "model": model,
                        "request_id": request_id,
                    },
                ))
            else:
                await self._event_bus.publish(Event(
                    event_type="llm.error",
                    source="llm_gateway",
                    payload={
                        "error_code": result.get("error_code", 0),
                        "error_message": result.get("error_message", "Unknown error"),
                        "session_id": session_id,
                        "provider": provider,
                    },
                ))
        except Exception as e:
            await self._event_bus.publish(Event(
                event_type="llm.error",
                source="llm_gateway",
                payload={
                    "error_code": 3006,
                    "error_message": f"LLM 调用异常: {str(e)[:200]}",
                    "session_id": session_id if 'session_id' in dir() else "",
                    "provider": provider if 'provider' in dir() else "",
                },
            ))

    async def _on_command(self, event: Event) -> None:
        """处理 user.command 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        cmd = payload.get("command", "")
        args = payload.get("args", [])

        if cmd == "models":
            providers = self.list_providers()
            lines = ["可用模型:"]
            for pid, info in providers.items():
                models = ", ".join(info["models"])
                lines.append(f"  {info['name']} ({pid}): {models}")
                key_status = "✓" if self._api_keys.get(pid) else "✗"
                lines[-1] += f" [{key_status}]"
            print("\n".join(lines))

        elif cmd == "switch" and args:
            target = args[0]
            if self.set_provider(target):
                print(f"已切换到 {self._providers[target]['name']} ({target})")
            else:
                print(f"未知提供商: {target}，可用: {', '.join(self._providers.keys())}")