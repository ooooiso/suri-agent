#!/usr/bin/env python3
"""
创建对话状态机测试

验证：
1. CreationDialog 状态流转正确
2. 部门/角色/技能创建对话完整流程
3. 对话取消/回退

运行方式:
    python -m pytest suri-agent/tests/unit/test_creation_dialog.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest


class MockTerminal:
    """模拟 SuriTerminal"""
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
    
    def _execute_creation(self, action, data):
        return f"mock_created:{action}"


# ────────────────────────────── Fixtures ──────────────────────────────

@pytest.fixture
def dialog():
    from access.tui.cli import CreationDialog
    terminal = MockTerminal()
    return CreationDialog(terminal)


# ────────────────────────────── C01: 状态流转 ──────────────────────────────

def test_dialog_initial_state(dialog):
    """C01: CreationDialog 初始状态为 idle"""
    assert dialog.state == 'idle'
    assert dialog.action is None
    assert dialog.step == 0


def test_dialog_start_changes_state(dialog):
    """C02: start() 后状态变为 creating"""
    prompt = dialog.start('create_dept')
    assert dialog.state == 'creating'
    assert dialog.action == 'create_dept'
    assert dialog.step == 0
    assert len(prompt) > 0


# ────────────────────────────── C02: 部门创建对话 ──────────────────────────────

def test_dept_creation_flow(dialog):
    """C03: 部门创建对话完整流程"""
    # 开始
    r1 = dialog.start('create_dept')
    assert "创建新部门" in r1
    
    # 用户确认
    r2 = dialog.handle_input("是")
    assert r2.startswith("[CREATION]")
    assert "名称" in r2
    assert dialog.step == 1
    
    # 输入名称
    r3 = dialog.handle_input("数据分析部")
    assert r3.startswith("[CREATION]")
    assert "职责" in r3
    assert dialog.step == 2
    
    # 输入职责
    r4 = dialog.handle_input("负责数据统计与分析")
    assert r4.startswith("[CREATION]")
    assert "负责人" in r4
    assert dialog.step == 3
    
    # 输入负责人
    r5 = dialog.handle_input("suri_stats")
    assert r5.startswith("[CREATION]")
    assert "确认" in r5
    assert dialog.state == 'confirming'
    
    # 确认
    r6 = dialog.handle_input("确认")
    assert r6 == "[COMPLETE]"


# ────────────────────────────── C03: 角色创建对话 ──────────────────────────────

def test_role_creation_flow(dialog):
    """C04: 角色创建对话完整流程"""
    r1 = dialog.start('create_role', dept='central')
    assert "central" in r1
    
    r2 = dialog.handle_input("是")
    assert "名称" in r2
    
    r3 = dialog.handle_input("测试工程师")
    assert "职责" in r3
    
    r4 = dialog.handle_input("负责测试和质量保证")
    assert "确认" in r4
    assert dialog.state == 'confirming'
    
    r5 = dialog.handle_input("确认")
    assert r5 == "[COMPLETE]"


# ────────────────────────────── C04: 技能增加对话 ──────────────────────────────

def test_skill_addition_flow(dialog):
    """C05: 技能增加对话完整流程"""
    r1 = dialog.start('add_skill', role='suri_dev')
    assert "suri_dev" in r1
    
    r2 = dialog.handle_input("是")
    assert "名称" in r2
    
    r3 = dialog.handle_input("代码重构")
    assert "功能" in r3
    
    r4 = dialog.handle_input("自动检测坏味道并重构代码")
    assert "确认" in r4
    
    r5 = dialog.handle_input("确认")
    assert r5 == "[COMPLETE]"


# ────────────────────────────── C05: 取消与回退 ──────────────────────────────

def test_cancel_at_first_step(dialog):
    """C06: 第一步取消对话"""
    dialog.start('create_dept')
    r = dialog.handle_input("否")
    assert r == "[CANCELLED]"
    assert dialog.state == 'idle'


def test_cancel_by_keyword(dialog):
    """C07: 任何步骤输入'取消'都可终止"""
    dialog.start('create_dept')
    dialog.handle_input("是")  # 进入 step 1
    r = dialog.handle_input("取消")
    assert r == "[CANCELLED]"
    assert dialog.state == 'idle'


def test_modify_at_confirm(dialog):
    """C08: 确认阶段选择修改可重新收集"""
    dialog.start('create_dept')
    dialog.handle_input("是")
    dialog.handle_input("数据分析部")  # step 1
    dialog.handle_input("负责数据统计")  # step 2
    dialog.handle_input("suri_stats")  # step 3 → confirming
    
    r = dialog.handle_input("修改")
    assert r.startswith("[CREATION]")
    assert dialog.state == 'creating'
    assert dialog.step == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
