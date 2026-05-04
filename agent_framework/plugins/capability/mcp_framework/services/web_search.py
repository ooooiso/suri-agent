"""web_search — MCP 网络搜索服务。

提供网页获取和网络搜索能力。

安全规则：
- 禁止访问内网地址和 file:// 协议
- 缓存机制减少重复请求
- 超时控制
"""

import asyncio
import json
import time
import re
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

# ── 安全配置 ──

BLOCKED_SCHEMES = ("file://", "ftp://")
BLOCKED_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0", "::1", "10.", "172.16.", "192.168.")

DEFAULT_TIMEOUT = 15
CACHE_EXPIRY = {
    "search": 3600,      # 搜索结果缓存 1 小时
    "fetch": 86400,      # 网页内容缓存 24 小时
}

TOOL_DEFINITIONS = {
    "web_fetch": {
        "name": "web_fetch",
        "description": "获取网页内容并转为 Markdown 格式",
        "params_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要获取的网页 URL"},
                "timeout": {"type": "integer", "description": "超时秒数", "default": 15},
            },
            "required": ["url"],
        },
        "permission": "public",
    },
    "web_search": {
        "name": "web_search",
        "description": "搜索网络内容（使用 DuckDuckGo）",
        "params_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"},
                "limit": {"type": "integer", "description": "返回结果数量", "default": 5},
            },
            "required": ["query"],
        },
        "permission": "public",
    },
}

# 缓存
_cache: Dict[str, Dict] = {}


def _validate_url(url: str) -> Optional[str]:
    """验证 URL 安全性。返回错误信息或 None。"""
    # 检查 scheme
    for scheme in BLOCKED_SCHEMES:
        if url.lower().startswith(scheme):
            return f"禁止访问此协议: {scheme}"

    # 解析 URL
    try:
        parsed = urlparse(url)
    except Exception:
        return f"无效 URL: {url}"

    host = parsed.hostname or ""
    # 检查内网地址
    for blocked in BLOCKED_HOSTS:
        if host.startswith(blocked):
            return f"禁止访问内网地址: {host}"

    return None


def _get_cache(key: str, cache_type: str) -> Optional[str]:
    """获取缓存内容（如果未过期）。"""
    cache_key = f"{cache_type}:{key}"
    entry = _cache.get(cache_key)
    if not entry:
        return None
    if time.time() - entry["time"] < CACHE_EXPIRY.get(cache_type, 3600):
        return entry["data"]
    del _cache[cache_key]
    return None


def _set_cache(key: str, data: str, cache_type: str) -> None:
    """设置缓存。"""
    cache_key = f"{cache_type}:{key}"
    _cache[cache_key] = {"data": data, "time": time.time()}


async def handle_tool_call(tool_name: str, params: Dict[str, Any],
                           project_root: Path) -> Dict[str, Any]:
    """处理 web_search 工具调用。"""
    if tool_name == "web_fetch":
        return await _handle_web_fetch(params)
    elif tool_name == "web_search":
        return await _handle_web_search(params)
    else:
        return {"error_code": 5001, "error_message": f"未知网络搜索工具: {tool_name}"}


async def _handle_web_fetch(params: Dict[str, Any]) -> Dict[str, Any]:
    """获取网页内容。"""
    url = params.get("url", "")
    timeout = min(int(params.get("timeout", DEFAULT_TIMEOUT)), 60)

    # 安全检查
    error = _validate_url(url)
    if error:
        return {"error_code": 6001, "error_message": error}

    # 检查缓存
    cached = _get_cache(url, "fetch")
    if cached:
        return {"success": True, "content": cached, "cached": True, "source": url}

    # 获取网页
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SuriBot/1.0)",
            })
            response.raise_for_status()
            html = response.text

        # 简单 HTML 转 Markdown
        markdown = _html_to_markdown(html)

        _set_cache(url, markdown, "fetch")
        return {"success": True, "content": markdown, "cached": False, "source": url}
    except ImportError:
        return {"error_code": 6002, "error_message": "httpx 未安装，无法获取网页"}
    except Exception as e:
        return {"error_code": 6003, "error_message": f"获取网页失败: {e}"}


async def _handle_web_search(params: Dict[str, Any]) -> Dict[str, Any]:
    """搜索网络内容。"""
    query = params.get("query", "")
    limit = min(int(params.get("limit", 5)), 20)

    # 检查缓存
    cached = _get_cache(query, "search")
    if cached:
        return {"success": True, "results": json.loads(cached), "cached": True, "query": query}

    try:
        import httpx
        # 使用 DuckDuckGo 搜索
        url = "https://lite.duckduckgo.com/lite/"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, data={"q": query})
            response.raise_for_status()
            html = response.text

        # 从 HTML 提取搜索结果
        results = _parse_duckduckgo_results(html, limit)

        _set_cache(query, json.dumps(results), "search")
        return {"success": True, "results": results, "cached": False, "query": query}
    except ImportError:
        return {"error_code": 6002, "error_message": "httpx 未安装，无法搜索"}
    except Exception as e:
        return {"error_code": 6003, "error_message": f"搜索失败: {e}"}


def _html_to_markdown(html: str) -> str:
    """简单 HTML 转 Markdown。"""
    # 移除 script 和 style
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
    # 移除 HTML 标签
    html = re.sub(r'<[^>]+>', '', html)
    # 解码 HTML 实体
    html = html.replace('&', '&').replace('<', '<').replace('>', '>')
    html = html.replace('"', '"').replace('&#39;', "'")
    # 移除多余空白
    lines = [line.strip() for line in html.split('\n')]
    lines = [line for line in lines if line]
    return '\n'.join(lines)


def _parse_duckduckgo_results(html: str, limit: int) -> list:
    """解析 DuckDuckGo 搜索结果。"""
    results = []
    # 提取搜索结果链接
    links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html)
    seen = set()
    for href, text in links:
        if not href.startswith('http'):
            continue
        if href in seen:
            continue
        seen.add(href)
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if clean_text:
            results.append({
                "title": clean_text[:100],
                "url": href,
            })
        if len(results) >= limit:
            break
    return results