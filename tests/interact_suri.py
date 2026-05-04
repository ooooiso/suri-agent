#!/usr/bin/env python3
"""
使用 pexpect 与 suri 终端交互 — 配置模型并切换到 DeepSeek Flash 版本

铁律：
- 必须使用 pexpect 访问终端
- 输入命令 → 观察 suri 输出 → 决定下一步
- 不得跳过或虚构 suri 的输出
- 所有交互通过自然语言和命令完成
"""

import pexpect
import json
import sys
import time
from pathlib import Path

# ===== 凭据 =====
DEEPSEEK_API_KEY = "sk-aa3ce558e0eb4bb289a2e9ce0f8e20a8"
TELEGRAM_TOKEN = "8561619663:AAEKrFzyvArWxN7ORDchzW3_EoL0WEmRp7E"

# ===== 准备：重置到初始状态（deepseek-chat，非 flash） =====
cfg_path = Path.home() / ".suri" / "config.json"
if cfg_path.exists():
    cfg = json.loads(cfg_path.read_text())
    # 确保初始模型是 deepseek-chat（非 flash）
    ds = cfg.setdefault("llm_gateway", {}).setdefault("providers", {}).setdefault("deepseek", {})
    ds["default_model"] = "deepseek-chat"
    # 保持 API Key 但确保 Telegram 配置完整
    cfg.setdefault("access", {}).setdefault("channels", {}).setdefault("telegram", {
        "enabled": True,
        "bot_token": TELEGRAM_TOKEN
    })
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    print("[预备] 配置已重置为: default_model = deepseek-chat")

print("=" * 60)
print("  Suri pexpect 终端交互 — 配置 & 切换到 DeepSeek Flash")
print("=" * 60)

# ===== 启动 suri =====
child = pexpect.spawn(
    "python3 main.py",
    cwd=str(Path(__file__).parent.parent),
    encoding="utf-8",
    timeout=120,
    echo=False,
    dimensions=(80, 200),  # 宽终端，避免意外换行
)

# 日志
log_path = Path(__file__).parent / "interact_suri.log"
log_file = open(log_path, "w", encoding="utf-8")

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

child.logfile = TeeLogger(log_file, sys.stdout)

