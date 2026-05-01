#!/usr/bin/env python3
"""
空间分离完整性测试 — 确保 group/ 与 suri-agent/ 严格分离

关联文档: AGENTS.md § 空间分离规则

验证项：
1. suri-agent/ 下不存在 group/ 子目录
2. group/ 下不存在 suri-agent/ 子目录
3. 角色工作目录只在 group/ 下，不在 suri-agent/ 下
4. 主程序代码不在 group/ 下

运行方式:
    python -m pytest suri-agent/tests/unit/test_space_separation.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest


@pytest.fixture
def project_root():
    return Path(__file__).parent.parent.parent.parent


# ────────────────────────────── S01: suri-agent 下无 group ──────────────────────────────

def test_suri_agent_has_no_group_directory(project_root):
    """S01: suri-agent/ 下禁止存在 group/ 子目录（角色数据不得混入主程序空间）"""
    suri_agent_dir = project_root / "suri-agent"
    forbidden = suri_agent_dir / "group"
    
    assert not forbidden.exists(), \
        f"发现违反空间分离规则: {forbidden} 不应存在。" \
        f"角色数据必须在根目录 group/ 下，严禁放入 suri-agent/。"


# ────────────────────────────── S02: group 下无 suri-agent ──────────────────────────────

def test_group_has_no_suri_agent_directory(project_root):
    """S02: group/ 下禁止存在 suri-agent/ 子目录（主程序代码不得混入角色空间）"""
    group_dir = project_root / "group"
    forbidden = group_dir / "suri-agent"
    
    assert not forbidden.exists(), \
        f"发现违反空间分离规则: {forbidden} 不应存在。" \
        f"主程序代码必须在 suri-agent/ 下，严禁放入 group/。"


# ────────────────────────────── S03: 角色目录只在 group/ 下 ──────────────────────────────

def test_role_directories_only_in_group(project_root):
    """S03: 所有角色工作目录必须位于 group/ 下，不得在 suri-agent/ 或 resources/ 下"""
    from infrastructure.config import ConfigService
    
    config = ConfigService(project_root)
    config.load_all()
    
    forbidden_parents = [
        project_root / "suri-agent",
        project_root / "resources",
    ]
    
    for role_id in config.list_roles(include_aliases=False):
        for parent in forbidden_parents:
            bad_path = parent / role_id
            assert not bad_path.exists(), \
                f"角色 '{role_id}' 的数据目录不应存在于 {parent}: {bad_path}"


# ────────────────────────────── S04: 主程序 .py 文件不在 group/ 下 ──────────────────────────────

def test_no_source_code_in_group(project_root):
    """S04: group/ 下不应存在属于主程序代码库的 .py 文件
    
    角色输出目录（如 output/、memories/）下的文件是角色自身生成的，允许存在。
    禁止的是把 suri-agent/ 下的核心代码文件放入 group/。
    """
    group_dir = project_root / "group"
    if not group_dir.exists():
        return
    
    # 只检查直接位于 group/ 下或角色根目录下的 .py 文件
    # 排除角色输出目录（output/、memories/、skills/ 等）下的文件
    excluded_dirs = {'output', 'memories', 'skills', 'reference', 'reports'}
    
    py_files = []
    for f in group_dir.rglob("*.py"):
        rel_parts = f.relative_to(group_dir).parts
        # 如果文件位于 excluded 目录下，跳过
        if any(part in excluded_dirs for part in rel_parts[:-1]):
            continue
        py_files.append(f)
    
    assert len(py_files) == 0, \
        f"group/ 下发现 {len(py_files)} 个不应存在的 .py 文件（主程序代码不得混入角色根目录）: " \
        f"{[str(p.relative_to(project_root)) for p in py_files]}"


# ────────────────────────────── S05: 禁止同名嵌套目录 ──────────────────────────────

def test_no_self_nested_directories(project_root):
    """S05: 禁止同名目录嵌套（如 suri-agent/suri-agent/）"""
    found = []
    
    for dirpath in project_root.rglob("*/"):
        # 只检查项目根目录下直接的项目级目录
        if dirpath == project_root:
            continue
        try:
            rel = dirpath.relative_to(project_root)
        except ValueError:
            continue
        
        parts = rel.parts
        if len(parts) >= 2:
            for i in range(len(parts) - 1):
                if parts[i] == parts[i + 1]:
                    found.append(str(rel))
                    break
    
    assert len(found) == 0, \
        f"发现 {len(found)} 个同名嵌套目录，这是路径计算错误的结果: {found}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
