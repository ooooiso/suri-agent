"""
任务规划器

关联文档: suri-agent/core/core.md

职责：
- 接收用户需求，生成任务分解草案
- 每个草案包含：步骤列表、涉及角色、预估耗时
- 支持从角色 Soul 文件中读取任务分解方法论

V3.0 新增模块
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

from infrastructure.config import ConfigService
from core.task_state import TaskStep


@dataclass
class TaskPlan:
    """任务规划草案"""
    task_name: str
    steps: List[TaskStep]
    involved_roles: List[str]
    estimated_total_time: Optional[int] = None  # 预估总耗时（秒）
    dependencies: List[str] = field(default_factory=list)  # 前置依赖描述
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_name": self.task_name,
            "steps": [s.to_dict() for s in self.steps],
            "involved_roles": self.involved_roles,
            "estimated_total_time": self.estimated_total_time,
            "dependencies": self.dependencies,
        }


class TaskPlanService:
    """
    任务规划服务
    
    生成任务分解草案的两种方式：
    1. LLM 生成：调用模型分析需求，生成步骤列表
    2. 规则生成：基于角色能力模板匹配，生成预设步骤
    """
    
    # 预设任务模板（基于常见任务类型）
    TASK_TEMPLATES = {
        "code": {
            "steps": [
                "理解需求，确认输入输出",
                "识别依赖，列出需要的前置材料或工具",
                "设计实现方案",
                "编写代码",
                "自测与调试",
                "输出交付物",
            ],
            "roles": ["suri_dev"],
        },
        "review": {
            "steps": [
                "收集变更文件清单",
                "逐文件审查差异",
                "逻辑影响分析",
                "出具审查报告",
            ],
            "roles": ["suri_review"],
        },
        "statistics": {
            "steps": [
                "数据抽取",
                "数据清洗",
                "计算与聚合",
                "可视化输出",
            ],
            "roles": ["suri_stats"],
        },
        "role_creation": {
            "steps": [
                "分析新角色需求",
                "设计角色能力矩阵",
                "生成 Soul 文件",
                "创建目录结构",
                "通知 suri 集成",
            ],
            "roles": ["suri_hr"],
        },
    }
    
    def __init__(self, config: ConfigService):
        self.config = config
    
    def generate_plan(self, task_text: str, matched_roles: List[str]) -> TaskPlan:
        """
        生成任务规划草案
        
        策略：
        1. 如果只有1个匹配角色，使用该角色的能力模板
        2. 如果多个角色，生成跨角色协作步骤
        3. 如果没有匹配角色，使用通用模板
        """
        # 简化实现：基于匹配角色数量选择模板
        if len(matched_roles) == 1:
            return self._single_role_plan(task_text, matched_roles[0])
        elif len(matched_roles) > 1:
            return self._multi_role_plan(task_text, matched_roles)
        else:
            return self._generic_plan(task_text)
    
    def _single_role_plan(self, task_text: str, role_id: str) -> TaskPlan:
        """单角色任务规划"""
        # 根据角色类型选择模板
        role_type = self.config.get_role_type(role_id)
        template_key = self._map_type_to_template(role_type)
        template = self.TASK_TEMPLATES.get(template_key, self.TASK_TEMPLATES["code"])
        
        steps = []
        prev_step_id = None
        for i, desc in enumerate(template["steps"], 1):
            step_id = f"step_{i}"
            depends_on = [prev_step_id] if prev_step_id else []
            steps.append(TaskStep(
                step_id=step_id,
                description=desc,
                status="pending",
                assignee=role_id,
                depends_on=depends_on,
            ))
            prev_step_id = step_id
        
        return TaskPlan(
            task_name=task_text[:50],
            steps=steps,
            involved_roles=[role_id],
        )
    
    def _multi_role_plan(self, task_text: str, roles: List[str]) -> TaskPlan:
        """多角色协作任务规划"""
        prev_step_id = None
        steps = []
        
        def add_step(step_id: str, desc: str, assignee: str):
            nonlocal prev_step_id
            depends_on = [prev_step_id] if prev_step_id else []
            steps.append(TaskStep(
                step_id=step_id,
                description=desc,
                status="pending",
                assignee=assignee,
                depends_on=depends_on,
            ))
            return step_id
        
        prev_step_id = add_step("step_1", "理解需求，确认整体目标", "suri")
        prev_step_id = add_step("step_2", "各角色评估自身负责范围", ",".join(roles))
        
        # 为每个角色添加执行步骤
        step_idx = 3
        for role_id in roles:
            role_type = self.config.get_role_type(role_id)
            template_key = self._map_type_to_template(role_type)
            template = self.TASK_TEMPLATES.get(template_key, self.TASK_TEMPLATES["code"])
            # 取前3个关键步骤
            for desc in template["steps"][:3]:
                prev_step_id = add_step(f"step_{step_idx}", f"[{role_id}] {desc}", role_id)
                step_idx += 1
        
        add_step(f"step_{step_idx}", "suri 汇总各角色输出，整合交付", "suri")
        
        return TaskPlan(
            task_name=task_text[:50],
            steps=steps,
            involved_roles=roles,
        )
    
    def _generic_plan(self, task_text: str) -> TaskPlan:
        """通用任务规划（无匹配角色时）"""
        steps = [
            TaskStep(step_id="step_1", description="分析需求，识别任务类型", status="pending", assignee="suri"),
            TaskStep(step_id="step_2", description="匹配最合适的执行角色", status="pending", assignee="suri"),
            TaskStep(step_id="step_3", description="执行具体任务", status="pending", assignee="suri"),
            TaskStep(step_id="step_4", description="验证结果，向用户交付", status="pending", assignee="suri"),
        ]
        return TaskPlan(
            task_name=task_text[:50],
            steps=steps,
            involved_roles=["suri"],
        )
    
    def _map_type_to_template(self, role_type: Optional[str]) -> str:
        """角色类型映射到任务模板"""
        mapping = {
            "maintainer": "code",
            "reviewer": "review",
            "specialist": "statistics",
            "admin": "role_creation",
            "scheduler": "code",
        }
        return mapping.get(role_type, "code")
    
    def generate_plan_prompt(self, task_text: str, matched_roles: List[str]) -> str:
        """
        生成调用 LLM 的规划 prompt（当需要更智能的分解时使用）
        
        返回 prompt 文本，由调用方传给 model_manager.chat()
        """
        role_descriptions = []
        for role_id in matched_roles:
            nickname = self.config.get_role_nickname(role_id)
            capabilities = self.config.get_role_capabilities(role_id)
            role_descriptions.append(f"- {nickname} ({role_id}): {', '.join(capabilities)}")
        
        prompt = f"""你是一个任务规划专家。请为以下需求生成详细的任务分解方案。

