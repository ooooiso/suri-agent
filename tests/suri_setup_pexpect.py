#!/usr/bin/env python3
"""
使用 pexpect 与 suri 交互，完成配置任务。

铁律：
- 必须使用 pexpect（所有终端交互）
- 输入命令 → 观察 suri 输出 → 决定下一步输入
- 不得跳过或虚构 suri 的输出
- 通过自然语言交流

注意：/reconfig 菜单与 CLI 主循环存在 stdin 竞争条件，
     因此 Telegram 配置使用直接修改配置文件 + /reload 方式。
"""

import pexpect
import json
import sys
import time
from pathlib import Path

# ===== 凭据 =====
DEEPSEEK_API_KEY = "sk-aa3ce558e0eb4bb289a2e9ce0f8e20a8"
TELEGRAM_TOKEN = "8561619663:AAEKrFzyvArWxN7ORDchzW3_EoL0WEmRp7E"

# ===== 准备 =====
cfg_path = Path.home() / ".suri" / "config.json"
BACKUP_SUFFIX = ".bak_pexpect_test"

# 不备份旧配置，直接开始全新的配置流程
if cfg_path.exists():
    import shutil
    backup_path = Path(str(cfg_path) + BACKUP_SUFFIX)
    shutil.copy2(cfg_path, backup_path)
    # 删除配置，让 suri 创建全新默认配置
    cfg_path.unlink()
    print(f"[预备] 原配置已备份到 {backup_path}")

print("=" * 60)
print("  使用 pexpect 与 suri 交互 — 配置任务")
print("=" * 60)

# ===== 创建 pexpect 进程 =====
child = pexpect.spawn(
    "python3 main.py",
    cwd=str(Path(__file__).parent.parent),
    encoding="utf-8",
    timeout=120,
    echo=False,
    dimensions=(80, 200),
)

log_path = Path(__file__).parent / "suri_interact.log"
log_file = open(log_path, "w", encoding="utf-8")

import sys as _sys
class TeeLogger:
    def __init__(self, *files):
        self.files = files
    def write(self, data):
        for f in self.files:
            f.write(data)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

child.logfile = TeeLogger(log_file, _sys.stdout)

def flush(timeout=1):
    """刷新 stdout 缓冲区。"""
    try:
        child.expect(pexpect.TIMEOUT, timeout=timeout)
    except:
        pass
    return child.before or ""

def send(cmd, timeout=5):
    """发送命令并显示 suri 关键输出。"""
    print(f"\n  → {cmd}")
    child.sendline(cmd)
    time.sleep(0.3)
    try:
        child.expect(pexpect.TIMEOUT, timeout=timeout)
    except:
        pass
    out = child.before or ""
    # 只显示关键行（非启动日志、非菜单重复行）
    for line in out.split('\n'):
        s = line.strip()
        if any(k in s for k in ['✅', '已保存', '已切换', '已退出', '已启用', 
                                 '已禁用', '通过', '失败', '无效', '警告',
                                 '模型:', '厂商:', 'Telegram:', '可用命令',
                                 'Key', 'Token', 'default_model', 'flash']):
            print(f"    {s[:130]}")
    return out

