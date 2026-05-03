"""task_planner 插件 — 任务分解引擎"""

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from shared.interfaces.plugin import (
    PluginInterface, TaskPlan, TaskStep, TaskTemplate, TemplateStep
)
from shared.utils.event_types import Event, Priority


class TaskPlannerPlugin(PluginInterface):
    """任务分解引擎插件。
    
    将复杂任务分解为带依赖关系的可执行步骤序列。
    支持规则驱动 + LLM 驱动双轨规划。
    支持从外部 YAML 文件加载模板和热更新。
    """
    
    # 外部模板文件路径
    EXTERNAL_TEMPLATES_PATH = os.path.expanduser("~/.suri/data/templates/task_templates.yaml")
    
    def __init__(self):
        self.name = "task_planner"
        self.event_bus = None
        self.config = {}
        self._templates: Dict[str, TaskTemplate] = {}  # template_id -> template
        self._plans: Dict[str, TaskPlan] = {}  # plan_id -> plan
        self._builtin_templates = self._load_builtin_templates()
    
    def _load_builtin_templates(self) -> Dict[str, TaskTemplate]:
        """加载内置默认模板（代码内 fallback）"""
        return {
            "builtin.code": TaskTemplate(
                template_id="builtin.code",
                name="代码开发",
                keywords=["实现", "编写", "开发", "code", "implement", "write", "创建"],
                steps=[
                    TemplateStep("理解需求", "suri"),
                    TemplateStep("识别依赖", "suri"),
                    TemplateStep("设计", "suri"),
                    TemplateStep("编码", "suri"),
                    TemplateStep("自测", "suri"),
                    TemplateStep("交付", "suri"),
                ],
                default_role="suri",
                priority=0,
                description="标准代码开发流程"
            ),
            "builtin.review": TaskTemplate(
                template_id="builtin.review",
                name="代码审查",
                keywords=["审查", "review", "检查", "audit", "审阅"],
                steps=[
                    TemplateStep("收集变更", "suri"),
                    TemplateStep("逐文件审查", "suri"),
                    TemplateStep("影响分析", "suri"),
                    TemplateStep("出具报告", "suri"),
                ],
                default_role="suri",
                priority=0,
                description="代码审查流程"
            ),
            "builtin.statistics": TaskTemplate(
                template_id="builtin.statistics",
                name="数据分析",
                keywords=["统计", "分析", "stat", "analyze", "报告", "汇总"],
                steps=[
                    TemplateStep("数据抽取", "suri"),
                    TemplateStep("清洗", "suri"),
                    TemplateStep("计算聚合", "suri"),
                    TemplateStep("可视化", "suri"),
                ],
                default_role="suri",
                priority=0,
                description="数据分析流程"
            ),
            "builtin.role_creation": TaskTemplate(
                template_id="builtin.role_creation",
                name="角色创建",
                keywords=["创建角色", "new role", "角色", "添加角色", "新增角色"],
                steps=[
                    TemplateStep("分析需求", "suri"),
                    TemplateStep("设计能力矩阵", "suri"),
                    TemplateStep("生成 Soul", "suri"),
                    TemplateStep("创建目录", "suri"),
                    TemplateStep("通知 suri", "suri"),
                ],
                default_role="suri",
                priority=0,
                description="创建新角色的流程"
            ),
        }
    
    def _load_external_templates(self) -> Dict[str, TaskTemplate]:
        """从外部 YAML 文件加载模板"""
        templates = {}
        try:
            if not os.path.exists(self.EXTERNAL_TEMPLATES_PATH):
                return templates
            
            import yaml
            with open(self.EXTERNAL_TEMPLATES_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data or "templates" not in data:
                return templates
            
            for t_data in data["templates"]:
                template = TaskTemplate(
                    template_id=t_data.get("template_id", f"external_{len(templates)}"),
                    name=t_data.get("name", ""),
                    keywords=t_data.get("keywords", []),
                    steps=[TemplateStep(**s) for s in t_data.get("steps", [])],
                    default_role=t_data.get("default_role", "suri"),
                    priority=min(t_data.get("priority", 0), 99),
                    description=t_data.get("description", ""),
                )
                templates[template.template_id] = template
            
            return templates
        except Exception as e:
            print(f"[task_planner] 加载外部模板失败: {e}")
            return templates
    
    def _reload_templates(self) -> None:
        """重新加载所有模板（内置 + 外部），用于热更新"""
        # 内置模板始终保留（不可覆盖）
        self._templates = dict(self._builtin_templates)
        
        # 加载外部模板（优先级高于内置，但不覆盖内置）
        external = self._load_external_templates()
        for tid, template in external.items():
            if tid not in self._builtin_templates:
                self._templates[tid] = template
            else:
                print(f"[task_planner] 跳过内置模板覆盖: {tid}")
        
        print(f"[task_planner] 模板加载完成: {len(self._builtin_templates)} 内置 + {len(external)} 外部 = {len(self._templates)} 总")
    
    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        """初始化插件"""
        self.event_bus = event_bus
        self.config = config.get("task_planner", {})
        # 从外部文件加载模板（内置 + 外部）
        self._reload_templates()
    
    def register_events(self) -> None:
        """注册事件订阅"""
        self.event_bus.subscribe("task.plan_requested", self._on_plan_requested)
        self.event_bus.subscribe("task.replan_requested", self._on_replan_requested)
        self.event_bus.subscribe("task_planner.register_rules", self._on_register_rules)
        # 热更新事件
        self.event_bus.subscribe("config.updated", self._on_config_updated)
        self.event_bus.subscribe("task_planner.templates_updated", self._on_templates_updated)
    
    async def start(self) -> None:
        """启动插件"""
        pass
    
    async def pause(self) -> None:
        """暂停插件"""
        pass
    
    async def resume(self) -> None:
        """恢复插件"""
        pass
    
    async def stop(self) -> None:
        """停止插件"""
        self._plans.clear()
    
    async def cleanup(self) -> None:
        """清理资源"""
        self._templates.clear()
        self._plans.clear()
    
    # --- 事件处理 ---
    
    async def _on_plan_requested(self, event: Event) -> None:
        """处理任务规划请求"""
        task_text = event.payload.get("task_text", "")
        context = event.payload.get("context", {})
        matched_roles = event.payload.get("matched_roles", [])
        
        plan = await self.plan(task_text, context, matched_roles)
        
        await self.event_bus.publish(Event(
            event_type="task.planned",
            source=self.name,
            target=event.source,
            payload={
                "plan_id": plan.plan_id,
                "task_name": plan.task_name,
                "steps": [s.__dict__ for s in plan.steps],
                "involved_roles": plan.involved_roles,
                "estimated_total_time": plan.estimated_total_time,
            }
        ))
    
    async def _on_replan_requested(self, event: Event) -> None:
        """处理重新规划请求"""
        plan_id = event.payload.get("plan_id")
        reason = event.payload.get("reason", "")
        blocked_step_id = event.payload.get("blocked_step_id")
        
        if plan_id in self._plans:
            old_plan = self._plans[plan_id]
            # 重新规划：基于原任务文本重新生成
            new_plan = await self.plan(
                old_plan.task_name,
                {"reason": reason, "blocked_step_id": blocked_step_id}
            )
            
            await self.event_bus.publish(Event(
                event_type="task.plan_updated",
                source=self.name,
                payload={
                    "plan_id": new_plan.plan_id,
                    "updated_steps": [s.__dict__ for s in new_plan.steps],
                    "update_reason": reason,
                }
            ))
    
    async def _on_register_rules(self, event: Event) -> None:
        """处理规则注册事件"""
        plugin_id = event.payload.get("plugin_id", "unknown")
        templates_data = event.payload.get("templates", [])
        
        count = 0
        for t_data in templates_data:
            template = TaskTemplate(
                template_id=t_data.get("template_id", f"{plugin_id}_{count}"),
                name=t_data.get("name", ""),
                keywords=t_data.get("keywords", []),
                steps=[TemplateStep(**s) for s in t_data.get("steps", [])],
                default_role=t_data.get("default_role", "suri"),
                priority=min(t_data.get("priority", 0), 99),  # 不超过 99
                description=t_data.get("description", ""),
            )
            self._templates[template.template_id] = template
            count += 1
    
    # --- 热更新事件处理 ---
    
    async def _on_config_updated(self, event: Event) -> None:
        """处理配置变更事件（热更新）"""
        plugin_id = event.payload.get("plugin_id")
        # 只响应 task_planner 自身的配置变更
        if plugin_id and plugin_id != self.name:
            return
        
        print(f"[task_planner] 收到配置变更事件，重新加载模板...")
        self._reload_templates()
    
    async def _on_templates_updated(self, event: Event) -> None:
        """处理模板更新事件（热更新）"""
        print(f"[task_planner] 收到模板更新事件，重新加载模板...")
        self._reload_templates()
    
    # --- 核心规划逻辑 ---
    
    async def plan(self, task_text: str, context: Dict = None,
                   matched_roles: List[str] = None) -> TaskPlan:
        """生成任务规划"""
        context = context or {}
        matched_roles = matched_roles or []
        
        # 1. 尝试规则驱动
        if self.config.get("enable_template_matching", True):
            rule_plan = self._rule_based_plan(task_text, matched_roles)
            if rule_plan:
                return rule_plan
        
        # 2. 尝试 LLM 驱动
        if self.config.get("default_planning_mode") != "rule":
            llm_plan = await self._llm_plan(task_text, context)
            if llm_plan:
                return llm_plan
        
        # 3. 降级为 generic_plan
        return self._generic_plan(task_text)
    
    def _rule_based_plan(self, task_text: str,
                         matched_roles: List[str]) -> Optional[TaskPlan]:
        """规则驱动规划"""
        task_lower = task_text.lower()
        
        # 按 priority 降序匹配
        sorted_templates = sorted(
            self._templates.values(),
            key=lambda t: t.priority,
            reverse=True
        )
        
        # 先收集所有匹配的模板，按匹配关键词长度降序选择最佳匹配
        best_match = None
        best_keyword_len = 0
        
        for template in sorted_templates:
            for keyword in template.keywords:
                if keyword.lower() in task_lower:
                    # 优先匹配更长的关键词（更精确）
                    if len(keyword) > best_keyword_len:
                        best_match = template
                        best_keyword_len = len(keyword)
                    break  # 一个模板匹配一个关键词即可
        
        if best_match:
            return self._template_to_plan(best_match, task_text)
        
        return None
    
    def _template_to_plan(self, template: TaskTemplate,
                          task_text: str) -> TaskPlan:
        """将模板转换为 TaskPlan"""
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        steps = []
        
        for i, t_step in enumerate(template.steps):
            step_id = f"step_{i + 1}"
            depends_on = []
            if t_step.depends_on:
                depends_on = t_step.depends_on
            elif i > 0:
                # 引用前一步的 step_id，而非当前步骤
                depends_on = [steps[i - 1].step_id]
            
            steps.append(TaskStep(
                step_id=step_id,
                description=t_step.description,
                assignee=t_step.assignee or template.default_role,
                depends_on=depends_on,
            ))
        
        return TaskPlan(
            plan_id=plan_id,
            task_name=task_text[:100],
            steps=steps,
            involved_roles=list(set(s.assignee for s in steps)),
            dependencies=[s.step_id for s in steps if s.depends_on],
            created_at=self._now(),
        )
    
    async def _llm_plan(self, task_text: str,
                        context: Dict) -> Optional[TaskPlan]:
        """LLM 驱动规划"""
        try:
            # 构建 LLM 请求
            prompt = self._build_llm_prompt(task_text)
            
            # 发布 LLM 请求事件
            request_id = f"llm_req_{uuid.uuid4().hex[:8]}"
            await self.event_bus.publish(Event(
                event_type="llm.request",
                source=self.name,
                payload={
                    "request_id": request_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "model": self.config.get("llm_model", "deepseek/deepseek-chat"),
                    "temperature": 0.3,
                }
            ))
            
            # 等待 LLM 响应（通过事件）
            response = await self._wait_for_llm_response(request_id)
            if not response:
                return None
            
            # 解析 JSON
            plan_data = self._parse_llm_response(response)
            if not plan_data:
                return None
            
            return self._llm_response_to_plan(plan_data, task_text)
            
        except Exception as e:
            print(f"[task_planner] LLM 规划失败: {e}")
            return None
    
    def _build_llm_prompt(self, task_text: str) -> str:
        """构建 LLM 规划提示词"""
        return f"""请将以下任务分解为可执行的步骤序列，以 JSON 格式返回。

任务：{task_text}

要求：
1. 步骤数 1-20
2. 每个步骤有唯一 step_id（step_1, step_2, ...）
3. 用 depends_on 表示依赖关系
4. 不允许循环依赖
5. 指定每个步骤的负责角色（默认 suri）

JSON 格式：
{{
  "task_name": "任务名称",
  "steps": [
    {{"step_id": "step_1", "description": "步骤描述", "assignee": "suri", "depends_on": []}}
  ],
  "involved_roles": ["suri"],
  "estimated_total_time": 60
}}

只返回 JSON，不要其他内容。"""
    
    async def _wait_for_llm_response(self, request_id: str,
                                     timeout: int = 30) -> Optional[str]:
        """等待 LLM 响应"""
        import asyncio
        
        response_event = asyncio.Event()
        response_data = {}
        
        async def on_response(event: Event):
            if event.payload.get("request_id") == request_id:
                response_data["content"] = event.payload.get("content", "")
                response_event.set()
        
        async def on_error(event: Event):
            if event.payload.get("request_id") == request_id:
                response_data["error"] = event.payload.get("error_message", "Unknown error")
                response_event.set()
        
        self.event_bus.subscribe("llm.response", on_response)
        self.event_bus.subscribe("llm.error", on_error)
        
        try:
            await asyncio.wait_for(response_event.wait(), timeout=timeout)
            if "error" in response_data:
                print(f"[task_planner] LLM 错误: {response_data['error']}")
                return None
            return response_data.get("content")
        except asyncio.TimeoutError:
            print(f"[task_planner] LLM 响应超时")
            return None
        finally:
            # 取消订阅，防止内存泄漏
            self.event_bus.unsubscribe("llm.response", on_response)
            self.event_bus.unsubscribe("llm.error", on_error)
    
    def _parse_llm_response(self, response: str) -> Optional[Dict]:
        """解析 LLM 返回的 JSON"""
        # 尝试提取 JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            return None
        
        try:
            data = json.loads(json_match.group())
            return data
        except json.JSONDecodeError:
            return None
    
    def _llm_response_to_plan(self, data: Dict,
                              task_text: str) -> TaskPlan:
        """将 LLM 响应转换为 TaskPlan"""
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        steps = []
        
        max_steps = self.config.get("max_steps_per_plan", 20)
        raw_steps = data.get("steps", [])[:max_steps]
        
        for s in raw_steps:
            steps.append(TaskStep(
                step_id=s.get("step_id", f"step_{len(steps) + 1}"),
                description=s.get("description", ""),
                assignee=s.get("assignee", "suri"),
                depends_on=s.get("depends_on", []),
                estimated_time=s.get("estimated_time"),
            ))
        
        # 检测循环依赖
        if self._has_cycle(steps):
            # 有循环依赖时，全部改为并行
            for s in steps:
                s.depends_on = []
        
        return TaskPlan(
            plan_id=plan_id,
            task_name=data.get("task_name", task_text[:100]),
            steps=steps,
            involved_roles=data.get("involved_roles", ["suri"]),
            dependencies=[s.step_id for s in steps if s.depends_on],
            estimated_total_time=data.get("estimated_total_time"),
            created_at=self._now(),
        )
    
    def _generic_plan(self, task_text: str) -> TaskPlan:
        """通用降级规划"""
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        
        # 按中文句号、分号、换行符拆分（不拆分英文句点，避免 manifest.json 被误拆）
        segments = re.split(r'[。；;\n]', task_text)
        segments = [s.strip() for s in segments if s.strip()]
        
        if not segments:
            segments = [task_text]
        
        max_steps = self.config.get("max_steps_per_plan", 20)
        segments = segments[:max_steps]
        
        steps = []
        for i, seg in enumerate(segments):
            steps.append(TaskStep(
                step_id=f"step_{i + 1}",
                description=seg[:200],
                assignee="suri",
                depends_on=[],  # 全部并行
            ))
        
        return TaskPlan(
            plan_id=plan_id,
            task_name=task_text[:100],
            steps=steps,
            involved_roles=["suri"],
            dependencies=[],
            created_at=self._now(),
        )
    
    def _has_cycle(self, steps: List[TaskStep]) -> bool:
        """检测循环依赖（DFS）"""
        graph = {s.step_id: s.depends_on or [] for s in steps}
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            rec_stack.add(node)
            for dep in graph.get(node, []):
                if dep in graph and dfs(dep):
                    return True
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if dfs(node):
                return True
        return False
    
    def get_ready_steps(self, plan_id: str) -> List[TaskStep]:
        """返回依赖已满足的步骤"""
        plan = self._plans.get(plan_id)
        if not plan:
            return []
        
        ready = []
        for step in plan.steps:
            if step.status != "pending":
                continue
            if not step.depends_on:
                ready.append(step)
            else:
                all_done = all(
                    any(s.step_id == dep and s.status == "completed"
                        for s in plan.steps)
                    for dep in step.depends_on
                )
                if all_done:
                    ready.append(step)
        
        return ready
    
    def update_step_status(self, plan_id: str, step_id: str,
                           status: str) -> bool:
        """更新步骤状态"""
        plan = self._plans.get(plan_id)
        if not plan:
            return False
        
        for step in plan.steps:
            if step.step_id == step_id:
                step.status = status
                return True
        
        return False
    
    def register_template(self, template: TaskTemplate) -> bool:
        """注册任务模板"""
        if template.priority > 99:
            return False
        self._templates[template.template_id] = template
        return True
    
    def unregister_template(self, template_id: str) -> bool:
        """注销任务模板"""
        if template_id in self._builtin_templates:
            return False  # 不能注销内置模板
        return self._templates.pop(template_id, None) is not None
    
    def _now(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().isoformat()