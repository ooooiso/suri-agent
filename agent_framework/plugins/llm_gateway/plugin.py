"""llm_gateway 插件 — 国内 5 家大模型路由（迭代 1 简化版）。"""

import asyncio
import json
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


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
            "models": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat"],
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
        # 会话级模型隔离：session_id -> provider/model
        self._session_provider: Dict[str, str] = {}
        self._session_model: Dict[str, str] = {}

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
                # 从配置中读取 API Key（向导保存的）
                if "api_key" in provider_cfg:
                    self._api_keys[name] = provider_cfg["api_key"]
        
        # 默认使用第一个模型
        if self.PROVIDERS[self._active_provider]["models"]:
            self._active_model = self.PROVIDERS[self._active_provider]["models"][0]
        
        # 尝试从 config.json 加载（如果插件配置中没有）
        self._load_from_config_file()

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
        self._event_bus.subscribe("llm.request", self._on_llm_request)
        self._event_bus.subscribe("user.command", self._on_command)
        self._event_bus.subscribe("system.config_changed", self._on_config_changed)

    def set_provider(self, provider: str, model: Optional[str] = None,
                       session_id: Optional[str] = None) -> bool:
        """切换提供商。若指定 session_id，则仅切换该会话的模型。"""
        if provider not in self.PROVIDERS:
            return False
        mdl = model if (model and model in self.PROVIDERS[provider]["models"]) \
              else self.PROVIDERS[provider]["models"][0]
        if session_id:
            self._session_provider[session_id] = provider
            self._session_model[session_id] = mdl
        else:
            self._active_provider = provider
            self._active_model = mdl
        return True

    def list_providers(self) -> Dict[str, List[str]]:
        """列出所有提供商和模型。"""
        return {k: v["models"] for k, v in self.PROVIDERS.items()}

    async def chat(self, messages: List[Dict[str, str]], 
                   provider: Optional[str] = None,
                   model: Optional[str] = None,
                   session_id: Optional[str] = None) -> Dict[str, Any]:
        """聊天接口。若 session_id 有会话级覆盖，优先使用。"""
        if session_id and session_id in self._session_provider:
            prov = provider or self._session_provider[session_id]
            mdl = model or self._session_model[session_id]
        else:
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
            # 区分 HTTP 错误码，给出可操作建议
            error_msg = str(e)
            error_code = 3003
            if "HTTP Error 401" in error_msg or "Unauthorized" in error_msg:
                error_code = 401
                error_msg = (
                    f"API Key 无效或已过期（厂商：{prov}）。"
                    f"提示: /setkey {prov} <key> 快速修改 或 /switch <厂商> 切换。"
                )
            elif "HTTP Error 429" in error_msg or "Too Many Requests" in error_msg:
                error_code = 429
                error_msg = (
                    f"请求过于频繁（厂商：{prov}）。"
                    f"提示: 稍后重试 或 /switch <厂商> 切换。"
                )
            elif "HTTP Error 503" in error_msg or "Service Unavailable" in error_msg:
                error_code = 503
                error_msg = (
                    f"模型服务暂不可用（厂商：{prov}）。"
                    f"提示: /switch <厂商> 切换 或稍后重试。"
                )
            elif "HTTP Error" in error_msg:
                # 尝试提取状态码
                import re
                m = re.search(r"HTTP Error (\d+)", error_msg)
                if m:
                    error_code = int(m.group(1))
            return {
                "error_code": error_code,
                "error_message": error_msg,
                "provider": prov,
                "success": False,
            }

    async def _send_request(self, provider: str, model: str, 
                            messages: List[Dict[str, str]], 
                            api_key: str) -> str:
        """发送 HTTP 请求。
        
        统一异常处理：
        - HTTP 401/403 → API Key 无效
        - HTTP 429 → 限流
        - HTTP 500/502/503 → 服务端错误
        - 网络超时 → 连接失败
        - 编码错误 → 请求格式错误
        """
        prov_cfg = self.PROVIDERS[provider]
        base_url = prov_cfg["base_url"]
        path = prov_cfg["chat_path"]
        
        # 前置检查：API Key 必须是可编码字符
        try:
            api_key.encode("ascii")
        except UnicodeEncodeError:
            raise ValueError(f"API Key for {provider} contains invalid characters")
        
        # OpenAI 兼容格式（deepseek、chatglm、kimi、tongyi）
        if provider in ("deepseek", "chatglm", "kimi", "tongyi"):
            url = f"{base_url}{path}"
            payload = json.dumps({
                "model": model,
                "messages": messages,
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            context = ssl.create_default_context()
            
            loop = asyncio.get_event_loop()
            
            # 重试逻辑：最多重试 2 次（仅对 429/503 重试）
            max_retries = 2
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    response = await loop.run_in_executor(
                        None, lambda: urllib.request.urlopen(req, context=context, timeout=60)
                    )
                    data = json.loads(response.read().decode("utf-8"))
                    
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"]
                    # 部分厂商返回格式不同
                    if "response" in data:
                        return data["response"]
                    return str(data)
                    
                except urllib.error.HTTPError as e:
                    body = e.read().decode("utf-8", errors="replace")
                    if e.code in (429, 502, 503) and attempt < max_retries - 1:
                        # 可重试错误，等待后重试
                        wait = 2 ** attempt  # 1s, 2s
                        await asyncio.sleep(wait)
                        last_error = e
                        continue
                    # 不可重试错误，直接抛出
                    if e.code == 401:
                        raise PermissionError(
                            f"HTTP Error 401: API Key 无效或已过期（厂商：{provider}）。"
                            f"提示: /setkey {provider} <key> 修改Key 或 /switch <厂商> 切换。"
                        )
                    elif e.code == 403:
                        raise PermissionError(
                            f"HTTP Error 403: API Key 无权限（厂商：{provider}）。"
                            f"提示: /setkey {provider} <key> 修改Key 或 /switch <厂商> 切换。"
                        )
                    elif e.code == 429:
                        raise ConnectionError(
                            f"HTTP Error 429: 请求过于频繁（厂商：{provider}）。"
                            f"提示: 稍后重试 或 /switch <厂商> 切换。"
                        )
                    elif e.code in (500, 502, 503):
                        raise ConnectionError(
                            f"HTTP Error {e.code}: 模型服务暂不可用（厂商：{provider}）。"
                            f"提示: /switch <厂商> 切换 或稍后重试。"
                        )
                    else:
                        raise RuntimeError(
                            f"HTTP Error {e.code}: {body[:200]}（厂商：{provider}）"
                        )
                        
                except urllib.error.URLError as e:
                    raise ConnectionError(
                        f"网络连接失败: {e.reason}（厂商：{provider}）。"
                        f"提示: 检查网络连接或代理设置。"
                    )
            
            # 所有重试都失败
            raise ConnectionError(
                f"请求失败（厂商：{provider}），已重试 {max_retries} 次。"
                f"提示: /switch <厂商> 切换 或稍后重试。"
            )
        
        # 文心一言（需要 access_token，流程更复杂）
        else:
            return f"[Provider {provider} not fully implemented in iteration 1]"

    async def _on_llm_request(self, event: Event) -> None:
        """处理 llm.request 事件。在 system prompt 中注入当前模型信息。"""
        payload = event.payload
        messages = list(payload.get("messages", []))  # 复制，避免修改原始列表
        provider = payload.get("provider")
        model = payload.get("model")
        request_id = payload.get("request_id")
        session_id = payload.get("session_id", request_id)
        
        # 确定当前实际使用的模型
        if session_id and session_id in self._session_provider:
            actual_prov = self._session_provider[session_id]
            actual_mdl = self._session_model[session_id]
        else:
            actual_prov = self._active_provider
            actual_mdl = self._active_model
        
        # 在 system prompt 中注入当前模型信息和切换命令说明
        self._inject_model_info(messages, actual_prov, actual_mdl)
        
        result = await self.chat(messages, provider, model, session_id)
        
        if result.get("success"):
            await self._event_bus.publish(Event(
                event_type="llm.response",
                source="llm_gateway",
                target=event.source,
                payload={
                    "request_id": request_id,
                    "session_id": session_id,
                    "model_id": f"{actual_prov}/{actual_mdl}",
                    "content": result.get("content", ""),
                    "usage": {"input": 0, "output": 0, "total": 0},  # 迭代1简化
                    "finish_reason": "stop",
                },
                priority=Priority.NORMAL,
            ))
        else:
            await self._event_bus.publish(Event(
                event_type="llm.error",
                source="llm_gateway",
                target=event.source,
                payload={
                    "request_id": request_id,
                    "session_id": session_id,
                    "error_code": result.get("error_code", 3003),
                    "error_type": "model_error",
                    "message": result.get("error_message", "Unknown error"),
                    "provider": result.get("provider", actual_prov),
                    "retryable": result.get("error_code") in (3003,),
                },
                priority=Priority.HIGH,
            ))

    def _inject_model_info(self, messages: List[Dict[str, str]], 
                           provider: str, model: str) -> None:
        """在 system prompt 中注入当前模型信息和切换命令说明。"""
        env_text = (
            f"\n[当前运行环境] 你正在通过 {provider}/{model} 模型为用户服务。"
            f"用户可以通过命令 '/switch <厂商> [模型]' 切换模型，"
            f"例如 '/switch kimi' 或 '/switch deepseek deepseek-v4-flash'。"
        )
        # 找到第一个 system message，在其 content 末尾追加
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = msg["content"].rstrip() + env_text
                return
        # 如果没有 system message，在开头插入一个
        messages.insert(0, {
            "role": "system",
            "content": f"你是 Suri，一个 AI 助手。{env_text}"
        })

    def _load_from_config_file(self) -> None:
        """从 config.json 加载 API Key 和模型配置。"""
        try:
            config_path = Path.home() / ".suri" / "config.json"
            if not config_path.exists():
                return
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            llm_cfg = cfg.get("llm_gateway", {})
            if "default_provider" in llm_cfg:
                self._active_provider = llm_cfg["default_provider"]
            providers = llm_cfg.get("providers", {})
            for name, provider_cfg in providers.items():
                if name in self.PROVIDERS:
                    if "models" in provider_cfg:
                        self.PROVIDERS[name]["models"] = provider_cfg["models"]
                    if "base_url" in provider_cfg:
                        self.PROVIDERS[name]["base_url"] = provider_cfg["base_url"]
                    if "api_key" in provider_cfg:
                        self._api_keys[name] = provider_cfg["api_key"]
                    if "default_model" in provider_cfg:
                        if self._active_provider == name:
                            self._active_model = provider_cfg["default_model"]
        except Exception:
            pass

    async def _on_config_changed(self, event: Event) -> None:
        """配置变更时重新加载。"""
        # 如果是 /reconfig 触发，先清空内存中的 key，再重新加载
        if event.payload.get("reason") == "reconfig":
            self._api_keys.clear()
            self._active_provider = "deepseek"
            self._active_model = "deepseek-chat"
            self._session_provider.clear()
            self._session_model.clear()
        self._load_from_config_file()

    async def _on_command(self, event: Event) -> None:
        """处理命令。"""
        cmd = event.payload.get("command", "")
        args = event.payload.get("args", [])
        session_id = event.payload.get("session_id")
        
        if cmd in ("models",):
            providers = self.list_providers()
            print("Available providers:")
            for name, models in providers.items():
                marker = " ← active" if name == self._active_provider else ""
                print(f"  {name}: {', '.join(models)}{marker}")
        elif cmd in ("switch",) and args:
            provider = args[0]
            model = args[1] if len(args) > 1 else None
            if self.set_provider(provider, model, session_id):
                print(f"✅ 已切换到 {provider}/{self._active_model}")
            else:
                print(f"❌ 未知厂商: {provider}")
