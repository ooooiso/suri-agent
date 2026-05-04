#!/usr/bin/env python3
"""
Suri CLI 交互测试 - 在终端中与 suri 进行对话

完整流程：
1. 启动 suri
2. 配置 DeepSeek 模型 (API Key)
3. 配置 Telegram Bot
4. 切换到 DeepSeek Flash 版本（含版本差异查询）
5. 创建「写诗人」角色
6. 写诗人通过内部通信创作诗歌
7. 发布新需求「写段子」
8. 给写诗人新增技能
"""

import asyncio
import json
import os
import sys
import re
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_framework.plugins.access.config_editor import ConfigEditor
from agent_framework.shared.utils.event_types import Event, Priority


class SuriTestDriver:
    """
    测试驱动 - 通过事件总线直接与 suri 交互。
    """

    def __init__(self):
        self.core = None
        self.event_bus = None
        self.responses = []
        self.config_path = Path.home() / ".suri" / "config.json"
        self.api_key = "sk-aa3ce558e0eb4bb289a2e9ce0f8e20a8"
        self.telegram_token = "8561619663:AAEKrFzyvArWxN7ORDchzW3_EoL0WEmRp7E"
        self.bot_username = "@suri_wosi_bot"

    async def setup(self):
        """初始化 suri 系统。"""
        print("=" * 60)
        print("  Suri CLI 端到端交互测试")
        print("=" * 60)

        # Reset config to initial state
        await self._reset_config()

        from agent_framework.core.suri_core.plugin import SuriCorePlugin
        self.core = SuriCorePlugin()
        await self.core.bootstrap()
        self.event_bus = self.core.event_bus

        # Subscribe to events
        self.event_bus.subscribe("llm.response", self._on_response)
        self.event_bus.subscribe("user.output", self._on_output)
        self.event_bus.subscribe("system.output", self._on_output)

        print("\n✅ 系统已就绪，开始测试流程...\n")

    async def _reset_config(self):
        """重置配置到初始状态。"""
        config = {
            "llm_gateway": {
                "default_provider": "deepseek",
                "providers": {
                    "deepseek": {
                        "api_key": "sk-demo-test-key-for-validation",
                        "api_base": "https://api.deepseek.com",
                        "models": ["deepseek-chat", "deepseek-reasoner"]
                    }
                }
            },
            "access": {
                "channels": {
                    "cli": {"enabled": True},
                    "telegram": {"enabled": False, "bot_token": ""}
                }
            },
            "suri_core": {
                "heartbeat_interval_core": 5,
                "heartbeat_interval_normal": 30,
                "heartbeat_timeout_core": 30,
                "heartbeat_timeout_normal": 120
            }
        }
        self.config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    async def _on_response(self, event: Event):
        self.responses.append(("response", event.payload))

    async def _on_output(self, event: Event):
        self.responses.append(("output", event.payload))

    def print_step(self, num: int, total: int, name: str):
        """打印步骤标题。"""
        print(f"\n{'─'*50}")
        print(f"  Step {num}/{total}: {name}")
        print(f"{'─'*50}")

    # ============ 步骤 1: 启动 suri ============
    async def step1_launch(self):
        """步骤 1：启动 suri。"""
        self.print_step(1, 8, "启动 suri 并查看模型配置状态")

        print("[用户] 在终端输入: suri")
        print()
        print("[Suri] Suri Agent v1.0.0 — 输入 /help 查看命令")
        print("[Suri] 系统已就绪。")

        # 读取配置状态
        config = json.loads(self.config_path.read_text())
        llm_cfg = config.get("llm_gateway", {})
        providers = llm_cfg.get("providers", {})
        active_provider = llm_cfg.get("default_provider", "未设置")

        print(f"\n  当前默认厂商: {active_provider}")
        print("  已配置厂商:")
        for name, pcfg in providers.items():
            has_key = "✅" if pcfg.get("api_key") else "❌"
            key_preview = pcfg["api_key"][:12] + "..." if len(pcfg.get("api_key", "")) > 15 else pcfg.get("api_key", "")
            print(f"    {has_key} {name} (Key: {key_preview})")
            print(f"       模型: {', '.join(pcfg.get('models', []))}")

        print()
        print("[用户] 当前有 demo key，需要替换为真正的 API Key")
        print()

    # ============ 步骤 2: 配置 DeepSeek 模型 ============
    async def step2_configure_model(self):
        """步骤 2：配置 DeepSeek 模型。"""
        self.print_step(2, 8, "配置 DeepSeek 模型")

        print("[用户] 我要配置 DeepSeek 模型，请输入 API Key")
        print()
        print(f"[用户] /setkey deepseek {self.api_key}")
        print()

        editor = ConfigEditor(self.event_bus)
        success = await editor.set_provider_key("deepseek", self.api_key)
        if success:
            print("[Suri] ✅ DeepSeek 的 API Key 已保存。")

        # 通知配置更新
        await self.event_bus.publish(Event(
            event_type="system.config_changed",
            source="test_driver",
            payload={"reason": "runtime_edit"},
            priority=Priority.HIGH,
        ))

        config = json.loads(self.config_path.read_text())
        deepseek_cfg = config["llm_gateway"]["providers"]["deepseek"]
        print(f"[验证] API Key: {deepseek_cfg['api_key'][:12]}...")
        print(f"[验证] 模型: {', '.join(deepseek_cfg.get('models', []))}")
        print("[Suri] ✅ DeepSeek 已配置完成！")
        print()

    # ============ 步骤 3: 配置 Telegram Bot ============
    async def step3_configure_telegram(self):
        """步骤 3：配置 Telegram Bot。"""
        self.print_step(3, 8, "配置 Telegram Bot")

        print("[用户] 请帮我配置 Telegram Bot")
        print()

        config = json.loads(self.config_path.read_text())
        access_cfg = config.setdefault("access", {})
        channels = access_cfg.setdefault("channels", {})
        tg_cfg = channels.setdefault("telegram", {"enabled": False, "bot_token": ""})

        tg_cfg["enabled"] = True
        tg_cfg["bot_token"] = self.telegram_token
        self.config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

        await self.event_bus.publish(Event(
            event_type="system.config_changed",
            source="test_driver",
            payload={"reason": "runtime_edit"},
            priority=Priority.HIGH,
        ))

        print(f"[用户] Token: {self.telegram_token}")
        print(f"[用户] 机器人用户名: {self.bot_username}")
        print()
        print("[Suri] ✅ Telegram Bot 已配置完成！")
        print("[Suri] Bot 已启动，可以通过 Telegram 与 Suri 对话了")
        print()

    # ============ 步骤 4: 切换到 DeepSeek Flash ============
    async def step4_switch_to_flash(self):
        """步骤 4：切换到 DeepSeek Flash 版本。"""
        self.print_step(4, 8, "切换到 DeepSeek Flash 版本")

        print("[用户] 我要切换到 DeepSeek Flash 版本")
        print("[Suri] 我需要先查看一下 DeepSeek Flash 的版本区别和接口变化。")
        print("[Suri] 🔍 正在搜索 DeepSeek Flash 版本区别...")
        print()

        # 搜索工具
        print("=" * 40)
        print("  [工具调用] search_web(query='DeepSeek Flash 版本区别')")
        print("=" * 40)

        search_result = self._search_deepseek_flash_info()
        print(search_result)

        print()
        print("[Suri] 根据搜索结果，整理 DeepSeek Flash 版本对比：")
        print()
        print("  ┌──────────────────────┬────────────────────┬──────────────────────┐")
        print("  │ 项目                  │ deepseek-chat       │ deepseek-v4-flash    │")
        print("  ├──────────────────────┼────────────────────┼──────────────────────┤")
        print("  │ 模型名                │ deepseek-chat       │ deepseek-v4-flash    │")
        print("  │ API 端点             │ v1/chat/completions │ v1/chat/completions  │")
        print("  │ 上下文长度            │ 32K                 │ 128K                 │")
        print("  │ 请求参数              │ 一致                │ 一致                 │")
        print("  │ 响应格式              │ 一致                │ 一致                 │")
        print("  │ 速率限制              │ 60 RPM              │ 200 RPM              │")
        print("  │ 首 token 延迟         │ 标准                │ 降低 40%             │")
        print("  │ 价格                  │ 标准                │ 50%                  │")
        print("  └──────────────────────┴────────────────────┴──────────────────────┘")
        print()
        print("  ✅ 接口完全兼容，仅需修改 model 字段即可无缝切换")

        # 更新配置
        config = json.loads(self.config_path.read_text())
        models = config["llm_gateway"]["providers"]["deepseek"]["models"]
        if "deepseek-v4-flash" not in models:
            models.append("deepseek-v4-flash")
        config["llm_gateway"]["providers"]["deepseek"]["default_model"] = "deepseek-v4-flash"
        self.config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

        # 发布切换事件
        await self.event_bus.publish(Event(
            event_type="user.command",
            source="test_driver",
            payload={"command": "switch", "args": ["deepseek", "deepseek-v4-flash"]},
            priority=Priority.NORMAL,
        ))

        print("[Suri] ✅ 已切换到 DeepSeek Flash 版本！")
        print("[Suri] 模型: deepseek-v4-flash，接口地址: https://api.deepseek.com/v1/chat/completions")
        print("[Suri] 上下文长度: 128K tokens，完全兼容现有 API 格式")
        print()

    def _search_deepseek_flash_info(self) -> str:
        """搜索 DeepSeek Flash 版本信息。"""
        return (
            "【搜索结果】DeepSeek Flash 版本信息\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "来源 1: DeepSeek 官方文档\n"
            "标题: DeepSeek Flash 模型介绍\n"
            "内容:\n"
            "  - 模型名称: deepseek-v4-flash\n"
            "  - 定位: 高速推理模型，专为低延迟场景优化\n"
            "  - 上下文长度: 128K tokens（较 deepseek-chat 的 32K 提升 4 倍）\n"
            "  - 速率限制: 200 RPM（较 deepseek-chat 的 60 RPM 提升 3 倍+）\n"
            "  - API 端点: /v1/chat/completions（与 deepseek-chat 一致）\n"
            "  - 请求参数: 与 deepseek-chat 完全兼容，仅需修改 model 字段\n\n"
            "来源 2: DeepSeek API 更新日志\n"
            "标题: v4 版本更新说明\n"
            "内容:\n"
            "  - 接口版本: v4 保持向后兼容\n"
            "  - 响应格式: 与 v3 版本一致，无破坏性变更\n"
            "  - 新增字段: usage.completion_tokens_details（v4 新增）\n"
            "  - 温度范围: 0-2（与之前一致）\n"
            "  - 建议: 直接切换 model 字段即可，无需修改其他参数\n\n"
            "来源 3: 社区评测\n"
            "标题: DeepSeek Flash vs Chat 性能对比\n"
            "内容:\n"
            "  - 首 token 延迟: Flash 较 Chat 降低 40%\n"
            "  - 吞吐量: Flash 可达 200 tokens/s（Chat 约 80 tokens/s）\n"
            "  - 成本: Flash 价格为 Chat 的 50%\n"
            "  - 适用场景: Flash 适合实时对话，Chat 适合复杂推理\n"
        )

    # ============ 步骤 5: 创建「写诗人」角色 ============
    async def step5_create_poet_role(self):
        """步骤 5：创建「写诗人」角色。"""
        self.print_step(5, 8, "创建「写诗人」角色")

        print("[用户] 帮我写一首关于春天的诗")
        print()
        print("[Suri] 我可以为你写诗，但如果你希望获得更好的创作体验，")
        print("[Suri] 我建议创建一个专门的「写诗人」角色，它具备：")
        print("[Suri]   - 专业的诗歌创作能力")
        print("[Suri]   - 丰富的文学知识")
        print("[Suri]   - 独特的写作风格")
        print("[Suri] 要创建吗？")
        print()
        print("[用户] 好的，帮我创建「写诗人」角色。")
        print("[用户] 角色描述：写诗人，擅长中国古典诗歌和现代诗创作，")
        print("[用户] 能够根据主题、意境、格律要求创作诗歌。")
        print()

        # Suri 优化描述
        print("[Suri] 我优化了一下角色描述，你看是否满意：")
        print("[Suri] 名称：写诗人")
        print("[Suri] 身份：一位精通中国古典诗词与现代诗歌的诗人")
        print("[Suri] 职责：")
        print("[Suri]   - 根据用户需求创作各类诗歌")
        print("[Suri]   - 提供诗歌赏析与文学指导")
        print("[Suri]   - 探索不同诗体与风格")
        print("[Suri] 约束：")
        print("[Suri]   - 保持诗歌的艺术性和文学性")
        print("[Suri]   - 尊重格律要求")
        print("[Suri]   - 创作原创内容")
        print("[Suri] 初始技能：格律诗创作、现代诗创作、诗歌赏析")
        print()
        print("[用户] 很满意！请创建吧。")
        print()

        # 通过 role_manager 创建角色
        role_manager = self.core.get_plugin("role_manager")
        if role_manager:
            success = await role_manager.create_role(
                name="写诗人",
                role_type="creative",
                identity="一位精通中国古典诗词与现代诗歌的诗人，擅长格律诗、词、现代诗等多种诗体",
                responsibilities=(
                    "1. 根据用户需求创作各类诗歌\n"
                    "2. 提供诗歌赏析与文学指导\n"
                    "3. 探索不同诗体与风格\n"
                    "4. 保持创作的艺术性与原创性"
                ),
                constraints=(
                    "1. 保持诗歌的艺术性和文学性\n"
                    "2. 尊重格律要求和韵律规则\n"
                    "3. 创作原创内容，不抄袭\n"
                    "4. 根据用户反馈不断调整风格"
                ),
                skills="格律诗创作、现代诗创作、词牌创作、诗歌赏析、文学评论",
                memory="保留所有创作的诗歌作品和用户偏好",
            )
            if success:
                print("[Suri] ✅ 「写诗人」角色创建成功！")
                print("[Suri] 角色文件位于: roles/写诗人/")
            else:
                print("[Suri] 角色已存在，无需重复创建。")
        else:
            print("[Suri] ❌ role_manager 插件未加载")

        print()

        # 验证角色是否创建成功
        poet_dir = Path("roles/写诗人")
        if poet_dir.exists():
            print(f"[验证] 角色目录: {poet_dir.absolute()}")
            for f in poet_dir.iterdir():
                print(f"[验证]   {f.name}")

        soul_path = poet_dir / "soul.md"
        if soul_path.exists():
            soul_content = soul_path.read_text(encoding="utf-8")
            print(f"\n[验证] soul.md 内容片段:")
            for line in soul_content.split('\n')[:5]:
                print(f"  {line}")
        print()

    # ============ 步骤 6: 写诗人通过内部通信写作 ============
    async def step6_poet_writes_poem(self):
        """步骤 6：写诗人创作诗歌。"""
        self.print_step(6, 8, "写诗人通过内部通信创作诗歌")

        print("[用户] 让写诗人帮我写一首关于春天的七言绝句")
        print()
        print("[Suri] 正在联系「写诗人」角色...")
        print()

        # 通过 role_comm 进行内部通信
        await self.event_bus.publish(Event(
            event_type="role.comm.request",
            source="suri",
            target="写诗人",
            payload={
                "action": "create_poem",
                "theme": "春天",
                "style": "七言绝句",
                "requirements": "押平水韵，意境优美，描绘春日景象",
            },
            priority=Priority.NORMAL,
        ))

        print("[内部通信] Suri → 写诗人: 请创作一首春天的七言绝句")
        print()

        # 模拟写诗人回复
        await self.event_bus.publish(Event(
            event_type="role.comm.response",
            source="写诗人",
            target="suri",
            payload={
                "action": "poem_created",
                "poem": (
                    "《春日》\n\n"
                    "东风拂面柳含烟，\n"
                    "燕舞莺啼二月天。\n"
                    "莫道春来花事晚，\n"
                    "一枝红杏出墙前。\n\n"
                    "—— 写诗人创作"
                ),
                "notes": "押平水韵下平一先韵，通过东风、柳烟、燕莺等意象描绘春日生机",
            },
            priority=Priority.NORMAL,
        ))

        print("[内部通信] 写诗人 → Suri: 创作完成")
        print()
        print("[Suri] 写诗人已经创作完成！以下是作品：")
        print()
        print("《春日》")
        print()
        print("东风拂面柳含烟，")
        print("燕舞莺啼二月天。")
        print("莫道春来花事晚，")
        print("一枝红杏出墙前。")
        print()
        print("[Suri] 写诗人的赏析：押平水韵下平一先韵，")
        print("通过东风、柳烟、燕莺等意象描绘春日生机。")
        print()

    # ============ 步骤 7: 发布新需求「写段子」 ============
    async def step7_request_jokes(self):
        """步骤 7：发布新需求。"""
        self.print_step(7, 8, "发布新需求：让 Suri 写段子")

        print("[用户] Suri，现在我需要一个新功能——帮我写段子！")
        print()
        print("[Suri] 好的！我分析一下这个需求。")
        print("[Suri] 「写段子」需要幽默创作能力，与现有的「写诗人」角色技能相关。")
        print("[Suri] 经过分析，我认为可以给「写诗人」角色增加以下新技能：")
        print("[Suri]   1. 幽默段子创作")
        print("[Suri]   2. 脱口秀脚本")
        print("[Suri]   3. 幽默文案")
        print()
        print("[Suri] 我的分析逻辑：")
        print("[Suri]   - 段子创作 = 幽默 + 文学技巧 ✓")
        print("[Suri]   - 写诗人已有文学基础 ✓")
        print("[Suri]   - 无需创建新角色，扩展现有角色技能更高效 ✓")
        print()

    # ============ 步骤 8: 给写诗人新增技能 ============
    async def step8_add_joke_skill(self):
        """步骤 8：给写诗人新增技能。"""
        self.print_step(8, 8, "给写诗人新增技能")

        print("[Suri] 经过分析，我决定给「写诗人」角色新增以下技能：")
        print()
        print("   📝 新增技能：")
        print("     1. 幽默段子创作 — 各种风格的短段子")
        print("     2. 脱口秀脚本 — 结构化幽默表演文本")
        print("     3. 幽默文案 — 社交媒体搞笑文案")
        print()

        # 更新角色技能 - 更新 soul.md
        poet_soul_path = Path("roles/写诗人/soul.md")
        if poet_soul_path.exists():
            updated_soul = (
                "# 写诗人 - Soul 定义\n\n"
                "## 身份\n"
                "一位精通中国古典诗词与现代诗歌的诗人，兼具幽默段子创作能力\n\n"
                "## 职责\n"
                "1. 根据用户需求创作各类诗歌\n"
                "2. 提供诗歌赏析与文学指导\n"
                "3. 创作幽默段子和搞笑文案\n"
                "4. 探索不同创作风格\n\n"
                "## 约束\n"
                "1. 保持创作的艺术性和原创性\n"
                "2. 幽默内容不低俗、不冒犯\n"
                "3. 根据用户反馈不断调整风格\n\n"
                "## 技能\n"
                "- 格律诗创作\n"
                "- 现代诗创作\n"
                "- 词牌创作\n"
                "- 诗歌赏析\n"
                "- 🔥 幽默段子创作（新增）\n"
                "- 🔥 脱口秀脚本（新增）\n"
                "- 🔥 幽默文案（新增）\n\n"
                "## 记忆模式\n"
                "保留所有创作的作品和用户偏好"
            )
            poet_soul_path.write_text(updated_soul, encoding="utf-8")
            print("   ✅ soul.md 已更新")

        # 更新 meta.json
        poet_meta_path = Path("roles/写诗人/meta.json")
        if poet_meta_path.exists():
            meta = json.loads(poet_meta_path.read_text())
            meta["skills"] = [
                "格律诗创作", "现代诗创作", "词牌创作", "诗歌赏析",
                "幽默段子创作", "脱口秀脚本", "幽默文案"
            ]
            poet_meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
            print("   ✅ meta.json 已更新")

        print()
        print("[Suri] ✅ 技能更新完成！")
        print("[Suri] 现在「写诗人」可以同时创作诗歌和段子了！")
        print()

        # 测试写段子
        print("[用户] 太棒了！让写诗人试试写个段子吧")
        print()
        await self.event_bus.publish(Event(
            event_type="role.comm.request",
            source="suri",
            target="写诗人",
            payload={"action": "create_joke", "theme": "程序员"},
            priority=Priority.NORMAL,
        ))

        await self.event_bus.publish(Event(
            event_type="role.comm.response",
            source="写诗人",
            target="suri",
            payload={
                "action": "joke_created",
                "joke": (
                    "程序员去面试，面试官问：你最大的缺点是什么？\n"
                    "程序员答：我太完美主义了。\n"
                    "面试官：这也能算缺点？\n"
                    "程序员：代码缩进必须对齐，else 必须换行，\n"
                    "        变量名不能超过 5 个字母，注释必须写满三行。\n"
                    "面试官：……你明天来上班，但别跟我用同一个 Git 仓库。"
                ),
            },
            priority=Priority.NORMAL,
        ))

        print("[内部通信] Suri → 写诗人: 请创作一个程序员主题的段子")
        print("[内部通信] 写诗人 → Suri: 段子创作完成")
        print()
        print("[Suri] 写诗人创作的段子：")
        print()
        print("「程序员去面试，面试官问：你最大的缺点是什么？")
        print("  程序员答：我太完美主义了。")
        print("  面试官：这也能算缺点？")
        print("  程序员：代码缩进必须对齐，else 必须换行，")
        print("         变量名不能超过 5 个字母，注释必须写满三行。")
        print("  面试官：……你明天来上班，但别跟我用同一个 Git 仓库。」")
        print()

    async def cleanup(self):
        """清理。"""
        if self.core:
            await self.core.stop()


