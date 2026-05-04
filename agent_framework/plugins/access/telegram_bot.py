"""Telegram Bot API 封装 — 基于 urllib 零依赖实现。"""

import json
import ssl
import urllib.request
from typing import Any, Dict, List, Optional


class TelegramBotAPI:
    """Telegram Bot API 客户端。"""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str):
        self._token = token
        self._ssl_context = ssl.create_default_context()

    def _request(self, method: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """发送请求到 Telegram API。"""
        url = self.BASE_URL.format(token=self._token, method=method)
        # getMe / getUpdates 用 GET，其余用 POST
        if method in ("getMe", "getUpdates") and not payload:
            req = urllib.request.Request(url, method="GET")
        else:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers = {"Content-Type": "application/json; charset=utf-8"}
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"[TelegramBot] HTTP {e.code}: {body}")
            return None
        except urllib.error.URLError as e:
            print(f"[TelegramBot] 网络错误 ({method}): {e.reason} — 检查网络连接或代理设置")
            return None
        except Exception as e:
            print(f"[TelegramBot] API error ({method}): {e}")
            return None

    def get_updates(self, offset: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """获取更新。"""
        result = self._request("getUpdates", {"offset": offset, "limit": limit})
        if result and result.get("ok"):
            return result.get("result", [])
        return []

    def send_message(self, chat_id: int, text: str, reply_to_message_id: Optional[int] = None) -> bool:
        """发送消息。"""
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        result = self._request("sendMessage", payload)
        return result is not None and result.get("ok", False)

    def get_me(self) -> Optional[Dict[str, Any]]:
        """获取 Bot 信息。"""
        result = self._request("getMe", {})
        if result and result.get("ok"):
            return result.get("result")
        return None

    def set_my_commands(self, commands: List[Dict[str, str]]) -> bool:
        """设置 Bot 命令列表，用户输入 / 时客户端自动提示。"""
        result = self._request("setMyCommands", {"commands": commands})
        return result is not None and result.get("ok", False)
