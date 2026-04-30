"""
模型管理器

职责：
- 管理模型配置（名称、API Key、端点）
- 调用模型 API 生成回复
- 首次启动引导配置（两级菜单：品牌 → 型号）
- 模型自动降级切换

模型切换规则：
- 默认模型调用失败时，自动按优先级尝试其他已配置模型
- 用户可通过 /model 命令管理模型池和切换规则
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


# ========== 两级模型菜单定义 ==========
MODEL_MENU = {
    "1": {
        "brand": "智谱 AI (GLM)",
        "provider": "glm",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": {
            "1": ("GLM-4", "glm-4"),
            "2": ("GLM-4V", "glm-4v"),
            "3": ("GLM-4-Flash", "glm-4-flash"),
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
    name: str           # 模型显示名称
    model_id: str       # 模型标识（如 gpt-4o、claude-3-5-sonnet）
    api_key: str        # API Key
    base_url: str       # API 端点
    provider: str       # 提供商（openai、anthropic、moonshot 等）
    is_default: bool = False
    priority: int = 0   # 优先级，数字越小优先级越高（用于自动降级）


class ModelManager:
    """模型管理器"""
    
    CONFIG_FILE = "model_config.json"
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_path = project_root / self.CONFIG_FILE
        self._models: Dict[str, ModelConfig] = {}
        self._load()
    
    def _load(self) -> None:
        """加载模型配置"""
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                for key, val in data.items():
                    self._models[key] = ModelConfig(**val)
            except Exception as e:
                print(f"[ModelManager] 加载配置失败: {e}")
    
    def _save(self) -> None:
        """保存模型配置"""
        data = {k: asdict(v) for k, v in self._models.items()}
        self.config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def is_first_run(self) -> bool:
        """检查是否首次运行（无模型配置）"""
        return len(self._models) == 0
    
    def setup_wizard(self) -> bool:
        """
        首次启动引导配置（两级菜单：品牌 → 型号）
        返回是否配置成功
        """
        if not sys.stdin.isatty():
            print("[ModelManager] 非交互环境，跳过模型配置引导")
            print("[ModelManager] 请手动创建 model_config.json 或使用 /model add 命令")
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
        
        # 自定义品牌
        if brand_choice == "6":
            return self._setup_custom()
        
        brand_info = MODEL_MENU.get(brand_choice)
        if not brand_info:
            print("\n❌ 无效选项")
            return False
        
        # 第二级：选择型号
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
        provider_name = brand_info["provider"]
        base_url = brand_info["base_url"]
        
        print(f"\n请输入您的 {name} API Key：")
        api_key = input("API Key: ").strip()
        
        if not api_key:
            print("\n❌ API Key 不能为空")
            return False
        
        self._persist_config(name, model_id, api_key, base_url, provider_name)
        
        print("\n✅ 模型配置完成！")
        print(f"   模型: {name} ({model_id})")
        print(f"   提供商: {provider_name}")
        print("")
        return True
    
    def _setup_custom(self) -> bool:
        """自定义模型配置"""
        print("")
        print("自定义模型配置：")
        name = input("显示名称: ").strip()
        model_id = input("模型 ID: ").strip()
        base_url = input("API 端点: ").strip()
        provider_name = input("提供商名称: ").strip() or "custom"
        api_key = input("API Key: ").strip()
        
        if not all([name, model_id, base_url, api_key]):
            print("\n❌ 所有字段必填")
            return False
        
        self._persist_config(name, model_id, api_key, base_url, provider_name)
        print("\n✅ 自定义模型配置完成！")
        return True
    
    def _persist_config(self, name: str, model_id: str, api_key: str,
                        base_url: str, provider: str) -> None:
        """持久化模型配置到 .env 和 model_config.json"""
        # 保存到 .env
        env_path = self.project_root / ".env"
        env_lines = []
        if env_path.exists():
            env_lines = env_path.read_text(encoding="utf-8").splitlines()
        
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
        
        # 添加到模型池（优先级设为 0，默认模型）
        self.add_model(name, model_id, api_key, base_url, provider, is_default=True, priority=0)
    
    def add_model(self, name: str, model_id: str, api_key: str,
                  base_url: str, provider: str, is_default: bool = False,
                  priority: int = 0) -> None:
        """添加模型"""
        if is_default:
            for m in self._models.values():
                m.is_default = False
        
        self._models[model_id] = ModelConfig(
            name=name,
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            provider=provider,
            is_default=is_default,
            priority=priority,
        )
        self._save()
    
    def list_models(self) -> List[ModelConfig]:
        """列出所有模型"""
        return list(self._models.values())
    
    def get_default_model(self) -> Optional[ModelConfig]:
        """获取默认模型"""
        for m in self._models.values():
            if m.is_default:
                return m
        if self._models:
            return list(self._models.values())[0]
        return None
    
    def set_default(self, model_id: str) -> bool:
        """设置默认模型"""
        if model_id not in self._models:
            return False
        for m in self._models.values():
            m.is_default = False
        self._models[model_id].is_default = True
        self._save()
        return True
    
    # ========== 模型调用与自动降级 ==========
    
    def chat(self, messages: List[Dict[str, str]], 
             model_id: Optional[str] = None) -> Optional[str]:
        """
        调用模型生成回复（带自动降级）
        
        1. 先尝试指定/默认模型
        2. 失败时按优先级自动尝试其他已配置模型
        
        Args:
            messages: 消息列表，每项含 role 和 content
            model_id: 指定模型，默认使用默认模型
            
        Returns:
            模型回复文本，或 None（所有模型均不可用）
        """
        # 构建候选列表：优先使用指定/默认模型，其余按 priority 排序
        candidates = []
        primary = None
        
        if model_id and model_id in self._models:
            primary = self._models[model_id]
        else:
            primary = self.get_default_model()
        
        if primary:
            candidates.append(primary)
        
        # 其他模型按优先级排序
        others = sorted(
            [m for m in self._models.values() if m.model_id != (primary.model_id if primary else None)],
            key=lambda m: m.priority
        )
        candidates.extend(others)
        
        if not candidates:
            print("[ModelManager] 错误: 没有可用的模型配置")
            return None
        
        # 依次尝试
        for model in candidates:
            print(f"[ModelManager] 尝试调用 {model.name} ({model.model_id})...")
            result = self._call_single(model, messages)
            if result is not None:
                if model.model_id != (primary.model_id if primary else None):
                    print(f"[ModelManager] ⚠️ 已自动降级到备用模型: {model.name}")
                return result
        
        print("[ModelManager] ❌ 所有模型均不可用，请检查 API Key 和网络连接")
        return None
    
    def _call_single(self, model: ModelConfig,
                     messages: List[Dict[str, str]]) -> Optional[str]:
        """调用单个模型"""
        if model.provider in ["openai", "moonshot", "deepseek", "glm"]:
            return self._call_openai_compatible(model, messages)
        elif model.provider == "anthropic":
            return self._call_anthropic(model, messages)
        else:
            return self._call_openai_compatible(model, messages)
    
    def _call_openai_compatible(self, model: ModelConfig, 
                                 messages: List[Dict[str, str]]) -> Optional[str]:
        """调用 OpenAI 兼容格式的 API"""
        try:
            import urllib.request
            import urllib.error
            
            url = f"{model.base_url}/chat/completions"
            data = json.dumps({
                "model": model.model_id,
                "messages": messages,
                "temperature": 0.7,
            }).encode("utf-8")
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {model.api_key}",
                },
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                choices = result.get("choices", [{}])
                if choices and isinstance(choices, list):
                    return choices[0].get("message", {}).get("content")
                return None
                
        except Exception as e:
            print(f"[ModelManager] {model.name} 调用失败: {e}")
            return None
    
    def _call_anthropic(self, model: ModelConfig,
                        messages: List[Dict[str, str]]) -> Optional[str]:
        """调用 Anthropic API"""
        try:
            import urllib.request
            
            url = f"{model.base_url}/messages"
            data = json.dumps({
                "model": model.model_id,
                "messages": messages,
                "max_tokens": 4096,
            }).encode("utf-8")
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": model.api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result.get("content", [{}])
                if content and isinstance(content, list):
                    return content[0].get("text")
                return None
                
        except Exception as e:
            print(f"[ModelManager] {model.name} 调用失败: {e}")
            return None
