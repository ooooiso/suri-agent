"""task_planner 插件 — 任务规划引擎。

支持三种规划模式：
  - 模板匹配规则（内置 + 外部注册）
  - LLM 驱动规划
  - 通用降级规划（句号拆分）
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework.shared.interfaces.plugin import (
    PluginInterface, RuleProvider, TaskPlan, TaskStep, TaskTemplate, TemplateStep,
)
from agent_framework.shared.utils.event_types import Event


# 内置任务模板
BUILTIN_TEMPLATES = {
    "builtin.code": TaskTemplate(
        template_id="builtin.code",
        name="代码开发",
        keywords=["实现", "开发", "编写", "创建", "写", "code", "implement", "create", "write"],
        steps=[
            TemplateStep("需求分析", "suri"),
            TemplateStep("方案设计", "suri"),
            TemplateStep("编码实现", "suri"),
            TemplateStep("代码审查", "suri"),
            TemplateStep("单元测试", "suri"),
            TemplateStep("集成验证", "suri"),
        ],
        default_role="suri",
        priority=10,
    ),
    "builtin.review": TaskTemplate(
        template_id="builtin.review",
        name="代码审查",
        keywords=["审查", "review", "审核", "检查代码"],
        steps=[
            TemplateStep("获取代码", "suri"),
            TemplateStep("分析结构", "suri"),
            TemplateStep("检查问题", "suri"),
            TemplateStep("生成报告", "suri"),
        ],
        default_role="suri",
        priority=10,
    ),
    "builtin.statistics": TaskTemplate(
        template_id="builtin.statistics",
        name="数据分析",
        keywords=["统计", "分析", "统计", "行数", "数量", "statistics", "analyze", "stats"],
        steps=[
            TemplateStep("数据收集", "suri"),
            TemplateStep("数据清洗", "suri"),
            TemplateStep("数据分析", "suri"),
            TemplateStep("生成报告", "suri"),
        ],
        default_role="suri",
        priority=10,
    ),
    "builtin.role_creation": TaskTemplate(
        template_id="builtin.role_creation",
        name="角色创建",
        keywords=["新增角色", "创建角色", "新角色", "add role", "create role", "new role"],
        steps=[
            TemplateStep("定义角色身份", "suri"),
            TemplateStep("设定角色职责", "suri"),
            TemplateStep("编写角色约束", "suri"),
            TemplateStep("配置角色技能", "suri"),
            TemplateStep("确认角色信息", "suri"),
        ],
        default_role="suri",
        priority=20,
    ),
}


class TaskPlannerPlugin(PluginInterface):
    """任务规划插件。"""

    EXTERNAL_TEMPLATES_PATH = str(Path.home() / ".suri" / "config" / "task_templates.yaml")
    
    def __init__(self):
        self._event_bus = None
        self._status = "stopped"
        self._templates: Dict[str, TaskTemplate] = {}
        self._plans: Dict[str, TaskPlan] = {}
        self._rule_providers: List[RuleProvider] = []
        self._config: Dict[str, Any] = {}

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config
        self._reload_templates()
        self._status = "initialized"

    async def start(self) -> None:
        self._status = "running"

    async def pause(self) -> None:
        self._status = "paused"

    async def resume(self) -> None:
        self._status = "running"

    async def stop(self) -> None:
        self._status = "stopped"

    async def cleanup(self) -> None:
        self._status = "stopped"
        self._templates.clear()
        self._plans.clear()

    def register_events(self) -> None:
        self._event_bus.subscribe("task.plan_requested", self._on_plan_requested)
        self._event_bus.subscribe("config.updated", self._on_config_updated)
        self._event_bus.subscribe("task_planner.templates_updated", self._on_templates_updated)

    # ── 公开 API ──

    async def plan(self, task_description: str) -> Optional[TaskPlan]:
        """入口：规划任务。"""
        # 先尝试模板匹配
        plan = self._rule_based_plan(task_description, [])
        if plan:
            return plan
        
        # 尝试 LLM 规划
        # （当前未接入 LLM，略过）
        
        # 通用降级
        return self._generic_plan(task_description)

    def _rule_based_plan(self, task_description: str,
                         external_templates: List[TaskTemplate]) -> Optional[TaskPlan]:
        """基于规则匹配模板。"""
        # 收集所有模板
        all_templates = list(self._templates.values()) + external_templates

        # 按关键词长度降序排列（优先匹配更长的关键词）
        matched = []
        desc_lower = task_description.lower()
        
        for template in all_templates:
            for kw in template.keywords:
                if kw.lower() in desc_lower:
                    matched.append((len(kw), template))
                    break

        if not matched:
            return None

        # 选择最长关键词匹配的，同长度选优先级高的
        matched.sort(key=lambda x: (-x[0], -x[1].priority))
        best = matched[0][1]

        # 注册的 RuleProvider 的模板优先级更高的话覆盖
        # （当前无外部模板）
        if external_templates:
            for t in external_templates:
                if t.priority > best.priority:
                    best = t

        return self._template_to_plan(best, task_description)

    def _template_to_plan(self, template: TaskTemplate, task_name: str) -> TaskPlan:
        """将模板转换为规划。"""
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        steps = []
        
        for i, tstep in enumerate(template.steps):
            step_id = f"step_{i + 1}"
            depends_on = [f"step_{i}"] if i > 0 else []
            step = TaskStep(
                step_id=step_id,
                description=tstep.description,
                assignee=tstep.assignee,
                depends_on=depends_on,
            )
            steps.append(step)

        return TaskPlan(
            plan_id=plan_id,
            task_name=task_name,
            steps=steps,
            involved_roles=[template.default_role],
            dependencies=[s.step_id for s in steps if s.depends_on],
            created_at=datetime.now().isoformat(),
        )

    def _generic_plan(self, task_description: str) -> TaskPlan:
        """通用降级规划：按中文句号拆分。"""
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        # 只按中文句号拆分，不拆分英文句点（如 manifest.json 不被拆分）
        parts = [p.strip() for p in task_description.replace('。', '|').split('|') if p.strip()]
        
        steps = []
        for i, part in enumerate(parts):
            step = TaskStep(
                step_id=f"step_{i + 1}",
                description=part,
                assignee="suri",
                depends_on=[],
            )
            steps.append(step)

        return TaskPlan(
            plan_id=plan_id,
            task_name=task_description[:50] + ("..." if len(task_description) > 50 else ""),
            steps=steps,
            involved_roles=["suri"],
            dependencies=[],
            created_at=datetime.now().isoformat(),
        )

    def register_template(self, template: TaskTemplate) -> bool:
        """注册外部模板。"""
        if template.priority > 99:
            return False
        self._templates[template.template_id] = template
        return True

    def unregister_template(self, template_id: str) -> bool:
        """注销模板。内置模板不可注销。"""
        if template_id.startswith("builtin."):
            return False
        if template_id in self._templates:
            del self._templates[template_id]
            return True
        return False

    def get_ready_steps(self, plan_id: str) -> List[TaskStep]:
        """获取计划中就绪的步骤。"""
        plan = self._plans.get(plan_id)
        if not plan:
            return []

        ready = []
        for step in plan.steps:
            if step.status == "completed":
                continue
            if not step.depends_on:
                ready.append(step)
            else:
                # 依赖全部完成则就绪
                all_done = all(
                    any(s.step_id == dep and s.status == "completed" for s in plan.steps)
                    for dep in step.depends_on
                )
                if all_done:
                    ready.append(step)
        return ready

    def _has_cycle(self, steps: List[TaskStep]) -> bool:
        """检测循环依赖。"""
        graph = {}
        for step in steps:
            graph[step.step_id] = set(step.depends_on or [])

        visited = set()
        path = set()

        def dfs(node):
            if node in path:
                return True
            if node in visited:
                return False
            visited.add(node)
            path.add(node)
            for dep in graph.get(node, set()):
                if dep in graph and dfs(dep):
                    return True
            path.remove(node)
            return False

        for node in graph:
            if dfs(node):
                return True
        return False

    def _parse_llm_response(self, response: str) -> Optional[dict]:
        """解析 LLM 返回的 JSON 规划。"""
        try:
            data = json.loads(response)
            if "task_name" in data and "steps" in data:
                return data
            return None
        except (json.JSONDecodeError, ValueError):
            return None

    def register_rule_provider(self, provider: RuleProvider) -> None:
        """注册规则提供者。"""
        self._rule_providers.append(provider)
        for template in provider.get_task_templates():
            self.register_template(template)

    # ── 事件处理 ──

    async def _on_plan_requested(self, event: Event) -> None:
        """处理 task.plan_requested 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        task_description = payload.get("task_description", "")
        plan = await self.plan(task_description)

        if plan:
            self._plans[plan.plan_id] = plan
            await self._event_bus.publish(Event(
                event_type="task.plan_ready",
                source="task_planner",
                payload={
                    "plan_id": plan.plan_id,
                    "plan": {
                        "plan_id": plan.plan_id,
                        "task_name": plan.task_name,
                        "steps": [s.__dict__ if hasattr(s, '__dict__') else {
                            "step_id": s.step_id,
                            "description": s.description,
                            "assignee": s.assignee,
                            "status": s.status,
                            "depends_on": s.depends_on,
                        } for s in plan.steps],
                        "involved_roles": plan.involved_roles,
                    },
                },
            ))

    async def _on_config_updated(self, event: Event) -> None:
        """处理 config.updated 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        if payload.get("plugin_id") == "task_planner":
            self._reload_templates()

    async def _on_templates_updated(self, event: Event) -> None:
        """处理 templates_updated 事件。"""
        self._reload_templates()

    # ── 热更新 ──

    def _reload_templates(self) -> None:
        """重新加载模板（内置 + 外部文件）。"""
        self._templates = {}
        for tid, template in BUILTIN_TEMPLATES.items():
            self._templates[tid] = template

        # 加载外部模板（覆盖同名）
        external = self._load_external_templates()
        for tid, template in external.items():
            if not tid.startswith("builtin."):
                self._templates[tid] = template

    def _load_external_templates(self) -> Dict[str, TaskTemplate]:
        """加载外部模板文件。"""
        path = Path(self.EXTERNAL_TEMPLATES_PATH)
        if not path.exists():
            return {}
        # YAML 格式的外部模板文件（暂未实现解析）
        return {}