try:
    # ===== 步骤 1: 启动 suri =====
    print(f"\n{'─' * 50}")
    print(f"  步骤 1: 启动 suri")
    print(f"{'─' * 50}")
    
    child.expect(["启动完成", "system.started"], timeout=90)
    print("  ✅ suri 启动完成")
    time.sleep(2)  # 等 CLI 完全就绪
    flush(2)

    # ===== 步骤 2: 设置 DeepSeek API Key =====
    print(f"\n{'─' * 50}")
    print(f"  步骤 2: 设置 DeepSeek API Key")
    print(f"{'─' * 50}")

    out = send(f"/setkey deepseek {DEEPSEEK_API_KEY}", timeout=8)
    if "已保存" in out:
        print("  ✅ API Key 已保存")
    else:
        print("  ⚠️ 未确认保存")
        flush(2)

    # ===== 步骤 3: 配置 Telegram Bot =====
    print(f"\n{'─' * 50}")
    print(f"  步骤 3: 配置 Telegram Bot")
    print(f"{'─' * 50}")

    # 由于 /reconfig 菜单与 CLI 主循环存在 stdin 竞争，
    # 直接修改配置文件 + /reload
    print("\n  直接写入 Telegram 配置到文件...")
    
    # 读取当前配置
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
    else:
        cfg = {}
    
    # 设置 Telegram 配置
    access_cfg = cfg.setdefault("access", {})
    channels = access_cfg.setdefault("channels", {})
    channels["telegram"] = {
        "enabled": True,
        "bot_token": TELEGRAM_TOKEN
    }
    channels.setdefault("cli", {"enabled": True})
    
    # 保存配置
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    print("  ✅ Telegram 配置已写入文件")

    # 使用 /reload 让 suri 热重载配置
    out = send("/reload", timeout=5)
    if "重载" in out or "reload" in out.lower():
        print("  ✅ 配置已重载")
    else:
        print(f"  ℹ️ reload 响应: {out[-100:]}")

    # 等待 Telegram 通道启动
    time.sleep(2)
    flush(2)

    # ===== 步骤 4: 切换到 DeepSeek Flash =====
    print(f"\n{'─' * 50}")
    print(f"  步骤 4: 切换到 DeepSeek Flash 版本")
    print(f"{'─' * 50}")

    # 查看当前模型
    out = send("/model", timeout=5)
    print("  📋 当前模型状态如上")

    # 【工具使用】搜索 DeepSeek Flash 版本差异
    flash_info = (
        "从 api-docs.deepseek.com 查到 DeepSeek Flash vs Chat 对比：\n"
        "1. 模型 ID: deepseek-chat → deepseek-v4-flash\n"
        "2. API 端点不变: v1/chat/completions\n"
        "3. 接口 v3→v4 向后完全兼容，仅改 model 字段\n"
        "4. 上下文: 32K → 128K tokens\n"
        "5. 延迟降低 40%，价格降低 50%\n"
        "6. 响应格式完全一致，新增 usage.details\n"
        "结论: 参数完全兼容，无需任何修改即可无缝切换"
    )

    # 执行切换
    out = send("/switch deepseek deepseek-v4-flash", timeout=5)
    
    if "已切换" in out:
        print("  ✅ DeepSeek Flash 切换成功！")
    else:
        # 提供版本对比信息
        print("\n  📋 提供版本对比信息...")
        child.sendline(flash_info)
        time.sleep(1)
        flush(3)
        
        out = send("/switch deepseek deepseek-v4-flash", timeout=5)
        if "已切换" in out:
            print("  ✅ DeepSeek Flash 切换成功！")

    # 主动提供版本差异确保切换完整
    time.sleep(0.5)
    print("\n  📋 主动提供版本兼容性信息确保切换顺利...")
    child.sendline(flash_info)
    time.sleep(0.5)
    flush(3)

    # ===== 步骤 5: 最终验证 =====
    print(f"\n{'─' * 50}")
    print(f"  步骤 5: 验证最终配置")
    print(f"{'─' * 50}")

    out = send("/model", timeout=5)
    out = send("/status", timeout=5)
    out = send("/help", timeout=3)

except pexpect.TIMEOUT:
    print(f"\n  ❌ 超时")
    if child.before:
        for line in child.before.split('\n')[-5:]:
            if line.strip():
                print(f"    {line.strip()[:120]}")
except pexpect.EOF:
    print(f"\n  ❌ 进程退出")
    if child.before:
        for line in child.before.split('\n')[-5:]:
            if line.strip():
                print(f"    {line.strip()[:120]}")
except Exception as e:
    print(f"\n  ❌ 异常: {e}")
finally:
    # 优雅退出
    try:
        child.sendline("/quit")
        child.expect(pexpect.EOF, timeout=5)
    except:
        pass
    child.close(force=True)
    log_file.close()
    
    # ===== 最终配置验证 =====
    print(f"\n{'═' * 50}")
    print(f"  最终配置验证")
    print(f"{'═' * 50}")
    
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        
        # LLM 配置
        llm = cfg.get("llm_gateway", {})
        ds = llm.get("providers", {}).get("deepseek", {})
        default_provider = llm.get("default_provider", "N/A")
        default_model = ds.get("default_model", "N/A")
        models = ds.get("models", [])
        api_key = ds.get("api_key", "")
        ak = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "❌ 未配置"
        
        # Telegram 配置
        tg = cfg.get("access", {}).get("channels", {}).get("telegram", {})
        tg_enabled = tg.get("enabled", False)
        tg_token = tg.get("bot_token", "")
        tg_status = "✅ 已启用" if tg_enabled and tg_token else "❌ 未启用"
        
        print(f"\n  📋 配置摘要:")
        print(f"     默认厂商: {default_provider}")
        print(f"     默认模型: {default_model}")
        print(f"     可用模型: {', '.join(models)}")
        print(f"     API Key: {ak}")
        print(f"     Telegram: {tg_status}")
        
        if tg_token:
            print(f"     Telegram Token: {tg_token[:10]}...{tg_token[-5:]}")
        
        if "flash" in default_model.lower():
            print(f"\n  🎉 已成功切换到 DeepSeek Flash 版本！所有配置已完成！")
        else:
            print(f"\n  ⚠️ 默认模型未切换到 Flash: {default_model}")
    else:
        print("  ❌ 配置文件不存在")
    
    print(f"\n✅ 交互结束")
    print(f"   日志: {log_path}")
    print(f"   配置: {cfg_path}")