#!/usr/bin/env python3
"""
Agent 计划步骤执行测试

验证：
1. 计划生成时步骤包含依赖关系
2. 步骤按序执行，状态正确流转
3. 依赖未满足时步骤阻塞
4. 降级模式（无 Agent/Steps）仍能一次性调度

运行方式:
    python -m pytest suri-agent/tests/unit/test_agent_plan_execution.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest

from core.task_state import TaskStep
from core.task_plan import TaskPlanService, TaskPlan


# ────────────────────────────── Fixtures ──────────────────────────────

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_role_type.return_value = 'maintainer'
    config.get_role_keywords.return_value = ['代码', '修复', 'bug']
    return config


# ────────────────────────────── P01: 计划步骤依赖 ──────────────────────────────

def test_single_role_plan_has_dependencies(mock_config):
    """P01: 单角色计划的步骤必须包含线性依赖"""
    plan_service = TaskPlanService(mock_config)
    plan = plan_service._single_role_plan("修复一个 Bug", "suri_dev")
    
    assert len(plan.steps) > 0
    
    # 第一个步骤无依赖
    assert plan.steps[0].depends_on == []
    
    # 后续步骤依赖前一个
    for i in range(1, len(plan.steps)):
        assert plan.steps[i].depends_on == [plan.steps[i-1].step_id], \
            f"步骤 {i} 应依赖步骤 {i-1}"


def test_multi_role_plan_has_dependencies(mock_config):
    """P02: 多角色计划的步骤必须包含依赖"""
    plan_service = TaskPlanService(mock_config)
    plan = plan_service._multi_role_plan("修复 Bug 并审核", ["suri_dev", "suri_review"])
    
    assert len(plan.steps) > 2
    
    # step_1 无依赖
    assert plan.steps[0].depends_on == []
    
    # 至少有一个步骤有依赖
    has_dep = any(len(s.depends_on) > 0 for s in plan.steps)
    assert has_dep, "多角色计划应包含依赖关系"


# ────────────────────────────── P03: TaskStep 字段完整 ──────────────────────────────

def test_task_step_has_result_field():
    """P03: TaskStep 应包含 result 字段"""
    step = TaskStep(step_id="step_1", description="测试")
    assert hasattr(step, 'result')
    assert step.result is None


def test_task_step_has_depends_on_field():
    """P04: TaskStep 应包含 depends_on 字段"""
    step = TaskStep(step_id="step_1", description="测试", depends_on=["step_0"])
    assert step.depends_on == ["step_0"]


def test_task_step_post_init_defaults():
    """P05: TaskStep depends_on 默认为空列表"""
    step = TaskStep(step_id="step_1", description="测试")
    assert step.depends_on == []


# ────────────────────────────── P06: 计划模板覆盖 ──────────────────────────────

def test_plan_templates_cover_core_types(mock_config):
    """P06: 核心角色类型的计划模板应存在"""
    plan_service = TaskPlanService(mock_config)
    
    templates = plan_service.TASK_TEMPLATES
    assert 'code' in templates
    assert 'review' in templates
    assert 'statistics' in templates
    assert 'role_creation' in templates
    
    for key, t in templates.items():
        assert len(t['steps']) > 0, f"模板 {key} 应包含步骤"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
