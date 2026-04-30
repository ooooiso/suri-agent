"""
任务服务

职责：
- 管理任务状态机（pending → in_progress → completed / failed / cancelled）
- 实现 suri 的核心调度逻辑（task_dispatch skill）
- 异常处理与升级（escalation skill）
- 跨部门协作同步（cross_department_sync skill）

原则：调度策略由外部 scheduling.md 和 workflow.md 驱动，主程序只执行状态流转。
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
                 context: ContextService, model: ModelService, comm: CommService, logger=None):
        self.config = config
        self.memory = memory
        self.context = context
        self.model = model
        self.comm = comm
        self.logger = logger
    
    def receive_task(self, user_id: str, raw_input: str) -> str:
        """
        接收用户任务
        
        Returns:
            task_id
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
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
        
        print(f"[TaskService] 新任务 {task_id} 来自用户 {user_id}")
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
        
        # 读取 function_index
        func_index = self.config.get_function_index()
        if not func_index:
            return {'success': False, 'error': '部门职能索引未加载'}
        
        departments = func_index.meta.get('departments', [])
        
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
        
        # 调用模型生成分派消息
        prompt = f"{suri_context}\n\n请根据以上信息，生成发给 {target_director} 的结构化任务消息。"
        model_result = self.model.call_model(prompt, model_type='chat')
        
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
        
        print(f"[TaskService] 任务 {task_id} 已分派给 {target_director} ({target_dept})")
        return {
            'success': True,
            'task_id': task_id,
            'target_department': target_dept,
            'target_director': target_director
        }
    
    async def _match_department(self, raw_input: str, departments: List[Dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
        """
        匹配责任部门
        
        TODO: 实现更智能的匹配（关键词/模型分类）
        当前简化返回第一个部门。
        """
        # 简单关键词匹配示例
        keywords = {
            'design': ['设计', '图像', '视频', '美术', '视觉', '画图'],
            'engineering': ['开发', '代码', '程序', '脚本', '后台', '部署'],
            'ops': ['运维', '安全', '配置', '流程', 'Git', '监控'],
            'resource': ['资源', '文件', '存储', '归档', '清理'],
            'hr': ['角色', '人事', '组织', '创建角色', '注销'],
        }
        
        for dept in departments:
            dept_id = dept.get('id', '')
            for kw in keywords.get(dept_id, []):
                if kw in raw_input:
                    return dept_id, dept.get('lead_role')
        
        # 默认返回设计部（或第一个可用部门）
        if departments:
            return departments[0].get('id'), departments[0].get('lead_role')
        
        return None, None
    
    async def handle_escalation(self, task_id: str, error_info: str) -> Dict[str, Any]:
        """
        处理任务升级
        
        1. 增加重试计数
        2. 若超过 3 次，回流用户
        """
        retry = self.memory.increment_retry('suri', task_id)
        
        if retry >= 3:
            self.memory.update_task_status(task_id, 'failed')
            # TODO: 向用户汇报失败原因
            return {'success': False, 'action': 'user_fallback', 'reason': f'重试 {retry} 次后失败'}
        
        # TODO: 重试逻辑
        print(f"[TaskService] 任务 {task_id} 第 {retry} 次重试")
        return {'success': True, 'action': 'retry', 'retry_count': retry}
