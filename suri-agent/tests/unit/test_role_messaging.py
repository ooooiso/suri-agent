"""
角色通信与构建测试

覆盖模块:
- role.messenger: RoleMessenger
- role.builder: RoleBuilder
- role.coordinator: RoleCoordinator

关联文档: suri-agent/role/role.md
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from role.messenger import RoleMessenger
from role.builder import RoleBuilder
from role.coordinator import RoleCoordinator


class TestRoleMessenger:
    """角色通信管理器测试"""

    @pytest.fixture
    def tmp_project(self, tmp_path):
        """创建临时项目结构"""
        group_dir = tmp_path / "group" / "central"
        group_dir.mkdir(parents=True)
        for role in ["suri", "suri_dev", "suri_hr", "suri_stats"]:
            rdir = group_dir / role
            rdir.mkdir()
            (rdir / f"{role}.md").write_text(
                f"---\nrole_id: {role}\ndepartment: central\n---\n", encoding="utf-8"
            )
        yield tmp_path
        shutil.rmtree(tmp_path, ignore_errors=True)

    @pytest.fixture
    def messenger(self, tmp_project):
        """创建 RoleMessenger 实例"""
        from infrastructure.config import ConfigService
        config = ConfigService(tmp_project)
        config.load_all()
        return RoleMessenger(tmp_project, config=config)

    def _make_message(self, **overrides):
        """辅助：构建标准消息"""
        base = {
            "message_id": "msg_001",
            "sender_role": "suri_dev",
            "receiver_role": "suri_hr",
            "timestamp": "2026-05-01T10:00:00",
            "priority": "normal",
            "task_ref": "task_001",
            "body": {"type": "task", "content": "请帮我创建一个新角色"},
        }
        base.update(overrides)
        return base

    def test_send_valid_message(self, messenger):
        """M01: 发送有效消息应成功"""
        msg = self._make_message()
        result = messenger.send(msg)
        assert result["success"] is True
        assert result["routed"] is True
        assert result["channel"] == "department_group"

    def test_send_missing_required_field(self, messenger):
        """M02: 缺少必填字段应失败"""
        msg = self._make_message()
        del msg["message_id"]
        result = messenger.send(msg)
        assert result["success"] is False
        assert "缺少必填字段" in result["error"]

    def test_send_invalid_body_type(self, messenger):
        """M03: 无效的 body.type 应失败"""
        msg = self._make_message(body={"type": "invalid_type", "content": "test"})
        result = messenger.send(msg)
        assert result["success"] is False
        assert "无效的 body.type" in result["error"]

    def test_send_invalid_priority(self, messenger):
        """M04: 无效的 priority 应失败"""
        msg = self._make_message(priority="urgent")
        result = messenger.send(msg)
        assert result["success"] is False
        assert "无效的 priority" in result["error"]

    def test_self_communication(self, messenger):
        """M05: 自己给自己发消息应允许"""
        msg = self._make_message(sender_role="suri_dev", receiver_role="suri_dev")
        result = messenger.send(msg)
        assert result["success"] is True
        assert result["channel"] == "self"

    def test_cross_department_director_communication(self, messenger):
        """M06: 跨部门总监级通信应允许"""
        # 创建 central 和 design 部门的总监角色（ID 需包含 _admin/_director/_lead）
        design_dir = messenger.project_root / "group" / "design"
        design_dir.mkdir(parents=True)
        (design_dir / "design_director").mkdir()
        (design_dir / "design_director" / "design_director.md").write_text(
            "---\nrole_id: design_director\ndepartment: design\n---\n", encoding="utf-8"
        )
        # central 部门也创建一个 admin 角色
        central_admin_dir = messenger.project_root / "group" / "central" / "central_admin"
        central_admin_dir.mkdir()
        (central_admin_dir / "central_admin.md").write_text(
            "---\nrole_id: central_admin\ndepartment: central\n---\n", encoding="utf-8"
        )
        messenger.config.load_all()
        
        # central_admin (含 _admin) → design_director (含 _director) 应允许
        msg = self._make_message(sender_role="central_admin", receiver_role="design_director")
        result = messenger.send(msg)
        assert result["success"] is True

    def test_cross_department_non_director_blocked(self, messenger):
        """M07: 跨部门非总监通信应被拒绝"""
        # 创建 design 部门的普通角色
        design_dir = messenger.project_root / "group" / "design"
        design_dir.mkdir(parents=True)
        (design_dir / "designer").mkdir()
        (design_dir / "designer" / "designer.md").write_text(
            "---\nrole_id: designer\ndepartment: design\n---\n", encoding="utf-8"
        )
        messenger.config.load_all()
        
        msg = self._make_message(sender_role="suri_dev", receiver_role="designer")
        result = messenger.send(msg)
        assert result["success"] is False
        assert "跨部门通信被拒绝" in result["error"]

    def test_suri_can_communicate_with_anyone(self, messenger):
        """M08: suri 可与任何角色通信"""
        msg = self._make_message(sender_role="suri", receiver_role="suri_stats")
        result = messenger.send(msg)
        assert result["success"] is True

    def test_retention_days(self, messenger):
        """M09: 不同消息类型的留存天数"""
        assert messenger._get_retention_days({"body": {"type": "approval"}}) == 90
        assert messenger._get_retention_days({"body": {"type": "task"}}) == 30
        assert messenger._get_retention_days({"body": {"type": "notify"}}) == 30
        assert messenger._get_retention_days({"body": {"type": "escalation"}}) == 90
        assert messenger._get_retention_days({"body": {"type": "unknown"}}) == 30

    def test_channel_selection(self, messenger):
        """M10: 通道选择逻辑"""
        assert messenger._get_channel("suri_dev", "suri_dev") == "self"
        assert messenger._get_channel("suri_dev", "suri_hr") == "department_group"

    def test_project_targets_same_department(self, messenger):
        """M11: 同部门通信投影到该部门群"""
        targets = messenger._get_project_targets("suri_dev", "suri_hr")
        assert "tg:central" in targets

    def test_project_targets_cross_department(self, messenger):
        """M12: 跨部门通信投影到双方+中枢群"""
        # 创建 design 部门
        design_dir = messenger.project_root / "group" / "design"
        design_dir.mkdir(parents=True)
        (design_dir / "designer").mkdir()
        (design_dir / "designer" / "designer.md").write_text(
            "---\nrole_id: designer\ndepartment: design\n---\n", encoding="utf-8"
        )
        messenger.config.load_all()
        
        targets = messenger._get_project_targets("suri_dev", "designer")
        assert "tg:central" in targets
        assert "tg:design" in targets


class TestRoleBuilder:
    """角色构建器测试"""

    @pytest.fixture
    def tmp_project(self, tmp_path):
        group_dir = tmp_path / "group"
        group_dir.mkdir()
        yield tmp_path
        shutil.rmtree(tmp_path, ignore_errors=True)

    @pytest.fixture
    def builder(self, tmp_project):
        return RoleBuilder(tmp_project)

    def test_create_role_success(self, builder, tmp_project):
        """B01: 成功创建角色"""
        result = builder.create_role("test_role", "测试角色", "central", "specialist")
        assert result["success"] is True
        assert result["role_id"] == "test_role"
        
        role_dir = tmp_project / "group" / "central" / "test_role"
        assert role_dir.exists()
        assert (role_dir / "test_role.md").exists()
        assert (role_dir / "memories").exists()
        assert (role_dir / "memories" / "insights").exists()
        assert (role_dir / "memories" / "patterns").exists()
        assert (role_dir / "reference").exists()
        assert (role_dir / "skills").exists()
        assert (role_dir / "reference" / "files_i_use.md").exists()
        assert (role_dir / "skills" / "skills.md").exists()

    def test_create_role_invalid_id(self, builder):
        """B02: 无效的角色 ID 应失败"""
        result = builder.create_role("Test-Role", "测试")
        assert result["success"] is False
        assert "无效的角色 ID" in result["error"]

    def test_create_role_duplicate(self, builder):
        """B03: 重复创建应失败"""
        builder.create_role("dup_role", "重复角色")
        result = builder.create_role("dup_role", "重复角色")
        assert result["success"] is False
        assert "已存在" in result["error"]

    def test_validate_soul_valid(self, builder, tmp_project):
        """B04: 验证有效的 Soul 文件"""
        soul_path = tmp_project / "test_soul.md"
        soul_path.write_text(
            "---\nrole_id: test\n---\n\n# Test\n\n## 人设\n\n## 职责\n\n## 能力边界\n",
            encoding="utf-8"
        )
        result = builder.validate_soul(soul_path)
        assert result["valid"] is True

    def test_validate_soul_missing_frontmatter(self, builder, tmp_project):
        """B05: 缺少 frontmatter 应失败"""
        soul_path = tmp_project / "bad_soul.md"
        soul_path.write_text("# No frontmatter\n", encoding="utf-8")
        result = builder.validate_soul(soul_path)
        assert result["valid"] is False
        assert "缺少 YAML Frontmatter" in result["error"]

    def test_validate_soul_missing_sections(self, builder, tmp_project):
        """B06: 缺少必要章节应失败"""
        soul_path = tmp_project / "incomplete_soul.md"
        soul_path.write_text("---\nrole_id: test\n---\n\n# Test\n", encoding="utf-8")
        result = builder.validate_soul(soul_path)
        assert result["valid"] is False
        assert "缺少必要章节" in result["error"]

    def test_analyze_capabilities(self, builder):
        """B07: 能力分析基于关键词"""
        result = builder.analyze_capabilities("designer", "需要进行视觉设计和创意构思")
        assert "visual_design" in result["suggested_skills"]
        assert "creative_thinking" in result["suggested_skills"]

    def test_generate_soul_contains_required_fields(self, builder):
        """B08: 生成的 Soul 包含必要字段"""
        soul = builder._generate_soul("my_role", "我的角色", "design", "specialist")
        assert "role_id: my_role" in soul
        assert "type: specialist" in soul
        assert "department: design" in soul
        assert "## 人设" in soul
        assert "## 职责" in soul
        assert "## 能力边界" in soul


class TestRoleCoordinator:
    """角色协同调度器测试"""

    @pytest.fixture
    def tmp_project(self, tmp_path):
        group_dir = tmp_path / "group" / "central"
        group_dir.mkdir(parents=True)
        for role in ["suri", "suri_dev", "suri_stats"]:
            rdir = group_dir / role
            rdir.mkdir()
            caps = {
                "suri": ["task_analysis", "dispatch"],
                "suri_dev": ["coding", "debugging"],
                "suri_stats": ["statistics", "reporting"],
            }
            (rdir / f"{role}.md").write_text(
                f"---\nrole_id: {role}\ndepartment: central\ncapabilities: {caps[role]}\n---\n",
                encoding="utf-8"
            )
        yield tmp_path
        shutil.rmtree(tmp_path, ignore_errors=True)

    @pytest.fixture
    def coordinator(self, tmp_project):
        from infrastructure.config import ConfigService
        config = ConfigService(tmp_project)
        config.load_all()
        return RoleCoordinator(tmp_project, config)

    def test_assign_task_by_capability(self, coordinator):
        """C01: 按能力匹配分配任务"""
        task = {"type": "coding", "requirement": "编写代码", "priority": "normal"}
        result = coordinator.assign_task(task, ["suri_dev", "suri_stats"])
        assert result["assigned_role"] == "suri_dev"
        assert "coding" in result["reason"]

    def test_assign_task_fallback_to_suri(self, coordinator):
        """C02: 无匹配时回退到 suri"""
        task = {"type": "unknown_task", "requirement": "未知任务"}
        result = coordinator.assign_task(task, ["suri_dev", "suri_stats"])
        assert result["assigned_role"] == "suri"

    def test_coordinate_cross_department(self, coordinator):
        """C03: 跨部门协调返回结构化结果"""
        result = coordinator.coordinate_cross_department(
            "suri_dev", ["suri_stats"], {"type": "report", "content": "统计需求"}
        )
        assert result["success"] is True
        assert result["coordinator"] == "suri"
        assert result["requester"] == "suri_dev"
        assert "providers" in result
        assert "sync_interval" in result

    def test_resolve_dependencies_no_deps(self, coordinator):
        """C04: 无依赖时状态为 ready"""
        result = coordinator.resolve_dependencies("suri_dev", [])
        assert result["status"] == "ready"
        assert result["dependencies"] == []

    def test_resolve_dependencies_with_deps(self, coordinator):
        """C05: 有依赖时状态为 waiting"""
        result = coordinator.resolve_dependencies("suri_dev", ["doc.md", "data.json"])
        assert result["status"] == "waiting"
        assert result["dependencies"] == ["doc.md", "data.json"]