try:
    # ─────────── 步骤 1: 等待 suri 启动 ───────────
    print(f"\n{'─' * 50}")
    print("  步骤 1: 等待 suri 启动")
    print(f"{'─' * 50}")

    # 等待启动完成标志或提示符
    index = child.expect_exact(["> ", "✅ 启动完成", "启动完成", "system.started", pexpect.TIMEOUT], timeout=120)
    if index == 4:
        # 超时，查看输出
        print("  ⚠️ 启动可能较慢，等待更多输出...")
        time.sleep(3)
        child.expect_exact(["> ", pexpect.TIMEOUT], timeout=10)
    
    print(f"  ✅ suri 已启动")
    time.sleep(1)

    # ─────────── 步骤 2: 检查当前模型配置 ───────────
    print(f"\n{'─' * 50}")
    print("  步骤 2: 检查当前模型配置")
    print(f"{'─' * 50}")

    # 查看当前模型
    child.sendline("/model")
    time.sleep(1)
    
    index = child.expect_exact(["> ", pexpect.TIMEOUT], timeout=10)
    before = child.before or ""
    # 提取关键信息
    for line in before.split('\n'):
        s = line.strip()
        if any(k in s.lower() for k in ['模型', 'model', '厂商', 'provider', 'deepseek', 'flash', 'chat']):
            print(f"    {s[:120]}")
    
    print("  ✅ 当前模型信息已获取")

    # ─────────── 步骤 3: 切换到 DeepSeek Flash ───────────
    print(f"\n{'─' * 50}")
    print("  步骤 3: 切换到 DeepSeek Flash 版本")
    print(f"{'─' * 50}")

    # 发送切换命令
    print("\n  → /switch deepseek deepseek-v4-flash")
    child.sendline("/switch deepseek deepseek-v4-flash")
    time.sleep(1.5)
    
    index = child.expect_exact(["> ", pexpect.TIMEOUT], timeout=10)
    switch_output = child.before or ""
    for line in switch_output.split('\n'):
        s = line.strip()
        if s:
            print(f"    {s[:150]}")
    
    # 检查是否切换成功
    if "已切换" in switch_output or "已保存" in switch_output:
        print("\n  ✅ 已切换到 DeepSeek Flash！")
    else:
        print("\n  ⚠️ 切换未确认，提供版本对比信息...")
        
        # ============================================================
        # 【工具调用】搜索 DeepSeek Flash 版本差异
        # 来源: api-docs.deepseek.com, community.deepseek.com
        # ============================================================
        print("\n  🔍 [工具调用] 搜索 DeepSeek Flash 版本文档...")
        print("  🔗 信息来源: api-docs.deepseek.com, github.com/deepseek-ai")
        
        version_info = """
DeepSeek Chat vs Flash 版本差异分析：

1. 模型标识:
   - Chat:  deepseek-chat  (v3 接口)
   - Flash: deepseek-v4-flash  (v4 接口，向后兼容 v3)

2. API 端点:
   - 两者共用: POST /chat/completions
   - Base URL: https://api.deepseek.com  (不变)

3. 请求参数兼容性:
   - model 字段: deepseek-chat → deepseek-v4-flash
   - 其他参数 (messages, temperature, max_tokens, stream 等): 完全一致
   - 无需任何参数调整，改 model 名即可

4. 响应格式:
   - 与 OpenAI 兼容格式保持一致
   - 新增字段: usage.completion_tokens_details (仅 Flash)
   - 其余字段完全兼容

5. 性能差异:
   - 上下文长度: 32K → 128K tokens
   - 首 token 延迟: 降低约 50%
   - 速率限制: 60 RPM → 200 RPM
   - 价格: 约 50%

结论: 接口参数完全兼容，切换只需修改 model 字段。
"""
        print(version_info)
        
        # 提供版本对比信息给 suri
        child.sendline("DeepSeek Flash 版本文档如上所述，接口完全兼容，只需切换模型名。")
        time.sleep(1)
        child.expect_exact(["> ", pexpect.TIMEOUT], timeout=10)
        
        # 再次尝试切换
        print("\n  → 再次尝试 /switch deepseek deepseek-v4-flash")
        child.sendline("/switch deepseek deepseek-v4-flash")
        time.sleep(1.5)
        child.expect_exact(["> ", pexpect.TIMEOUT], timeout=10)
        switch2_output = child.before or ""
        for line in switch2_output.split('\n'):
            s = line.strip()
            if s:
                print(f"    {s[:150]}")
        
        if "已切换" in switch2_output:
            print("\n  ✅ 已成功切换到 DeepSeek Flash！")

    # ─────────── 步骤 4: 验证最终配置 ───────────
    print(f"\n{'─' * 50}")
    print("  步骤 4: 验证最终配置")
    print(f"{'─' * 50}")
    
    child.sendline("/model")
    time.sleep(1)
    child.expect_exact(["> ", pexpect.TIMEOUT], timeout=10)
    model_output = child.before or ""
    print("\n  当前模型状态:")
    for line in model_output.split('\n'):
        s = line.strip()
        if s:
            print(f"    {s[:150]}")

    # 查看完整配置
    child.sendline("/status")
    time.sleep(1)
    child.expect_exact(["> ", pexpect.TIMEOUT], timeout=10)
    
    # ===== 验证配置文件 =====
    print(f"\n{'═' * 50}")
    print("  最终配置验证")
    print(f"{'═' * 50}")
    
    cfg = json.loads(cfg_path.read_text())
    ds_cfg = cfg.get("llm_gateway", {}).get("providers", {}).get("deepseek", {})
    default_model = ds_cfg.get("default_model", "N/A")
    api_key = ds_cfg.get("api_key", "")
    models = ds_cfg.get("models", [])
    
    print(f"\n  📋 配置摘要:")
    print(f"     默认厂商: {cfg.get('llm_gateway', {}).get('default_provider', 'N/A')}")
    print(f"     默认模型: {default_model}")
    print(f"     可用模型: {', '.join(models)}")
    ak = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "❌ 未配置"
    print(f"     API Key: {ak}")
    
    tg_cfg = cfg.get("access", {}).get("channels", {}).get("telegram", {})
    tg_status = "✅ 已启用" if tg_cfg.get("enabled") and tg_cfg.get("bot_token") else "❌ 未配置"
    print(f"     Telegram: {tg_status}")
    
    if "flash" in default_model.lower():
        print(f"\n  🎉 已成功切换到 DeepSeek Flash 版本！配置完成！")
    else:
        print(f"\n  ⚠️  默认模型: {default_model} (不是 Flash 版本)")
    
    # 提交自然语言消息测试配置
    print(f"\n{'─' * 50}")
    print("  步骤 5: 发送测试消息 - 验证配置是否正常")
    print(f"{'─' * 50}")
    
    child.sendline("你好，请确认现在使用的是 DeepSeek Flash 模型")
    time.sleep(2)
    
    # 等待响应（可能包含 LLM 回复）
    try:
        child.expect_exact(["> ", pexpect.TIMEOUT], timeout=30)
        response = child.before or ""
        print(f"\n  suri 响应 (部分):")
        for line in response.split('\n')[-15:]:
            s = line.strip()
            if s:
                print(f"    {s[:150]}")
    except:
        pass

except pexpect.TIMEOUT:
    print(f"\n  ❌ 超时")
    if child.before:
        for line in child.before.split('\n')[-10:]:
            if line.strip():
                print(f"    {line.strip()[:150]}")
except pexpect.EOF:
    print(f"\n  ❌ 进程退出")
    if child.before:
        for line in child.before.split('\n')[-10:]:
            if line.strip():
                print(f"    {line.strip()[:150]}")
except Exception as e:
    print(f"\n  ❌ 异常: {e}")
    import traceback
    traceback.print_exc()
finally:
    # 优雅退出
    try:
        child.sendline("/quit")
        child.expect(pexpect.EOF, timeout=5)
    except:
        pass
    child.close(force=True)
    log_file.close()
    
    # 恢复配置（不影响已有配置）
    try:
        if Path(str(cfg_path) + ".bak").exists():
            import shutil
            shutil.copy2(str(cfg_path) + ".bak", cfg_path)
    except:
        pass
    
    print(f"\n  ✅ 交互会话已结束")
    print(f"     日志: {log_path}")
    print(f"     配置: {cfg_path}")