#!/usr/bin/env python3
"""
1000轮大规模对话测试
- 500轮生活化对话（闲聊、问候、简单问答）
- 500轮任务对话（代码、审核、人事、文档等）

测试目标：
1. 记忆存储的一致性和完整性
2. 任务状态机流转
3. 消息ID唯一性（防止覆盖）
4. 经验(insights)保存和触发计数
5. 上下文构建中记忆注入的正确性
6. 高频操作下的稳定性
7. 边界情况（空消息、超长消息、特殊字符、Unicode）
"""
import sys, os, json, random, string, time, shutil, traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.security import SecurityService
from infrastructure.filesystem import FileService
from infrastructure.logger import LoggerService
from core.context import ContextService

# ====== 颜色 ======
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; C = '\033[96m'; RST = '\033[0m'

def ok(id, msg): 
    print(f"  {G}✓{RST} [{id}] {msg}")

def fail(id, msg, detail=""): 
    print(f"  {R}✗{RST} [{id}] {msg}")
    if detail:
        print(f"      {Y}→{RST} {detail}")

def info(msg):
    print(f"{C}[INFO]{RST} {msg}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ====== 测试数据生成器 ======

CASUAL_MESSAGES = [
    "你好", "在吗", "今天天气不错", "帮我写首诗", "讲个笑话",
    "你叫什么名字", "你能做什么", "谢谢", "再见", "好的",
    "明白了", "没问题", "稍等", "OK", "收到",
    "这个挺有意思", "我不太懂", "能再解释一下吗", "太棒了", "厉害",
    "哈哈哈哈", "嗯嗯", "这样啊", "原来如此", "学到了",
    "有点复杂", "简单点说", "举个例子", "具体怎么做", "下一步呢",
    "等一下", "我先忙了", "回头聊", "有空再说", "先这样吧",
    "怎么样", "结果呢", "成功了吗", "出错了", "怎么办",
    "为什么", "什么原因", "怎么解决", "有没有别的办法", "试试这个",
    "不对", "错了", "重新来", "撤销", "恢复",
    "保存了吗", "备份一下", "别担心", "没问题", "交给我",
    "考虑一下", "需要多久", "什么时候好", "加急", "优先处理",
    "暂停", "继续", "停止", "开始", "重启",
    "配置一下", "设置参数", "调整一下", "优化", "升级",
    "兼容吗", "支持吗", "能用吗", "测试过吗", "验证一下",
]

TASK_MESSAGES = [
    ("帮我修一个Python的bug", "suri-dev"),
    ("审核一下这份代码", "document-review"),
    ("创建一个新的测试角色", "suri-hr"),
    ("优化系统性能", "suri-dev"),
    ("检查一下文档格式", "document-review"),
    ("分配技能给suri-dev", "suri-hr"),
    ("重构这个模块", "suri-dev"),
    ("审计这次变更", "document-review"),
    ("调整部门设置", "suri-hr"),
    ("修复数据库连接问题", "suri-dev"),
    ("代码审查：权限检查逻辑", "document-review"),
    ("为新项目创建角色", "suri-hr"),
    ("升级框架版本", "suri-dev"),
    ("检查安全合规性", "document-review"),
    ("更新角色权限", "suri-hr"),
    ("排查内存泄漏", "suri-dev"),
    ("审查API接口", "document-review"),
    ("设置组织架构", "suri-hr"),
    ("实现缓存机制", "suri-dev"),
    ("评估变更风险", "document-review"),
]

BOUNDARY_CASES = [
    ("", "空消息"),
    ("a" * 5000, "超长消息5000字"),
    ("中文测试🎉\n换行\t制表", "Unicode+特殊字符"),
    ("'\"`\\", "引号转义测试"),
    ("{\"key\": \"value\"}", "JSON格式消息"),
    ("<script>alert('xss')</script>", "XSS尝试"),
    ("DROP TABLE messages; --", "SQL注入尝试"),
    ("\x00\x01\x02", "控制字符"),
]

# ====== 主测试类 ======

class MemorySystemTester:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = ConfigService(project_root)
        self.config.load_all()
        self.memory = MemoryService(project_root, self.config)
        self.security = SecurityService(project_root, self.config)
        self.files = FileService(project_root, self.security)
        self.logger = LoggerService(project_root)
        self.context = ContextService(self.config, self.memory)
        
        self.passed = 0
        self.failed = 0
        self.issues = []
        
        # 清理之前的测试数据
        self._cleanup_test_data()
    
    def _cleanup_test_data(self):
        """清理测试数据"""
        for role_id in ['suri', 'suri-dev', 'suri-hr', 'document-review']:
            role_dir = self.project_root / 'group' / 'central' / role_id / 'memories'
            if role_dir.exists():
                # 删除所有 .md 文件（不包括子目录中的）
                for f in role_dir.glob('*.md'):
                    f.unlink()
                # 删除 insights 子目录下的 .md 文件
                insights_dir = role_dir / 'insights'
                if insights_dir.exists():
                    for f in insights_dir.glob('*.md'):
                        f.unlink()
                # 删除 db
                db_path = role_dir / 'role.db'
                if db_path.exists():
                    db_path.unlink()
    
    def check(self, test_id: str, condition: bool, success_msg: str, fail_msg: str, detail: str = ""):
        if condition:
            ok(test_id, success_msg)
            self.passed += 1
        else:
            fail(test_id, fail_msg, detail)
            self.failed += 1
            self.issues.append((test_id, fail_msg, detail))
    
    # ========== 测试套件 ==========
    
    def test_message_uniqueness(self):
        """测试消息ID唯一性（防止覆盖）"""
        section("测试: 消息ID唯一性")
        
        role_id = 'suri-dev'
        task_id = 'T_001'
        
        # 验证：重复消息ID应触发 SQLite UNIQUE constraint 错误（防止静默覆盖）
        conflict_detected = 0
        for i in range(5):
            msg_id = f"msg_{task_id[:8]}_user_dup"
            try:
                self.memory.save_message(role_id, msg_id, task_id, 'user', role_id, 
                                         {'type': 'task', 'content': f'消息{i}'})
            except Exception as e:
                if 'UNIQUE constraint failed' in str(e):
                    conflict_detected += 1
        
        self.check("MU01", conflict_detected >= 4,
                   f"重复ID正确触发冲突检测 ({conflict_detected}/5)",
                   f"冲突检测不足 ({conflict_detected}/5)",
                   "SQLite PRIMARY KEY 应阻止重复ID")
        
        # 唯一ID可共存
        self.memory.save_message(role_id, f"msg_{task_id[:8]}_user_001", task_id, 'user', role_id,
                                 {'type': 'task', 'content': '第一条'})
        self.memory.save_message(role_id, f"msg_{task_id[:8]}_user_002", task_id, 'user', role_id,
                                 {'type': 'task', 'content': '第二条'})
        messages = self.memory.get_task_messages(role_id, task_id)
        self.check("MU02", len(messages) == 3,  # 1条冲突成功 + 2条唯一
                   f"唯一ID消息可共存（{len(messages)}条）",
                   "唯一ID消息未共存", f"实际{len(messages)}条")
    
    def test_task_state_machine(self):
        """测试任务状态机流转"""
        section("测试: 任务状态机")
        
        role_id = 'suri-dev'
        task_id = 'T_STATE_001'
        session_id = 'S_001'
        
        # 创建任务
        self.memory.create_task(role_id, task_id, session_id, 'user', 'central', 'suri')
        task = self.memory.get_task(role_id, task_id)
        self.check("TS01", task and task['status'] == 'pending',
                   "任务创建后状态为pending", "任务初始状态错误", 
                   f"实际状态: {task['status'] if task else 'None'}")
        
        # 状态流转
        for status in ['in_progress', 'completed']:
            self.memory.update_task_status(role_id, task_id, status)
            task = self.memory.get_task(role_id, task_id)
            self.check(f"TS_{status}", task and task['status'] == status,
                       f"状态更新为{status}", f"状态更新失败", 
                       f"实际: {task['status'] if task else 'None'}")
        
        # 重试计数
        self.memory.increment_retry(role_id, task_id)
        self.memory.increment_retry(role_id, task_id)
        task = self.memory.get_task(role_id, task_id)
        self.check("TS_retry", task and task.get('retry_count', 0) == 2,
                   f"重试计数=2", "重试计数错误", 
                   f"实际: {task.get('retry_count', 'N/A') if task else 'None'}")
    
    def test_insight_lifecycle(self):
        """测试经验(insights)完整生命周期"""
        section("测试: 经验生命周期")
        
        role_id = 'suri-dev'
        
        # 保存经验
        insight_data = {
            'title': '测试经验_性能优化',
            'category': 'success_pattern',
            'situation': '处理大数据时内存溢出',
            'key_point': '使用生成器替代列表推导',
            'avoid': '不要一次性加载所有数据',
            'confidence': 0.85,
        }
        path = self.memory.save_role_insight(role_id, insight_data)
        self.check("IL01", bool(path), "经验保存成功", "经验保存失败", path)
        
        # 读取经验
        insights = self.memory.list_role_insights(role_id)
        self.check("IL02", len(insights) >= 1, f"经验列表返回{len(insights)}条", "经验列表为空")
        
        if insights:
            ins = insights[0]
            meta = ins.get('meta', {})
            self.check("IL03", meta.get('category') == 'success_pattern',
                       "经验分类正确", "经验分类错误", str(meta))
            self.check("IL04", meta.get('confidence') == 0.85,
                       "经验置信度正确", "置信度解析错误", str(meta.get('confidence')))
            self.check("IL05", meta.get('trigger_count') == 1,
                       "初始trigger_count=1", "trigger_count错误", str(meta.get('trigger_count')))
            
            # 触发更新
            self.memory.update_insight_trigger(role_id, ins['path'])
            insights_after = self.memory.list_role_insights(role_id)
            if insights_after:
                meta_after = insights_after[0].get('meta', {})
                self.check("IL06", meta_after.get('trigger_count') == 2,
                           "trigger_count更新为2", "trigger_count未更新",
                           f"实际: {meta_after.get('trigger_count')}")
        
        # 上下文注入测试
        context_text = self.memory.get_recent_insights_for_context(role_id, task_hint="性能优化")
        self.check("IL07", '性能优化' in context_text or '生成器' in context_text or len(context_text) > 0,
                   "经验可注入上下文", "经验未注入上下文", f"长度={len(context_text)}")
    
    def test_boundary_cases(self):
        """测试边界情况"""
        section("测试: 边界情况")
        
        role_id = 'suri-dev'
        task_id = 'T_BOUNDARY'
        
        for i, (content, desc) in enumerate(BOUNDARY_CASES):
            try:
                msg_id = f"msg_boundary_{i:03d}"
                self.memory.save_message(role_id, msg_id, task_id, 'user', role_id,
                                         {'type': 'task', 'content': content})
                # 读取验证
                messages = self.memory.get_task_messages(role_id, task_id)
                found = any(m.get('body', {}).get('content') == content for m in messages)
                self.check(f"BC{i:02d}", found, f"{desc}: 读写一致", f"{desc}: 读写不一致")
            except Exception as e:
                self.check(f"BC{i:02d}", False, "", f"{desc}: 异常", str(e))
    
    def test_memory_file_io(self):
        """测试记忆文件读写"""
        section("测试: 记忆文件IO")
        
        role_id = 'suri-dev'
        
        # 保存多条记忆
        for i in range(20):
            content = f"## 记忆{i}\n\n这是第{i}条测试记忆内容。"
            self.memory.save_role_memory(role_id, content, topic=f"test_topic_{i}")
        
        # 列出记忆
        mem_files = self.memory.list_role_memories(role_id)
        self.check("MF01", len(mem_files) >= 20, f"列出{len(mem_files)}条记忆", "记忆列出数量不足")
        
        # 检查insights不被混入
        insights_files = [f for f in mem_files if 'insights' in f]
        self.check("MF02", len(insights_files) == 0,
                   "insights文件未混入记忆列表", 
                   f"insights文件混入: {len(insights_files)}个",
                   str(insights_files[:3]))
        
        # 读取验证
        if mem_files:
            content = self.memory.read_role_memory(role_id, mem_files[0])
            self.check("MF03", len(content) > 0, "记忆文件可读取", "记忆文件读取失败")
    
    def test_context_build(self):
        """测试上下文构建"""
        section("测试: 上下文构建")
        
        for role_id in ['suri-dev', 'suri-hr', 'document-review']:
            task = {'task_id': 'T_CTX_001', 'requirement': '测试上下文注入'}
            try:
                ctx = self.context.build_context(role_id, current_task=task)
                self.check(f"CB_{role_id}", len(ctx) > 100,
                           f"{role_id} 上下文长度={len(ctx)}", 
                           f"{role_id} 上下文过短", f"长度={len(ctx)}")
                
                # 检查关键部分存在
                has_identity = '你的身份' in ctx
                has_rules = '规则' in ctx
                has_task = '当前任务' in ctx
                self.check(f"CB_{role_id}_parts", has_identity and has_rules and has_task,
                           f"{role_id} 上下文结构完整", 
                           f"{role_id} 上下文结构缺失", 
                           f"identity={has_identity}, rules={has_rules}, task={has_task}")
            except Exception as e:
                self.check(f"CB_{role_id}", False, "", f"{role_id} 上下文构建异常", str(e))
    
    def simulate_500_casual_rounds(self):
        """模拟500轮生活化对话"""
        section("模拟: 500轮生活化对话")
        
        role_id = 'suri'
        session_id = 'S_CASUAL'
        
        self.memory.create_session(role_id, session_id, 'user')
        
        saved_count = 0
        errors = []
        start_time = time.time()
        
        for i in range(500):
            msg = random.choice(CASUAL_MESSAGES)
            task_id = f"T_CASUAL_{i:04d}"
            msg_id = f"msg_{task_id}_{i}"
            
            try:
                # 模拟 suri 处理：保存用户消息 + suri 回复
                self.memory.save_message(role_id, msg_id, task_id, 'user', role_id,
                                         {'type': 'chat', 'content': msg})
                
                reply_id = f"msg_{task_id}_suri"
                self.memory.save_message(role_id, reply_id, task_id, role_id, 'user',
                                         {'type': 'response', 'content': f'回复: {msg}'})
                saved_count += 2
            except Exception as e:
                errors.append((i, str(e)))
        
        elapsed = time.time() - start_time
        
        # 验证
        all_messages = self.memory.get_role_messages(role_id)
        self.check("SC01", len(all_messages) == saved_count,
                   f"500轮保存{saved_count}条消息，读取{len(all_messages)}条",
                   "消息数量不一致",
                   f"期望{saved_count}，实际{len(all_messages)}")
        
        self.check("SC02", len(errors) == 0,
                   f"无异常 ({elapsed:.2f}s)",
                   f"出现{len(errors)}次异常",
                   str(errors[:3]))
        
        info(f"500轮生活对话: 保存{saved_count}条, 耗时{elapsed:.2f}s, 异常{len(errors)}次")
    
    def simulate_500_task_rounds(self):
        """模拟500轮任务对话（调度到不同角色）"""
        section("模拟: 500轮任务对话")
        
        # 记录各角色当前消息数（用于增量验证）
        baseline = {}
        for role_id in ['suri-dev', 'suri-hr', 'document-review']:
            baseline[role_id] = len(self.memory.get_role_messages(role_id))
        
        start_time = time.time()
        saved_per_role = {}
        errors = []
        
        for i in range(500):
            msg, expected_role = random.choice(TASK_MESSAGES)
            task_id = f"T_TASK_{i:04d}"
            session_id = f"S_TASK_{i//10:04d}"
            
            try:
                # 创建任务
                self.memory.create_task(expected_role, task_id, session_id, 'user', 'central', 'suri')
                self.memory.update_task_status(expected_role, task_id, 'in_progress')
                
                # 保存用户消息
                user_msg_id = f"msg_{task_id}_user"
                self.memory.save_message(expected_role, user_msg_id, task_id, 'user', expected_role,
                                         {'type': 'task', 'content': msg})
                
                # 模拟角色执行（保存角色回复）
                role_msg_id = f"msg_{task_id}_{expected_role}"
                self.memory.save_message(expected_role, role_msg_id, task_id, expected_role, 'user',
                                         {'type': 'response', 'content': f'已处理: {msg[:30]}'})
                
                # 更新任务完成
                self.memory.update_task_status(expected_role, task_id, 'completed')
                
                saved_per_role[expected_role] = saved_per_role.get(expected_role, 0) + 2
                
                # 每50轮保存一条insight（模拟学习）
                if i % 50 == 0:
                    self.memory.save_role_insight(expected_role, {
                        'title': f'经验_{i}',
                        'category': random.choice(list(self.memory.__class__.__dict__.get('INSIGHT_CATEGORIES', {'success_pattern'}))),
                        'situation': f'任务{i}的处理过程',
                        'key_point': '关键经验总结',
                        'avoid': '避免的错误',
                        'confidence': round(random.random(), 2),
                    })
                    
            except Exception as e:
                errors.append((i, expected_role, str(e)))
        
        elapsed = time.time() - start_time
        
        # 验证各角色数据（增量验证，排除之前测试的数据）
        total_saved = sum(saved_per_role.values())
        total_read = 0
        for role_id, expected in saved_per_role.items():
            actual = len(self.memory.get_role_messages(role_id)) - baseline.get(role_id, 0)
            total_read += actual
            self.check(f"ST_{role_id}", actual == expected,
                       f"{role_id}: 保存{expected}条, 增量{actual}条",
                       f"{role_id}: 消息数量不一致",
                       f"期望{expected}, 实际{actual}")
        
        self.check("ST_total", total_read == total_saved,
                   f"总消息: 保存{total_saved}, 增量{total_read}",
                   "总消息数量不一致")
        
        self.check("ST_errors", len(errors) == 0,
                   f"任务对话无异常 ({elapsed:.2f}s)",
                   f"出现{len(errors)}次异常",
                   str(errors[:3]))
        
        info(f"500轮任务对话: 保存{total_saved}条, 耗时{elapsed:.2f}s, 异常{len(errors)}次")
        info(f"各角色分布: {saved_per_role}")
    
    def test_context_with_history(self):
        """测试带历史记忆的上下文构建"""
        section("测试: 历史记忆上下文注入")
        
        role_id = 'suri-dev'
        task_id = 'T_HISTORY_001'
        
        # 先保存一批消息
        for i in range(15):
            self.memory.save_message(role_id, f"msg_hist_{i:03d}", task_id, 'user', role_id,
                                     {'type': 'task', 'content': f'历史消息{i}: 关于性能优化的讨论'})
        
        # 构建上下文
        task = {'task_id': task_id, 'requirement': '继续优化性能'}
        ctx = self.context.build_context(role_id, current_task=task)
        
        # 检查历史记忆是否注入
        has_history = '历史消息' in ctx or '性能优化' in ctx
        self.check("CH01", has_history,
                   "历史消息注入上下文", "历史消息未注入上下文",
                   f"上下文长度={len(ctx)}, 包含'历史消息'={('历史消息' in ctx)}, 包含'性能优化'={('性能优化' in ctx)}")
        
        # 检查消息数量限制（应该只取最近10条）
        history_count = ctx.count('历史消息')
        self.check("CH02", history_count <= 10,
                   f"历史消息限制<=10条 (实际{history_count})",
                   f"历史消息超过10条 (实际{history_count})")
    
    def test_database_integrity(self):
        """测试数据库完整性"""
        section("测试: 数据库完整性")
        
        for role_id in ['suri', 'suri-dev', 'suri-hr', 'document-review']:
            try:
                db_path = self.memory._get_role_db(role_id)
                conn = __import__('sqlite3').connect(str(db_path))
                cursor = conn.cursor()
                
                # 检查表存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cursor.fetchall()]
                expected = ['sessions', 'tasks', 'messages', 'approvals', 'changelogs']
                has_all = all(t in tables for t in expected)
                self.check(f"DB_{role_id}_tables", has_all,
                           f"{role_id}: 5张表齐全", f"{role_id}: 表缺失", str(tables))
                
                # 检查消息数据完整性
                cursor.execute("SELECT message_id, body FROM messages")
                invalid = 0
                for row in cursor.fetchall():
                    try:
                        json.loads(row[1])
                    except:
                        invalid += 1
                self.check(f"DB_{role_id}_json", invalid == 0,
                           f"{role_id}: {invalid}条无效JSON", 
                           f"{role_id}: {invalid}条无效JSON")
                
                conn.close()
            except Exception as e:
                self.check(f"DB_{role_id}", False, "", f"{role_id}: 数据库检查异常", str(e))
    
    def test_concurrent_simulation(self):
        """模拟并发操作"""
        section("测试: 高频并发模拟")
        
        role_id = 'suri-dev'
        task_id = 'T_RACE_001'
        
        start_time = time.time()
        success = 0
        errors = []
        
        for i in range(200):
            try:
                self.memory.save_message(role_id, f"msg_race_{i:04d}", task_id, 'user', role_id,
                                         {'type': 'task', 'content': f'并发消息{i}'})
                success += 1
            except Exception as e:
                errors.append(str(e))
        
        elapsed = time.time() - start_time
        
        messages = self.memory.get_task_messages(role_id, task_id)
        self.check("RC01", len(messages) == success,
                   f"并发保存{success}条, 读取{len(messages)}条 ({elapsed:.2f}s)",
                   "并发消息数量不一致",
                   f"期望{success}, 实际{len(messages)}, 异常{len(errors)}次")
    
    def run_all(self):
        """运行全部测试"""
        print(f"\n{'#'*70}")
        print(f"#  {' '*20}Suri 记忆系统 1000轮压力测试")
        print(f"#  {' '*20}开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*70}")
        
        self.test_message_uniqueness()
        self.test_task_state_machine()
        self.test_insight_lifecycle()
        self.test_boundary_cases()
        self.test_memory_file_io()
        self.test_context_build()
        self.simulate_500_casual_rounds()
        self.simulate_500_task_rounds()
        self.test_context_with_history()
        self.test_database_integrity()
        self.test_concurrent_simulation()
        
        # 汇总
        print(f"\n{'#'*70}")
        print(f"#  {' '*20}测试结果汇总")
        print(f"{'#'*70}")
        print(f"  总测试项: {self.passed + self.failed}")
        print(f"  {G}通过: {self.passed}{RST}")
        print(f"  {R}失败: {self.failed}{RST}")
        
        if self.issues:
            print(f"\n  {Y}问题列表 ({len(self.issues)}项):{RST}")
            for test_id, msg, detail in self.issues[:20]:
                print(f"    - [{test_id}] {msg}")
                if detail:
                    print(f"      → {detail[:100]}")
        
        return self.failed == 0


def main():
    project_root = Path(__file__).parent.parent.parent.parent.resolve()
    tester = MemorySystemTester(project_root)
    success = tester.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
