"""
模型管理器

职责：
- 管理模型配置（名称、API Key、端点）
- 调用模型 API 生成回复
- 首次启动引导配置
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ModelConfig:
    """单个模型配置"""
    name: str           # 模型显示名称
    model_id: str       # 模型标识（如 gpt-4o、claude-3-5-sonnet）
    api_key: str        # API Key
    base_url: str       # API 端点
    provider: str       # 提供商（openai、anthropic、moonshot 等）
    is_default: bool = False


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
        首次启动引导配置
        返回是否配置成功
        """
        import sys
        if not sys.stdin.isatty():
            print("[ModelManager] 非交互环境，跳过模型配置引导")
            print("[ModelManager] 请手动创建 model_config.json 或使用 /model add 命令")
            return False
        
        print("")
        print("=" * 50)
        print("  欢迎使用 Suri 智能体平台")
        print("=" * 50)
        print("")
        print("请选择您的 AI 模型提供商：")
        print("")
        print("  1) GLM-4 (智谱 AI)    ← 推荐")
        print("  2) Moonshot (Kimi)")
        print("  3) DeepSeek")
        print("  4) GPT-4o (OpenAI)")
        print("  5) Claude (Anthropic)")
        print("  6) 自定义")
        print("")
        
        presets = {
            "1": ("GLM-4", "glm-4", "glm", "https://open.bigmodel.cn/api/paas/v4"),
            "2": ("Moonshot", "moonshot-v1-8k", "moonshot", "https://api.moonshot.cn/v1"),
            "3": ("DeepSeek", "deepseek-chat", "deepseek", "https://api.deepseek.com/v1"),
            "4": ("GPT-4o", "gpt-4o", "openai", "https://api.openai.com/v1"),
            "5": ("Claude", "claude-3-5-sonnet", "anthropic", "https://api.anthropic.com/v1"),
        }
        
        choice = input("输入选项 [1-6]: ").strip()
        
        if choice in presets:
            name, model_id, provider_name, base_url = presets[choice]
        elif choice == "6":
            name = input("显示名称: ").strip()
            model_id = input("模型 ID: ").strip()
            base_url = input("API 端点: ").strip()
            provider_name = input("提供商名称: ").strip() or "custom"
        else:
            print("\n❌ 无效选项，请重新运行程序")
            return False
        
        print(f"\n请输入您的 {name} API Key:")
        api_key = input("API Key: ").strip()
        
        if not api_key:
            print("\n❌ API Key 不能为空")
            return False
        
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
        env_dict["DEFAULT_MODEL_PROVIDER"] = provider_name
        
        env_content = "\n".join(f"{k}={v}" for k, v in env_dict.items())
        env_path.write_text(env_content + "\n", encoding="utf-8")
        
        # 添加到模型池
        self.add_model(name, model_id, api_key, base_url, provider_name, is_default=True)
        
        print("\n✅ 模型配置完成！")
        print(f"   模型: {name} ({model_id})")
        print(f"   提供商: {provider_name}")
        print("")
        return True
    
    def add_model(self, name: str, model_id: str, api_key: str,
                  base_url: str, provider: str, is_default: bool = False) -> None:
        """添加模型"""
        if is_default:
            # 取消其他模型的默认状态
            for m in self._models.values():
                m.is_default = False
        
        self._models[model_id] = ModelConfig(
            name=name,
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            provider=provider,
            is_default=is_default,
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
        # 如果没有默认模型，返回第一个
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
    
    def chat(self, messages: List[Dict[str, str]], 
             model_id: Optional[str] = None) -> Optional[str]:
        """
        调用模型生成回复
        
        Args:
            messages: 消息列表，每项含 role 和 content
            model_id: 指定模型，默认使用默认模型
            
        Returns:
            模型回复文本，或 None（调用失败）
        """
        model = self._models.get(model_id) if model_id else self.get_default_model()
        if not model:
            return None
        
        # 根据提供商调用对应 API
        if model.provider in ["openai", "moonshot", "deepseek", "glm"]:
            return self._call_openai_compatible(model, messages)
        elif model.provider == "anthropic":
            return self._call_anthropic(model, messages)
        else:
            # 默认使用 OpenAI 兼容格式
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
            print(f"[ModelManager] API 调用失败: {e}")
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
            print(f"[ModelManager] Anthropic API 调用失败: {e}")
            return None
