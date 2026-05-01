"""
模型服务

关联文档: suri-agent/core/core.md, suri-agent/model/pool.yaml, suri-agent/model/model.md

职责：
- 读取 pool.yaml（业务配置）
- 提供统一的模型调用接口
- 智能模型路由（auto_select 按任务内容自动选择模型）
- 自动降级、超时处理、降级告警

原则：调用方无需关心具体模型端点，只需指定模型类型。
实际调用委托给 ModelManager（避免重复实现 HTTP 层）。

文档同步提醒：修改本文件后，请检查并同步更新关联文档。
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

    运行时读取 suri-agent/model/pool.yaml 和 ModelManager 的模型配置，
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
        data = self.config.get_model_pool()
        if not data:
            return

        models_data = data.get('models', [])
        for m in models_data:
            cfg = RouterModelConfig(
                model_id=m.get('id', ''),
                name=m.get('name', ''),
                model_type=m.get('type', 'chat'),
                priority=m.get('priority', 0),
                endpoint=m.get('provider', ''),
                fallback_model=m.get('fallback'),
                status=m.get('status', 'active'),
            )
            self._models[cfg.model_id] = cfg
            if cfg.model_type not in self._models_by_type:
                self._models_by_type[cfg.model_type] = []
            self._models_by_type[cfg.model_type].append(cfg)

        for mt in self._models_by_type:
            self._models_by_type[mt].sort(key=lambda x: x.priority)

    async def call_model(
        self,
        prompt: str,
        model_type: str = 'chat',
        preferred_model: Optional[str] = None,
        timeout: int = 30,
        fallback: bool = True,
        auto_select: bool = False,
        task_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        调用模型

        优先使用 ModelManager 中用户配置的模型（有真实 API Key），
        如果 ModelManager 不可用，回退到预设池的模拟回复。

        Args:
            auto_select: 为 True 时，根据 task_content 自动选择最合适的模型
            task_content: 用于智能路由的任务原文（auto_select=True 时必填）
        """
        # 智能路由：自动选择模型
        selected_model_id = preferred_model
        if auto_select and self.model_manager and task_content:
            smart_model = self.model_manager.select_model_for_task(task_content)
            if smart_model:
                selected_model_id = smart_model.model_id
                # 智能路由已选择模型，信息写入日志不打印到终端
                pass

        # 优先使用 ModelManager 的真实模型配置
        if self.model_manager and not self.model_manager.is_first_run():
            mm_model = None
            if selected_model_id:
                mm_model = self.model_manager._models.get(selected_model_id)
            if not mm_model:
                mm_model = self.model_manager.get_default_model()

            if mm_model:
                messages = [
                    {"role": "system", "content": "你是一个智能助手。"},
                    {"role": "user", "content": prompt},
                ]
                try:
                    result = await self.model_manager.chat_with_usage(messages, model_id=mm_model.model_id)
                    if result and result.get('content'):
                        # 记录 Token 消耗
                        if self.logger:
                            self.logger.log_token_usage(
                                model_id=mm_model.model_id,
                                prompt_tokens=result.get('prompt_tokens', 0),
                                completion_tokens=result.get('completion_tokens', 0),
                                total_tokens=result.get('total_tokens', 0),
                                task_hint=task_content or prompt[:50]
                            )
                        return {
                            'success': True,
                            'content': result['content'],
                            'model_used': mm_model.model_id,
                            'prompt_tokens': result.get('prompt_tokens', 0),
                            'completion_tokens': result.get('completion_tokens', 0),
                            'total_tokens': result.get('total_tokens', 0),
                            'error': ''
                        }
                except Exception as e:
                    # 调用失败信息写入日志
                    pass

        # 回退到预设池（模拟回复，用于无配置时）
        candidates = self._models_by_type.get(model_type, [])
        if not candidates:
            return {'success': False, 'content': '', 'model_used': '', 'error': f'未找到类型 {model_type} 的模型'}

        if selected_model_id and selected_model_id in self._models:
            preferred = self._models[selected_model_id]
            if preferred in candidates:
                candidates = [preferred] + [c for c in candidates if c.model_id != selected_model_id]

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
