#!/usr/bin/env python3
"""
Suri 终端客户端

简易的命令行交互界面，直接调用 suri-agent 核心服务。
无需启动 JSON-RPC 后端，直接在进程中与 suri 对话。

使用方式:
    python -m suri-agent.access.tui.cli
    或: python suri-agent/access/tui/cli.py
"""

import sys
import uuid
import readline  # 改善终端输入体验（支持中文退格删除、光标移动）
from pathlib import Path
from datetime import datetime

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.filesystem import FileService
from core.context import ContextService
from core.model_router import ModelService
from core.task_dispatcher import TaskService
from core.approval import ApprovalService
from core.tool_executor import ToolService
from mcp.registry import MCPRegistry


class SuriTerminal:
    """终端交互界面"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.config = None
        self.memory = None
        self.security = None
        self.filesystem = None
        self.context = None
        self.model = None
        self.task = None
        self.user_id = f"terminal_user_{datetime.now().strftime('%H%M%S')}"
        
    def initialize(self):
        """初始化服务"""
        print("[初始化] 加载配置...")
        self.config = ConfigService(self.project_root)
        self.config.load_all()
        
        self.memory = MemoryService(self.project_root, self.config)
        self.security = SecurityService(self.config)
        self.filesystem = FileService(self.project_root, self.security)
        self.model = ModelService(self.config)
        self.context = ContextService(self.config, self.memory)
        self.task = TaskService(self.config, self.memory, self.context, self.model, None)
        
        print(f"[就绪] 已加载 {len(self.config.list_roles())} 个角色")
        print("")
        
    def print_banner(self):
        """打印欢迎信息"""
        print("╔══════════════════════════════════════╗")
        print("║         Suri 智能体平台              ║")
        print("║     终端交互界面 (CLI Mode)          ║")
        print("╠══════════════════════════════════════╣")
        print("║  输入需求，suri 将为您调度          ║")
        print("║  输入 /help 查看命令                ║")
        print("║  输入 /quit 退出                    ║")
        print("╚══════════════════════════════════════╝")
        print("")
        
    def handle_command(self, text: str) -> bool:
        """处理斜杠命令，返回是否继续运行"""
        text = text.strip().lower()
        
        if text in ['/quit', '/exit', 'quit', 'exit']:
            print("\n再见！")
            return False
            
        if text == '/help':
            print("")
            print("可用命令:")
            print("  /roles      - 列出所有角色")
            print("  /rules      - 列出所有规则")
            print("  /tasks      - 查看任务列表")
            print("  /status     - 查看平台状态")
            print("  /clear      - 清屏")
            print("  /help       - 显示此帮助")
            print("  /quit       - 退出")
            print("")
            return True
            
        if text == '/roles':
            roles = self.config.list_roles()
            print(f"\n共 {len(roles)} 个角色:")
            for role_id in roles:
                entry = self.config.get_role_soul(role_id)
                if entry:
                    print(f"  • {role_id:20s} | {entry.meta.get('nickname', ''):10s} | {entry.meta.get('department', '')}")
            print("")
            return True
            
        if text == '/rules':
            rules = self.config.list_rules()
            print(f"\n共 {len(rules)} 条规则:")
            for rule_id in rules:
                entry = self.config.get_rule(rule_id)
                if entry:
                    print(f"  • {rule_id:25s} | {entry.meta.get('name', '')}")
            print("")
            return True
            
        if text == '/tasks':
            print("\n[任务列表] 功能待实现（需要查询 state.db）")
            print("")
            return True
            
        if text == '/status':
            print("\n平台状态:")
            print(f"  角色数: {len(self.config.list_roles())}")
            print(f"  规则数: {len(self.config.list_rules())}")
            print(f"  用户ID: {self.user_id}")
            print("")
            return True
            
        if text == '/clear':
            print("\033[2J\033[H", end="")
            self.print_banner()
            return True
            
        return True
        
    async def handle_user_input(self, text: str):
        """处理用户输入"""
        if text.startswith('/'):
            return self.handle_command(text)
            
        # 创建任务
        task_id = self.task.receive_task(self.user_id, text)
        print(f"\n[suri] 已接收任务 {task_id}")
        print(f"[suri] 正在分析需求: {text[:60]}...")
        
        # 1. 问候语/闲聊识别
        greetings = ['你好', '您好', '在吗', '嗨', 'hello', 'hi', '早上好', '下午好', '晚上好']
        if any(g in text.lower() for g in greetings):
            print(f"\n[suri] 你好！我是 Suri，你的智能体调度助手。")
            print(f"[suri] 我可以帮你：")
            print(f"  • 开发新功能、编写脚本 → 开发部（达芬奇）")
            print(f"  • 设计图像、视频、海报 → 设计部（香奈儿）")
            print(f"  • 运维、安全、配置管理 → 运维部（居里）")
            print(f"  • 角色管理、组织架构 → 人力资源部（玛丽安）")
            print(f"[suri] 请直接告诉我你的需求，我会帮你调度到最合适的团队。")
            print("")
            return True
        
        # 2. 读取 function_index 进行匹配（模拟二次调度）
        func_index = self.config.get_function_index()
        if func_index and 'departments' in func_index.meta:
            # 简单关键词匹配
            keywords = {
                'design': ['设计', '图像', '视频', '美术', '视觉', '画图', '海报', '画画', '绘制'],
                'engineering': ['开发', '代码', '程序', '脚本', '后台', '部署', '功能', '写个', '做一个', '搭建', '编程'],
                'ops': ['运维', '安全', '配置', '流程', 'Git', '监控', '审查', '备份'],
                'resource': ['资源', '文件', '存储', '归档', '清理', '压缩'],
                'hr': ['角色', '人事', '组织', '创建角色', '注销', '新员工', '招聘'],
            }
            
            matched_dept = None
            for dept in func_index.meta['departments']:
                dept_id = dept.get('id', '')
                if dept_id == 'central':
                    continue
                for kw in keywords.get(dept_id, []):
                    if kw in text:
                        matched_dept = dept
                        break
                if matched_dept:
                    break
            
            if matched_dept:
                lead_role = matched_dept.get('lead_role', '')
                dept_name = matched_dept.get('name', '')
                print(f"\n[suri] 分析完成，匹配到部门: {dept_name}")
                print(f"[suri] 调度给总监: {lead_role}")
                print(f"\n  → 任务已下发，等待 {lead_role} 处理...")
                print(f"  → 如遇问题将通过用户决策回路回流给您")
            else:
                # 3. 无法匹配时，识别能力缺口，提示用户扩展
                print(f"\n[suri] 我分析了你的需求，但当前平台暂无匹配的处理能力。")
                print(f"[suri] 当前覆盖的部门：")
                for dept in func_index.meta['departments']:
                    if dept.get('id') == 'central':
                        continue
                    print(f"  • {dept.get('name', '')}：{dept.get('function', '')[:30]}...")
                print(f"\n[suri] 建议方案：")
                print(f"  1. 重新描述需求，使用更具体的关键词（如\"开发\"\"设计\"\"运维\"）")
                print(f"  2. 输入 /roles 查看所有可用角色")
                print(f"  3. 如果你认为需要新的部门或角色来处理这个需求，")
                print(f"     请回复：\"新建部门：[部门名称]，职能：[描述]\" 或")
                print(f"     \"新建角色：[角色名称]，技能：[描述]\"")
                print(f"\n[suri] 我将把组织扩展请求转发给 hr_admin（玛丽安）处理。")
        else:
            print(f"\n[suri] 部门索引未加载，请联系 config_admin")
            
        print("")
        return True
        
    async def run(self):
        """主循环"""
        self.initialize()
        self.print_banner()
        
        running = True
        while running:
            try:
                text = input("您 > ").strip()
                if not text:
                    continue
                running = await self.handle_user_input(text)
            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except EOFError:
                break


async def main():
    terminal = SuriTerminal()
    await terminal.run()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
