"""
模型服务

职责：
- 读取 model_pool.md
- 提供统一的模型调用接口
- 自动降级、超时处理、降级告警

原则：调用方无需关心具体模型端点，只需指定模型类型。
"""

import os
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from suri_agent.infrastructure.config import ConfigService


@dataclass
class ModelConfig:
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
    
    运行时读取 manifest/models/model_pool.md
    维护模型池缓存，自动降级策略。
    """
    
    def __init__(self, config: ConfigService):
        self.config = config
        self._models: Dict[str, ModelConfig] = {}
        self._models_by_type: Dict[str, List[ModelConfig]] = {}
        self._degradation_log: List[Dict[str, Any]] = []
        self._load_models()
    
    def _load_models(self) -> None:
        """解析 model_pool.md"""
        entry = self.config.get_model_pool()
        if not entry:
            return
        
        # 简化解析：从 meta 中提取模型列表（实际可用更健壮的 Markdown 表格解析）
        # 这里使用预设加载，实际应根据 Markdown 正文动态解析
        presets = [
            ModelConfig('gpt-4o', 'GPT-4o', 'chat', 1, 'openai/gpt-4o', 'gpt-4o-mini', 'active'),
            ModelConfig('gpt-4o-mini', 'GPT-4o Mini', 'chat', 2, 'openai/gpt-4o-mini', 'claude-3-haiku', 'active'),
            ModelConfig('claude-3-opus', 'Claude 3 Opus', 'chat', 3, 'anthropic/claude-3-opus', 'gpt-4o', 'active'),
            ModelConfig('claude-3-haiku', 'Claude 3 Haiku', 'chat', 4, 'anthropic/claude-3-haiku', 'gpt-4o-mini', 'active'),
            ModelConfig('dall-e-3', 'DALL-E 3', 'text2image', 1, 'openai/dall-e-3', 'stable-diffusion-xl', 'active'),
            ModelConfig('stable-diffusion-xl', 'SD XL', 'text2image', 2, 'stability/sd-xl', 'dall-e-3', 'standby'),
        ]
        for m in presets:
            self._models[m.model_id] = m
            if m.model_type not in self._models_by_type:
                self._models_by_type[m.model_type] = []
            self._models_by_type[m.model_type].append(m)
        
        # 按优先级排序
        for mt in self._models_by_type:
            self._models_by_type[mt].sort(key=lambda x: x.priority)
    
    def call_model(
        self,
        prompt: str,
        model_type: str = 'chat',
        preferred_model: Optional[str] = None,
        timeout: int = 30,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        调用模型
        
        Args:
            prompt: 输入提示词
            model_type: 模型类型 chat/expert/text2image/image2image
            preferred_model: 偏好模型 ID（可选）
            timeout: 超时时间（秒）
            fallback: 是否允许自动降级
            
        Returns:
            {'success': bool, 'content': str, 'model_used': str, 'error': str}
        """
        candidates = self._models_by_type.get(model_type, [])
        if not candidates:
            return {'success': False, 'content': '', 'model_used': '', 'error': f'未找到类型 {model_type} 的模型'}
        
        # 确定候选列表
        if preferred_model and preferred_model in self._models:
            # 将偏好模型置顶
            preferred = self._models[preferred_model]
            if preferred in candidates:
                candidates = [preferred] + [c for c in candidates if c.model_id != preferred_model]
        
        # 依次尝试
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
    
    def _do_call(self, model: ModelConfig, prompt: str, timeout: int) -> Dict[str, Any]:
        """
        实际调用模型（占位实现）
        
        实际集成时，此处应调用对应的 API 客户端：
        - OpenAI API
        - Anthropic API
        - 其他模型端点
        """
        # TODO: 集成实际的模型 API 调用
        # 当前为模拟实现
        print(f"[ModelService] 调用 {model.model_id} ({model.endpoint})")
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
        
        # 连续 3 次降级触发告警
        recent = [d for d in self._degradation_log 
                  if time.time() - d['timestamp'] < 3600]  # 1小时内
        if len(recent) >= 3:
            print(f"[ALERT] 模型降级告警：1 小时内降级 {len(recent)} 次，通知 config_admin 和 ops_admin")
    
    def get_model_pool(self) -> Dict[str, ModelConfig]:
        """获取当前模型池"""
        return self._models.copy()
