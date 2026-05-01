#!/usr/bin/env python3
"""
Suri 统一测试入口

运行方式:
    python suri-agent/tests/run.py                  # 运行全部测试
    python suri-agent/tests/run.py --unit           # 只跑单元测试
    python suri-agent/tests/run.py --fullforce      # 只跑全力量测试
    python suri-agent/tests/run.py --list           # 列出所有测试
    python suri-agent/tests/run.py --pytest         # 用 pytest 运行 pytest 格式测试

关联文档: suri-agent/tests/README.md
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

# 颜色
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; RST = '\033[0m'


def get_tests_dir() -> Path:
    """获取 tests 目录"""
    return Path(__file__).parent


def discover_tests(tests_dir: Path, category: str = "all") -> List[Dict]:
    """
    发现测试文件

    Args:
        category: 'unit' | 'fullforce' | 'all'

    Returns:
        测试文件信息列表，每项包含 file、dir、category、is_pytest
    """
    results = []
    dirs = []

    if category in ("all", "unit"):
        dirs.append(("unit", tests_dir / "unit"))
    if category in ("all", "fullforce"):
        dirs.append(("fullforce", tests_dir / "fullforce"))

    for cat_name, dir_path in dirs:
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.glob("*.py")):
            if f.name.startswith("_"):
                continue
            if f.name == "__init__.py":
                continue
            # 检测是否为 pytest 格式
            content = f.read_text(encoding="utf-8")
            is_pytest = "import pytest" in content or "pytest.main" in content
            results.append({
                "file": f.name,
                "dir": cat_name,
                "path": f,
                "is_pytest": is_pytest,
                "category": cat_name,
            })

    return results


def check_model_config() -> bool:
    """检查是否已配置模型"""
    tests_dir = get_tests_dir()
    project_root = tests_dir.parent.parent
    model_config = project_root / "model_config.json"
    if model_config.exists():
        import json
        try:
            with open(model_config) as f:
                data = json.load(f)
                return len(data) > 0
        except Exception:
            pass
    return False


def run_pytest_test(test_path: Path, tests_dir: Path) -> Tuple[bool, str, int]:
    """运行 pytest 格式测试"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(tests_dir.parent.parent)
        )
        output = result.stdout + (result.stderr if result.stderr else "")
        success = result.returncode == 0
        return success, output, result.returncode
    except subprocess.TimeoutExpired:
        return False, f"超时 (>5分钟)", -1
    except Exception as e:
        return False, f"运行异常: {e}", -1


def run_script_test(test_path: Path, tests_dir: Path) -> Tuple[bool, str, int]:
    """运行独立脚本格式测试"""
    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=True,
            text=True,
            timeout=900,  # 15分钟超时
            cwd=str(tests_dir.parent.parent)
        )
        output = result.stdout + (result.stderr if result.stderr else "")
        success = result.returncode == 0
        return success, output, result.returncode
    except subprocess.TimeoutExpired:
        return False, f"超时 (>15分钟)", -1
    except Exception as e:
        return False, f"运行异常: {e}", -1


def main():
    parser = argparse.ArgumentParser(description='Suri 统一测试入口')
    parser.add_argument('--unit', action='store_true', help='只跑单元测试')
    parser.add_argument('--fullforce', action='store_true', help='只跑全力量测试')
    parser.add_argument('--all', action='store_true', help='运行全部测试（默认）')
    parser.add_argument('--list', action='store_true', help='列出所有测试')
    parser.add_argument('--pytest', action='store_true', help='只运行 pytest 格式测试')
    parser.add_argument('--skip-model-tests', action='store_true',
                        help='跳过需要模型的测试')
    args = parser.parse_args()

    tests_dir = get_tests_dir()
    project_root = tests_dir.parent.parent

    # 确定分类
    category = "all"
    if args.unit:
        category = "unit"
    elif args.fullforce:
        category = "fullforce"

    # 发现测试
    tests = discover_tests(tests_dir, category)

    if args.pytest:
        tests = [t for t in tests if t["is_pytest"]]

    # 列出模式
    if args.list:
        print("=" * 70)
        print("Suri 测试清单")
        print("=" * 70)
        current_cat = ""
        for test in tests:
            if test["category"] != current_cat:
                current_cat = test["category"]
                cat_name = {'unit': '单元测试', 'fullforce': '全力量测试'}.get(current_cat, current_cat)
                print(f"\n【{cat_name}】")
            fmt = "[pytest]" if test["is_pytest"] else "[script]"
            print(f"  {fmt:10s} {test['dir']}/{test['file']}")
        print("")
        return 0

    if not tests:
        print("没有符合条件的测试")
        return 0

    # 检查模型配置
    has_model = check_model_config()

    # 运行测试
    print("=" * 70)
    cat_display = {'unit': '单元测试', 'fullforce': '全力量测试', 'all': '全部测试'}.get(category, category)
    print(f"Suri 测试运行 — {cat_display} ({len(tests)} 项)")
    print("=" * 70)
    print("")

    passed = 0
    failed = 0
    skipped = 0
    results = []

    for i, test in enumerate(tests, 1):
        # 全力量测试需要模型
        is_model_test = test["category"] == "fullforce"
        if is_model_test and args.skip_model_tests:
            print(f"[{i}/{len(tests)}] {test['dir']}/{test['file']} ... SKIP (跳过模型测试)")
            skipped += 1
            results.append((test["file"], 'SKIP', "跳过模型测试"))
            continue

        if is_model_test and not has_model:
            print(f"[{i}/{len(tests)}] {test['dir']}/{test['file']} ... SKIP (未配置模型)")
            skipped += 1
            results.append((test["file"], 'SKIP', "未配置模型"))
            continue

        print(f"[{i}/{len(tests)}] {test['dir']}/{test['file']} ... ", end="", flush=True)

        if test["is_pytest"]:
            success, output, code = run_pytest_test(test["path"], tests_dir)
        else:
            success, output, code = run_script_test(test["path"], tests_dir)

        if success:
            print(f"{G}PASS{RST}")
            passed += 1
        else:
            print(f"{R}FAIL{RST} (exit={code})")
            failed += 1

        results.append((test["file"], 'PASS' if success else 'FAIL', output[:200] if not success else ""))

    # 汇总
    print("")
    print("=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    total_ran = passed + failed
    print(f"  总测试项: {len(tests)}")
    print(f"  {G}通过: {passed}{RST}")
    if failed:
        print(f"  {R}失败: {failed}{RST}")
    if skipped:
        print(f"  {Y}跳过: {skipped}{RST}")
    if total_ran > 0:
        print(f"  通过率: {passed / total_ran * 100:.1f}%")
    print("=" * 70)

    # 失败详情
    if failed > 0:
        print("")
        print("失败详情:")
        for name, status, detail in results:
            if status == 'FAIL':
                print(f"  {R}❌{RST} {name}")
                if detail:
                    print(f"     {detail[:150]}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
