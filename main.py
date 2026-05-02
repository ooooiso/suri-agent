#!/usr/bin/env python3
"""Suri Agent 入口文件，<20 行核心逻辑。"""

import asyncio
import sys
from pathlib import Path

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent))

from agent_framework.suri_core_plugin.plugin import SuriCorePlugin


async def main():
    """启动 Suri Agent。"""
    core = SuriCorePlugin()
    await core.bootstrap()
    # 保持运行直到收到关闭信号
    await core.run()


if __name__ == "__main__":
    asyncio.run(main())
