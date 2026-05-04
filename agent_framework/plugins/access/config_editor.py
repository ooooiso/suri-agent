"""access 配置编辑器 — 运行时修改配置（不删除）。

核心设计：
- 接受可选的 input_func 参数，统一输入方式
- 所有输入通过 input_func 获取，避免与 CLI 主循环竞争 stdin
- 配置编辑逻辑集中在此文件，access/plugin.py 只做事件路由
"""

import json
from pathlib import Path
from typing import Callable, Dict, Optional

from agent_framework.shared.utils.event_types import Event, Priority
from agent_framework.plugins.access.wizard import ConfigWizard


class ConfigEditor:
    """运行时配置编辑器。
    
    支持：
    - 修改已有厂商的 API Key
    - 添加新厂商
    - 修改 Telegram Token
    - 删除所有配置（需确认）
    
    所有输入通过 input_func 获取，默认为同步 input()。
    CLI 模式下传入异步 _async_input，Telegram 模式下传入其他实现。
    """

    CONFIG_PATH = Path.home() / ".suri" / "config.json"

    def __init__(self, event_bus=None, input_func: Optional[Callable] = None):
        self._event_bus = event_bus
        self._input_func = input_func or self._sync_input
        self._wizard = ConfigWizard()

    @staticmethod
    async def _sync_input(prompt: str = "") -> str:
        """默认同步 input（用于非 CLI 场景）。"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt))

    def load_config(self) -> Dict:
        """加载当前配置。"""
        if self.CONFIG_PATH.exists():
            try:
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self, config: Dict) -> bool:
        """保存配置到文件。"""
        try:
            self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[Suri] 保存配置失败: {e}")
            return False

    async def set_provider_key(self, provider: str, api_key: str) -> bool:
        """快速设置/修改某个厂商的 API Key。
        
        Returns True if saved successfully.
        """
        config = self.load_config()
        llm_cfg = config.setdefault("llm_gateway", {})
        providers = llm_cfg.setdefault("providers", {})
        
        # 获取厂商默认配置
        base_url = self._wizard._get_base_url(provider)
        models = self._wizard.PROVIDERS.get(
            self._provider_key_by_id(provider), (provider, provider, [])
        )[2]
        
        prov_cfg = providers.setdefault(provider, {})
        prov_cfg["api_key"] = api_key
        if base_url:
            prov_cfg["base_url"] = base_url
        if models and "models" not in prov_cfg:
            prov_cfg["models"] = models
            prov_cfg["default_model"] = models[0]
        
        # 如果是第一个厂商或当前没有默认厂商，设为默认
        if "default_provider" not in llm_cfg or not llm_cfg.get("default_provider"):
            llm_cfg["default_provider"] = provider
        # 如果 deepseek 已有 default_model 配置，保留；否则用第一个
        if "default_model" not in prov_cfg or not prov_cfg.get("default_model"):
            if models:
                prov_cfg["default_model"] = models[0]
        
        if self.save_config(config):
            print(f"[Suri] {provider} 的 API Key 已保存。")
            await self._notify_change()
            return True
        return False

    async def verify_and_set_key(self, provider: str) -> bool:
        """交互式输入并验证 Key，然后保存。"""
        models = []
        for k, (pid, name, mdl_list) in self._wizard.PROVIDERS.items():
            if pid == provider:
                models = mdl_list
                break
        
        print(f"\n请输入 {provider} 的新 API Key（输入 /cancel 取消）：")
        while True:
            key = await self._input_func("> ")
            if key == "/cancel":
                print("已取消。\n")
                return False
            if not key:
                print("Key 不能为空，请重新输入（或 /cancel 取消）：")
                continue
            
            print("  正在验证 API Key...")
            if self._wizard._verify_key(provider, key, models):
                print("  ✅ 验证通过。")
                return await self.set_provider_key(provider, key)
            else:
                print("  ❌ 验证失败，Key 可能无效。")
                retry = await self._input_func("  仍要保存? [y/N]: ")
                if retry.lower() in ("y", "yes"):
                    return await self.set_provider_key(provider, key)
                print("  请重新输入（或 /cancel 取消）：")

    async def run_menu(self) -> None:
        """运行交互式配置菜单。"""
        config = self.load_config()
        llm_cfg = config.get("llm_gateway", {})
        providers = llm_cfg.get("providers", {})
        default_prov = llm_cfg.get("default_provider", "未设置")
        tg_cfg = config.get("access", {}).get("channels", {}).get("telegram", {})
        
        while True:
            print("\n" + "=" * 40)
            print("  Suri 配置编辑")
            print("=" * 40)
            print(f"\n当前默认厂商: {default_prov}")
            print("已配置厂商:")
            for name, pcfg in providers.items():
                has_key = "✅" if pcfg.get("api_key") else "❌"
                print(f"  {has_key} {name}")
            tg_status = "已启用" if tg_cfg.get("enabled") else "未启用"
            print(f"Telegram: {tg_status}")
            
            print("\n操作选项：")
            print("  1. 修改某个厂商的 API Key")
            print("  2. 添加新厂商")
            print("  3. 修改 Telegram Token")
            print("  4. 删除所有配置（需确认）")
            print("  0. 退出")
            
            choice = await self._input_func("\n请选择 [0-4]: ")
            
            if choice == "0":
                print("\n[Suri] 已退出配置编辑。\n")
                break
            elif choice == "1":
                await self._menu_change_key(providers)
            elif choice == "2":
                await self._menu_add_provider()
            elif choice == "3":
                await self._menu_change_telegram(config)
            elif choice == "4":
                await self._menu_reset_config()
            else:
                print("无效选择。")

    async def _menu_change_key(self, providers: Dict) -> None:
        """菜单：修改已有厂商的 Key。"""
        if not providers:
            print("\n暂无已配置厂商，请先添加。")
            return
        print("\n选择要修改 Key 的厂商：")
        names = list(providers.keys())
        for i, name in enumerate(names, 1):
            print(f"  [{i}] {name}")
        choice = await self._input_func("请选择: ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                await self.verify_and_set_key(names[idx])
            else:
                print("无效选择。")
        except ValueError:
            print("无效输入。")

    async def _menu_add_provider(self) -> None:
        """菜单：添加新厂商。"""
        print("\n可用厂商：")
        for key, (pid, name, _) in self._wizard.PROVIDERS.items():
            print(f"  [{key}] {name}")
        choice = await self._input_func("请选择厂商 [1-5]: ")
        if choice not in self._wizard.PROVIDERS:
            print("无效选择。")
            return
        provider = self._wizard.PROVIDERS[choice][0]
        await self.verify_and_set_key(provider)

    async def _menu_change_telegram(self, config: Dict) -> None:
        """菜单：修改 Telegram Token。"""
        print("\n请输入新的 Telegram Bot Token（输入 /disable 禁用，/cancel 取消）：")
        token = await self._input_func("> ")
        if token == "/cancel":
            print("已取消。")
            return
        
        access_cfg = config.setdefault("access", {})
        channels = access_cfg.setdefault("channels", {})
        tg_cfg = channels.setdefault("telegram", {"enabled": False, "bot_token": ""})
        
        if token == "/disable":
            tg_cfg["enabled"] = False
            tg_cfg["bot_token"] = ""
            print("Telegram 已禁用。")
        elif token:
            print("  正在验证 Token...")
            if self._wizard._verify_telegram_token(token):
                print("  ✅ Token 验证通过。")
                tg_cfg["enabled"] = True
                tg_cfg["bot_token"] = token
            else:
                print("  ❌ Token 验证失败。")
                retry = await self._input_func("  仍要保存? [y/N]: ")
                if retry.lower() not in ("y", "yes"):
                    print("已取消。")
                    return
                tg_cfg["enabled"] = True
                tg_cfg["bot_token"] = token
        
        if self.save_config(config):
            print("[Suri] Telegram 配置已保存。")
            await self._notify_change()

    async def _menu_reset_config(self) -> None:
        """菜单：删除所有配置。"""
        print("\n⚠️  这将删除 ~/.suri/config.json 中的所有配置，不可恢复！")
        confirm = await self._input_func("输入 'DELETE' 确认删除: ")
        if confirm == "DELETE":
            if self.CONFIG_PATH.exists():
                self.CONFIG_PATH.unlink()
            print("[Suri] 配置已删除，下次启动将重新进入向导。")
            await self._notify_change(reason="reconfig")
        else:
            print("已取消删除。")

    def _provider_key_by_id(self, provider_id: str) -> str:
        """根据厂商 ID 查找 wizard 中的 key。"""
        for key, (pid, _, _) in self._wizard.PROVIDERS.items():
            if pid == provider_id:
                return key
        return "1"

    async def _notify_change(self, reason: str = "runtime_edit") -> None:
        """发布配置变更事件。"""
        if self._event_bus:
            await self._event_bus.publish(Event(
                event_type="system.config_changed",
                source="access",
                payload={"reason": reason},
                priority=Priority.HIGH,
            ))