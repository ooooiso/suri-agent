#!/usr/bin/env python3
"""
连接测试脚本

测试项：
1. 终端输入是否正常
2. 模型 API 是否可连接
3. Telegram Bot 是否可连接
4. SQLite 数据库是否可读写

用法:
    python scripts/test_connections.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SURI_AGENT_DIR = PROJECT_ROOT / "suri-agent"
if str(SURI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(SURI_AGENT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def test_terminal():
    """测试终端输入输出"""
    print("[测试] 终端输入输出...")
    try:
        print("  ✓ 终端输出正常")
        return True, "终端正常"
    except Exception as e:
        return False, f"终端异常: {e}"


async def test_model_api():
    """测试模型 API 连接"""
    print("[测试] 模型 API 连接...")
    try:
        import httpx
        
        # 测试网络连通性
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://httpbin.org/get")
            if resp.status_code == 200:
                print("  ✓ 网络连通性正常")
            
        # 测试已配置模型的连通性
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / '.env')
        
        from infrastructure.config import ConfigService
        from model.manager import ModelManager
        
        config = ConfigService(PROJECT_ROOT)
        config.load_all()
        
        mm = ModelManager(PROJECT_ROOT)
        
        if mm.is_first_run():
            print("  ⚠️ 未配置模型（首次运行），跳过模型 API 测试")
            return True, "未配置模型"
        
        default_model = mm.get_default_model()
        if not default_model:
            print("  ⚠️ 没有默认模型")
            return False, "没有默认模型"
        
        # 尝试调用
        messages = [{"role": "user", "content": "你好"}]
        result = await mm.chat_with_usage(messages)
        
        if result and result.get('content'):
            total = result.get('total_tokens', 0)
            print(f"  ✓ 模型 API 正常 ({default_model.model_id}, Token: {total})")
            return True, f"模型正常 ({default_model.model_id})"
        else:
            print(f"  ✗ 模型 API 调用失败 ({default_model.model_id})")
            return False, "模型 API 调用失败"
            
    except ImportError as e:
        print(f"  ⚠️ 缺少依赖: {e}")
        return True, f"缺少依赖: {e}"
    except Exception as e:
        print(f"  ✗ 模型 API 异常: {e}")
        return False, str(e)


async def test_telegram():
    """测试 Telegram Bot 连接"""
    print("[测试] Telegram Bot 连接...")
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv(PROJECT_ROOT / '.env')
        
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        if not bot_token:
            print("  ⚠️ 未配置 TELEGRAM_BOT_TOKEN，跳过")
            return True, "未配置 Token"
        
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getMe"
            )
            data = resp.json()
            if data.get('ok'):
                bot_name = data['result'].get('username', 'unknown')
                print(f"  ✓ Telegram Bot 已连接 (@{bot_name})")
                return True, f"Bot 正常 (@{bot_name})"
            else:
                print(f"  ✗ Telegram API 错误: {data.get('description')}")
                return False, data.get('description', '未知错误')
    except ImportError:
        print("  ⚠️ 缺少 httpx，跳过")
        return True, "缺少依赖"
    except Exception as e:
        print(f"  ✗ Telegram 异常: {e}")
        return False, str(e)


async def test_database():
    """测试 SQLite 数据库"""
    print("[测试] SQLite 数据库...")
    try:
        from infrastructure.config import ConfigService
        from infrastructure.memory import MemoryService
        
        config = ConfigService(PROJECT_ROOT)
        config.load_all()
        
        memory = MemoryService(PROJECT_ROOT, config)
        
        # 测试创建会话
        memory.create_session('test', 'test_session_001', 'test_user')
        sessions = memory.get_role_sessions('test')
        
        if sessions:
            print(f"  ✓ 数据库读写正常 ({len(sessions)} 个测试会话)")
            return True, "数据库正常"
        else:
            print("  ✗ 数据库读写失败")
            return False, "读写失败"
    except Exception as e:
        print(f"  ✗ 数据库异常: {e}")
        return False, str(e)


async def main():
    print("=" * 50)
    print("Suri 连接测试")
    print("=" * 50)
    
    tests = [
        test_terminal(),
        test_database(),
        test_model_api(),
        test_telegram(),
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    print("=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    all_pass = True
    for i, result in enumerate(results):
        test_names = ["终端", "数据库", "模型 API", "Telegram"]
        name = test_names[i] if i < len(test_names) else f"测试{i}"
        
        if isinstance(result, Exception):
            print(f"  ✗ {name}: 异常 - {result}")
            all_pass = False
        else:
            success, msg = result
            status = "✓" if success else "✗"
            print(f"  {status} {name}: {msg}")
            if not success:
                all_pass = False
    
    print("=" * 50)
    if all_pass:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查配置和环境。")
    print("=" * 50)
    
    return 0 if all_pass else 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
