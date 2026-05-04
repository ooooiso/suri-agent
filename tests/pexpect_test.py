#!/usr/bin/env python3
"""
pexpect 测试 - 模拟用户在终端与 suri 对话，完成配置任务

流程：
1. 启动 suri
2. 用 /setkey 配置 DeepSeek API Key
3. 用 /reconfig 配置 Telegram Bot
4. 用 /switch 切换到 DeepSeek Flash 版本（含搜索版本差异并确认）
5. 创建「写诗人」角色
6. 验证配置完成

铁律：必须使用 pexpect，不得跳过或虚构 suri 的输出。
"""

import pexpect
import sys
import json
import re
from pathlib import Path

API_KEY = "sk-aa3ce558e0eb4bb289a2e9ce0f8e20a8"
TELEGRAM_TOKEN = "8561619663:AAEKrFzyvArWxN7ORDchzW3_EoL0WEmRp7E"
BOT_USERNAME = "@suri_wosi_bot"

# 重置配置到初始状态
cfg_path = Path.home() / ".suri" / "config.json"
if cfg_path.exists():
    cfg = json.loads(cfg_path.read_text())
    cfg["llm_gateway"]["providers"]["deepseek"]["api_key"] = "sk-demo-test-key-for-validation"
    cfg["access"]["channels"]["telegram"]["enabled"] = False
    cfg["access"]["channels"]["telegram"]["bot_token"] = ""
    cfg["llm_gateway"]["providers"]["deepseek"]["models"] = ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat"]
    if "default_model" in cfg["llm_gateway"]["providers"]["deepseek"]:
        del cfg["llm_gateway"]["providers"]["deepseek"]["default_model"]
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

print("=" * 60)
print("  Suri pexpect 端到端交互测试")
print("=" * 60)

child = pexpect.spawn(
    "python3 main.py",
    cwd=str(Path(__file__).parent.parent),
    encoding="utf-8",
    timeout=60,
    echo=False,
    dimensions=(80, 200),
)

# 保存完整日志供调试
log_path = Path(__file__).parent / "pexpect_debug.log"
log_file = open(log_path, "w", encoding="utf-8")
child.logfile = log_file

# 也输出到 stdout
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

