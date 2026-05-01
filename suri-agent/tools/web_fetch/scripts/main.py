"""
web_fetch 工具

职责：
- 获取指定 URL 的网页内容，提取纯文本
- 使用搜索引擎搜索关键词，返回结果摘要

调用方：所有角色（通过 ToolService）

安全说明：
- 只读操作，不修改任何本地文件
- URL 经过格式校验，禁止 file:// 等本地协议
- 返回内容长度限制在 8000 字符以内，避免超出模型上下文
"""

import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse

# 定位项目根目录
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "suri-agent"))


def execute(params: dict) -> dict:
    """
    web_fetch 工具入口

    Args:
        params:
            action: str 操作类型
                - "fetch": 获取指定 URL 的网页内容
                    url: str 目标网页地址
                    max_length: int 可选，最大返回字符数（默认 8000）
                - "search": 使用搜索引擎搜索关键词
                    query: str 搜索关键词
                    max_results: int 可选，最大结果数（默认 5）

    Returns:
        dict: {'success': bool, 'data': Any, 'error': str}
    """
    action = params.get('action', 'fetch')

    try:
        if action == 'fetch':
            return _fetch_url(params.get('url'), params.get('max_length', 8000))
        elif action == 'search':
            return _search(params.get('query'), params.get('max_results', 5))
        else:
            return {'success': False, 'data': None, 'error': f'未知操作: {action}'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}


def _validate_url(url: str) -> Optional[str]:
    """校验 URL 格式，返回错误信息或 None"""
    if not url:
        return '缺少参数 url'

    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return f'无效的 URL: {url}'

    if parsed.scheme not in ('http', 'https'):
        return f'不支持的协议: {parsed.scheme}，仅支持 http/https'

    # 禁止访问本地地址
    hostname = parsed.netloc.split(':')[0].lower()
    if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '[::1]'):
        return '禁止访问本地地址'

    return None


def _extract_text(html: str, max_length: int = 8000) -> str:
    """从 HTML 中提取纯文本"""
    # 移除 script 和 style 标签及其内容
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 将常用块级标签替换为换行
    for tag in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr', 'br']:
        html = re.sub(rf'</{tag}>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(rf'<{tag}[^>]*>', '\n', html, flags=re.IGNORECASE)

    # 移除所有剩余 HTML 标签
    text = re.sub(r'<[^>]+>', '', html)

    # 解码 HTML 实体
    import html as html_module
    text = html_module.unescape(text)

    # 清理空白
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    text = '\n'.join(lines)

    # 限制长度
    if len(text) > max_length:
        text = text[:max_length] + '\n...（内容已截断）'

    return text


def _fetch_url(url: str, max_length: int = 8000) -> dict:
    """获取指定 URL 的网页内容"""
    error = _validate_url(url)
    if error:
        return {'success': False, 'data': None, 'error': error}

    try:
        import httpx
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            resp = client.get(url, headers=headers)
            resp.raise_for_status()

            content_type = resp.headers.get('content-type', '')
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                # 非 HTML 内容，直接返回文本
                text = resp.text[:max_length]
                if len(resp.text) > max_length:
                    text += '\n...（内容已截断）'
                return {
                    'success': True,
                    'data': {
                        'url': url,
                        'title': '',
                        'text': text,
                        'content_type': content_type,
                    },
                    'error': ''
                }

            # 提取标题
            title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.DOTALL | re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else ''

            # 提取正文文本
            text = _extract_text(resp.text, max_length)

            return {
                'success': True,
                'data': {
                    'url': url,
                    'title': title,
                    'text': text,
                    'content_type': content_type,
                },
                'error': ''
            }

    except httpx.TimeoutException:
        return {'success': False, 'data': None, 'error': '请求超时（15秒）'}
    except httpx.HTTPStatusError as e:
        return {'success': False, 'data': None, 'error': f'HTTP 错误: {e.response.status_code}'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': f'获取网页失败: {e}'}


def _search(query: str, max_results: int = 5) -> dict:
    """使用 DuckDuckGo HTML 接口搜索关键词"""
    if not query or not query.strip():
        return {'success': False, 'data': None, 'error': '缺少参数 query'}

    try:
        import httpx
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            # DuckDuckGo HTML 搜索接口
            search_url = 'https://html.duckduckgo.com/html/'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
            }
            resp = client.post(search_url, data={'q': query.strip()}, headers=headers)
            resp.raise_for_status()

            # 解析搜索结果
            results = []
            # DuckDuckGo HTML 结果格式
            result_blocks = re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                resp.text
            )

            for i, (href, title_html) in enumerate(result_blocks[:max_results]):
                # 清理标题 HTML
                title = re.sub(r'<[^>]+>', '', title_html)
                title = title.strip()

                # 获取摘要
                snippet_match = re.search(
                    rf'<a[^>]*class="result__a"[^>]*href="{re.escape(href)}"[^>]*>.*?</a>\s*</h2>\s*<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                    resp.text,
                    re.DOTALL
                )
                snippet = ''
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1))
                    snippet = snippet.strip()

                results.append({
                    'title': title,
                    'url': href,
                    'snippet': snippet,
                })

            return {
                'success': True,
                'data': {
                    'query': query,
                    'results': results,
                    'count': len(results),
                },
                'error': ''
            }

    except httpx.TimeoutException:
        return {'success': False, 'data': None, 'error': '搜索请求超时（15秒）'}
    except httpx.HTTPStatusError as e:
        return {'success': False, 'data': None, 'error': f'搜索 HTTP 错误: {e.response.status_code}'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': f'搜索失败: {e}'}


if __name__ == '__main__':
    # 简单测试
    import json
    print(json.dumps(execute({'action': 'fetch', 'url': 'https://api.deepseek.com/docs'}), ensure_ascii=False, indent=2))
