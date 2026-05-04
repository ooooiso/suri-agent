"""PluginInterface — 所有插件必须实现的接口。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class PluginInterface(ABC):
    """插件接口基类。
    
    所有插件的主类必须继承此接口，并实现所有抽象方法。
    """

    @abstractmethod
    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        """初始化插件。
        
        Args:
            event_bus: EventBus 实例，用于发布/订阅事件
            config: 插件配置字典
        """
        pass

    @abstractmethod
    async def start(self, **kwargs) -> None:
        """启动插件，标记为就绪状态。
        
        Args:
            **kwargs: 可选的启动参数，如 plugin_manager 注入
        """
        pass

    @abstractmethod
    async def pause(self) -> None:
        """暂停插件，停止处理新事件。"""
        pass

    @abstractmethod
    async def resume(self) -> None:
        """恢复插件。"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止插件。"""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """清理资源。"""
        pass

    def register_events(self) -> None:
        """注册事件订阅（可选重写）。"""
        pass


class RuleProvider(ABC):
    """规则提供者接口。
    
    插件实现此接口可向 task_planner 注册自己的任务模板。
    新增能力时，只需新增插件并实现此接口，无需修改 task_planner 代码。
    """
    
    @abstractmethod
    def get_task_templates(self) -> List['TaskTemplate']:
        """返回该插件提供的任务模板列表。
        
        在插件 start() 时被 task_planner 调用。
        """
        pass


@dataclass
class TaskTemplate:
    """任务模板数据类。
    
    插件通过 RuleProvider.get_task_templates() 返回此对象列表，
    向 task_planner 注册自己的任务分解规则。
    """
    template_id: str              # 唯一标识，如 "code_tool.write_file"
    name: str                     # 模板名称，如 "文件写入"
    keywords: List[str]           # 触发关键词，如 ["写入", "创建文件", "write"]
    steps: List['TemplateStep']   # 预设步骤
    default_role: str             # 默认执行角色
    priority: int = 0             # 匹配优先级，越高越优先
    description: str = ""         # 模板说明


@dataclass
class TemplateStep:
    """模板步骤数据类。"""
    description: str              # 步骤描述
    assignee: str                 # 负责角色
    depends_on: Optional[List[str]] = None  # 前置步骤 ID（可选）


@dataclass
class TaskPlan:
    """任务规划数据类。"""
    plan_id: str
    task_name: str
    steps: List['TaskStep']
    involved_roles: List[str]
    dependencies: List[str]
    estimated_total_time: Optional[int] = None
    created_at: str = ""


@dataclass
class TaskStep:
    """任务步骤数据类。"""
    step_id: str
    description: str
    assignee: str
    status: str = "pending"           # pending | in_progress | completed | blocked
    depends_on: Optional[List[str]] = None
    estimated_time: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    block_reason: Optional[str] = None
    result: Optional[str] = None


@dataclass
class Agent:
    """Agent 数据类。"""
    agent_id: str
    task_id: str
    task_name: str
    parent_agent_id: Optional[str]
    role_id: str
    status: str                        # planning | running | paused | completed | blocked | cancelled
    steps: List[TaskStep]
    user_id: str
    plan_id: Optional[str]
    created_at: str
    updated_at: str
    
    @property
    def progress(self) -> str:
        completed = sum(1 for s in self.steps if s.status == "completed")
        return f"{completed}/{len(self.steps)}" if self.steps else "0/0"
    
    @property
    def current_step(self) -> Optional[TaskStep]:
        for s in self.steps:
            if s.status == "in_progress":
                return s
        for s in self.steps:
            if s.status == "pending":
                return s
        return None


@dataclass
class InterruptResult:
    """中断处理结果数据类。"""
    handled: bool
    action: str                    # wait | escalate | cancel | auto_resolve | retry
    suggestion: str                # 给用户的中文建议文本
    new_agent_id: Optional[str] = None
    reason: str = ""
    escalation_target: Optional[str] = None