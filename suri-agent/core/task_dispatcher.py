"""
任务服务

关联文档: suri-agent/core/core.md

职责：
- 管理任务状态机（pending → in_progress → completed / failed / cancelled）
- 实现 suri 的核心调度逻辑（task_dispatch skill）
- 异常处理与升级（escalation skill）
- 跨部门协作同步（cross_department_sync skill）
- 调用模型时启用智能路由（auto_select=True）

原则：调度策略由外部 scheduling.md 和 workflow.md 驱动，主程序只执行状态流转。

文档同步提醒：修改本文件后，请检查并同步更新关联文档。
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from core.context import ContextService
from core.model_router import ModelService
from access.telegram.bot import CommService, StandardMessage


class TaskService:
    """
    任务调度引擎
    
    核心流程：
    1. receive_task: 接收用户需求，创建任务
    2. dispatch: 读取 function_index.md，匹配部门，下发总监
    3. track: 跟踪任务状态，处理进度汇报
    4. escalate: 异常时重试/升级
    """
    
    def __init__(self, config: ConfigService, memory: MemoryService,
                 context: ContextService, model: ModelService, comm: CommService, 
                 logger=None, learner=None):
        self.config = config
        self.memory = memory
        self.context = context
        self.model = model
        self.comm = comm
        self.logger = logger
        self._learner = learner  # 新增：学习引擎实例
    
    def receive_task(self, user_id: str, raw_input: str, session_id: str = "") -> str:
        """
        接收用户任务
        
        Args:
            user_id: 用户标识
            raw_input: 用户原始输入
            session_id: 会话ID（多用户隔离，由调用方传入）
        
        Returns:
            task_id
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        if not session_id:
            session_id = f"session_{user_id}_{datetime.now().strftime('%Y%m%d')}"
        
        # 创建任务记录（在 suri 的数据库中）
        self.memory.create_task('suri', task_id, session_id, 'user', 'central', 'suri')
        
        # 保存初始消息
        self.memory.save_message(
            'suri',
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            sender='user',
            receiver='suri',
            body={'type': 'task', 'content': raw_input}
        )
        
        # 记录任务调度日志
        if self.logger:
            self.logger.log_task_created(task_id, user_id, raw_input)
            self.logger.log_task_dispatched(task_id, 'user', 'suri', 'central')
        
        return task_id
    
    async def dispatch(self, task_id: str) -> Dict[str, Any]:
        """
        分派任务
        
        1. 读取 function_index.md
        2. 分析需求，匹配部门
        3. 生成结构化消息，下发给总监
        """
        # 任务存储在 suri 的 role.db 中
        task = self.memory.get_task('suri', task_id)
        if not task:
            return {'success': False, 'error': '任务不存在'}
        
        # 获取用户原始需求
        messages = self.memory.get_task_messages('suri', task_id)
        raw_input = messages[0]['body']['content'] if messages else ''
        
        # 获取部门列表（从 Soul 文件扫描）
        departments = self.config.list_departments()
        if not departments:
            return {'success': False, 'error': '未找到任何部门'}
        
        # TODO: 使用模型或关键词匹配确定目标部门
        # 当前简化：调用 model_service 进行需求分类
        target_dept, target_director = await self._match_department(raw_input, departments)
        
        if not target_dept:
            return {'success': False, 'error': '无法匹配责任部门'}
        
        # 更新任务（在 suri 的 role.db 中）
        self.memory.update_task_status('suri', task_id, 'in_progress')
        
        # TODO: 更新数据库中的 target_department 和 target_director
        
        # 组装 suri 的调度上下文
        suri_context = self.context.build_context('suri', {
            'task_id': task_id,
            'requirement': raw_input,
            'target_department': target_dept,
            'target_director': target_director
        })
        
        # 调用模型生成分派消息（启用智能路由，按任务内容自动选择模型）
        prompt = f"{suri_context}\n\n请根据以上信息，生成发给 {target_director} 的结构化任务消息。"
        model_result = await self.model.call_model(
            prompt, model_type='chat',
            auto_select=True, task_content=raw_input
        )
        
        # 发送给总监
        msg = StandardMessage(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            sender_role='suri',
            receiver_role=target_director,
            timestamp=datetime.now().isoformat(),
            priority='normal',
            task_ref=task_id,
            body={'type': 'task', 'content': model_result.get('content', raw_input)}
        )
        
        await self.comm.send_to_role(target_director, msg)
        
        # 异步触发学习（不阻塞主流程）
        if self._learner:
            import asyncio
            asyncio.create_task(
                self._learner.learn_from_task(target_director, task_id)
            )
        
        return {
            'success': True,
            'task_id': task_id,
            'target_department': target_dept,
            'target_director': target_director
        }
    
    def _build_dept_keywords(self, departments: List[str]) -> Dict[str, set]:
        """
        从所有角色 Soul 动态推导部门关键词映射。
        
        每个部门的关键词 = 该部门下所有角色的 keywords 集合。
        结果缓存，避免每次调用重复扫描。
        """
        # 简单缓存：用 departments 列表的 frozenset 作为 key
        cache_key = frozenset(departments)
        if hasattr(self, '_dept_kw_cache') and self._dept_kw_cache.get('key') == cache_key:
            return self._dept_kw_cache['value']
        
        dept_keywords: Dict[str, set] = {}
        for role_id in self.config.list_roles(include_aliases=False):
            soul = self.config.get_role_soul(role_id)
            if not soul:
                continue
            dept = soul.meta.get('department', 'central')
            if dept not in departments:
                continue
            keywords = soul.meta.get('keywords', [])
            if dept not in dept_keywords:
                dept_keywords[dept] = set()
            dept_keywords[dept].update(keywords)
            # 同时加入 capabilities 作为补充关键词
            capabilities = soul.meta.get('capabilities', [])
            dept_keywords[dept].update(capabilities)
        
        self._dept_kw_cache = {'key': cache_key, 'value': dept_keywords}
        return dept_keywords

    async def _match_department(self, raw_input: str, departments: List[str]) -> tuple[Optional[str], Optional[str]]:
        """
        匹配责任部门
        
        三级策略：
        1. 动态关键词匹配（从角色 Soul 实时推导，O(1) 快速路径）
        2. 模型辅助分类（LLM 语义理解，当关键词未命中时触发）
        3. Fallback 回 central（中枢部门兜底，避免乱派）
        """
        if not departments:
            return None, None

        # === 第一级：动态关键词匹配（从角色 Soul 推导）===
        dept_keywords = self._build_dept_keywords(departments)
        
        for dept_id in departments:
            for kw in dept_keywords.get(dept_id, []):
                if kw in raw_input:
                    return dept_id, self.config.get_department_lead(dept_id)
        
        # 动态匹配未命中：使用兜底关键词映射（兼容测试和扩展部门）
        fallback_keywords = {
            'design': ['设计', '图像', '视频', '美术', '视觉', '画图', 'UI', 'UX', '配色', '排版', '渲染'],
            'engineering': ['开发', '代码', '程序', '脚本', '后台', '部署', 'API', '数据库', 'bug', '修复', '重构', '架构'],
            'ops': ['运维', '安全', '配置', '流程', 'Git', '监控', '日志', '备份', '容灾', '权限', '审计'],
            'resource': ['资源', '文件', '存储', '归档', '清理', '缓存', 'CDN', '压缩', '迁移'],
            'hr': ['角色', '人事', '组织', '创建角色', '注销', '招聘', '离职', '权限分配', '组织架构'],
            'central': ['调度', '协调', '汇总', 'suri', '中枢', '平台', '总览', '状态'],
        }
        for dept_id in departments:
            for kw in fallback_keywords.get(dept_id, []):
                if kw in raw_input:
                    return dept_id, self.config.get_department_lead(dept_id)

        # === 第二级：模型辅助分类 ===
        # 当关键词未命中时，使用 LLM 做语义分类（如果模型可用）
        try:
            dept_list = ', '.join(departments)
            prompt = (
                f"用户需求：'{raw_input}'\n"
                f"可选部门：{dept_list}\n"
                f"请判断该需求应分配给哪个部门，只返回部门 ID，不要解释。"
            )
            model_result = await self.model.call_model(prompt, model_type='chat')
            if model_result and model_result.get('success'):
                predicted = model_result.get('content', '').strip().lower()
                for dept_id in departments:
                    if dept_id in predicted:
                        return dept_id, self.config.get_department_lead(dept_id)
        except Exception:
            pass  # 模型分类失败，继续 fallback

        # === 第三级：Fallback 回 central（中枢部门兜底）===
        # 避免乱派到不相关的部门，central 负责进一步询问用户或人工分配
        if 'central' in departments:
            return 'central', self.config.get_department_lead('central')

        # 如果连 central 都没有，返回第一个（兜底兜底）
        return departments[0], self.config.get_department_lead(departments[0])
    
    async def handle_escalation(self, task_id: str, error_info: str) -> Dict[str, Any]:
        """
        处理任务升级
        
        1. 增加重试计数
        2. 若超过 3 次，回流用户
        """
        retry = self.memory.increment_retry('suri', task_id)
        
        if retry >= 3:
            self.memory.update_task_status('suri', task_id, 'failed')
            if self.logger:
                self.logger.log_task_completed(task_id, 'suri', 'failed', 0)
            # TODO: 向用户汇报失败原因
            return {'success': False, 'action': 'user_fallback', 'reason': f'重试 {retry} 次后失败'}
        
        # TODO: 重试逻辑
        return {'success': True, 'action': 'retry', 'retry_count': retry}
