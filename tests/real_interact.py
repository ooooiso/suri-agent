#!/usr/bin/env python3
"""
真实的终端交互测试 - 使用 pty 伪终端
每步输入一条命令，等待完整输出后再输入下一条
"""

import os
import sys
import time
import json
import select
import shutil
from pathlib import Path

API_KEY = "sk-aa3ce558e0eb4bb289a2e9ce0f8e20a8"
TELEGRAM_TOKEN = "8561619663:AAEKrFzyvArWxN7ORDchzW3_EoL0WEmRp7E"

# 重置配置
cfg_path = Path.home() / ".suri" / "config.json"
cfg = json.loads(cfg_path.read_text())
cfg["llm_gateway"]["providers"]["deepseek"]["api_key"] = ""
cfg["access"]["channels"]["telegram"]["enabled"] = False
cfg["access"]["channels"]["telegram"]["bot_token"] = ""
cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

poet_dir = Path.cwd() / "roles" / "写诗人"
if poet_dir.exists():
    shutil.rmtree(poet_dir)

print("=" * 60)
print("  Suri CLI 真实终端交互测试 (pty 方式)")
print("=" * 60)
print()

pid, master_fd = pty = os.forkpty()
if pid == 0:
    os.chdir(str(Path(__file__).parent.parent))
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.execvp("python3", ["python3", "main.py"])

def read_until(timeout, marker=""):
    out = ""
    start = time.time()
    while time.time() - start < timeout:
        r, _, _ = select.select([master_fd], [], [], 0.5)
        if r:
            try:
                chunk = os.read(master_fd, 4096).decode("utf-8", errors="replace")
                if not chunk:
                    break
                out += chunk
                lines = out.split("\n")
                for line in lines:
                    stripped = line.strip()
                    if stripped:
                        print(f"  [{stripped[:80]}]")
                if marker and marker in out:
                    return out
            except:
                break
    return out

def send(cmd):
    os.write(master_fd, (cmd + "\n").encode("utf-8"))
    time.sleep(0.2)

try:
    # Step 1: 启动
    print("--- [1] 启动 suri ---")
    time.sleep(15)  # 等待启动
    read_until(10)
    print("  启动完成\n")

    # Step 2: 查看状态
    print("--- [2] /status ---")
    send("/status")
    read_until(5)
    print()

    # Step 3: 设置 API Key
    print("--- [3] /setkey ---")
    send(f"/setkey deepseek {API_KEY}")
    read_until(5)
    print()

    # Step 4: 配置 Telegram
    print("--- [4] Telegram ---")
    cfg = json.loads(cfg_path.read_text())
    cfg["access"]["channels"]["telegram"]["enabled"] = True
    cfg["access"]["channels"]["telegram"]["bot_token"] = TELEGRAM_TOKEN
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    send("/reload")
    read_until(5)
    print()

    # Step 5: 切换 Flash
    print("--- [5] /switch deepseek-v4-flash ---")
    send("/switch deepseek deepseek-v4-flash")
    read_until(5)
    print()

    # 检查配置
    cfg = json.loads(cfg_path.read_text())
    d = cfg["llm_gateway"]["providers"]["deepseek"]
    tg = cfg["access"]["channels"]["telegram"]
    print(f"  API Key: {'✅' if d['api_key'] else '❌'}")
    print(f"  Models: {d['models']}")
    print(f"  Default: {d.get('default_model', 'N/A')}")
    print(f"  Telegram: {'✅' if tg['enabled'] else '❌'}")
    print()

    # Step 6: 自然语言 - 创建写诗人
    print("--- [6] 创建写诗人角色 ---")
    print("  [输入] 帮我创建写诗人角色")
    send("帮我创建一个叫写诗人的角色，用来写诗和段子")
    # 等待 LLM 回复 (可能 30-60 秒)
    read_until(60, ">")
    print("  LLM 回复完成")
    print()

    # 检查角色是否创建
    if poet_dir.exists():
        print(f"  ✅ 写诗人角色已创建")
        for f in poet_dir.iterdir():
            print(f"     - {f.name}")
    else:
        print(f"  ⚠️ 写诗人角色目录不存在")
    print()

    # Step 7: 写诗
    print("--- [7] 写诗 ---")
    print("  [输入] 写一首春的七言绝句")
    send("帮我写一首关于春天的七言绝句")
    read_until(60, ">")
    print()

    # Step 8: 写段子
    print("--- [8] 写段子 ---")
    print("  [输入] 程序员段子")
    send("写个程序员主题的段子")
    read_until(60, ">")
    print()

    print("=" * 60)
    print("  ✅ 终端交互测试完成！")
    print("=" * 60)

finally:
    try:
        send("/quit")
    except:
        pass
    os.close(master_fd)
    os.waitpid(pid, 0)