#!/usr/bin/env python3
"""
模型连接深度诊断脚本

测试项：
1. 多次调用同一模型，观察成功率/延迟/错误类型
2. 测试不同端点的连通性
3. 检查 httpx 超时和重 retry 行为
4. 记录完整的请求/响应链

用法:
    python scripts/diagnose_model.py
"""

import sys
import asyncio
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "suri-agent"))
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from model.manager import ModelManager


async def test_single_call(mm: ModelManager, messages, attempt: int):
    """单次调用测试，返回详细结果"""
    start = time.time()
    try:
        result = await mm.chat_with_usage(messages)
        elapsed = time.time() - start
        if result and result.get("content"):
            return {
                "attempt": attempt,
                "success": True,
                "latency_ms": round(elapsed * 1000, 1),
                "model_used": result.get("model_used", "unknown"),
                "prompt_tokens": result.get("prompt_tokens", 0),
                "completion_tokens": result.get("completion_tokens", 0),
                "total_tokens": result.get("total_tokens", 0),
                "content_preview": result["content"][:60],
            }
        else:
            return {
                "attempt": attempt,
                "success": False,
                "latency_ms": round(elapsed * 1000, 1),
                "error": "返回空内容",
            }
    except httpx.TimeoutException as e:
        elapsed = time.time() - start
        return {
            "attempt": attempt,
            "success": False,
            "latency_ms": round(elapsed * 1000, 1),
            "error": f"超时: {e}",
        }
    except httpx.HTTPStatusError as e:
        elapsed = time.time() - start
        return {
            "attempt": attempt,
            "success": False,
            "latency_ms": round(elapsed * 1000, 1),
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "attempt": attempt,
            "success": False,
            "latency_ms": round(elapsed * 1000, 1),
            "error": f"{type(e).__name__}: {e}",
        }


async def diagnose():
    print("=" * 60)
    print("模型连接深度诊断")
    print("=" * 60)

    mm = ModelManager(PROJECT_ROOT)
    print(f"\n[配置] 首次运行: {mm.is_first_run()}")
    models = mm.list_models()
    print(f"[配置] 已配置模型数: {len(models)}")
    for m in models:
        print(f"       - {m.name} ({m.model_id}) @ {m.base_url}")
        print(f"         API Key: {'已设置' if m.api_key else '未设置'} (长度 {len(m.api_key)})")
        print(f"         默认: {m.is_default}")

    if not models:
        print("\n❌ 没有配置任何模型，诊断终止。")
        return

    # 测试网络连通性
    print("\n" + "=" * 60)
    print("网络连通性测试")
    print("=" * 60)
    for m in models:
        domain = m.base_url.split("/")[2]
        url = f"{m.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 用错误 key 发一个极简请求，只看能否连上服务器
                resp = await client.post(
                    url,
                    json={"model": m.model_id, "messages": [{"role": "user", "content": "hi"}]},
                    headers={"Authorization": "Bearer test_invalid_key"},
                )
                print(f"  {m.model_id} → {domain}: HTTP {resp.status_code}, 可达 ✅")
        except httpx.ConnectError as e:
            print(f"  {m.model_id} → {domain}: 连接失败 ❌ ({e})")
        except httpx.TimeoutException:
            print(f"  {m.model_id} → {domain}: 连接超时 ❌")
        except Exception as e:
            print(f"  {m.model_id} → {domain}: 异常 ❌ ({type(e).__name__}: {e})")

    # 连续调用测试
    print("\n" + "=" * 60)
    print("连续调用压力测试 (10 次)")
    print("=" * 60)

    messages = [{"role": "user", "content": "你好，简单回复一个'收到'即可。"}]
    results = []

    for i in range(1, 11):
        print(f"\n  第 {i}/10 次调用...", end=" ")
        r = await test_single_call(mm, messages, i)
        results.append(r)
        if r["success"]:
            print(f"✅ {r['latency_ms']}ms | {r['total_tokens']} tokens")
        else:
            print(f"❌ {r['latency_ms']}ms | {r['error'][:80]}")
        await asyncio.sleep(0.5)  # 间隔 500ms，避免触发限流

    # 汇总
    print("\n" + "=" * 60)
    print("诊断汇总")
    print("=" * 60)

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count
    avg_latency = sum(r["latency_ms"] for r in results if r["success"]) / max(success_count, 1)

    print(f"  总调用次数: {len(results)}")
    print(f"  成功: {success_count} | 失败: {fail_count}")
    print(f"  成功率: {success_count / len(results) * 100:.0f}%")
    if success_count > 0:
        print(f"  平均延迟: {avg_latency:.0f}ms")

    if fail_count > 0:
        print("\n  错误分布:")
        errors = {}
        for r in results:
            if not r["success"]:
                err = r["error"]
                # 归类
                if "429" in err or "1305" in err or "访问量过大" in err:
                    key = "429 限流"
                elif "401" in err:
                    key = "401 鉴权失败"
                elif "超时" in err:
                    key = "超时"
                elif "连接" in err:
                    key = "连接失败"
                else:
                    key = err[:30]
                errors[key] = errors.get(key, 0) + 1
        for k, v in errors.items():
            print(f"    - {k}: {v} 次")

    if fail_count >= 7:
        print("\n⚠️ 判定: 模型服务不稳定，建议：")
        print("   1. 配置备用模型（不同厂商）")
        print("   2. 降低并发/增加重试间隔")
        print("   3. 避开高峰期使用")
    elif fail_count >= 3:
        print("\n⚠️ 判定: 模型服务偶发异常，建议配置备用模型")
    else:
        print("\n✅ 判定: 模型连接基本正常")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(diagnose())
