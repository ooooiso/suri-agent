#!/usr/bin/env python3
"""Suri Agent 入口文件。

启动流程：SuriCorePlugin.bootstrap() → system.started → system.ready
关闭流程：SIGTERM/SIGINT → system.shutting_down → 插件暂停 → system.shutdown
"""

import asyncio
import locale
import signal
import sys
from pathlib import Path

# 设置 locale 为 UTF-8，避免编码问题
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except locale.Error:
        pass  # 忽略，保持默认

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent))

from agent_framework.core.suri_core.plugin import SuriCorePlugin


async def main():
    """启动 Suri Agent。"""
    core = SuriCorePlugin()

    # 注册信号处理（SIGTERM=kill, SIGINT=Ctrl+C）
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(_shutdown(core, s)),
            )

    await core.bootstrap()
    # 保持运行直到收到关闭信号
    await core.run()


async def _shutdown(core: SuriCorePlugin, sig: signal.Signals) -> None:
    """优雅关闭处理器。"""
    print(f"\n[main] 收到 {sig.name} 信号，开始优雅关闭...")
    
    # 超时控制：30 秒内必须关闭完毕
    try:
        await asyncio.wait_for(core.stop(), timeout=30.0)
    except asyncio.TimeoutError:
        print("[main] 关闭超时（30s），强制退出")
    
    # 取消所有待处理任务
    pending = [t for t in asyncio.all_tasks() 
               if t is not asyncio.current_task()]
    for task in pending:
        task.cancel()
    
    # 停止事件循环
    loop = asyncio.get_running_loop()
    loop.stop()


if __name__ == "__main__":
    asyncio.run(main())