用户需求：{task_text}

涉及角色：
{chr(10).join(role_descriptions)}

请按以下格式输出 JSON：
{{
  "task_name": "任务名称",
  "steps": [
    {{"step_id": "1", "description": "步骤描述", "assignee": "角色ID", "estimated_time": 120}}
  ],
  "dependencies": ["前置依赖描述"]
}}

要求：
1. 每个步骤有明确的执行者
2. 标注每个步骤的预估耗时（秒）
3. 无依赖的步骤可以并行
4. 只输出 JSON，不要其他内容"""
        return prompt
    
    def parse_llm_plan(self, llm_response: str, task_text: str) -> TaskPlan:
        """解析 LLM 生成的规划 JSON"""
        import json
        try:
            # 提取 JSON
            if "```json" in llm_response:
                json_str = llm_response.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_response:
                json_str = llm_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = llm_response.strip()
            
            data = json.loads(json_str)
            steps = []
            for s in data.get("steps", []):
                steps.append(TaskStep(
                    step_id=s.get("step_id", f"step_{len(steps)+1}"),
                    description=s.get("description", ""),
                    status="pending",
                    assignee=s.get("assignee", ""),
                    estimated_time=s.get("estimated_time"),
                ))
            
            return TaskPlan(
                task_name=data.get("task_name", task_text[:50]),
                steps=steps,
                involved_roles=list(set(s.assignee for s in steps if s.assignee)),
                dependencies=data.get("dependencies", []),
            )
        except Exception:
            # 解析失败时回退到规则生成
            return self._generic_plan(task_text)
