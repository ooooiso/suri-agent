#!/usr/bin/env python3
"""Suri Agent 入口文件，<20 行核心逻辑。"""

import asyncio
import locale
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
    await core.bootstrap()
    # 保持运行直到收到关闭信号
    await core.run()


if __name__ == "__main__":
    asyncio.run(main())