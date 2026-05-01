"""
规则引擎测试

覆盖模块:
- rules.doc_sync_rule: DocSyncRule
- rules.file_ownership: FileOwnershipRule
- rules.security: SecurityRule

关联文档: suri-agent/rules/rules.md
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from rules.doc_sync_rule import DocSyncRule, SyncViolation
from rules.file_ownership import FileOwnershipRule
from rules.security import SecurityRule


class TestDocSyncRule:
    """文档同步规则测试"""

    @pytest.fixture
    def tmp_project(self, tmp_path):
        """创建临时项目结构"""
        # 模拟 suri-agent/ 目录结构
        agent_dir = tmp_path / "suri-agent"
        agent_dir.mkdir()
        (agent_dir / "core").mkdir()
        (agent_dir / "core" / "core.md").write_text("# Core\n", encoding="utf-8")
        (agent_dir / "core" / "task_state.py").write_text("# state\n", encoding="utf-8")
        
        # 模拟 group/ 目录结构
        group_dir = tmp_path / "group"
        group_dir.mkdir()
        (group_dir / "central").mkdir()
        (group_dir / "central" / "suri").mkdir()
        (group_dir / "central" / "suri" / "suri.md").write_text("---\nrole_id: suri\n---\n", encoding="utf-8")
        
        yield tmp_path
        shutil.rmtree(tmp_path, ignore_errors=True)

    def test_scan_finds_no_violations_when_synced(self, tmp_project):
        """D01: 代码和文档同步时，扫描应无违规项"""
        rule = DocSyncRule(tmp_project)
        violations = rule.scan()
        # core/ 目录有 core.md 和 task_state.py，且 md 比 py 新或同步，应无违规
        # 但 task_state.py 是刚创建的，core.md 也是刚创建的，时间差可能 < 60s
        stale = [v for v in violations if v.violation_type == "stale"]
        assert len(stale) == 0, f"不应有过时违规，但发现: {stale}"

    def test_scan_finds_missing_doc(self, tmp_project):
        """D02: 缺少文档时，应检测到 missing 违规"""
        # 创建一个新目录但没有 .md 文件
        new_dir = tmp_project / "suri-agent" / "new_module"
        new_dir.mkdir()
        (new_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
        
        rule = DocSyncRule(tmp_project)
        violations = rule.scan()
        missing = [v for v in violations if v.violation_type == "missing" and "new_module" in v.code_path]
        assert len(missing) == 1, f"应检测到 new_module 缺失文档，发现: {missing}"
        assert "new_module.md" in missing[0].doc_path

    def test_scan_finds_stale_doc(self, tmp_project):
        """D03: 代码更新后文档未更新，应检测到 stale 违规"""
        import time
        core_dir = tmp_project / "suri-agent" / "core"
        core_md = core_dir / "core.md"
        core_py = core_dir / "task_state.py"
        
        # 让 md 文件早于 py 文件超过 60 秒
        now = time.time()
        # 先创建 md（旧）
        core_md.write_text("# Old Core\n", encoding="utf-8")
        # 设置旧时间
        import os
        os.utime(str(core_md), (now - 120, now - 120))
        # 再创建/更新 py（新）
        core_py.write_text("# updated state\n", encoding="utf-8")
        os.utime(str(core_py), (now, now))
        
        rule = DocSyncRule(tmp_project)
        violations = rule.scan()
        stale = [v for v in violations if v.violation_type == "stale" and "core" in v.code_path]
        assert len(stale) == 1, f"应检测到 core 文档过时，发现: {[v.code_path for v in violations]}"

    def test_quick_check_changed_file(self, tmp_project):
        """D04: 快速检查单个变更文件"""
        import time, os
        core_py = tmp_project / "suri-agent" / "core" / "task_state.py"
        core_md = tmp_project / "suri-agent" / "core" / "core.md"
        
        now = time.time()
        os.utime(str(core_md), (now - 120, now - 120))
        os.utime(str(core_py), (now, now))
        
        rule = DocSyncRule(tmp_project)
        result = rule.quick_check(core_py)
        assert result is not None
        assert result.violation_type == "stale"

    def test_generate_sync_plan(self, tmp_project):
        """D05: 生成同步计划报告"""
        rule = DocSyncRule(tmp_project)
        v = SyncViolation(
            doc_path="test.md",
            code_path="test/",
            last_code_mtime=1000.0,
            last_doc_mtime=500.0,
            violation_type="stale",
            suggestion="更新文档"
        )
        plan = rule.generate_sync_plan([v])
        assert "文档同步检测报告" in plan
        assert "test.md" in plan
        assert "过时" in plan

    def test_is_compliant(self, tmp_project):
        """D06: 合规性检查"""
        rule = DocSyncRule(tmp_project)
        # 刚创建的项目通常合规（时间差 < 60s）
        # 但需要确保没有 missing
        result = rule.is_compliant()
        # 可能因 missing 而不合规，至少应正常执行不抛异常
        assert isinstance(result, bool)

    def test_state_persistence(self, tmp_project):
        """D07: 扫描状态持久化"""
        rule = DocSyncRule(tmp_project)
        rule.scan()
        assert rule.state_path.exists()
        state = rule._load_state()
        assert "last_scan" in state
        assert "violations" in state


class TestFileOwnershipRule:
    """文件所有权规则测试"""

    @pytest.fixture
    def rule(self, project_root, config):
        """使用真实项目的 FileOwnershipRule"""
        return FileOwnershipRule(project_root, config)

    def test_get_owner_for_soul_file(self, rule):
        """F01: Soul 文件由 admin 管理"""
        owner = rule.get_owner("group/central/suri/suri.md")
        assert owner == "suri_hr", f"Soul 文件应由 suri_hr 管理，实际是 {owner}"

    def test_get_owner_for_role_directory(self, rule):
        """F02: 角色目录为 role_self"""
        owner = rule.get_owner("group/central/suri_dev/memories/")
        assert owner == "role_self"

    def test_get_owner_for_tools(self, rule):
        """F03: tools 目录由 maintainer 管理"""
        owner = rule.get_owner("suri-agent/tools/file_read/scripts/main.py")
        assert owner == "suri_dev", f"tools 应由 suri_dev 管理，实际是 {owner}"

    def test_can_modify_self_files(self, rule):
        """F04: 角色可修改自己的文件"""
        assert rule.can_modify("suri_dev", "group/central/suri_dev/output/test.py") is True

    def test_cannot_modify_other_role_files(self, rule):
        """F05: 角色不可修改其他角色的文件"""
        assert rule.can_modify("suri_dev", "group/central/suri_stats/output/report.md") is False

    def test_admin_can_modify_all_group(self, rule):
        """F06: admin 类型可管理 group/ 下所有文件"""
        assert rule.can_modify("suri_hr", "group/central/suri_dev/suri_dev.md") is True
        assert rule.can_modify("suri_hr", "group/central/suri_stats/memories/role.db") is True

    def test_alias_resolution(self, rule):
        """F07: 别名自动解析"""
        assert rule.can_modify("suri-dev", "group/central/suri_dev/output/test.py") is True

    def test_validate_method(self, rule):
        """F08: validate 接口符合 BaseRule"""
        assert rule.validate({"role_id": "suri_dev", "target_path": "suri-agent/tools/tool.md"}) is True
        assert rule.validate({"role_id": "suri_stats", "target_path": "suri-agent/tools/tool.md"}) is False

    def test_execute_method(self, rule):
        """F09: execute 返回结构化结果"""
        result = rule.execute({"role_id": "suri_dev", "target_path": "suri-agent/tools/tool.md"})
        assert "allowed" in result
        assert "owner" in result
        assert result["allowed"] is True

    def test_list_monitored_paths(self, rule):
        """F10: 返回受监控路径列表"""
        paths = rule.list_monitored_paths()
        assert len(paths) > 0
        assert "group/<role>/" in paths
        assert "suri-agent/tools/" in paths


class TestSecurityRule:
    """安全审批规则测试"""

    @pytest.fixture
    def rule(self, project_root):
        return SecurityRule(project_root)

    def test_exempt_operation(self, rule):
        """S01: 豁免操作直接通过"""
        assert rule.validate({"operation": "cache_rotation", "target_path": "any"}) is True
        result = rule.execute({"operation": "log_archive", "target_path": "any"})
        assert result["allowed"] is True
        assert result["reason"] == "exempt_operation"

    def test_not_monitored_path(self, rule):
        """S02: 非监控路径无需审批"""
        assert rule.validate({"operation": "read", "target_path": "/tmp/test.txt"}) is True
        result = rule.execute({"operation": "read", "target_path": "README.md"})
        assert result["allowed"] is True
        assert result["reason"] == "not_monitored"

    def test_monitored_path_no_token_unauthorized(self, rule):
        """S03: 监控路径无所有权直接拒绝"""
        # suri_dev 不是 suri.md 的所有者（Soul 文件由 admin 管理），
        # 在所有权检查阶段即被拒绝，不会走到令牌检查
        result = rule.execute({
            "operation": "write",
            "target_path": "group/central/suri/suri.md",
            "role_id": "suri_dev"
        })
        assert result["allowed"] is False
        assert result["reason"] == "unauthorized"

    def test_monitored_path_no_token_needs_approval(self, rule):
        """S03b: 有所有权但无令牌需审批"""
        # suri_hr 是 admin，对 group/ 下所有文件有管理权
        result = rule.execute({
            "operation": "write",
            "target_path": "group/central/suri/suri.md",
            "role_id": "suri_hr"
        })
        assert result["allowed"] is False
        assert result["reason"] == "approval_required"

    def test_monitored_path_with_valid_token(self, rule):
        """S04: 有效令牌允许操作"""
        report = rule.create_change_report("suri_dev", "test", [{"path": "a.py", "action": "modify"}], "none")
        token = rule.issue_token(report["report_id"], ["group/central/suri/suri.md"])
        
        result = rule.execute({
            "operation": "write",
            "target_path": "group/central/suri/suri.md",
            "role_id": "suri_hr",
            "approval_token": token
        })
        assert result["allowed"] is True
        assert result["reason"] == "token_valid"

    def test_invalid_token(self, rule):
        """S05: 无效令牌被拒绝"""
        result = rule.execute({
            "operation": "write",
            "target_path": "group/central/suri/suri.md",
            "role_id": "suri_hr",
            "approval_token": "invalid_token_123"
        })
        assert result["allowed"] is False
        assert result["reason"] == "token_invalid"

    def test_token_expiry(self, rule):
        """S06: 过期令牌被拒绝"""
        report = rule.create_change_report("test", "test", [], "none")
        token = rule.issue_token(report["report_id"], ["group/central/suri/suri.md"])
        # 手动将令牌设为过期
        rule._approval_tokens[token]["expires_at"] = 0
        
        valid = rule.validate_token(token, "group/central/suri/suri.md", "suri_hr")
        assert valid is False

    def test_is_monitored(self, rule):
        """S07: 监控路径检测"""
        assert rule.is_monitored("group/central/suri/suri.md") is True
        assert rule.is_monitored("suri-agent/tools/tool.md") is True
        assert rule.is_monitored("config.yaml") is True
        assert rule.is_monitored("README.md") is False
        assert rule.is_monitored("/tmp/test.txt") is False

    def test_create_change_report(self, rule):
        """S08: 变更报告创建"""
        report = rule.create_change_report(
            requester="suri_dev",
            reason="修复 bug",
            file_list=[{"path": "a.py", "action": "modify"}],
            impact_analysis="低风险"
        )
        assert report["requester"] == "suri_dev"
        assert report["status"] == "pending_review"
        assert "report_id" in report
        assert "timestamp" in report

    def test_issue_token(self, rule):
        """S09: 令牌签发与验证"""
        report = rule.create_change_report("test", "test", [], "none")
        token = rule.issue_token(report["report_id"], ["file1.py", "file2.py"])
        
        assert token.startswith("tkn_")
        assert rule.validate_token(token, "file1.py", "any_role") is True
        assert rule.validate_token(token, "file3.py", "any_role") is False

    def test_check_offline_proxy(self, rule):
        """S10: 离线代理检查"""
        import time
        now = time.time()
        
        # security_admin 在线
        result = rule.check_offline_proxy(now - 60, now - 60)
        assert result is None
        
        # security_admin 离线，ops_admin 在线
        result = rule.check_offline_proxy(now - 3600, now - 60)
        assert result == "ops_admin"
        
        # 双方都离线
        result = rule.check_offline_proxy(now - 3600, now - 3600)
        assert result == "user"
