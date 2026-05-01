#!/usr/bin/env python3
"""
100次角色能力测试
作为用户模拟各种输入，验证调度逻辑的正确性
"""
import sys, os, asyncio
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from core.context import ContextService

G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; RST = '\033[0m'

# 100个测试用例: (用户输入, 期望调度的角色列表, 描述)
TEST_CASES = [
    # === 生活化对话（不应调度）===
    ("你好", [], "问候"),
    ("在吗", [], "简单问候"),
    ("今天天气不错", [], "闲聊"),
    ("你叫什么名字", [], "问身份"),
    ("你能做什么", [], "问能力"),
    ("谢谢", [], "感谢"),
    ("再见", [], "道别"),
    ("讲个笑话", [], "娱乐请求"),
    ("帮我写首诗", [], "创作请求"),
    ("1+1等于几", [], "简单问答"),
    ("北京现在几点", [], "事实查询"),
    ("你用的什么模型", [], "平台状态查询"),
    ("suri平台怎么样", [], "平台评价"),
    ("介绍一下你自己", [], "自我介绍"),
    ("OK", [], "确认"),
    ("明白了", [], "理解确认"),
    ("稍等", [], "等待"),
    ("没问题", [], "同意"),
    ("哈哈哈哈", [], "情绪表达"),
    ("嗯嗯", [], "附和"),

    # === suri-dev 调度（代码/技术）===
    ("帮我修一个Python的bug", ["suri_dev"], "Bug修复"),
    ("系统性能太慢了，优化一下", ["suri_dev"], "性能优化"),
    ("升级框架版本", ["suri_dev"], "框架升级"),
    ("排查内存泄漏", ["suri_dev"], "内存问题"),
    ("实现缓存机制", ["suri_dev"], "功能开发"),
    ("重构这个模块", ["suri_dev"], "代码重构"),
    ("修复数据库连接问题", ["suri_dev"], "数据库修复"),
    ("代码里有bug，帮我看看", ["suri_dev"], "Bug排查"),
    ("性能优化方案", ["suri_dev"], "性能方案"),
    ("升级依赖包", ["suri_dev"], "依赖升级"),
    ("这个函数有性能问题", ["suri_dev"], "函数优化"),
    ("需要修改核心代码", ["suri_dev"], "核心修改"),
    ("基础设施需要维护", ["suri_dev"], "基础设施"),
    ("框架维护计划", ["suri_dev"], "框架维护"),
    ("程序崩溃了", ["suri_dev"], "程序崩溃"),

    # === suri-hr 调度（人事/组织）===
    ("创建一个新的测试角色", ["suri_hr"], "创建角色"),
    ("分配技能给suri-dev", ["suri_hr"], "技能分配"),
    ("调整部门设置", ["suri_hr"], "部门设置"),
    ("为新项目创建角色", ["suri_hr"], "项目角色"),
    ("设置组织架构", ["suri_hr"], "组织架构"),
    ("更新角色权限", ["suri_hr"], "权限更新"),
    ("角色管理规范", ["suri_hr"], "角色管理"),
    ("人事调整通知", ["suri_hr"], "人事调整"),
    ("部门架构设计", ["suri_hr"], "部门架构"),
    ("技能体系规划", ["suri_hr"], "技能规划"),

    # === document-review 调度（审核）===
    ("审核一下这份代码", ["suri_review"], "代码审核"),
    ("检查一下文档格式", ["suri_review"], "文档检查"),
    ("审计这次变更", ["suri_review"], "变更审计"),
    ("审查API接口", ["suri_dev"], "API审查"),
    ("评估变更风险", ["suri_review"], "风险评估"),
    ("质量检查报告", ["suri_review"], "质量检查"),
    ("代码审查清单", ["suri_review"], "审查清单"),
    ("文档审核流程", ["suri_review"], "审核流程"),
    ("变更审计要求", ["suri_review"], "审计要求"),

    # === 多角色调度 ===
    ("开发电商数据分析平台，需要写代码、做测试、写文档", ["suri_dev", "suri_review"], "多角色需求"),
    ("创建新角色并审核其权限配置", ["suri_hr", "suri_review"], "创建+审核"),
    ("优化系统性能并审核变更方案", ["suri_dev", "suri_review"], "优化+审核"),
    ("重构代码并更新角色权限", ["suri_dev", "suri_hr"], "重构+权限"),
    ("设计新功能，写代码，做代码审查", ["suri_dev", "suri_review"], "设计+开发+审查"),

    # === 边界/模糊情况 ===
    ("suri-dev 的权限有问题", ["suri_hr"], "角色权限问题"),
    ("document-review 的审核规则需要修改", ["suri_dev", "suri_review"], "规则修改"),
    ("suri-hr 的代码有bug", ["suri_dev"], "跨角色技术问题"),
    ("如何创建一个角色", ["suri_hr"], "操作指导"),
    ("怎么审核代码", ["suri_review"], "操作指导"),
    ("Python怎么写", ["suri_dev"], "技术教学"),
    ("帮我看看这段代码有没有问题", ["suri_dev"], "代码检查"),
    ("系统需要升级，请评估风险", ["suri_dev", "suri_review"], "升级+评估"),
    ("组织架构调整需要代码支持", ["suri_dev", "suri_hr"], "组织+技术"),
    ("新角色需要文档和代码", ["suri_hr", "suri_dev", "suri_review"], "全角色"),

    # === 关键词变体/同义词 ===
    ("程序出错了", ["suri_dev"], "错误变体"),
    ("代码有问题", ["suri_dev"], "问题变体"),
    ("需要修复bug", ["suri_dev"], "修复变体"),
    ("建立新部门", ["suri_hr"], "建立变体"),
    ("添加新角色", ["suri_hr"], "添加变体"),
    ("检查质量", ["suri_review"], "检查变体"),
    ("做审计", ["suri_review"], "审计变体"),
    ("验证代码", ["suri_review"], "验证变体"),

    # === 无明确匹配（应无调度）===
    ("随便聊聊", [], "模糊输入"),
    ("你觉得怎么样", [], "评价请求"),
    ("告诉我更多", [], "信息请求"),
    ("继续", [], "继续指令"),
    ("好的知道了", [], "确认结束"),
]


