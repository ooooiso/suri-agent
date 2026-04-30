#!/usr/bin/env python3
"""
suri-agent 入口

启动顺序：
1. 加载环境变量 (.env)
2. 初始化 ConfigService（扫描 group/、skills/、tools/ 中的 .md 配置）
3. 初始化 MemoryService（角色级独立 SQLite 存储）
4. 初始化 SecurityService（加载代码化安全规则）
5. 初始化 FileService（注册安全钩子）
6. 初始化 ModelService（模型路由）
7. 初始化 ContextService（上下文构建器）
8. 初始化 CommService（连接 Telegram，可选）
9. 初始化 ApprovalService（审批引擎）
10. 初始化 ToolService（工具执行器）
11. 初始化 TaskService（调度引擎）
12. 初始化 MCPRegistry（MCP 扩展，可选）
13. 启动消息监听循环
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.filesystem import FileService
from core.model_router import ModelService
from core.context import ContextService
from access.telegram.bot import CommService
from core.approval import ApprovalService
from core.tool_executor import ToolService
from core.task_dispatcher import TaskService
from mcp.registry import MCPRegistry


class SuriAgent:
    """
    Suri 平台主程序
    
    所有服务通过此入口协调，外部配置驱动业务逻辑。
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config: ConfigService = None
        self.memory: MemoryService = None
        self.security: SecurityService = None
        self.file_service: FileService = None
        self.model: ModelService = None
        self.context: ContextService = None
        self.comm: CommService = None
        self.approval: ApprovalService = None
        self.tool: ToolService = None
        self.task: TaskService = None
        self.mcp: MCPRegistry = None
    
    async def initialize(self) -> bool:
        """初始化所有服务"""
        print("=" * 50)
        print("Suri Agent 启动中...")
        print("=" * 50)
        
        # 1. 加载环境变量
        env_path = self.project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print("[OK] 环境变量已加载")
        
        # 2. 配置服务（最先初始化，其他服务依赖它）
        self.config = ConfigService(self.project_root)
        self.config.load_all()
        print("[OK] 配置服务已启动")
        
        # 3. 记忆服务
        self.memory = MemoryService(self.project_root, self.config)
        print("[OK] 记忆服务已启动")
        
        # 4. 安全服务
        self.security = SecurityService(self.project_root, self.config)
        print("[OK] 安全服务已启动")
        
        # 5. 文件服务
        self.file_service = FileService(self.project_root, self.security)
        print("[OK] 文件服务已启动")
        
        # 6. 模型服务
        self.model = ModelService(self.config)
        print("[OK] 模型服务已启动")
        
        # 7. 上下文服务
        self.context = ContextService(self.config, self.memory)
        print("[OK] 上下文服务已启动")
        
        # 8. 通信服务
        self.comm = CommService(self.config)
        connected = await self.comm.connect()
        if not connected:
            print("[WARN] Telegram 连接失败，继续以离线模式运行")
        else:
            print("[OK] 通信服务已启动")
        
        # 9. 审批服务
        self.approval = ApprovalService(self.config, self.memory, self.security)
        print("[OK] 审批服务已启动")
        
        # 10. 工具服务
        self.tool = ToolService(self.project_root, self.config)
        print("[OK] 工具服务已启动")
        
        # 11. 任务服务
        self.task = TaskService(self.config, self.memory, self.context, self.model, self.comm)
        print("[OK] 任务服务已启动")
        
        # 12. MCP 服务（可选）
        self.mcp = MCPRegistry()
        print("[OK] MCP 服务已启动（预留）")
        
        print("=" * 50)
        print("Suri Agent 启动完成")
        print(f"角色数: {len(self.config.list_roles())}")
        print(f"规则数: {len(self.config.list_rules())}")
        print("=" * 50)
        return True
    
    async def run(self) -> None:
        """主循环"""
        print("\n等待用户消息...")
        
        # TODO: 实现 Telegram 消息监听循环
        # 当前为占位，实际应使用 asyncio 事件循环处理消息
        
        try:
            while True:
                # 模拟处理：每 10 秒检查一次超时审批
                await asyncio.sleep(10)
                self.approval.check_timeout()
                
        except KeyboardInterrupt:
            print("\n正在关闭 Suri Agent...")
    
    async def handle_user_message(self, user_id: str, text: str) -> None:
        """
        处理用户消息入口
        
        1. 创建任务
        2. 调度分派
        """
        task_id = self.task.receive_task(user_id, text)
        result = await self.task.dispatch(task_id)
        
        if not result['success']:
            # 调度失败，直接回复用户
            print(f"[ERROR] 任务调度失败: {result.get('error')}")


def main():
    """命令行入口"""
    project_root = Path(__file__).parent.parent
    agent = SuriAgent(project_root)
    
    asyncio.run(agent.initialize())
    asyncio.run(agent.run())


if __name__ == '__main__':
    main()
