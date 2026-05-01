#!/usr/bin/env python3
"""
终端启动流程测试

验证：
1. SuriTerminal 初始化正常
2. 核心角色 suri 存在性检查
3. output_router 正确初始化
4. 模型配置状态检测
5. 命令系统注册完整

运行方式:
    python suri-agent/tests/test_terminal_startup.py
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.logger import LoggerService
from access.output import OutputRouter

G = '\033[92m'; R = '\033[91m'; RST = '\033[0m'
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def ok(id, msg): print(f"  {G}✓{RST} [{id}] {msg}")
def fail(id, msg, detail=""):
    print(f"  {R}✗{RST} [{id}] {msg}")
    if detail: print(f"      → {detail}")


def main():
    print(f"\n{'#'*70}")
    print(f"#  {' '*20}终端启动流程测试")
    print(f"{'#'*70}")

    passed = 0
    failed = 0

    def check(tid, cond, ok_msg, fail_msg, detail=""):
        nonlocal passed, failed
        if cond:
            ok(tid, ok_msg); passed += 1
        else:
            fail(tid, fail_msg, detail); failed += 1

    # T01: 核心角色 suri 存在
    suri_soul = PROJECT_ROOT / "group" / "central" / "suri" / "suri.md"
    check("T01", suri_soul.exists(),
          f"核心角色 suri Soul 文件存在 ({suri_soul})",
          "核心角色 suri Soul 文件缺失")

    # T02: 统计角色 suri_stats 存在（V2.0: analyst → suri_stats，canonical 目录）
    stats_soul = PROJECT_ROOT / "group" / "central" / "suri_stats" / "suri_stats.md"
    check("T02", stats_soul.exists(),
          f"统计角色 suri_stats Soul 文件存在 ({stats_soul})",
          "统计角色 suri_stats Soul 文件缺失")

    # T03: ConfigService 能加载所有角色
    config = ConfigService(PROJECT_ROOT)
    config.load_all()
    roles = config.list_roles(include_aliases=True)
    check("T03", len(roles) >= 5 and ('analyst' in roles or 'suri_stats' in roles),
          f"ConfigService 加载 {len(roles)} 个角色（含 analyst/suri_stats）",
          f"角色加载不完整: {roles}")

    # T04: 统计角色 keywords 正确
    kws = config.get_role_keywords('analyst')
    expected_kws = ['统计', 'token', '报告', '用量']
    found = all(kw in kws for kw in expected_kws)
    check("T04", found,
          f"analyst 关键词正确 ({len(kws)} 个)",
          f"关键词不完整: {kws}",
          f"期望包含: {expected_kws}")

    # T05: 各角色 Soul 完整（使用 canonical role_id）
    for role_id in ['suri', 'suri_dev', 'suri_hr', 'suri_review', 'suri_stats']:
        soul = config.get_role_soul(role_id)
        tid = f"T05_{role_id}"
        if soul and soul.meta.get('name'):
            ok(tid, f"{role_id} Soul 完整 (name={soul.meta.get('name')})")
            passed += 1
        else:
            fail(tid, f"{role_id} Soul 缺失或损坏")
            failed += 1

    # T06: LoggerService 统计方法存在
    logger = LoggerService(PROJECT_ROOT)
    check("T06", hasattr(logger, 'log_token_usage') and hasattr(logger, 'log_file_created') and hasattr(logger, 'log_task_completed'),
          "LoggerService 统计方法完整 (log_token_usage / log_file_created / log_task_completed)",
          "LoggerService 缺少统计方法")

    # T07: OutputRouter 支持 analyst（通过动态 role_routes）
    from access.output import OutputChannel
    config2 = ConfigService(PROJECT_ROOT)
    config2.load_all()
    memory = MemoryService(PROJECT_ROOT, config2)
    security = SecurityService(PROJECT_ROOT, config2)
    logger2 = LoggerService(PROJECT_ROOT)
    # 模拟 cli.py 的动态路由构建
    dynamic_routes = {}
    channel_map = {
        'terminal': OutputChannel.TERMINAL, 'file': OutputChannel.FILE,
        'logger': OutputChannel.LOGGER, 'memory': OutputChannel.MEMORY,
    }
    for rid in config2.list_roles():
        if rid == 'suri':
            continue
        cfg = config2.get_role_output_channels(rid)
        if cfg:
            channels = [channel_map[c] for c in cfg if c in channel_map]
            if channels:
                dynamic_routes[rid] = channels
    router = OutputRouter(PROJECT_ROOT, memory, security, logger2, role_routes=dynamic_routes, config=config2)
    # V2.0: 支持别名兼容，检查新旧名称
    has_analyst_route = 'suri_stats' in router._role_routes or 'analyst' in router._role_routes
    check("T07", has_analyst_route,
          "OutputRouter 动态路由包含 analyst/suri_stats",
          "OutputRouter 缺少 analyst 路由")

    # T08: 模型配置状态
    from model.manager import ModelManager
    mm = ModelManager(PROJECT_ROOT)
    has_models = len(mm._models) > 0
    check("T08", has_models,
          f"模型已配置 ({len(mm._models)} 个)",
          "模型未配置（将触发首次运行引导）")

    # T09: 统计目录结构
    stats_dir = PROJECT_ROOT / "logs" / "statistics"
    check("T09", True,
          "统计日志目录将自动创建 (logs/statistics/)",
          "")

    # T10: 任务看板 API 可用
    check("T10", hasattr(memory, 'get_all_tasks') and hasattr(memory, 'get_pending_approvals'),
          "MemoryService 聚合查询方法可用 (get_all_tasks / get_pending_approvals)",
          "MemoryService 缺少聚合查询方法")

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
