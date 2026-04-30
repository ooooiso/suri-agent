#!/usr/bin/env python3
"""
suri-agent 入口

启动顺序：
1. 加载环境变量 (.env)
2. 初始化 ConfigService
3. 初始化 MemoryService（角色级独立 SQLite 存储）
4. 初始化 SecurityService
5. 初始化 FileService
6. 初始化 ModelManager（httpx 异步客户端）
7. 初始化 ModelService（委托 ModelManager 实际调用）
8. 初始化 ContextService
9. 初始化 CommService（Telegram，可选）
10. 初始化 ApprovalService
11. 初始化 ToolService
12. 初始化 TaskService
13. 启动消息监听循环

主循环架构：
- 消息队列 (asyncio.Queue) 解耦生产者和消费者
- 生产者：终端输入 / Telegram 消息 / Webhook
- 消费者：handle_user_message() → 调度 → 模型 → 结果回流
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.filesystem import FileService
from model.manager import ModelManager
from core.model_router import ModelService
from core.context import ContextService
from access.telegram.bot import CommService
from core.approval import ApprovalService
from core.tool_executor import ToolService
from core.task_dispatcher import TaskService
from mcp.registry import MCPRegistry


class SuriAgent:
    """Suri 平台主程序"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config: ConfigService = None
        self.memory: MemoryService = None
        self.security: SecurityService = None
        self.file_service: FileService = None
        self.model_manager: ModelManager = None
        self.model: ModelService = None
        self.context: ContextService = None
        self.comm: CommService = None
        self.approval: ApprovalService = None
        self.tool: ToolService = None
        self.task: TaskService = None
        self.mcp: MCPRegistry = None
        self._message_queue: asyncio.Queue = None
        self._running = False

    async def initialize(self) -> bool:
        """初始化所有服务"""
        print("=" * 50)
        print("Suri Agent 启动中...")
        print("=" * 50)

        env_path = self.project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print("[OK] 环境变量已加载")

        self.config = ConfigService(self.project_root)
        self.config.load_all()
        print("[OK] 配置服务已启动")

        self.memory = MemoryService(self.project_root, self.config)
        print("[OK] 记忆服务已启动")

        self.security = SecurityService(self.project_root, self.config)
        print("[OK] 安全服务已启动")

        self.file_service = FileService(self.project_root, self.security)
        print("[OK] 文件服务已启动")

        self.model_manager = ModelManager(self.project_root)
        self.model = ModelService(self.config, self.model_manager)
        print("[OK] 模型服务已启动")

        self.context = ContextService(self.config, self.memory)
        print("[OK] 上下文服务已启动")

        self.comm = CommService(self.config)
        connected = await self.comm.connect()
        if not connected:
            print("[WARN] 通信服务未连接，将以终端模式运行")
        else:
            print("[OK] 通信服务已启动")

        self.approval = ApprovalService(self.config, self.memory, self.security)
        print("[OK] 审批服务已启动")

        self.tool = ToolService(self.project_root, self.config)
        print("[OK] 工具服务已启动")

        self.task = TaskService(self.config, self.memory, self.context, self.model, self.comm)
        print("[OK] 任务服务已启动")

        self.mcp = MCPRegistry()
        print("[OK] MCP 服务已启动（预留）")

        # 消息队列
        self._message_queue = asyncio.Queue()
        self._running = True

        # 注册通信回调
        self.comm.on_message(self._on_external_message)

        print("=" * 50)
        print("Suri Agent 启动完成")
        print(f"角色数: {len(self.config.list_roles())}")
        print(f"规则数: {len(self.config.list_rules())}")
        print("=" * 50)
        return True

    async def run(self) -> None:
        """主循环：消息队列消费者 + 生产者 + 超时检查"""
        print("\n等待用户消息...\n")

        await asyncio.gather(
            self._message_consumer(),
            self._timeout_checker(),
            self._terminal_producer(),
            return_exceptions=True,
        )

    async def _message_consumer(self):
        """消息消费者：从队列取出消息并处理"""
        while self._running:
            try:
                user_id, text = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0
                )
                await self.handle_user_message(user_id, text)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[Consumer] 处理消息时出错: {e}")

    async def _timeout_checker(self):
        """审批超时检查器"""
        while self._running:
            try:
                await asyncio.sleep(10)
                self.approval.check_timeout()
            except Exception as e:
                print(f"[TimeoutChecker] 检查超时出错: {e}")

    async def _terminal_producer(self):
        """终端输入生产者：从 stdin 读取用户输入并放入队列"""
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                # 在非阻塞的 executor 中运行 input()
                text = await loop.run_in_executor(
                    None, lambda: input("您 > ")
                )
                text = text.strip()
                if text:
                    await self._message_queue.put(("terminal_user", text))
            except (EOFError, KeyboardInterrupt):
                self._running = False
                print("\n正在关闭 Suri Agent...")
                break
            except Exception as e:
                print(f"[Terminal] 读取输入出错: {e}")

    def _on_external_message(self, msg):
        """外部消息回调（Telegram / Webhook）"""
        # 将 StandardMessage 放入队列
        user_id = msg.sender_role or "external_user"
        text = msg.body.get('content', '')
        asyncio.create_task(self._message_queue.put((user_id, text)))

    async def handle_user_message(self, user_id: str, text: str) -> None:
        """
        处理用户消息入口

        闭环：创建任务 → 调度分派 → 模型分析 → 结果回流
        """
        # 1. 创建任务
        task_id = self.task.receive_task(user_id, text)
        print(f"[Main] 任务 {task_id} 已创建")

        # 2. 调度分派
        result = await self.task.dispatch(task_id)

        if not result['success']:
            print(f"[Main] 任务调度失败: {result.get('error')}")
            # 直接由 suri 回复用户（回退路径）
            await self._fallback_reply(user_id, text)
            return

        print(f"[Main] 任务 {task_id} 已分派给 {result['target_director']}")

        # 3. 结果回流（简化版：直接让 suri 处理并回复）
        # 实际应由目标角色执行后回流，此处用 suri 直接回复作为闭环演示
        await self._fallback_reply(user_id, text)

    async def _fallback_reply(self, user_id: str, text: str):
        """回退回复：当调度失败时，suri 直接调用模型回复用户"""
        if self.model_manager.is_first_run():
            print("[suri] 未配置模型，无法回复。请先使用 /model 命令添加模型。")
            return

        messages = [
            {"role": "system", "content": "你是 Suri，central 部门负责人。请简洁回复用户。"},
            {"role": "user", "content": text},
        ]

        try:
            reply = await self.model_manager.chat(messages)
            if reply:
                print(f"\n[suri] {reply}\n")
            else:
                print("\n[suri] 模型调用失败，请检查 API Key 和网络连接。\n")
        except Exception as e:
            print(f"\n[suri] 回复出错: {e}\n")

    async def shutdown(self):
        """优雅关闭"""
        self._running = False
        if self.model_manager:
            await self.model_manager.close()
        print("[OK] Suri Agent 已关闭")


def main():
    project_root = Path(__file__).parent.parent
    agent = SuriAgent(project_root)

    async def run():
        try:
            await agent.initialize()
            await agent.run()
        except KeyboardInterrupt:
            print("\n收到中断信号...")
        finally:
            await agent.shutdown()

    asyncio.run(run())


if __name__ == '__main__':
    main()
