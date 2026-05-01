#!/usr/bin/env python3
"""
角色目录完整性测试 — 确保物理目录与逻辑角色一致

关联文档: AGENTS.md § 角色目录管理规则

验证项：
1. group/central/ 下的目录数 = 角色数 + 1（central.md）
2. 每个角色目录名必须等于其 canonical role_id
3. 不存在孤立的别名目录（旧命名格式的目录）
4. _get_role_dir 返回的目录必须属于 canonical 角色

运行方式:
    python -m pytest suri-agent/tests/unit/test_role_directory_integrity.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService


@pytest.fixture
def project_root():
    return Path(__file__).parent.parent.parent.parent


@pytest.fixture
def config(project_root):
    cfg = ConfigService(project_root)
    cfg.load_all()
    return cfg


# ────────────────────────────── D01: 目录数量一致性 ──────────────────────────────

def test_central_directory_count_matches_roles(config, project_root):
    """D01: group/central/ 下的子目录数应等于角色数（不含 central.md）"""
    central_dir = project_root / "group" / "central"
    
    # 所有子目录（排除文件如 central.md）
    subdirs = [d for d in central_dir.iterdir() if d.is_dir()]
    subdir_names = {d.name for d in subdirs}
    
    # 所有 canonical 角色（不含别名）
    canonical_roles = set(config.list_roles(include_aliases=False))
    
    # 每个角色的 canonical 目录必须存在
    missing_dirs = canonical_roles - subdir_names
    extra_dirs = subdir_names - canonical_roles
    
    assert not missing_dirs, f"角色缺少对应目录: {missing_dirs}"
    assert not extra_dirs, f"存在孤立目录（无对应角色）: {extra_dirs}"
    assert len(subdirs) == len(canonical_roles), \
        f"目录数({len(subdirs)}) != 角色数({len(canonical_roles)}): 子目录={subdir_names}, 角色={canonical_roles}"


# ────────────────────────────── D02: 别名目录不存在 ──────────────────────────────

def test_no_legacy_alias_directories(project_root):
    """D02: group/central/ 下不应存在旧别名格式的目录"""
    central_dir = project_root / "group" / "central"
    
    # 已知的旧别名目录名（这些在 V2.0 后应已被清理）
    legacy_names = {'analyst', 'document-review', 'suri-dev', 'suri-hr'}
    
    subdirs = {d.name for d in central_dir.iterdir() if d.is_dir()}
    found_legacy = subdirs & legacy_names
    
    assert not found_legacy, \
        f"发现遗留别名目录，应已清理: {found_legacy}"


# ────────────────────────────── D03: _get_role_dir 解析别名 ──────────────────────────────

def test_get_role_dir_resolves_alias(config, project_root):
    """D03: MemoryService._get_role_dir 对别名应返回 canonical 目录"""
    memory = MemoryService(project_root, config)
    
    alias_map = {
        'suri-dev': 'suri_dev',
        'suri-hr': 'suri_hr',
        'document-review': 'suri_review',
        'analyst': 'suri_stats',
    }
    
    for alias, canonical in alias_map.items():
        role_dir = memory._get_role_dir(alias)
        expected = project_root / "group" / "central" / canonical
        assert role_dir == expected, \
            f"别名 '{alias}' 应解析到 {expected}, 实际: {role_dir}"


def test_get_role_dir_canonical_id_unchanged(config, project_root):
    """D04: MemoryService._get_role_dir 对 canonical id 应保持不变"""
    memory = MemoryService(project_root, config)
    
    for role_id in config.list_roles(include_aliases=False):
        role_dir = memory._get_role_dir(role_id)
        expected = project_root / "group" / "central" / role_id
        assert role_dir == expected, \
            f"canonical '{role_id}' 目录路径错误: 期望 {expected}, 实际: {role_dir}"


# ────────────────────────────── D05: 角色 Soul 文件存在 ──────────────────────────────

def test_each_role_has_soul_file(config, project_root):
    """D05: 每个 canonical 角色的 Soul 文件必须存在于对应目录中"""
    for role_id in config.list_roles(include_aliases=False):
        soul_path = project_root / "group" / "central" / role_id / f"{role_id}.md"
        assert soul_path.exists(), \
            f"角色 '{role_id}' 的 Soul 文件缺失: {soul_path}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
