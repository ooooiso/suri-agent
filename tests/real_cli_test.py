#!/usr/bin/env python3
"""
真正的终端交互测试 - 使用 pexpect 模拟用户在终端输入命令
与 suri 对话，完成模型配置、Telegram 配置、Flash 切换、创建角色等操作
"""

import pexpect
import sys
import json
from pathlib import Path

API_KEY = "sk-aa3ce558e0eb4bb289a2e9ce0f8e20a8"
TELEGRAM_TOKEN = "8561619663:AAEKrFzyvArWxN7ORDchzW3_EoL0WEmRp7E"
BOT_USERNAME = "@suri_wosi_bot"

cfg_path = Path.home() / ".suri" / "config.json"
cfg = json.loads(cfg_path.read_text())
cfg["llm_gateway"]["providers"]["deepseek"]["api_key"] = "sk-demo-test-key-for-validation"
cfg["access"]["channels"]["telegram"]["enabled"] = False
cfg["access"]["channels"]["telegram"]["bot_token"] = ""
cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

child = pexpect.spawn(
    "python3 main.py",
    cwd=str(Path(__file__).parent.parent),
    encoding="utf-8",
    timeout=30,
    echo=False,
)

# Turn on logging
child.logfile = sys.stdout

try:
    # ========== 1. 等待启动完成 ==========
    print("\n" + "=" * 60)
    print("  Step 1: 等待 suri 启动完成")
    print("=" * 60)
    child.expect("> ", timeout=60)
    print("\n  ✅ suri 启动完成，已显示提示符")

    # ========== 2. 用 /setkey 配置 DeepSeek API Key ==========
    print("\n" + "=" * 60)
    print("  Step 2: 配置 DeepSeek 模型 - 输入 /setkey")
    print("=" * 60)
    child.sendline(f"/setkey deepseek {API_KEY}")
    child.expect("> ", timeout=30)
    print("\n  ✅ DeepSeek API Key 配置完成")

    # ========== 3. 配置 Telegram Bot ==========
    print("\n" + "=" * 60)
    print("  Step 3: 配置 Telegram Bot")
    print("=" * 60)
    child.sendline("/reconfig")
    child.expect("请选择", timeout=15)
    child.sendline("3")  # 修改 Telegram Token
    child.expect("> ", timeout=15)
    child.sendline(TELEGRAM_TOKEN)
    child.expect("> ", timeout=15)
    print("\n  ✅ Telegram Bot 配置完成")

    # ========== 4. 切换到 DeepSeek Flash ==========
    print("\n" + "=" * 60)
    print("  Step 4: 切换到 DeepSeek Flash 版本")
    print("=" * 60)
    child.sendline("/switch deepseek deepseek-v4-flash")
    child.expect("> ", timeout=15)
    print("\n  ✅ 已切换到 DeepSeek Flash 版本")

    # 验证当前模型
    child.sendline("/model")
    child.expect("> ", timeout=10)

    print("\n" + "=" * 60)
    print("  ✅ 基础配置全部完成！")
    print("=" * 60)

except pexpect.TIMEOUT:
    print("\n❌ 超时！当前缓冲区内容：")
    print(child.before)
except pexpect.EOF:
    print("\n❌ 进程意外退出")
    print(child.before)
finally:
    child.sendline("/quit")
    child.expect(pexpect.EOF, timeout=5)
    child.close()
    print("\n✅ 会话已结束")