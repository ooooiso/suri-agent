#!/usr/bin/env python3
"""
统计角色（Analyst）专项测试

验证：
1. analyst 角色被 ConfigService 正确发现
2. 关键词匹配能正确调度到 analyst
3. 统计日志 JSON 结构化写入
4. 统计表结构正确
5. 聚合查询方法可用

运行方式:
    python suri-agent/tests/test_analyst_role.py
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.logger import LoggerService

G = '\033[92m'; R = '\033[91m'; RST = '\033[0m'
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def ok(id, msg): print(f"  {G}✓{RST} [{id}] {msg}")
def fail(id, msg, detail=""):
    print(f"  {R}✗{RST} [{id}] {msg}")
    if detail: print(f"      → {detail}")


def main():
    print(f"\n{'#'*70}")
    print(f"#  {' '*20}统计角色（Analyst）专项测试")
    print(f"{'#'*70}")

    passed = 0
    failed = 0

    def check(tid, cond, ok_msg, fail_msg, detail=""):
        nonlocal passed, failed
        if cond:
            ok(tid, ok_msg); passed += 1
        else:
            fail(tid, fail_msg, detail); failed += 1

    config = ConfigService(PROJECT_ROOT)
    config.load_all()
    memory = MemoryService(PROJECT_ROOT, config)
    security = SecurityService(PROJECT_ROOT, config)
    logger = LoggerService(PROJECT_ROOT)

    # A01: 角色发现（V2.0: analyst → suri_stats，别名兼容）
    roles = config.list_roles(include_aliases=True)
    check("A01", 'analyst' in roles or 'suri_stats' in roles,
          f"ConfigService 发现 analyst/suri_stats 角色（共 {len(roles)} 个角色）",
          f"analyst/suri_stats 不在角色列表中: {roles}")

    # A02: Soul 解析（V2.0: name 已改为 suri_stats，nickname 为 数据小能手）
    soul = config.get_role_soul('analyst')
    check("A02", soul is not None and soul.meta.get('role_id') == 'suri_stats',
          f"analyst Soul 正确 (role_id={soul.meta.get('role_id') if soul else 'None'})",
          "analyst Soul 解析失败")

    # A03: 关键词覆盖
    kws = config.get_role_keywords('analyst')
    expected = ['统计', 'token', '报告', '用量', '文件', '任务']
    missing = [k for k in expected if k not in kws]
    check("A03", len(missing) == 0,
          f"关键词覆盖 ({len(kws)} 个): {kws[:6]}...",
          f"缺少关键词: {missing}")

    # A04: 调度匹配验证（V2.0: analyst → suri_stats）
    test_inputs = [
        ("统计一下今天的消耗", True),
        ("生成token用量报告", True),
        ("查看文件统计", True),
        ("今天用了多少token", True),
        ("帮我写个Python程序", False),  # 不应该匹配 analyst
    ]
    all_roles = [rid for rid in config.list_roles(include_aliases=True) if rid != 'suri']
    for text, should_match in test_inputs:
        matched = False
        for role_id in all_roles:
            kws = config.get_role_keywords(role_id)
            for kw in kws:
                if kw.lower() in text.lower():
                    # V2.0: 使用 resolve_role_id 统一比较
                    resolved = ConfigService.resolve_role_id(role_id)
                    if resolved == 'suri_stats':
                        matched = True
                    break
        tid = f"A04_{text[:10]}"
        if should_match:
            if matched:
                ok(tid, f"\"{text}\" → 正确匹配 analyst/suri_stats")
                passed += 1
            else:
                fail(tid, f"\"{text}\" → 未匹配 analyst/suri_stats（应匹配）")
                failed += 1
        else:
            if not matched:
                ok(tid, f"\"{text}\" → 正确未匹配 analyst")
                passed += 1
            else:
                fail(tid, f"\"{text}\" → 错误匹配 analyst（不应匹配）")
                failed += 1

    # A05: 统计表存在
    db_path = memory._get_role_db('suri')
    import sqlite3
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='statistics'")
        has_table = cursor.fetchone() is not None
    check("A05", has_table,
          "statistics 表已创建（suri role.db）",
          "statistics 表不存在")

    # A06: 保存统计事件
    try:
        memory.save_statistic('suri', 'token_usage',
                              model_id='test-model',
                              prompt_tokens=100, completion_tokens=50, total_tokens=150,
                              task_hint='测试统计事件')
        stats = memory.get_statistics('suri', 'token_usage', limit=5)
        check("A06", len(stats) > 0 and stats[0].get('total_tokens') == 150,
              f"统计事件读写正常 ({len(stats)} 条记录)",
              "统计事件读写失败")
    except Exception as e:
        check("A06", False, "统计事件读写正常", f"异常: {e}")

    # A07: JSON 结构化日志
    logger.log_token_usage(
        model_id='test-model', prompt_tokens=10, completion_tokens=5, total_tokens=15,
        task_hint='测试JSON日志', role_id='analyst'
    )
    today = datetime.now().strftime("%Y-%m-%d")
    jsonl_file = PROJECT_ROOT / "logs" / "statistics" / f"suri-{today}.jsonl"
    has_jsonl = jsonl_file.exists()
    check("A07", has_jsonl,
          f"JSON 结构化日志已写入 ({jsonl_file.name})",
          "JSON 结构化日志未生成")

    if has_jsonl:
        try:
            lines = jsonl_file.read_text().strip().split('\n')
            last_entry = json.loads(lines[-1])
            check("A07b", last_entry.get('event') == 'token_usage' and last_entry.get('role_id') == 'analyst',
                  f"JSON 日志格式正确 (event={last_entry.get('event')}, role_id={last_entry.get('role_id')})",
                  f"JSON 日志格式异常: {last_entry}")
        except Exception as e:
            check("A07b", False, "JSON 日志格式正确", f"解析异常: {e}")

    # A08: 聚合查询
    try:
        all_tasks = memory.get_all_tasks(limit=10)
        check("A08", isinstance(all_tasks, list),
              f"get_all_tasks() 可用（返回 {len(all_tasks)} 条）",
              "get_all_tasks() 异常")
    except Exception as e:
        check("A08", False, "get_all_tasks() 可用", f"异常: {e}")

    # A09: 文件创建日志
    logger.log_file_created(role_id='analyst', filepath='test/file.txt', file_type='text/plain', size=1024)
    check("A09", True,
          "log_file_created() 调用成功",
          "")

    # A10: 任务完成日志
    logger.log_task_completed(task_id='task_test_001', role_id='suri', status='completed', duration_seconds=3.5)
    check("A10", True,
          "log_task_completed() 调用成功",
          "")

    # 汇总
    total = passed + failed
    print(f"\n{'#'*70}")
    print(f"#  {' '*20}测试结果汇总")
    print(f"{'#'*70}")
    print(f"  总测试项: {total}")
    print(f"  {G}通过: {passed}{RST}")
    print(f"  {R}失败: {failed}{RST}")
    print(f"  通过率: {passed/total*100:.1f}%")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