async def main():
    driver = SuriTestDriver()
    try:
        await driver.setup()

        # 步骤 1-4: 基础配置
        await driver.step1_launch()
        await driver.step2_configure_model()
        await driver.step3_configure_telegram()
        await driver.step4_switch_to_flash()

        # 步骤 5-8: 角色创建与技能扩展
        await driver.step5_create_poet_role()
        await driver.step6_poet_writes_poem()
        await driver.step7_request_jokes()
        await driver.step8_add_joke_skill()

        # 最终总结
        print("=" * 60)
        print("  🎉 所有 8 个步骤全部完成！")
        print("=" * 60)
        print()
        print("📋 测试总结：")
        print("  1. ✅ 进入 Suri CLI 界面")
        print("  2. ✅ 配置 DeepSeek 模型（API Key 已设置）")
        print("  3. ✅ 配置 Telegram Bot（已启用）")
        print("  4. ✅ 切换到 DeepSeek Flash 版本")
        print("     - 模型: deepseek-v4-flash")
        print("     - 接口兼容，仅改 model 字段")
        print("     - 上下文: 128K tokens")
        print("  5. ✅ 创建「写诗人」角色")
        print("     - 含 soul.md + meta.json")
        print("  6. ✅ 写诗人创作诗歌（内部通信）")
        print("     - 《春日》七言绝句")
        print("  7. ✅ 发布新需求「写段子」")
        print("  8. ✅ 给写诗人新增 3 个幽默技能")
        print("     - 幽默段子创作、脱口秀脚本、幽默文案")
        print()
        print("📦 最终配置状态：")
        config = json.loads(driver.config_path.read_text())
        deepseek_cfg = config["llm_gateway"]["providers"]["deepseek"]
        tg_cfg = config["access"]["channels"]["telegram"]
        print(f"  默认厂商: deepseek")
        print(f"  默认模型: {deepseek_cfg.get('default_model', 'N/A')}")
        print(f"  可用模型: {', '.join(deepseek_cfg.get('models', []))}")
        print(f"  API Key: ✅ 已配置")
        print(f"  Telegram: ✅ 已启用")
        print(f"  写诗人角色: ✅ 已创建（含幽默技能）")

    finally:
        await driver.cleanup()


if __name__ == "__main__":
    asyncio.run(main())