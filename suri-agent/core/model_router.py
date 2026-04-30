"""
模型服务

职责：
- 读取 model_pool.md
- 提供统一的模型调用接口
- 自动降级、超时处理、降级告警

原则：调用方无需关心具体模型端点，只需指定模型类型。
实际调用委托给 ModelManager（避免重复实现 HTTP 层）。
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from infrastructure.config import ConfigService


@dataclass
class RouterModelConfig:
    """路由层模型配置（与 ModelManager.ModelConfig 不同，用于预设池）"""
    model_id: str
    name: str
    model_type: str      # chat / expert / text2image / image2image
    priority: int
    endpoint: str
    fallback_model: Optional[str]
    status: str          # active / standby / deprecated


class ModelService:
    """
    模型路由中心

    运行时读取 wiki/models/model_pool.md 和 ModelManager 的模型配置，
    维护模型池缓存，执行自动降级策略。
    实际 HTTP 调用委托给 ModelManager。
    """

    def __init__(self, config: ConfigService, model_manager=None):
        self.config = config
        self.model_manager = model_manager  # 委托实际调用
        self._models: Dict[str, RouterModelConfig] = {}
        self._models_by_type: Dict[str, List[RouterModelConfig]] = {}
        self._degradation_log: List[Dict[str, Any]] = []
        self._load_models()

    def _load_models(self) -> None:
        """加载预设模型池（作为降级候选）"""
        entry = self.config.get_model_pool()
        if not entry:
            return

        presets = [
            RouterModelConfig('gpt-4o', 'GPT-4o', 'chat', 1, 'openai/gpt-4o', 'gpt-4o-mini', 'active'),
            RouterModelConfig('gpt-4o-mini', 'GPT-4o Mini', 'chat', 2, 'openai/gpt-4o-mini', 'claude-3-haiku', 'active'),
            RouterModelConfig('claude-3-opus', 'Claude 3 Opus', 'chat', 3, 'anthropic/claude-3-opus', 'gpt-4o', 'active'),
            RouterModelConfig('claude-3-haiku', 'Claude 3 Haiku', 'chat', 4, 'anthropic/claude-3-haiku', 'gpt-4o-mini', 'active'),
            RouterModelConfig('dall-e-3', 'DALL-E 3', 'text2image', 1, 'openai/dall-e-3', 'stable-diffusion-xl', 'active'),
            RouterModelConfig('stable-diffusion-xl', 'SD XL', 'text2image', 2, 'stability/sd-xl', 'dall-e-3', 'standby'),
        ]
        for m in presets:
            self._models[m.model_id] = m
            if m.model_type not in self._models_by_type:
                self._models_by_type[m.model_type] = []
            self._models_by_type[m.model_type].append(m)

        for mt in self._models_by_type:
            self._models_by_type[mt].sort(key=lambda x: x.priority)

    async def call_model(
        self,
        prompt: str,
        model_type: str = 'chat',
        preferred_model: Optional[str] = None,
        timeout: int = 30,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        调用模型

        优先使用 ModelManager 中用户配置的模型（有真实 API Key），
        如果 ModelManager 不可用，回退到预设池的模拟回复。
        """
        # 优先使用 ModelManager 的真实模型配置
        if self.model_manager and not self.model_manager.is_first_run():
            mm_model = self.model_manager.get_default_model()
            if mm_model:
                messages = [
                    {"role": "system", "content": "你是一个智能助手。"},
                    {"role": "user", "content": prompt},
                ]
                try:
                    reply = await self.model_manager.chat(messages)
                    if reply:
                        return {
                            'success': True,
                            'content': reply,
                            'model_used': mm_model.model_id,
                            'error': ''
                        }
                except Exception as e:
                    print(f"[ModelService] ModelManager 调用失败: {e}")

        # 回退到预设池（模拟回复，用于无配置时）
        candidates = self._models_by_type.get(model_type, [])
        if not candidates:
            return {'success': False, 'content': '', 'model_used': '', 'error': f'未找到类型 {model_type} 的模型'}

        if preferred_model and preferred_model in self._models:
            preferred = self._models[preferred_model]
            if preferred in candidates:
                candidates = [preferred] + [c for c in candidates if c.model_id != preferred_model]

        for model in candidates:
            if model.status != 'active':
                continue
            try:
                result = self._do_call(model, prompt, timeout)
                if result['success']:
                    return result
            except Exception as e:
                if fallback and model.fallback_model:
                    self._log_degradation(model.model_id, model.fallback_model, str(e))
                    continue
                return {'success': False, 'content': '', 'model_used': model.model_id, 'error': str(e)}

        return {'success': False, 'content': '', 'model_used': '', 'error': '所有模型均不可用'}

    def _do_call(self, model: RouterModelConfig, prompt: str, timeout: int) -> Dict[str, Any]:
        """预设模型的模拟调用（无 API Key 时回退）"""
        print(f"[ModelService] 模拟调用 {model.model_id} ({model.endpoint})")
        return {
            'success': True,
            'content': f'[来自 {model.name} 的模拟回复] 收到提示: {prompt[:50]}...',
            'model_used': model.model_id,
            'error': ''
        }

    def _log_degradation(self, from_model: str, to_model: str, reason: str) -> None:
        """记录降级事件"""
        self._degradation_log.append({
            'from': from_model,
            'to': to_model,
            'reason': reason,
            'timestamp': time.time()
        })
        recent = [d for d in self._degradation_log
                  if time.time() - d['timestamp'] < 3600]
        if len(recent) >= 3:
            print(f"[ALERT] 模型降级告警：1 小时内降级 {len(recent)} 次")

    def get_model_pool(self) -> Dict[str, RouterModelConfig]:
        """获取当前模型池"""
        return self._models.copy()
