#!/usr/bin/env python3
"""
输出框架测试
验证：
1. OutputPayload 创建和序列化
2. 各通道投递能力（终端/文件/记忆/日志）
3. OutputRouter 路由决策
4. 多通道链式投递
5. 角色-通道映射正确性
"""
import sys, os, json, time
from pathlib import Path
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.logger import LoggerService
from access.output import (
    OutputPayload, OutputType, OutputChannel,
    OutputRouter, TerminalChannel, FileChannel, MemoryChannel, LoggerChannel
)

G = '\033[92m'; R = '\033[91m'; RST = '\033[0m'


def ok(id, msg): print(f"  {G}✓{RST} [{id}] {msg}")
def fail(id, msg, detail=""): 
    print(f"  {R}✗{RST} [{id}] {msg}")
    if detail: print(f"      → {detail}")


class OutputFrameworkTester:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = ConfigService(project_root)
        self.config.load_all()
        self.memory = MemoryService(project_root, self.config)
        self.security = SecurityService(project_root, self.config)
        self.logger = LoggerService(project_root)
        # 从 Soul 文件动态构建角色路由（与 cli.py 保持一致）
        role_routes = self._build_dynamic_routes()
        self.router = OutputRouter(project_root, self.memory, self.security, self.logger, role_routes=role_routes, config=self.config)
        self.passed = 0
        self.failed = 0
    
    def _build_dynamic_routes(self):
        """从所有角色的 Soul 文件动态构建输出路由（V2.0 含别名兼容）"""
        routes = {}
        channel_map = {
            'terminal': OutputChannel.TERMINAL, 'file': OutputChannel.FILE,
            'logger': OutputChannel.LOGGER, 'memory': OutputChannel.MEMORY,
            'telegram': OutputChannel.TELEGRAM,
        }
        for role_id in self.config.list_roles(include_aliases=True):
            if role_id == 'suri':
                continue
            cfg = self.config.get_role_output_channels(role_id)
            if cfg:
                channels = [channel_map[c] for c in cfg if c in channel_map]
                if channels:
                    routes[role_id] = channels
        return routes

    def check(self, test_id, condition, success_msg, fail_msg, detail=""):
        if condition:
            ok(test_id, success_msg); self.passed += 1
        else:
            fail(test_id, fail_msg, detail); self.failed += 1

    def test_payload_creation(self):
        print("\n" + "="*60)
        print("  测试: OutputPayload 创建与序列化")
        print("="*60)

        # 文本
        p = OutputPayload.text("Hello", role_id="suri", task_id="T1")
        self.check("P01", p.type == OutputType.TEXT and p.role_id == "suri",
                   "文本Payload创建正确", "文本Payload创建失败")

        # 代码
        p = OutputPayload.code("print(1)", language="python", role_id="suri-dev")
        self.check("P02", p.type == OutputType.CODE and p.language == "python",
                   "代码Payload创建正确", "代码Payload创建失败")

        # 文件
        p = OutputPayload.file("test.py", content="x=1", role_id="suri-dev")
        self.check("P03", p.type == OutputType.FILE and p.filename == "test.py",
                   "文件Payload创建正确", "文件Payload创建失败")

        # 报告
        p = OutputPayload.report("# Report", title="Audit", role_id="document-review")
        self.check("P04", p.type == OutputType.REPORT and p.title == "Audit",
                   "报告Payload创建正确", "报告Payload创建失败")

        # 告警
        p = OutputPayload.alert("Error", priority="urgent", role_id="suri")
        self.check("P05", p.type == OutputType.ALERT and p.priority == "urgent",
                   "告警Payload创建正确", "告警Payload创建失败")

        # 图片
        p = OutputPayload.image("https://example.com/img.png", description="Test", role_id="designer")
        self.check("P06", p.type == OutputType.IMAGE and p.description == "Test",
                   "图片Payload创建正确", "图片Payload创建失败")

        # 序列化
        d = p.to_dict()
        self.check("P07", d['type'] == 'image/url' and d['role_id'] == 'designer',
                   "to_dict() 序列化正确", "序列化失败", str(d)[:100])

    def test_terminal_channel(self):
        print("\n" + "="*60)
        print("  测试: TerminalChannel 格式化")
        print("="*60)

        ch = TerminalChannel()

        # 文本
        p = OutputPayload.text("Hello", role_id="suri")
        r = ch.deliver(p)
        self.check("T01", r['success'] and r['channel'] == 'terminal',
                   "终端文本投递成功", "终端文本投递失败", r.get('detail'))

        # 代码
        p = OutputPayload.code("x = 1", language="python", role_id="suri-dev")
        r = ch.deliver(p)
        self.check("T02", r['success'], "终端代码投递成功", "终端代码投递失败")

        # 告警
        p = OutputPayload.alert("Warning", role_id="suri")
        r = ch.deliver(p)
        self.check("T03", r['success'], "终端告警投递成功", "终端告警投递失败")

        # 文件
        p = OutputPayload.file("/tmp/test.txt", role_id="suri-dev")
        r = ch.deliver(p)
        self.check("T04", r['success'], "终端文件通知投递成功", "终端文件通知投递失败")

    def test_file_channel(self):
        print("\n" + "="*60)
        print("  测试: FileChannel 文件写入")
        print("="*60)

        ch = FileChannel(self.project_root, self.security, config=self.config)

        # suri-dev 输出代码文件
        p = OutputPayload.code("def hello(): return 1", language="python", 
                               role_id="suri-dev", filename="test_output")
        r = ch.deliver(p)
        self.check("F01", r['success'], 
                   f"文件写入成功: {r.get('detail', '')}", 
                   f"文件写入失败: {r.get('detail', '')}")

        # document-review 输出审计报告
        p = OutputPayload.report("# Audit Report\n\nPassed", title="audit_test",
                                 role_id="document-review")
        r = ch.deliver(p)
        self.check("F02", r['success'],
                   f"审计报告写入成功: {r.get('detail', '')}",
                   f"审计报告写入失败: {r.get('detail', '')}")

        # 验证文件确实存在
        if r['success']:
            filepath = self.project_root / r['detail']
            self.check("F03", filepath.exists(),
                       f"文件确实存在 ({r['detail']})",
                       f"文件不存在: {r['detail']}")
            if filepath.exists():
                content = filepath.read_text()
                self.check("F04", "Audit Report" in content,
                           "文件内容正确", "文件内容错误", content[:50])

    def test_memory_channel(self):
        print("\n" + "="*60)
        print("  测试: MemoryChannel 记忆存储")
        print("="*60)

        ch = MemoryChannel(self.memory)

        p = OutputPayload.text("测试记忆存储", role_id="suri-dev", task_id="T_MEM_001")
        r = ch.deliver(p)
        self.check("M01", r['success'],
                   f"记忆存储成功: {r.get('detail', '')}",
                   f"记忆存储失败: {r.get('detail', '')}")

        # 验证可读回
        if r['success']:
            msgs = self.memory.get_task_messages('suri-dev', 'T_MEM_001')
            found = any('测试记忆存储' in str(m.get('body', {})) for m in msgs)
            self.check("M02", found,
                       "记忆内容可读取", "记忆内容读取失败",
                       f"消息数: {len(msgs)}")

    def test_router_routing(self):
        print("\n" + "="*60)
        print("  测试: OutputRouter 路由决策")
        print("="*60)

        # suri 文本 → terminal + logger + memory
        p = OutputPayload.text("Hello", role_id="suri")
        channels = self.router.route(p)
        self.check("R01", OutputChannel.TERMINAL in channels and OutputChannel.LOGGER in channels,
                   f"suri文本路由: {[c.value for c in channels]}",
                   f"suri文本路由错误: {[c.value for c in channels]}")

        # suri-dev 代码 → terminal + file + logger + memory
        p = OutputPayload.code("x=1", role_id="suri-dev")
        channels = self.router.route(p)
        self.check("R02", OutputChannel.FILE in channels and OutputChannel.TERMINAL in channels,
                   f"suri-dev代码路由: {[c.value for c in channels]}",
                   f"suri-dev代码路由错误: {[c.value for c in channels]}")

        # 告警 → terminal + logger（类型覆盖）
        p = OutputPayload.alert("Error", role_id="suri")
        channels = self.router.route(p)
        self.check("R03", OutputChannel.TERMINAL in channels,
                   f"告警路由: {[c.value for c in channels]}",
                   f"告警路由错误: {[c.value for c in channels]}")

        # 显式指定通道
        p = OutputPayload.text("Direct", role_id="suri", 
                               target_channels=[OutputChannel.TERMINAL])
        channels = self.router.route(p)
        self.check("R04", channels == [OutputChannel.TERMINAL],
                   "显式通道优先", f"显式通道未优先: {[c.value for c in channels]}")

        # 优先级提升
        p = OutputPayload.text("Urgent", role_id="suri", priority="urgent")
        channels = self.router.route(p)
        self.check("R05", OutputChannel.TELEGRAM in channels,
                   "urgent优先级触发Telegram通道", 
                   f"urgent未提升: {[c.value for c in channels]}")

    def test_router_deliver(self):
        print("\n" + "="*60)
        print("  测试: OutputRouter 多通道投递")
        print("="*60)

        # 多通道投递
        results = self.router.deliver_text("多通道测试", role_id="suri", task_id="T_DELIVER")
        self.check("D01", len(results) >= 2,
                   f"投递到 {len(results)} 个通道", 
                   f"通道数不足: {len(results)}")

        success_count = sum(1 for r in results if r['success'])
        self.check("D02", success_count >= 2,
                   f"{success_count}/{len(results)} 通道投递成功",
                   f"投递成功率低: {success_count}/{len(results)}")

    def test_role_output_mapping(self):
        print("\n" + "="*60)
        print("  测试: 角色-输出形式映射")
        print("="*60)

        # V2.0: 同时测试新旧角色名（别名兼容）
        roles_channels = {
            'suri': [OutputChannel.TERMINAL, OutputChannel.LOGGER, OutputChannel.MEMORY],
            'suri_dev': [OutputChannel.TERMINAL, OutputChannel.FILE, OutputChannel.LOGGER, OutputChannel.MEMORY],
            'suri_hr': [OutputChannel.TERMINAL, OutputChannel.FILE, OutputChannel.LOGGER, OutputChannel.MEMORY],
            'suri_review': [OutputChannel.TERMINAL, OutputChannel.FILE, OutputChannel.LOGGER, OutputChannel.MEMORY],
            # 别名也应正常工作
            'suri-dev': [OutputChannel.TERMINAL, OutputChannel.FILE, OutputChannel.LOGGER, OutputChannel.MEMORY],
            'suri-hr': [OutputChannel.TERMINAL, OutputChannel.FILE, OutputChannel.LOGGER, OutputChannel.MEMORY],
            'document-review': [OutputChannel.TERMINAL, OutputChannel.FILE, OutputChannel.LOGGER, OutputChannel.MEMORY],
        }

        for role_id, expected in roles_channels.items():
            p = OutputPayload.text("test", role_id=role_id)
            channels = self.router.route(p)
            all_expected = all(ec in channels for ec in expected)
            self.check(f"MAP_{role_id}", all_expected,
                       f"{role_id}: {[c.value for c in channels]}",
                       f"{role_id}: 缺少预期通道",
                       f"期望: {[c.value for c in expected]}, 实际: {[c.value for c in channels]}")

    def run_all(self):
        print(f"\n{'#'*70}")
        print(f"#  {' '*20}输出框架测试")
        print(f"{'#'*70}")

        self.test_payload_creation()
        self.test_terminal_channel()
        self.test_file_channel()
        self.test_memory_channel()
        self.test_router_routing()
        self.test_router_deliver()
        self.test_role_output_mapping()

        total = self.passed + self.failed
        print(f"\n{'#'*70}")
        print(f"#  {' '*20}测试结果汇总")
        print(f"{'#'*70}")
        print(f"  总测试项: {total}")
        print(f"  {G}通过: {self.passed}{RST}")
        print(f"  {R}失败: {self.failed}{RST}")
        print(f"  通过率: {self.passed/total*100:.1f}%")
        return self.failed == 0


def main():
    project_root = Path(__file__).parent.parent.parent.parent.resolve()
    tester = OutputFrameworkTester(project_root)
    success = tester.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
