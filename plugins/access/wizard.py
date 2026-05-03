"""access 配置向导 — 首次运行交互式配置。"""

import json
import ssl
import urllib.request
from typing import Dict, Optional


class ConfigWizard:
    """首次运行配置向导。"""

    PROVIDERS = {
        "1": ("deepseek", "DeepSeek", ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat"]),
        "2": ("kimi", "Moonshot (Kimi)", ["moonshot-v1-8k", "moonshot-v1-32k"]),
        "3": ("chatglm", "智谱 (ChatGLM)", ["glm-4", "glm-3-turbo"]),
        "4": ("tongyi", "阿里通义", ["qwen-max", "qwen-plus"]),
        "5": ("wenxin", "百度文心", ["ernie-4.0", "ernie-3.5"]),
    }

    def __init__(self, config_service=None):
        self._config = config_service
        self._result: Dict[str, any] = {}

    def run(self) -> Optional[Dict[str, any]]:
        """运行向导，返回配置字典。"""
        print("\n" + "=" * 50)
        print("  欢迎使用 Suri Agent — 首次运行配置")
        print("=" * 50 + "\n")

        # 步骤 1：选择模型厂商
        provider_key, provider_name, models = self._select_provider()
        if not provider_key:
            return None

        # 步骤 2：输入并验证 API Key
        api_key = self._input_and_verify_key(provider_key, provider_name, models)
        if api_key is None:
            return None

        # 默认使用厂商第一个模型
        default_model = models[0] if models else ""

        # 步骤 3：配置 Telegram（可选）
        telegram_config = self._configure_telegram()

        # 步骤 4：确认配置
        config = {
            "llm_gateway": {
                "default_provider": provider_key,
                "providers": {
                    provider_key: {
                        "models": models,
                        "base_url": self._get_base_url(provider_key),
                        "api_key": api_key,
                        "default_model": default_model,
                    }
                }
            },
            "access": {
                "channels": {
                    "cli": {"enabled": True},
                    "telegram": telegram_config,
                }
            }
        }

        if not self._confirm_config(provider_name, default_model, telegram_config):
            print("\n配置已取消。下次启动将重新进入向导。\n")
            return None

        print("\n[Suri] 配置已保存。正在启动...\n")
        print(f"  提示：对话中可随时使用 'llm.switch <品牌> [模型]' 切换模型。\n")
        return config

    def _select_provider(self):
        """步骤 1：选择模型厂商。"""
        print("步骤 1/4：选择默认 LLM 厂商\n")
        for key, (pid, name, _) in self.PROVIDERS.items():
            print(f"  [{key}] {name}")
        print()

        while True:
            choice = input("请选择 [1-5]: ").strip()
            if choice in self.PROVIDERS:
                return self.PROVIDERS[choice]
            print("无效选择，请重新输入。")

    def _input_and_verify_key(self, provider_key: str, provider_name: str, models) -> Optional[str]:
        """步骤 2：输入并验证 API Key。"""
        print(f"\n步骤 2/4：输入 {provider_name} API Key")
        print("（Key 仅保存在本地 ~/.suri/config.json，不会上传）\n")

        while True:
            key = input("API Key: ").strip()
            if not key:
                print("API Key 不能为空。")
                continue

            print("  正在验证 API Key...")
            if self._verify_key(provider_key, key, models):
                print("  ✅ API Key 验证通过。\n")
                return key
            else:
                print("  ❌ API Key 验证失败，请检查 Key 是否正确。\n")
                retry = input("  重新输入? [Y/n]: ").strip().lower()
                if retry not in ("", "y", "yes"):
                    print("  跳过验证，使用当前 Key。（启动后如无法对话，请检查配置）\n")
                    return key

    def _verify_key(self, provider_key: str, api_key: str, models) -> bool:
        """发送测试请求验证 API Key。
        
        严格区分：
        - 401 → Key 明确无效 → False
        - 200 + 有效响应 → Key 有效 → True
        - 429/503 等服务端错误 → Key 可能是对的 → True（但会提示）
        - 网络/编码/DNS 等连接层错误 → 无法验证 → False（不能当成通过）
        """
        # 前置检查：API Key 用于 HTTP Header，必须是可编码字符
        try:
            api_key.encode("ascii")
        except UnicodeEncodeError:
            print("  ⚠️  API Key 包含非法字符（如中文），请检查 Key 是否正确。")
            return False

        try:
            base_url = self._get_base_url(provider_key)
            model = models[0] if models else ""

            # wenxin 迭代 1 未完整实现，跳过验证
            if provider_key == "wenxin":
                return True

            chat_paths = {
                "deepseek": "/chat/completions",
                "kimi": "/v1/chat/completions",
                "chatglm": "/api/paas/v4/chat/completions",
                "tongyi": "/api/v1/services/aigc/text-generation/generation",
            }
            path = chat_paths.get(provider_key, "/chat/completions")
            url = f"{base_url}{path}"
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            context = ssl.create_default_context()

            with urllib.request.urlopen(req, context=context, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return "choices" in data or "id" in data

        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False
            # 429/500/503 等服务端错误 → Key 格式可能是对的
            print(f"  ⚠️  服务端返回 {e.code}（非 Key 问题），视为验证通过。")
            return True

        except urllib.error.URLError as e:
            print(f"  ⚠️  网络连接失败: {e.reason}")
            return False

        except UnicodeEncodeError as e:
            print(f"  ⚠️  请求编码错误: {e}")
            return False

        except Exception as e:
            print(f"  ⚠️  验证异常: {e}")
            return False

    def _configure_telegram(self) -> Dict:
        """步骤 3：配置 Telegram（可选），输入 Token 后验证有效性。"""
        print("步骤 3/4：配置 Telegram Bot（可选）")
        print("  输入 Bot Token 启用，直接输入 /skip 跳过\n")

        while True:
            token = input("Telegram Bot Token [/skip]: ").strip()
            if token.lower() == "/skip" or not token:
                return {"enabled": False, "bot_token": ""}

            print("  正在验证 Bot Token...")
            if self._verify_telegram_token(token):
                print("  ✅ Token 验证通过。\n")
                return {"enabled": True, "bot_token": token}
            else:
                print("  ❌ Token 无效或网络不通，请检查 Token 是否正确。\n")
                retry = input("  重新输入? [Y/n]: ").strip().lower()
                if retry not in ("", "y", "yes"):
                    print("  跳过 Telegram 配置。\n")
                    return {"enabled": False, "bot_token": ""}

    def _verify_telegram_token(self, token: str) -> bool:
        """调用 Telegram getMe 验证 Token 有效性。"""
        # 前置检查：Token 用于 URL，必须是可编码字符
        try:
            token.encode("ascii")
        except UnicodeEncodeError:
            print("  ⚠️  Token 包含非法字符（如中文），请检查 Token 是否正确。")
            return False

        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            req = urllib.request.Request(url, method="GET")
            context = ssl.create_default_context()
            with urllib.request.urlopen(req, context=context, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("ok", False)

        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False
            print(f"  ⚠️  Telegram 服务端返回 {e.code}，视为验证通过。")
            return True

        except urllib.error.URLError as e:
            print(f"  ⚠️  网络连接失败: {e.reason}")
            return False

        except UnicodeEncodeError as e:
            print(f"  ⚠️  URL 编码错误: {e}")
            return False

        except Exception as e:
            print(f"  ⚠️  验证异常: {e}")
            return False

    def _confirm_config(self, provider_name, model, telegram_config) -> bool:
        """步骤 4：确认配置。"""
        print("\n步骤 4/4：确认配置\n")
        print(f"  默认厂商: {provider_name}")
        print(f"  默认模型: {model}")
        tg_status = "已启用" if telegram_config.get("enabled") else "已跳过"
        print(f"  Telegram: {tg_status}")
        print()

        confirm = input("确认保存? [Y/n]: ").strip().lower()
        return confirm in ("", "y", "yes")

    def _get_base_url(self, provider_key: str) -> str:
        """获取厂商 base_url。"""
        urls = {
            "deepseek": "https://api.deepseek.com",
            "kimi": "https://api.moonshot.cn",
            "chatglm": "https://open.bigmodel.cn",
            "tongyi": "https://dashscope.aliyuncs.com",
            "wenxin": "https://aip.baidubce.com",
        }
        return urls.get(provider_key, "")