class RoleCapabilityTester:
    def __init__(self, project_root: Path):
        self.config = ConfigService(project_root)
        self.config.load_all()
        self.memory = MemoryService(project_root, self.config)
        self.context = ContextService(self.config, self.memory)
        self.passed = 0
        self.failed = 0
        self.issues = []

    def check(self, test_id, condition, success_msg, fail_msg, detail=""):
        if condition:
            print(f"  {G}✓{RST} [{test_id}] {success_msg}")
            self.passed += 1
        else:
            print(f"  {R}✗{RST} [{test_id}] {fail_msg}")
            if detail:
                print(f"      {Y}→{RST} {detail}")
            self.failed += 1
            self.issues.append((test_id, fail_msg, detail))

    def test_dispatch_logic(self):
        """测试调度逻辑：用户输入 → 角色匹配"""
        print("\n" + "=" * 60)
        print("  测试: 100次角色调度匹配")
        print("=" * 60)

        for i, (user_input, expected_roles, desc) in enumerate(TEST_CASES):
            test_id = f"R{i + 1:03d}"

            # 模拟 _detect_dispatch_target 的关键词匹配层
            all_roles = [rid for rid in self.config.list_roles() if rid != 'suri']
            user_text_lower = user_input.lower()
            matched = []

            for role_id in all_roles:
                keywords = self.config.get_role_keywords(role_id)
                for kw in keywords:
                    if kw.lower() in user_text_lower:
                        matched.append(role_id)
                        break

            matched = list(dict.fromkeys(matched))  # 去重保序

            # 验证
            if expected_roles:
                # 期望有调度
                all_expected_found = all(r in matched for r in expected_roles)
                any_match = len(matched) > 0

                if all_expected_found:
                    self.check(test_id, True,
                               f"{desc}: '{user_input[:30]}...' → {matched}",
                               "", "")
                else:
                    self.check(test_id, False, "",
                               f"{desc}: 期望 {expected_roles}, 实际 {matched}",
                               f"输入: '{user_input}'")
            else:
                # 期望无调度
                if len(matched) == 0:
                    self.check(test_id, True,
                               f"{desc}: '{user_input[:30]}...' → 无调度",
                               "", "")
                else:
                    self.check(test_id, False, "",
                               f"{desc}: 期望无调度, 实际 {matched}",
                               f"输入: '{user_input}'")

    def test_context_quality(self):
        """测试上下文构建质量"""
        print("\n" + "=" * 60)
        print("  测试: 上下文构建质量")
        print("=" * 60)

        for role_id in ['suri_dev', 'suri_hr', 'suri_review']:
            task = {'task_id': f'T_CTX_{role_id}', 'requirement': '测试上下文质量'}
            ctx = self.context.build_context(role_id, current_task=task)

            checks = [
                ("身份" in ctx, "包含身份部分"),
                ("规则" in ctx, "包含规则部分"),
                ("当前任务" in ctx, "包含任务部分"),
                (len(ctx) < 5000, f"长度合理 ({len(ctx)} < 5000)"),
                ("---" in ctx, "使用分隔符"),
            ]

            for cond, desc in checks:
                self.check(f"CTX_{role_id}_{desc}", cond,
                           f"{role_id}: {desc}",
                           f"{role_id}: {desc} 失败")

    def test_token_efficiency(self):
        """测试Token效率"""
        print("\n" + "=" * 60)
        print("  测试: Token 效率指标")
        print("=" * 60)

        import time

        # 缓存性能
        start = time.time()
        for _ in range(20):
            self.context.build_context('suri_dev')
        elapsed = (time.time() - start) * 1000
        avg = elapsed / 20
        self.check("TOK_cache", avg < 5.0,
                   f"热缓存构建耗时: {avg:.2f}ms/次",
                   f"构建耗时过高: {avg:.2f}ms/次")

        # 上下文长度
        for role_id in ['suri', 'suri_dev', 'suri_hr', 'suri_review']:
            ctx = self.context.build_context(role_id)
            est_tokens = len(ctx) // 2
            self.check(f"TOK_len_{role_id}", est_tokens < 2500,
                       f"{role_id}: ~{est_tokens} tokens",
                       f"{role_id}: {est_tokens} tokens 过高")

    def test_keyword_coverage(self):
        """测试关键词覆盖率"""
        print("\n" + "=" * 60)
        print("  测试: 关键词覆盖率")
        print("=" * 60)

        for role_id in ['suri_dev', 'suri_hr', 'suri_review']:
            keywords = self.config.get_role_keywords(role_id)
            self.check(f"KW_{role_id}", len(keywords) >= 3,
                       f"{role_id}: {len(keywords)} 个关键词",
                       f"{role_id}: 关键词过少 ({len(keywords)})")

    def run_all(self):
        self.test_dispatch_logic()
        self.test_context_quality()
        self.test_token_efficiency()
        self.test_keyword_coverage()

        total = self.passed + self.failed
        print(f"\n{'#' * 60}")
        print(f"#  {' '*15}100次角色能力测试完成")
        print(f"{'#' * 60}")
        print(f"  总测试项: {total}")
        print(f"  {G}通过: {self.passed}{RST}")
        print(f"  {R}失败: {self.failed}{RST}")
        print(f"  通过率: {self.passed / total * 100:.1f}%")

        if self.issues:
            print(f"\n  {Y}失败详情 ({len(self.issues)}项):{RST}")
            for tid, msg, detail in self.issues[:15]:
                print(f"    - [{tid}] {msg}")
                if detail:
                    print(f"      → {detail[:80]}")

        return self.failed == 0


def main():
    project_root = Path(__file__).parent.parent.parent.parent.resolve()
    tester = RoleCapabilityTester(project_root)
    success = tester.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
