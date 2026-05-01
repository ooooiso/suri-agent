#!/usr/bin/env python3
"""
CLI 回归测试 — 覆盖 V3.0 导入错误与自动刷新机制

关联文档: suri-agent/access/tui/tui.md

验证项：
1. typing.Dict 缺失导致的 NameError 不再发生（R01）
2. SuriTerminal V3.0 属性在 __init__ 中已声明（R02）
3. _build_dynamic_routes 返回类型签名使用 Dict（R03）
4. _compute_code_snapshot 返回有效字符串（R04）
5. _check_code_change 能正确检测代码变更（R05）
6. _perform_reload 方法存在且签名正确（R06）
7. suri_process 任务完成后包含自动刷新检测逻辑（R07）

运行方式:
    python -m pytest suri-agent/tests/unit/test_cli_regression.py -v
"""

import sys
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest


# ────────────────────────────── R01: 导入回归 ──────────────────────────────

def test_cli_import_no_name_error():
    """R01: cli.py 必须能完整导入，不因 typing.Dict 缺失而抛出 NameError"""
    # 如果 typing.Dict 缺失，_build_dynamic_routes 的类型注解会在类定义时触发 NameError
    try:
        from access.tui.cli import SuriTerminal
    except NameError as e:
        pytest.fail(f"cli.py 导入失败 (NameError): {e}")
    except Exception as e:
        pytest.fail(f"cli.py 导入失败 (其他错误): {type(e).__name__}: {e}")

    assert SuriTerminal is not None


# ────────────────────────────── R02: V3.0 属性 ──────────────────────────────

def test_suri_terminal_v3_attributes_in_initialize():
    """R02: initialize() 方法中必须初始化全部 V3.0 属性"""
    from access.tui.cli import SuriTerminal
    import inspect

    source = inspect.getsource(SuriTerminal.initialize)

    v3_attrs = [
        "self.task_state",           # core.task_state.TaskStateService
        "self.agent_registry",       # core.agent_registry.AgentRegistry
        "self.state_card",           # core.state_card.StateCardRenderer
        "self.task_plan",            # core.task_plan.TaskPlanService
        "self.message_bus",          # core.message_bus.MessageBus
        "self.interrupt_handler",    # core.interrupt_handler.InterruptHandler
        "self.department_registry",  # core.department_registry.DepartmentRegistry
    ]

    for attr in v3_attrs:
        assert attr in source, f"initialize() 源码中缺少 V3.0 属性赋值: {attr}"


# ────────────────────────────── R03: 类型签名 ──────────────────────────────

def test_build_dynamic_routes_uses_dict_annotation():
    """R03: _build_dynamic_routes 的类型注解必须引用 Dict（typing.Dict 已导入）"""
    from access.tui.cli import SuriTerminal
    import inspect

    sig = inspect.signature(SuriTerminal._build_dynamic_routes)
    return_annotation = sig.return_annotation

    # 返回注解应为 Dict[str, List[OutputChannel]] 或等价的字符串/泛型形式
    # Python 3.9 可能已解析为 typing._GenericAlias，也可能保留为字符串
    assert return_annotation is not inspect.Signature.empty, \
        "_build_dynamic_routes 缺少返回类型注解"

    annotation_str = str(return_annotation)
    assert "Dict" in annotation_str, \
        f"返回类型注解应包含 Dict，实际为: {annotation_str}"


# ────────────────────────────── R04: 代码快照 ──────────────────────────────

def test_compute_code_snapshot_returns_string():
    """R04: _compute_code_snapshot 必须返回非空字符串"""
    from access.tui.cli import SuriTerminal

    term = SuriTerminal()
    snapshot = term._compute_code_snapshot()

    assert isinstance(snapshot, str), f"快照应为字符串，实际为 {type(snapshot)}"
    assert len(snapshot) > 0, "快照不应为空（suri-agent/ 下应存在 .py 文件）"

    # 格式应为浮点数字符串（mtime 之和）
    try:
        float(snapshot)
    except ValueError:
        pytest.fail(f"快照格式错误，应为数字字符串: {snapshot}")


def test_compute_code_snapshot_consistent():
    """R04b: 连续调用应返回相同快照（文件未修改时）"""
    from access.tui.cli import SuriTerminal

    term = SuriTerminal()
    s1 = term._compute_code_snapshot()
    s2 = term._compute_code_snapshot()

    assert s1 == s2, f"未修改代码时快照应一致: {s1} != {s2}"


# ────────────────────────────── R05: 变更检测 ──────────────────────────────

def test_check_code_change_no_change():
    """R05: 代码未变更时 _check_code_change 返回 False"""
    from access.tui.cli import SuriTerminal

    term = SuriTerminal()
    term._code_snapshot = term._compute_code_snapshot()

    assert term._check_code_change() is False, "代码未变更时应返回 False"


def test_check_code_change_detects_modification():
    """R05b: 修改文件后 _check_code_change 返回 True"""
    from access.tui.cli import SuriTerminal

    term = SuriTerminal()

    # 使用临时目录模拟 suri-agent 代码目录
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # 创建一个假的 suri-agent 子目录和 .py 文件
        agent_dir = tmp_path / "suri-agent"
        agent_dir.mkdir()
        dummy_file = agent_dir / "dummy.py"
        dummy_file.write_text("# dummy")

        # 临时替换 project_root
        original_root = term.project_root
        term.project_root = tmp_path

        try:
            term._code_snapshot = term._compute_code_snapshot()

            # 未变更
            assert term._check_code_change() is False

            # 修改文件
            time.sleep(0.1)  # 确保 mtime 变化
            dummy_file.write_text("# modified")

            # 应检测到变更
            assert term._check_code_change() is True, \
                "修改 .py 文件后应检测到代码变更"
        finally:
            term.project_root = original_root


# ────────────────────────────── R06: 热重载方法 ──────────────────────────────

def test_perform_reload_exists():
    """R06: _perform_reload 方法必须存在且接受 reason 参数"""
    from access.tui.cli import SuriTerminal
    import inspect

    assert hasattr(SuriTerminal, '_perform_reload'), \
        "SuriTerminal 缺少 _perform_reload 方法"

    sig = inspect.signature(SuriTerminal._perform_reload)
    params = list(sig.parameters.keys())

    # 参数应为 self, reason
    assert 'reason' in params, \
        f"_perform_reload 应接受 reason 参数，实际参数: {params}"

    # reason 应有默认值
    reason_param = sig.parameters['reason']
    assert reason_param.default is not inspect.Parameter.empty, \
        "reason 参数应有默认值"


# ────────────────────────────── R07: 自动刷新逻辑 ──────────────────────────────

def test_suri_process_contains_reload_check():
    """R07: suri_process 方法源码中必须包含自动刷新检测逻辑"""
    from access.tui.cli import SuriTerminal
    import inspect

    source = inspect.getsource(SuriTerminal.suri_process)

    assert "_check_code_change" in source, \
        "suri_process 应调用 _check_code_change 进行代码变更检测"
    assert "_perform_reload" in source, \
        "suri_process 应在检测到变更后调用 _perform_reload"


# ────────────────────────────── 辅助：命令注册表 ──────────────────────────────

def test_reload_command_handled():
    """R08: handle_command 方法中必须处理 /reload 命令"""
    from access.tui.cli import SuriTerminal
    import inspect

    source = inspect.getsource(SuriTerminal.handle_command)

    assert "'/reload'" in source or '"/reload"' in source, \
        "handle_command 源码中未处理 /reload 命令"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
