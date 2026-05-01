#!/usr/bin/env python3
"""
多用户并发隔离测试
验证：
1. 多用户并发创建会话，互不干扰
2. 会话隔离：用户A的消息不出现在用户B的上下文中
3. WAL模式下并发读写性能
4. Session复用逻辑（同一用户多次请求复用同一session）
5. 并发任务创建无冲突
"""
import sys, os, threading, time, random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from core.context import ContextService

G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; RST = '\033[0m'


def ok(id, msg):
    print(f"  {G}✓{RST} [{id}] {msg}")


def fail(id, msg, detail=""):
    print(f"  {R}✗{RST} [{id}] {msg}")
    if detail:
        print(f"      {Y}→{RST} {detail}")


class ConcurrentUserTester:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = ConfigService(project_root)
        self.config.load_all()
        self.memory = MemoryService(project_root, self.config)
        self.context = ContextService(self.config, self.memory)
        self.passed = 0
        self.failed = 0
        self.issues = []

    def check(self, test_id, condition, success_msg, fail_msg, detail=""):
        if condition:
            ok(test_id, success_msg)
            self.passed += 1
        else:
            fail(test_id, fail_msg, detail)
            self.failed += 1
            self.issues.append((test_id, fail_msg, detail))

    def test_wal_mode(self):
        """验证 WAL 模式已启用"""
        print("\n" + "=" * 60)
        print("  测试: WAL 模式验证")
        print("=" * 60)

        db_path = self.memory._get_role_db('suri')
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()

        self.check("WAL01", mode == 'wal',
                   f"SQLite WAL 模式已启用 ({mode})",
                   f"WAL 模式未启用 (实际: {mode})")

    def test_multi_user_sessions(self):
        """多用户并发创建会话"""
        print("\n" + "=" * 60)
        print("  测试: 多用户并发会话创建")
        print("=" * 60)

        users = [f"user_{i:03d}" for i in range(10)]
        sessions = {}

        # 并发创建会话
        def create_session_for_user(user_id):
            # 查找或创建会话
            existing = self.memory.get_active_sessions('suri', user_id=user_id, since_hours=24)
            if existing:
                return existing[0]['session_id']
            sid = f"session_{user_id}_{time.strftime('%Y%m%d_%H%M%S')}_{random.randint(1000,9999)}"
            self.memory.create_session('suri', sid, user_id)
            return sid

        start = time.time()
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(create_session_for_user, users))
        elapsed = time.time() - start

        for uid, sid in zip(users, results):
            sessions[uid] = sid

        # 验证：每个用户有独立 session
        unique_sessions = set(sessions.values())
        self.check("S01", len(unique_sessions) == len(users),
                   f"10个用户各自独立session ({len(unique_sessions)}个唯一)",
                   f"session冲突: {len(unique_sessions)} != {len(users)}")

        self.check("S02", elapsed < 2.0,
                   f"并发创建耗时 {elapsed:.2f}s",
                   f"创建耗时过长: {elapsed:.2f}s")

        # 保存会话供后续测试使用
        self.test_sessions = sessions

    def test_session_isolation(self):
        """会话隔离：用户A的消息不出现在用户B的上下文中"""
        print("\n" + "=" * 60)
        print("  测试: 会话消息隔离")
        print("=" * 60)

        user_a = "isolation_user_A"
        user_b = "isolation_user_B"

        # 为用户A创建会话并发送消息
        sid_a = f"session_{user_a}_test"
        self.memory.create_session('suri', sid_a, user_a)
        task_a = f"task_{user_a}_001"
        self.memory.create_task('suri', task_a, sid_a, user_a, 'central', 'suri')
        self.memory.save_message('suri', f"msg_a_1", task_a, user_a, 'suri',
                                 {'type': 'task', 'content': '用户A的秘密消息'})

        # 为用户B创建会话并发送消息
        sid_b = f"session_{user_b}_test"
        self.memory.create_session('suri', sid_b, user_b)
        task_b = f"task_{user_b}_001"
        self.memory.create_task('suri', task_b, sid_b, user_b, 'central', 'suri')
        self.memory.save_message('suri', f"msg_b_1", task_b, user_b, 'suri',
                                 {'type': 'task', 'content': '用户B的秘密消息'})

        # 验证：用户A的session_messages只包含A的消息
        msgs_a = self.memory.get_session_messages('suri', sid_a)
        a_has_b = any('用户B' in str(m.get('body', {})) for m in msgs_a)
        self.check("ISO01", not a_has_b,
                   "用户A的session中不包含用户B的消息",
                   "用户A的session泄漏了用户B的消息",
                   f"A的session消息数: {len(msgs_a)}")

        # 验证：用户B的session_messages只包含B的消息
        msgs_b = self.memory.get_session_messages('suri', sid_b)
        b_has_a = any('用户A' in str(m.get('body', {})) for m in msgs_b)
        self.check("ISO02", not b_has_a,
                   "用户B的session中不包含用户A的消息",
                   "用户B的session泄漏了用户A的消息",
                   f"B的session消息数: {len(msgs_b)}")

        # 验证：按task_id查询仍然能查到全部（无session过滤时）
        all_msgs_a_task = self.memory.get_task_messages('suri', task_a)
        self.check("ISO03", len(all_msgs_a_task) >= 1,
                   f"按task_id查询正常 ({len(all_msgs_a_task)}条)",
                   "按task_id查询异常")

    def test_session_reuse(self):
        """Session复用：同一用户多次请求复用同一session"""
        print("\n" + "=" * 60)
        print("  测试: Session 复用逻辑")
        print("=" * 60)

        user_id = "reuse_test_user"

        # 模拟 SuriTerminal._get_or_create_session 逻辑
        def get_or_create_session():
            sessions = self.memory.get_active_sessions('suri', user_id=user_id, since_hours=24)
            if sessions:
                return sessions[0]['session_id'], True  # reused
            sid = f"session_{user_id}_{time.strftime('%Y%m%d_%H%M%S')}"
            self.memory.create_session('suri', sid, user_id)
            return sid, False  # new

        sid1, reused1 = get_or_create_session()
        sid2, reused2 = get_or_create_session()
        sid3, reused3 = get_or_create_session()

        self.check("REUSE01", not reused1,
                   "首次创建新session", f"首次应创建新session，但标记为复用")
        self.check("REUSE02", reused2,
                   "第二次复用同一session", f"第二次应复用，但创建了新的: {sid2}")
        self.check("REUSE03", reused3,
                   "第三次复用同一session", f"第三次应复用")
        self.check("REUSE04", sid1 == sid2 == sid3,
                   f"三次session_id一致: {sid1[:30]}...",
                   f"session_id不一致: {sid1} vs {sid2} vs {sid3}")

    def test_concurrent_message_writes(self):
        """并发消息写入压力测试"""
        print("\n" + "=" * 60)
        print("  测试: 并发消息写入压力")
        print("=" * 60)

        users = [f"concurrent_{i:02d}" for i in range(20)]
        total_writes = 100

        # 为每个用户创建session
        for uid in users:
            sid = f"session_{uid}_{random.randint(1000,9999)}"
            self.memory.create_session('suri', sid, uid)

        start = time.time()
        errors = []

        def write_messages(uid):
            sid = f"session_{uid}_{random.randint(1000,9999)}"
            # 确保session存在
            try:
                self.memory.create_session('suri', sid, uid)
            except Exception:
                pass
            for i in range(5):
                try:
                    task_id = f"task_{uid}_{i}"
                    self.memory.create_task('suri', task_id, sid, uid, 'central', 'suri')
                    self.memory.save_message('suri', f"msg_{uid}_{i}", task_id, uid, 'suri',
                                             {'type': 'task', 'content': f'消息{i}'})
                except Exception as e:
                    errors.append(str(e))

        with ThreadPoolExecutor(max_workers=10) as pool:
            pool.map(write_messages, users)

        elapsed = time.time() - start

        self.check("CC01", len(errors) == 0,
                   f"100条并发写入无错误 ({elapsed:.2f}s)",
                   f"并发写入出错: {len(errors)}次", str(errors[:3]))

        # 验证每个用户的数据完整性
        intact = 0
        for uid in users:
            try:
                msgs = self.memory.get_role_messages('suri')
                user_msgs = [m for m in msgs if uid in m.get('sender_role', '')]
                if len(user_msgs) >= 5:
                    intact += 1
            except Exception:
                pass

        self.check("CC02", intact >= len(users) * 0.9,
                   f"数据完整性: {intact}/{len(users)} 用户数据完整",
                   f"数据完整性不足: {intact}/{len(users)}")

    def test_context_isolation(self):
        """上下文构建隔离：不同用户的上下文包含不同的记忆"""
        print("\n" + "=" * 60)
        print("  测试: 上下文构建隔离")
        print("=" * 60)

        user_a = "ctx_user_A"
        user_b = "ctx_user_B"
        sid_a = f"session_{user_a}_ctx"
        sid_b = f"session_{user_b}_ctx"

        # 创建session和消息
        self.memory.create_session('suri', sid_a, user_a)
        self.memory.create_session('suri', sid_b, user_b)

        task_a = f"task_{user_a}_ctx"
        task_b = f"task_{user_b}_ctx"
        self.memory.create_task('suri', task_a, sid_a, user_a, 'central', 'suri')
        self.memory.create_task('suri', task_b, sid_b, user_b, 'central', 'suri')

        self.memory.save_message('suri', "msg_ctx_a", task_a, user_a, 'suri',
                                 {'type': 'task', 'content': 'A的上下文测试消息'})
        self.memory.save_message('suri', "msg_ctx_b", task_b, user_b, 'suri',
                                 {'type': 'task', 'content': 'B的上下文测试消息'})

        # 构建两个用户的上下文
        ctx_a = self.context.build_context('suri', current_task={'task_id': task_a, 'requirement': '测试'},
                                           session_id=sid_a)
        ctx_b = self.context.build_context('suri', current_task={'task_id': task_b, 'requirement': '测试'},
                                           session_id=sid_b)

        # 验证隔离
        a_has_a = 'A的上下文测试消息' in ctx_a
        a_has_b = 'B的上下文测试消息' in ctx_a
        b_has_a = 'A的上下文测试消息' in ctx_b
        b_has_b = 'B的上下文测试消息' in ctx_b

        self.check("CTX_ISO01", a_has_a and not a_has_b,
                   "用户A的上下文包含A的消息，不含B的",
                   f"A上下文隔离失败: has_a={a_has_a}, has_b={a_has_b}")

        self.check("CTX_ISO02", b_has_b and not b_has_a,
                   "用户B的上下文包含B的消息，不含A的",
                   f"B上下文隔离失败: has_b={b_has_b}, has_a={b_has_a}")

    def run_all(self):
        print(f"\n{'#' * 70}")
        print(f"#  {' '*15}多用户并发隔离测试")
        print(f"#  {' '*15}开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#' * 70}")

        self.test_wal_mode()
        self.test_multi_user_sessions()
        self.test_session_isolation()
        self.test_session_reuse()
        self.test_concurrent_message_writes()
        self.test_context_isolation()

        total = self.passed + self.failed
        print(f"\n{'#' * 70}")
        print(f"#  {' '*15}测试结果汇总")
        print(f"{'#' * 70}")
        print(f"  总测试项: {total}")
        print(f"  {G}通过: {self.passed}{RST}")
        print(f"  {R}失败: {self.failed}{RST}")
        print(f"  通过率: {self.passed / total * 100:.1f}%")

        if self.issues:
            print(f"\n  {Y}失败详情 ({len(self.issues)}项):{RST}")
            for tid, msg, detail in self.issues:
                print(f"    - [{tid}] {msg}")
                if detail:
                    print(f"      → {detail[:80]}")

        return self.failed == 0


def main():
    project_root = Path(__file__).parent.parent.parent.parent.resolve()
    tester = ConcurrentUserTester(project_root)
    success = tester.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
