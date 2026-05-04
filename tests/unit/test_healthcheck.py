"""HealthCheck 单元测试 — 5 个用例。"""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent_framework.core.suri_core.health import HealthCheck


@pytest.fixture
def mock_project(tmp_path):
    """构建完整的最小化项目结构。"""
    # roles/
    roles_suri = tmp_path / "roles" / "suri"
    roles_suri.mkdir(parents=True)
    (roles_suri / "soul.md").write_text("# Suri Soul")
    (roles_suri / "meta.json").write_text('{"name": "suri"}')

    # agent_framework/plugins/<每个插件>
    plugins = [
        "access", "code_tool", "role_manager", "llm_gateway",
        "task_planner", "task_scheduler", "security_service",
        "config_service", "log_service", "agent_registry",
        "interrupt_handler", "test_framework",
    ]
    for p in plugins:
        pdir = tmp_path / "agent_framework" / "plugins" / p
        pdir.mkdir(parents=True)
        (pdir / "plugin.py").write_text("# plugin stub")

    # 核心目录
    core_dirs = [
        "agent_framework/core/suri_core",
        "agent_framework/event_bus",
        "agent_framework/plugin_manager",
        "agent_framework/shared/interfaces",
        "agent_framework/shared/utils",
        "prd",
        "tests",
    ]
    for d in core_dirs:
        (tmp_path / d).mkdir(parents=True)

    return tmp_path


def test_healthcheck_all_pass(mock_project):
    """完整项目结构，6 项全 pass。"""
    hc = HealthCheck(mock_project)
    results = hc.check_all()
    for name, result in results.items():
        assert result["status"] in ("pass", "warn"), f"{name} 应该 pass 或 warn: {result}"
    assert hc.all_pass() is True
    assert hc.fail_summary() == []


def test_healthcheck_db_fail():
    """模拟 DB 不可用 — 需要模拟 sqlite3.connect 抛出异常。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 创建空目录结构，只测 db
        hc = HealthCheck(root)
        with patch("agent_framework.core.suri_core.health.sqlite3.connect") as mock_conn:
            mock_conn.side_effect = Exception("模拟 SQLite 不可用")
            result = hc._check_db()
            assert result["status"] == "fail"
            assert "模拟" in result["detail"]


def test_healthcheck_roles_missing(mock_project):
    """删除 roles/ 目录，期望 fail。"""
    import shutil
    shutil.rmtree(str(mock_project / "roles"))
    hc = HealthCheck(mock_project)
    result = hc._check_roles()
    assert result["status"] == "fail"
    assert "不存在" in result["detail"]


def test_healthcheck_plugins_missing(mock_project):
    """删除某个插件目录，期望 fail。"""
    import shutil
    shutil.rmtree(str(mock_project / "agent_framework" / "plugins" / "access"))
    hc = HealthCheck(mock_project)
    result = hc._check_plugins()
    assert result["status"] == "fail"
    assert "access" in result["detail"]


def test_healthcheck_env_missing(mock_project):
    """无 .env，期望 warn。

    HealthCheck 现在支持 config_path 和 db_path 注入。
    """
    # 使用不存在的 config.json 和临时 db 路径，避免真实系统文件干扰
    tmp_config = mock_project / "config.json"
    tmp_db = mock_project / "suri.db"
    hc = HealthCheck(mock_project, config_path=tmp_config, db_path=tmp_db)
    result = hc._check_api_keys()
    assert result["status"] == "warn"
    assert ".env" in result["detail"]
    # 但 all_pass 应为 True（warn 不算 fail）
    assert hc.all_pass() is True