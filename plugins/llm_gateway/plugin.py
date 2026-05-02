"""llm_gateway 插件 — 国内 5 家大模型路由（迭代 1 简化版）。"""

import asyncio
import json
import os
import ssl
import urllib.request
from typing import Any, Dict, List, Optional

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority


class LLMGatewayPlugin(PluginInterface):
    """大模型网关插件（迭代 1 简化版）。
    
    职责：
    - 支持 5 家国内模型提供商
    - 版本切换
    - 统一的 llm.call 事件处理
    
    实际实现需要 API Key。迭代 1 提供完整接口，实际调用需要配置 Key。
    """

    PROVIDERS = {
        "wenxin": {
            "models": ["ernie-4.0", "ernie-3.5"],
            "base_url": "https://aip.baidubce.com",
            "chat_path": "/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        },
        "tongyi": {
            "models": ["qwen-max", "qwen-plus"],
            "base_url": "https://dashscope.aliyuncs.com",
            "chat_path": "/api/v1/services/aigc/text-generation/generation",
        },
        "chatglm": {
            "models": ["glm-4", "glm-3-turbo"],
            "base_url": "https://open.bigmodel.cn",
            "chat_path": "/api/paas/v4/chat/completions",
        },
        "kimi": {
            "models": ["moonshot-v1-8k", "moonshot-v1-32k"],
            "base_url": "https://api.moonshot.cn",
            "chat_path": "/v1/chat/completions",
        },
        "deepseek": {
            "models": ["deepseek-chat", "deepseek-coder"],
            "base_url": "https://api.deepseek.com",
            "chat_path": "/chat/completions",
        },
    }

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._active_provider = "deepseek"
        self._active_model = "deepseek-chat"
        self._api_keys: Dict[str, str] = {}

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config
        self._active_provider = config.get("default_provider", "deepseek")
        providers = config.get("providers", {})
        
        for name in self.PROVIDERS:
            # 从环境变量读取 API Key
            env_key = f"SURI_{name.upper()}_API_KEY"
            self._api_keys[name] = os.environ.get(env_key, "")
            
            if name in providers:
                provider_cfg = providers[name]
                if "models" in provider_cfg:
                    self.PROVIDERS[name]["models"] = provider_cfg["models"]
                if "base_url" in provider_cfg:
                    self.PROVIDERS[name]["base_url"] = provider_cfg["base_url"]
        
        # 默认使用第一个模型
        if self.PROVIDERS[self._active_provider]["models"]:
            self._active_model = self.PROVIDERS[self._active_provider]["models"][0]

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
        self._event_bus.subscribe("llm.call", self._on_llm_call)
        self._event_bus.subscribe("user.command", self._on_command)

    def set_provider(self, provider: str, model: Optional[str] = None) -> bool:
        """切换提供商。"""
        if provider not in self.PROVIDERS:
            return False
        self._active_provider = provider
        if model and model in self.PROVIDERS[provider]["models"]:
            self._active_model = model
        else:
            self._active_model = self.PROVIDERS[provider]["models"][0]
        return True

    def list_providers(self) -> Dict[str, List[str]]:
        """列出所有提供商和模型。"""
        return {k: v["models"] for k, v in self.PROVIDERS.items()}

    async def chat(self, messages: List[Dict[str, str]], 
                   provider: Optional[str] = None,
                   model: Optional[str] = None) -> Dict[str, Any]:
        """聊天接口。"""
        prov = provider or self._active_provider
        mdl = model or self._active_model
        
        if prov not in self.PROVIDERS:
            return {
                "error_code": 3001,
                "error_message": f"Unknown provider: {prov}",
                "success": False,
            }
        
        api_key = self._api_keys.get(prov, "")
        if not api_key:
            return {
                "error_code": 3002,
                "error_message": f"No API key for {prov}. Set SURI_{prov.upper()}_API_KEY",
                "success": False,
            }
        
        # 迭代 1：构建请求并发送（简化实现）
        try:
            result = await self._send_request(prov, mdl, messages, api_key)
            return {"success": True, "content": result}
        except Exception as e:
            return {
                "error_code": 3003,
                "error_message": str(e),
                "success": False,
            }

    async def _send_request(self, provider: str, model: str, 
                            messages: List[Dict[str, str]], 
                            api_key: str) -> str:
        """发送 HTTP 请求。"""
        prov_cfg = self.PROVIDERS[provider]
        base_url = prov_cfg["base_url"]
        path = prov_cfg["chat_path"]
        
        # OpenAI 兼容格式（deepseek、chatglm、kimi、tongyi）
        if provider in ("deepseek", "chatglm", "kimi", "tongyi"):
            url = f"{base_url}{path}"
            payload = json.dumps({
                "model": model,
                "messages": messages,
            }).encode()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            context = ssl.create_default_context()
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(req, context=context, timeout=60)
            )
            data = json.loads(response.read().decode("utf-8"))
            
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            return str(data)
        
        # 文心一言（需要 access_token，流程更复杂）
        else:
            return f"[Provider {provider} not fully implemented in iteration 1]"

    async def _on_llm_call(self, event: Event) -> None:
        """处理 llm.call 事件。"""
        payload = event.payload
        messages = payload.get("messages", [])
        provider = payload.get("provider")
        model = payload.get("model")
        
        result = await self.chat(messages, provider, model)
        
        await self._event_bus.publish(Event(
            event_type="llm.result",
            source="llm_gateway",
            target=event.source,
            payload={
                "request_id": payload.get("request_id"),
                **result,
            },
            priority=Priority.NORMAL,
        ))

    async def _on_command(self, event: Event) -> None:
        """处理命令。"""
        cmd = event.payload.get("command", "")
        args = event.payload.get("args", [])
        
        if cmd == "llm.list":
            providers = self.list_providers()
            print("Available providers:")
            for name, models in providers.items():
                marker = " ← active" if name == self._active_provider else ""
                print(f"  {name}: {', '.join(models)}{marker}")
        elif cmd == "llm.switch" and args:
            provider = args[0]
            model = args[1] if len(args) > 1 else None
            if self.set_provider(provider, model):
                print(f"Switched to {provider}/{self._active_model}")
            else:
                print(f"Unknown provider: {provider}")