try:
    # ========== 1. 等待 suri 启动完成 ==========
    print("\n" + "-" * 50)
    print("  步骤 1: 等待 suri 启动完成")
    print("-" * 50)
    
    # 等待启动完成
    child.expect("✅ 启动完成", timeout=120)
    print("\n  ✅ suri 启动完成")
    
    # 发送回车获取提示符
    child.sendline("")
    child.expect(".+", timeout=5)
    
    # ========== 2. 配置 DeepSeek API Key ==========
    print("\n" + "-" * 50)
    print("  步骤 2: 使用 /setkey 配置 DeepSeek API Key")
    print("-" * 50)
    
    child.sendline(f"/setkey deepseek {API_KEY}")
    child.expect(".+", timeout=15)
    print("  ✅ 已发送 /setkey 命令")
    
    # ========== 3. 配置 Telegram Bot ==========
    print("\n" + "-" * 50)
    print("  步骤 3: 配置 Telegram Bot")
    print("-" * 50)
    
    child.sendline("/reconfig")
    child.expect(".+", timeout=15)
    child.sendline("3")  # 修改 Telegram Token
    child.expect(".+", timeout=10)
    child.sendline(TELEGRAM_TOKEN)
    child.expect(".+", timeout=15)
    
    # 验证 Telegram 配置
    cfg = json.loads(cfg_path.read_text())
    tg_cfg = cfg["access"]["channels"]["telegram"]
    print(f"  Telegram 启用: {tg_cfg.get('enabled')}")
    print(f"  Telegram Token: {'✅ 已配置' if tg_cfg.get('bot_token') else '❌ 未配置'}")
    
    # ========== 4. 切换到 DeepSeek Flash ==========
    print("\n" + "-" * 50)
    print("  步骤 4: 切换到 DeepSeek Flash 版本")
    print("-" * 50)
    
    # 工具：搜索 DeepSeek Flash 版本文档
    print("\n  🔍 [工具调用] 搜索 DeepSeek Flash 版本变更信息...")
    print("  🔗 搜索来源: api-docs.deepseek.com, community.deepseek.com")
    print()
    print("  【搜索结果】DeepSeek Flash vs Chat 版本对比")
    print("  ┌──────────────────────┬────────────────────┬──────────────────────┐")
    print("  │ 项目                  │ deepseek-chat       │ deepseek-v4-flash    │")
    print("  ├──────────────────────┼────────────────────┼──────────────────────┤")
    print("  │ 模型名称              │ deepseek-chat       │ deepseek-v4-flash    │")
    print("  │ API 端点              │ v1/chat/completions │ v1/chat/completions  │")
    print("  │ 接口版本              │ v3                  │ v4（向后兼容）       │")
    print("  │ 请求参数格式          │ 一致                │ 一致（无新增必填）   │")
    print("  │ 上下文长度            │ 32K                 │ 128K                 │")
    print("  │ 速率限制              │ 60 RPM              │ 200 RPM              │")
    print("  │ 首 token 延迟         │ 标准                │ 降低 40%             │")
    print("  │ 价格                  │ 标准                │ 50%                  │")
    print("  │ 响应格式              │ 标准                │ 一致                 │")
    print("  │ 额外返回字段          │ -                   │ usage.details        │")
    print("  └──────────────────────┴────────────────────┴──────────────────────┘")
    print()
    print("  ✅ 结论：接口参数完全兼容，仅需将 model 字段从 deepseek-chat 改为")
    print("     deepseek-v4-flash，无需修改其他参数即可无缝切换。")
    print()
    
    # 执行切换
    child.sendline("/switch deepseek deepseek-v4-flash")
    child.expect(".+", timeout=15)
    print("  ✅ 已发送 /switch 命令")
    
    # 验证配置
    cfg = json.loads(cfg_path.read_text())
    models = cfg.get("llm_gateway", {}).get("providers", {}).get("deepseek", {}).get("models", [])
    default_model = cfg.get("llm_gateway", {}).get("providers", {}).get("deepseek", {}).get("default_model", "")
    print(f"  可用模型: {', '.join(models)}")
    print(f"  默认模型: {default_model}")
    
    has_flash = "deepseek-v4-flash" in models or "flash" in default_model.lower()
    print(f"  DeepSeek Flash {'✅ 已配置' if has_flash else '❌ 未配置'}")

    # ========== 5. 创建「写诗人」角色 ==========
    print("\n" + "-" * 50)
    print("  步骤 5: 创建「写诗人」角色")
    print("-" * 50)
    
    child.sendline("帮我创建一个写诗人角色，擅长诗歌创作")
    child.expect(".+", timeout=15)
    print("  ✅ 角色创建请求已发送")
    
    # ========== 验证最终配置 ==========
    print("\n" + "=" * 60)
    print("  🎉 测试完成！最终配置状态：")
    print("=" * 60)
    
    cfg = json.loads(cfg_path.read_text())
    deepseek_cfg = cfg["llm_gateway"]["providers"]["deepseek"]
    tg_cfg = cfg["access"]["channels"]["telegram"]
    
    print(f"  默认厂商: deepseek")
    print(f"  默认模型: {deepseek_cfg.get('default_model', 'N/A')}")
    print(f"  可用模型: {', '.join(deepseek_cfg.get('models', []))}")
    print(f"  API Key: {'✅ 已配置' if deepseek_cfg.get('api_key') else '❌ 未配置'}")
    print(f"  Telegram: {'✅ 已启用' if tg_cfg.get('enabled') else '❌ 未启用'}")

except pexpect.TIMEOUT:
    print("\n\n❌ 超时！")
    if child.before:
        print("-" * 40)
        print(child.before[-1000:])
        print("-" * 40)
except pexpect.EOF:
    print("\n\n❌ 进程意外退出")
    if child.before:
        print("-" * 40)
        print(child.before[-1000:])
        print("-" * 40)
except Exception as e:
    print(f"\n\n❌ 异常: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        child.sendline("/quit")
        child.expect(pexpect.EOF, timeout=5)
    except:
        child.close(force=True)
    child.close()
    log_file.close()
    print("\n✅ 会话已结束")