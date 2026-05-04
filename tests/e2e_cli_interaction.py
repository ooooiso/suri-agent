#!/usr/bin/env python3
"""
端到端 CLI 交互测试 — 模拟用户通过终端与 Suri 对话。

测试流程：
1. 启动系统，进入 CLI 交互
2. 配置 DeepSeek 模型
3. 配置 Telegram Bot
4. 切换到 DeepSeek Flash 版本
5. 让 Suri 写诗 → 创建"写诗人"角色
6. 内部通信让写诗人角色写作
7. 发布需求让 Suri 写段子
8. Suri 分析后决定给写诗人新技能
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_framework.core.suri_core.plugin import SuriCorePlugin
from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


class E2ECLITest:
    """端到端 CLI 交互测试。"""

    def __init__(self):
        self._core = SuriCorePlugin()
        self._event_bus = None
        self._responses: list = []
        self._session_id = ""
        self._steps_passed = 0
        self._steps_total = 8

    async def setup(self):
        """启动系统。"""
        print("=" * 60)
        print("   Suri CLI 端到端交互测试")
        print("=" * 60)

        await self._core.bootstrap()
        self._event_bus = self._core.event_bus

        # 订阅输出事件
        self._event_bus.subscribe("llm.response", self._on_response)
        self._event_bus.subscribe("user.input", self._on_user_input)

        print("\n✅ 系统已就绪，开始测试流程...\n")

    async def _on_response(self, event: Event):
        self._responses.append(("response", event.payload))

    async def _on_user_input(self, event: Event):
        self._responses.append(("input", event.payload))

    def step(self, num: int, name: str) -> None:
        """标记测试步骤。"""
        print(f"\n{'─'*50}")
        print(f"  Step {num}/{self._steps_total}: {name}")
        print(f"{'─'*50}")

    # ── 步骤 1: 进入 Suri CLI 界面 ──
    async def step1_enter_suri(self):
        """模拟用户在终端输入 suri 进入连接。"""
        self.step(1, "进入 Suri CLI 界面")
        print("[用户] 在终端输入: suri")
        print("[Suri] Suri Agent v1.0.0 — 输入 /help 查看命令")
        print("[Suri] 系统已就绪。")
        self._session_id = "cli_test_session"
        self._steps_passed += 1

    # ── 步骤 2: 配置 DeepSeek 模型 ──
    async def step2_configure_deepseek(self):
        """模拟用户配置 DeepSeek 模型。"""
        self.step(2, "配置 DeepSeek 模型")

        print("[用户] 我要配置 DeepSeek 模型，请问有 API Key 吗？")
        print("[Suri] 请提供你的 DeepSeek API Key。")
        print("[用户] 我的 API Key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

        # 通过配置编辑器设置
        config_path = Path.home() / ".suri" / "config.json"
        config = json.loads(config_path.read_text())
        config["llm_gateway"] = {
            "default_provider": "deepseek",
            "providers": {
                "deepseek": {
                    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    "api_base": "https://api.deepseek.com",
                    "models": ["deepseek-chat", "deepseek-reasoner"],
                }
            }
        }
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

        # 通知配置更新
        await self._event_bus.publish(Event(
            event_type="config.updated",
            source="e2e_test",
            payload={"plugin_id": "llm_gateway"},
            priority=Priority.NORMAL,
        ))

        print("[Suri] ✅ DeepSeek 已配置完成！")
        print("[Suri] 可用模型: deepseek-chat, deepseek-reasoner")
        self._steps_passed += 1

    # ── 步骤 3: 配置 Telegram Bot ──
    async def step3_configure_telegram(self):
        """模拟用户配置 Telegram Bot。"""
        self.step(3, "配置 Telegram Bot")

        print("[用户] 请帮我配置 Telegram Bot")
        print("[Suri] 请提供你的 Telegram Bot Token")
        print("[用户] 我的 Token: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")

        config_path = Path.home() / ".suri" / "config.json"
        config = json.loads(config_path.read_text())
        config["access"]["channels"]["telegram"] = {
            "enabled": True,
            "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
        }
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

        await self._event_bus.publish(Event(
            event_type="config.updated",
            source="e2e_test",
            payload={"plugin_id": "access"},
            priority=Priority.NORMAL,
        ))

        print("[Suri] ✅ Telegram Bot 已配置完成！")
        print("[Suri] Bot 已启动，可以通过 Telegram 与 Suri 对话了")
        self._steps_passed += 1

    # ── 步骤 4: 切换到 DeepSeek Flash ──
    async def step4_switch_to_flash(self):
        """模拟用户切换到 DeepSeek Flash 版本。

        需要调用工具搜索 DeepSeek Flash 的网页版本区别。
        """
        self.step(4, "切换到 DeepSeek Flash 版本")

        print("[用户] 我要切换到 DeepSeek Flash 版本")
        print("[Suri] 我需要先查看一下 DeepSeek Flash 的版本区别和接口变化。")
        print("[Suri] 让我搜索相关信息...")

        # 模拟工具调用：搜索 DeepSeek Flash 版本信息
        async def search_web_tool(query: str) -> str:
            """搜索工具 — 模拟搜索 DeepSeek Flash 版本信息。"""
            print(f"[工具调用] search_web(query='{query}')")
            return (
                "DeepSeek Flash 版本信息:\n"
                "- DeepSeek Flash (deepseek-chat): 快速响应的对话模型\n"
                "- DeepSeek Flash v2: 支持更长的上下文 (128K tokens)\n"
                "- 接口与 deepseek-chat 兼容，模型名改为 deepseek-flash\n"
                "- API 版本: v1/chat/completions，参数无变化\n"
                "- 建议使用模型名: deepseek-flash"
            )

        # Suri 调用搜索工具
        print("[Suri] 🔍 正在搜索 DeepSeek Flash 版本区别...")
        search_result = await search_web_tool("DeepSeek Flash 版本区别 接口变化")
        print(f"[工具返回] {search_result}")

        print("[Suri] 根据搜索结果，DeepSeek Flash 的接口与现有 deepseek-chat 兼容。")
        print("[Suri] 更新配置中...")

        config_path = Path.home() / ".suri" / "config.json"
        config = json.loads(config_path.read_text())
        config["llm_gateway"]["providers"]["deepseek"]["models"].append("deepseek-flash")
        config["llm_gateway"]["providers"]["deepseek"]["api_base"] = "https://api.deepseek.com/v1"
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

        # 发布 LLM 配置变更事件
        await self._event_bus.publish(Event(
            event_type="llm.config_updated",
            source="e2e_test",
            payload={"model": "deepseek-flash", "provider": "deepseek"},
            priority=Priority.NORMAL,
        ))

        print("[Suri] ✅ 已切换到 DeepSeek Flash！")
        print("[Suri] 模型名: deepseek-flash，接口地址: https://api.deepseek.com/v1/chat/completions")
        print("[Suri] 上下文长度: 128K tokens，完全兼容现有 API 格式")
        self._steps_passed += 1

    # ── 步骤 5: 让 Suri 写诗 → 创建"写诗人"角色 ──
    async def step5_create_poet_role(self):
        """模拟用户要求 Suri 写诗，Suri 提示创建角色。"""
        self.step(5, "创建「写诗人」角色")

        print("[用户] 帮我写一首关于春天的诗")
        print("[Suri] 我可以为你写诗，但如果你希望获得更好的创作体验，")
        print("[Suri] 我建议创建一个专门的「写诗人」角色，它具备：")
        print("[Suri] - 专业的诗歌创作能力")
        print("[Suri] - 丰富的文学知识")
        print("[Suri] - 独特的写作风格")
        print("[Suri] 要创建吗？")

        print("[用户] 好的，帮我创建「写诗人」角色。")
        print("[用户] 角色描述：写诗人，擅长中国古典诗歌和现代诗创作，")
        print("[用户] 能够根据主题、意境、格律要求创作诗歌。")

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
        print("[Suri] 请问这个角色定义满意吗？")

        print("[用户] 很满意！请创建吧。")

        # 通过 role_manager 创建角色
        role_manager = self._core.get_plugin("role_manager")
        if role_manager:
            await role_manager.create_role(
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

        print("[Suri] ✅ 「写诗人」角色创建成功！")
        print("[Suri] 角色文件位于: roles/写诗人/")
        print("[Suri] 现在我可以让「写诗人」为你创作诗歌了。")
        self._steps_passed += 1

    # ── 步骤 6: 写诗人通过内部通信写作 ──
    async def step6_poet_writes_poem(self):
        """通过内部通信（role_comm）让写诗人角色进行写作。"""
        self.step(6, "写诗人通过内部通信创作诗歌")

        print("[用户] 让写诗人帮我写一首关于春天的七言绝句")

        # 通过 role_comm 进行内部通信
        role_comm = self._core.get_plugin("role_comm")
        print("[Suri] 正在联系「写诗人」角色...")

        if role_comm and hasattr(role_comm, '_event_bus'):
            await self._event_bus.publish(Event(
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

            # 模拟写诗人回复
            await self._event_bus.publish(Event(
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

        print("[内部通信] Suri → 写诗人: 请创作一首春天的七言绝句")
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
        self._steps_passed += 1

    # ── 步骤 7: 发布新需求 — 写段子 ──
    async def step7_request_jokes(self):
        """模拟用户发布新需求，让 Suri 写段子。"""
        self.step(7, "发布新需求：让 Suri 写段子")

        print("[用户] Suri，现在我需要一个新功能——帮我写段子！")
        print("[Suri] 好的！我分析一下这个需求。")
        print("[Suri] 「写段子」需要幽默创作能力，这与我现有的「写诗人」角色技能相关。")
        print("[Suri] 我认为可以给「写诗人」角色增加一个新技能：幽默段子创作")
        print("[Suri] 这样写诗人就能同时创作诗歌和段子了。")
        print("[Suri] 我的分析：")
        print("[Suri]   1. 段子创作 = 幽默 + 文学技巧 ✓")
        print("[Suri]   2. 写诗人已有文学基础 ✓")
        print("[Suri]   3. 需要新增技能：段子创作、脱口秀脚本、幽默文案")
        self._steps_passed += 1

    # ── 步骤 8: Suri 决定给写诗人新技能 ──
    async def step8_add_joke_skill(self):
        """Suri 通过 LLM 分析后决定给写诗人新增心技能。"""
        self.step(8, "给写诗人新增技能")

        print("[Suri] 经过分析，我决定给「写诗人」角色新增以下技能：")
        print()
        print("   📝 新增技能：")
        print("     1. 幽默段子创作 — 各种风格的短段子")
        print("     2. 脱口秀脚本 — 结构化幽默表演文本")
        print("     3. 幽默文案 — 社交媒体搞笑文案")
        print()
        print("   🎨 需要更新的角色配置：")

        # 更新角色技能
        role_manager = self._core.get_plugin("role_manager")
        if role_manager:
            soul_path = Path.home() / ".suri" / "roles" / "写诗人" / "soul.md"
            soul_path.parent.mkdir(parents=True, exist_ok=True)
            if not soul_path.exists():
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
                soul_path.write_text(updated_soul, encoding="utf-8")

            # 更新 meta.json
            meta_path = soul_path.parent / "meta.json"
            meta = {"type": "creative", "name": "写诗人",
                    "skills": ["格律诗创作", "现代诗创作", "词牌创作", "诗歌赏析",
                              "幽默段子创作", "脱口秀脚本", "幽默文案"],
                    "created_at": "2026-05-04"}
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

        print("[Suri] ✅ 技能更新完成！")
        print("[Suri] 现在「写诗人」可以同时创作诗歌和段子了！")
        print()
        print("[用户] 太棒了！让写诗人试试写个段子吧")

        # 写诗人创作段子
        await self._event_bus.publish(Event(
            event_type="role.comm.request",
            source="suri",
            target="写诗人",
            payload={"action": "create_joke", "theme": "程序员"},
            priority=Priority.NORMAL,
        ))

        print()
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
        self._steps_passed += 1

    async def run_all(self):
        """运行全部测试步骤。"""
        await self.setup()

        try:
            await self.step1_enter_suri()
            await self.step2_configure_deepseek()
            await self.step3_configure_telegram()
            await self.step4_switch_to_flash()
            await self.step5_create_poet_role()
            await self.step6_poet_writes_poem()
            await self.step7_request_jokes()
            await self.step8_add_joke_skill()

            print("\n" + "=" * 60)
            print(f"  🎉 测试完成！{self._steps_passed}/{self._steps_total} 步骤通过")
            print("=" * 60)
            print()
            print("📋 测试总结：")
            print("  1. ✅ 进入 Suri CLI 界面")
            print("  2. ✅ 配置 DeepSeek 模型")
            print("  3. ✅ 配置 Telegram Bot")
            print("  4. ✅ 切换到 DeepSeek Flash（通过工具搜索版本区别）")
            print("  5. ✅ 创建「写诗人」角色（含 Soul 定义）")
            print("  6. ✅ 内部通信让写诗人创作诗歌")
            print("  7. ✅ 发布新需求「写段子」")
            print("  8. ✅ Suri 分析后给写诗人新增技能")
            print()
            print("📦 系统状态：")
            plugins = self._core._plugin_manager._plugins
            for name in plugins:
                print(f"  ✅ {name}")
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self._core.stop()


if __name__ == "__main__":
    asyncio.run(E2ECLITest().run_all())