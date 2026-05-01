"""
Suri Learning — 进化引擎服务

职责：
1. 监听任务完成事件，异步触发学习
2. 经验提取（调用 LLM 分析任务历史）
3. 角色自学习（去重、合并、技能建议）
4. 平台级学习（夜间复盘、统计报表）
5. Soul 进化建议（提交审批）

包含模块：
- feedback_collector.py      → 反馈收集
- experience_extractor.py    → 经验提取
- role_learner.py            → 角色自学习
- platform_learner.py        → 平台级学习

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class LearningService(SuriService):
    """
    进化引擎服务 — 纯异步，不阻塞主流程
    
    订阅 NATS "suri.task.completed" 事件，
    后台提取经验并写入角色 Insight。
    """
    
    def __init__(self):
        super().__init__("suri-learning")
    
    def on_startup(self):
        """订阅任务完成事件"""
        pass
    
    def on_run(self):
        """运行事件消费循环"""
        pass
    
    def on_shutdown(self):
        """完成当前学习任务"""
        pass
    
    def on_persist_state(self):
        """保存正在处理的学习任务"""
        pass
    
    def on_restore_state(self):
        """恢复学习任务队列"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
