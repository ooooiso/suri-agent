"""
模型管理器

关联文档: suri-agent/model/model.md, suri-agent/model/pool.yaml

职责：
- 管理模型配置（名称、API Key、端点、能力标签、成本等级）
- 调用模型 API 生成回复
- 首次启动引导配置（两级菜单：品牌 → 型号）
- 模型自动降级切换
- 智能模型路由（按任务内容自动选择最优模型）

调用层特性：
- httpx 异步客户端（连接池复用）
- tenacity 自动重试（指数退避）
- SSE 流式输出支持
- 结构化错误信息

文档同步提醒：修改本文件后，请检查并同步更新关联文档。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, AsyncIterator, Any
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

# ========== 品牌菜单定义（用户只选品牌，系统自动选型号 + fallback） ==========
MODEL_MENU = {
    "1": {
        "brand": "智谱 AI (GLM)",
        "provider": "glm",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "primary": ("GLM-4", "glm-4"),
        "fallbacks": [
            ("GLM-4V", "glm-4v"),
            ("GLM-4.7-Flash", "glm-4.7-flash"),
        ],
    },
    "2": {
        "brand": "OpenAI",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "primary": ("GPT-4o", "gpt-4o"),
        "fallbacks": [
            ("GPT-4o Mini", "gpt-4o-mini"),
        ],
    },
    "3": {
        "brand": "Moonshot (Kimi)",
        "provider": "moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "primary": ("Moonshot v1-8k", "moonshot-v1-8k"),
        "fallbacks": [
            ("Moonshot v1-32k", "moonshot-v1-32k"),
        ],
    },
    "4": {
        "brand": "DeepSeek",
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "primary": ("DeepSeek Chat", "deepseek-chat"),
        "fallbacks": [
            ("DeepSeek Coder", "deepseek-coder"),
        ],
    },
    "5": {
        "brand": "Anthropic (Claude)",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "primary": ("Claude 3.5 Sonnet", "claude-3-5-sonnet"),
        "fallbacks": [
            ("Claude 3 Haiku", "claude-3-haiku"),
        ],
    },
}


# 预置模型的默认能力标签（用户可覆盖）
def _load_presets(presets_path: Optional[Path] = None) -> dict:
    """从 presets.json 加载模型预置配置"""
    if presets_path is None:
        presets_path = Path(__file__).parent / "presets.json"
    if presets_path.exists():
        try:
            with open(presets_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ModelManager] 加载 presets.json 失败: {e}")
    return {}


# 加载预置配置（单一来源：suri-agent/model/presets.json）
_PRESETS = _load_presets()
DEFAULT_CAPABILITIES = _PRESETS.get("capabilities", {})
DEFAULT_MODEL_TYPES = _PRESETS.get("model_types", {})
MODEL_TYPE_DESCRIPTIONS = _PRESETS.get("model_type_descriptions", {})
DEFAULT_COST_TIER = _PRESETS.get("cost_tiers", {})
COST_TIER_ORDER = _PRESETS.get("cost_tier_order", {})


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
    capabilities: List[str] = None
    cost_tier: str = "standard"
    model_type: str = "text_chat"

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = DEFAULT_CAPABILITIES.get(self.model_id, ["chat"])
        if self.cost_tier == "standard" and self.model_id in DEFAULT_COST_TIER:
            self.cost_tier = DEFAULT_COST_TIER[self.model_id]
        if self.model_type == "text_chat" and self.model_id in DEFAULT_MODEL_TYPES:
            self.model_type = DEFAULT_MODEL_TYPES[self.model_id]


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

    def _test_api_key(self, brand_info: dict, api_key: str) -> Optional[tuple]:
        """
        测试 API Key 并自动选择可用型号
        
        流程：
        1. 先测试 primary 型号
        2. 如果服务端报错（429/403/503），依次测试 fallbacks
        3. 如果是 401（Key 无效），直接返回 None
        
        Returns:
            (name, model_id) 或 None（Key 完全无效）
        """
        import httpx
        
        base_url = brand_info["base_url"]
        provider = brand_info["provider"]
        
        # 构建测试候选列表：primary + fallbacks
        candidates = [brand_info["primary"]] + brand_info.get("fallbacks", [])
        
        for name, model_id in candidates:
            url = f"{base_url}/chat/completions"
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            }
            
            # Anthropic 特殊处理
            if provider == "anthropic":
                url = f"{base_url}/messages"
                payload = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                }
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }
            else:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
            
            try:
                resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
                
                # 401 = Key 无效，不再尝试
                if resp.status_code == 401:
                    print(f"  ❌ {name}: API Key 无效 (401)")
                    return None
                
                # 200 系列 = 成功
                if resp.status_code in (200, 201):
                    print(f"  ✅ {name}: 可用")
                    return name, model_id
                
                # 429/403/503 = 服务端限额/不可用，尝试 fallback
                if resp.status_code in (429, 403, 503, 500):
                    err_text = resp.text[:100]
                    print(f"  ⚠️ {name}: 不可用 (HTTP {resp.status_code})，尝试备选...")
                    continue
                
                # 其他错误也尝试 fallback
                print(f"  ⚠️ {name}: 异常 (HTTP {resp.status_code})，尝试备选...")
                continue
                
            except httpx.TimeoutException:
                print(f"  ⚠️ {name}: 超时，尝试备选...")
                continue
            except httpx.ConnectError:
                print(f"  ⚠️ {name}: 连接失败，尝试备选...")
                continue
            except Exception as e:
                print(f"  ⚠️ {name}: 错误 ({e})，尝试备选...")
                continue
        
        # 全部失败
        return None
    
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
            primary_name = info["primary"][0]
            print(f"  {key}) {info['brand']}（首选: {primary_name}）")
        print(f"  0) 自定义")
        print("")

        choice = input("输入选项 [0-5]: ").strip()
        if choice == "0":
            return self._setup_custom()

        brand_info = MODEL_MENU.get(choice)
        if not brand_info:
            print("\n❌ 无效选项")
            return False

        print(f"\n请输入您的 {brand_info['brand']} API Key：")
        api_key = input("API Key: ").strip()
        if not api_key:
            print("\n❌ API Key 不能为空")
            return False

        # 自动测试并选择可用型号
        print("\n正在验证 API Key 并测试可用型号...")
        result = self._test_api_key(brand_info, api_key)
        
        if result is None:
            print("\n❌ API Key 无效或该品牌下所有型号均不可用。")
            print("   请检查 Key 是否正确，或更换品牌重试。")
            print("")
            return False
        
        name, model_id = result
        provider = brand_info["provider"]
        base_url = brand_info["base_url"]

        self._persist_config(name, model_id, api_key, base_url, provider)
        print("\n✅ 模型配置完成！")
        print(f"   品牌: {brand_info['brand']}")
        print(f"   实际型号: {name} ({model_id})")
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
                        base_url: str, provider: str,
                        capabilities: Optional[List[str]] = None,
                        cost_tier: Optional[str] = None) -> None:
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
        self.add_model(name, model_id, api_key, base_url, provider,
                       is_default=True, priority=0,
                       capabilities=capabilities, cost_tier=cost_tier)

    def add_model(self, name: str, model_id: str, api_key: str,
                  base_url: str, provider: str, is_default: bool = False,
                  priority: int = 0,
                  capabilities: Optional[List[str]] = None,
                  cost_tier: Optional[str] = None,
                  model_type: Optional[str] = None) -> None:
        if is_default:
            for m in self._models.values():
                m.is_default = False
        self._models[model_id] = ModelConfig(
            name=name, model_id=model_id, api_key=api_key,
            base_url=base_url, provider=provider,
            is_default=is_default, priority=priority,
            capabilities=capabilities,
            cost_tier=cost_tier or "standard",
            model_type=model_type or "text_chat",
        )
        self._save()
    
    def delete_model(self, model_id: str) -> bool:
        """删除指定模型"""
        if model_id not in self._models:
            return False
        
        was_default = self._models[model_id].is_default
        del self._models[model_id]
        
        # 如果删除的是默认模型，且还有其他模型，将第一个设为默认
        if was_default and self._models:
            first = list(self._models.values())[0]
            first.is_default = True
        
        self._save()
        return True

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

    # ========== 智能模型路由 ==========

    def select_model_for_task(self, task_content: str) -> Optional[ModelConfig]:
        """
        根据任务内容智能选择最合适的模型

        策略：
        1. 分析任务所需能力（coding / vision / reasoning / long_context / fast / chat）
        2. 筛选具备所需能力的已配置模型
        3. 按成本等级（free → cheap → standard → premium）排序，节省开支
        4. 无完全匹配时，放宽到部分匹配，最后 fallback 到默认模型
        """
        if not self._models:
            return None

        required_caps = self._infer_required_capabilities(task_content)
        if not required_caps:
            required_caps = {"chat"}

        candidates = list(self._models.values())

        # 阶段 1：完全匹配（具备所有所需能力）
        full_match = [
            m for m in candidates
            if required_caps.issubset(set(m.capabilities or []))
        ]
        if full_match:
            return self._pick_cheapest(full_match)

        # 阶段 2：部分匹配（具备至少一个所需能力）
        partial_match = [
            m for m in candidates
            if bool(required_caps & set(m.capabilities or []))
        ]
        if partial_match:
            return self._pick_cheapest(partial_match)

        # 阶段 3：fallback 到默认模型，或第一个可用模型
        return self.get_default_model()

    @staticmethod
    def _infer_required_capabilities(task_content: str) -> set:
        """从任务内容推断所需能力"""
        text = task_content.lower()
        caps = set()

        # 编程 / 代码
        coding_kw = [
            "代码", "程序", "脚本", "编程", "debug", "bug", "修复",
            "python", "javascript", "java", "cpp", "c++", "rust", "go",
            "函数", "类", "接口", "api", "重构", "编译", "运行错误",
            "code", "program", "script", "function", "class",
        ]
        if any(kw in text for kw in coding_kw):
            caps.add("coding")

        # 视觉 / 图像
        vision_kw = [
            "图", "图片", "图像", "视觉", "看图", "识别", "照片",
            "截图", "logo", "设计稿", "ui", "界面", "配色",
            "image", "picture", "photo", "screenshot", "vision",
            "describe the image", "what is in this image",
        ]
        if any(kw in text for kw in vision_kw):
            caps.add("vision")

        # 深度推理 / 复杂分析
        reasoning_kw = [
            "分析", "推理", "深度", "复杂", "策略", "优化", "架构设计",
            "评估", "对比", "总结", "报告", "研究", "论文",
            "analyze", "reasoning", "deep", "complex", "strategy",
            "architecture", "evaluate", "compare", "research",
        ]
        if any(kw in text for kw in reasoning_kw):
            caps.add("reasoning")

        # 长上下文（大文档处理）
        long_ctx_kw = [
            "长文", "文档", "全书", "批量", "大量", "总结全文",
            "10000", "一万", "几万", "整本书", "pdf", "论文全文",
            "long document", "full text", "entire book", "bulk",
        ]
        if any(kw in text for kw in long_ctx_kw):
            caps.add("long_context")

        # 快速响应（简单问候、短查询）
        fast_kw = [
            "你好", "在吗", "hi", "hello", "hey", "谢谢", "再见",
            "简单", "快速", "一句话", "简短",
        ]
        is_fast = any(kw in text for kw in fast_kw)
        has_complex_marker = bool(caps - {"chat"})

        # 如果没有任何特殊标记，或明确是快速查询，加入 fast
        if is_fast and not has_complex_marker:
            caps.add("fast")

        # 所有任务至少都需要 chat 能力
        caps.add("chat")
        return caps

    @staticmethod
    def _pick_cheapest(candidates: List[ModelConfig]) -> ModelConfig:
        """从候选模型中选择成本最低的"""
        def tier_score(m: ModelConfig) -> int:
            return COST_TIER_ORDER.get(m.cost_tier, 99)
        return min(candidates, key=lambda m: (tier_score(m), m.priority))

    # ========== 模型调用（自动降级 + 重试） ==========

    async def chat(self, messages: List[Dict[str, str]],
                   model_id: Optional[str] = None) -> Optional[str]:
        """
        调用模型生成回复（带自动降级和重试）

        1. 先尝试指定/默认模型（3 次重试）
        2. 失败时按优先级自动尝试其他已配置模型
        """
        result = await self.chat_with_usage(messages, model_id)
        return result.get('content') if result else None
    
    async def chat_with_usage(self, messages: List[Dict[str, str]],
                              model_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        调用模型生成回复，返回包含内容和 Token 使用量的字典
        
        Returns:
            {
                'content': str,      # 模型回复内容
                'model_used': str,   # 实际使用的模型 ID
                'prompt_tokens': int,
                'completion_tokens': int,
                'total_tokens': int,
            }
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
            result = await self._call_single_with_usage(model, messages)
            if result and result.get('content') is not None:
                result['model_used'] = model.model_id
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
        result = await self._call_single_with_usage(model, messages)
        return result.get('content') if result else None
    
    async def _call_single_with_usage(self, model: ModelConfig,
                                      messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """调用单个模型，返回包含内容和 usage 的字典"""
        if model.provider == "anthropic":
            return await self._call_anthropic_with_usage(model, messages)
        return await self._call_openai_compatible_with_usage(model, messages)

    # ---------- OpenAI 兼容格式 ----------

    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _call_openai_compatible(self, model: ModelConfig,
                                       messages: List[Dict[str, str]]) -> Optional[str]:
        result = await self._call_openai_compatible_with_usage(model, messages)
        return result.get('content') if result else None
    
    async def _call_openai_compatible_with_usage(self, model: ModelConfig,
                                                  messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
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
            content = None
            if choices and isinstance(choices, list):
                content = choices[0].get("message", {}).get("content")
            
            usage = data.get("usage", {})
            return {
                'content': content,
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0),
            }
        except httpx.HTTPStatusError as e:
            return None
        except Exception as e:
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
            pass

    # ---------- Anthropic 格式 ----------

    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _call_anthropic(self, model: ModelConfig,
                               messages: List[Dict[str, str]]) -> Optional[str]:
        result = await self._call_anthropic_with_usage(model, messages)
        return result.get('content') if result else None
    
    async def _call_anthropic_with_usage(self, model: ModelConfig,
                                          messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
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
            content_blocks = data.get("content", [{}])
            content = None
            if content_blocks and isinstance(content_blocks, list):
                content = content_blocks[0].get("text")
            
            usage = data.get("usage", {})
            # Anthropic usage 字段: input_tokens, output_tokens
            prompt_tokens = usage.get('input_tokens', 0)
            completion_tokens = usage.get('output_tokens', 0)
            
            return {
                'content': content,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': prompt_tokens + completion_tokens,
            }
        except httpx.HTTPStatusError as e:
            return None
        except Exception as e:
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
            pass
