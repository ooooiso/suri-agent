"""
主程序自学习引擎

职责：
- 汇总全平台角色任务数据
- 优化 suri 的调度策略、用户画像、模型路由
- 周期性复盘（夜间定时执行）

第一期实现要求：
- 搭好框架和接口
- 实现 daily_review() 的空壳（仅读取日志，不实际处理）
- 预留扩展点，不阻塞主流程

关联文档: suri-agent/learning/learning.md
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .base import BaseLearner


class PlatformLearner(BaseLearner):
    """主程序自学习引擎"""
    
    learner_id = "platform_learner"
    name = "主程序自学习引擎"
    version = "1.0.0"
    
    def __init__(self, memory, model, logger=None):
        self.memory = memory
        self.model = model
        self.logger = logger
    
    async def learn(self, context: Dict[str, Any]) -> Optional[str]:
        """预留接口"""
        return await self.daily_review()
    
    async def daily_review(self) -> Optional[str]:
        """
        夜间复盘
        
        第一期只需实现：
        1. 读取当天日志（logs/schedule/、logs/role/）
        2. 统计各角色任务数量、成功率
        3. 如 logger 存在，记录统计摘要
        4. 返回统计文本（暂不做 LLM 分析）
        
        第二期扩展：
        - 调用 LLM 分析调度失败根因
        - 生成 scheduling_patterns 更新建议
        - 更新 user_preference_profile
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            stats = self._read_daily_logs(today)
            
            summary = self._generate_summary(stats)
            
            if self.logger:
                self.logger.log_learning(
                    'platform',
                    '夜间复盘',
                    f"任务总计: {stats.get('total_tasks', 0)} | 成功: {stats.get('success', 0)} | 失败: {stats.get('failed', 0)}"
                )
            
            return summary
        except Exception as e:
            if self.logger:
                self.logger.error("自学习", f"平台夜间复盘失败: {e}")
            return None
    
    def _read_daily_logs(self, date_str: str) -> Dict[str, Any]:
        """读取当天日志并统计"""
        stats = {
            'total_tasks': 0,
            'success': 0,
            'failed': 0,
            'cancelled': 0,
            'role_counts': {},
            'model_calls': 0,
            'model_errors': 0,
        }
        
        project_root = getattr(self.memory, 'project_root', Path('.'))
        
        # 读取 schedule 日志
        schedule_log = project_root / 'logs' / 'schedule' / f'suri-{date_str}.log'
        if schedule_log.exists():
            try:
                content = schedule_log.read_text(encoding='utf-8')
                for line in content.split('\n'):
                    if '任务调度' in line and '已创建' in line:
                        stats['total_tasks'] += 1
                    if '任务调度' in line and '调度至' in line:
                        stats['success'] += 1
            except Exception:
                pass
        
        # 读取 error 日志
        error_log = project_root / 'logs' / 'error' / f'suri-{date_str}.log'
        if error_log.exists():
            try:
                content = error_log.read_text(encoding='utf-8')
                stats['failed'] += content.count('错误')
            except Exception:
                pass
        
        # 读取 runtime 日志（模型调用统计）
        runtime_log = project_root / 'logs' / 'runtime' / f'suri-{date_str}.log'
        if runtime_log.exists():
            try:
                content = runtime_log.read_text(encoding='utf-8')
                stats['model_calls'] = content.count('模型调用')
                stats['model_errors'] = content.count('模型调用失败')
            except Exception:
                pass
        
        return stats
    
    def _generate_summary(self, stats: Dict[str, Any]) -> str:
        """生成统计摘要"""
        lines = [
            "=== 平台每日复盘 ===",
            f"日期: {datetime.now().strftime('%Y-%m-%d')}",
            f"任务总数: {stats.get('total_tasks', 0)}",
            f"成功调度: {stats.get('success', 0)}",
            f"失败/错误: {stats.get('failed', 0)}",
            f"模型调用: {stats.get('model_calls', 0)} 次",
            f"模型错误: {stats.get('model_errors', 0)} 次",
            "==================",
        ]
        return "\n".join(lines)
    
    async def learn_scheduling(self) -> Optional[str]:
        """学习调度策略（预留）"""
        if self.logger:
            self.logger.log_learning('platform', '调度策略学习', '预留接口，第二期实现')
        return "预留接口"
    
    async def learn_user_preferences(self) -> Optional[str]:
        """学习用户偏好（预留）"""
        if self.logger:
            self.logger.log_learning('platform', '用户偏好学习', '预留接口，第二期实现')
        return "预留接口"
