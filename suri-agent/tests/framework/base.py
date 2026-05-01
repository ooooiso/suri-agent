"""
BaseTest 基类

为独立脚本格式的测试提供统一初始化基础设施。

关联文档: suri-agent/tests/README.md
"""

from pathlib import Path
from typing import Optional
from .utils import get_project_root, ok, fail, G, R, RST
from .fixtures import (
    make_config_service,
    make_memory_service,
    make_security_service,
    make_logger_service,
)


class BaseTest:
    """
    测试基类

    统一初始化 ConfigService、MemoryService、SecurityService、LoggerService。
    子类在 __init__ 中调用 super().__init__() 即可获得所有服务实例。

    示例:
        class MyTest(BaseTest):
            def __init__(self):
                super().__init__()
                # self.config, self.memory, self.security, self.logger 已可用

            def run(self):
                # 执行测试...
                pass

        if __name__ == "__main__":
            test = MyTest()
            success = test.run()
            sys.exit(0 if success else 1)
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or get_project_root()
        self.config = make_config_service(self.project_root)
        self.memory = make_memory_service(self.project_root, self.config)
        self.security = make_security_service(self.project_root, self.config)
        self.logger = make_logger_service(self.project_root)
        self.passed = 0
        self.failed = 0

    def ok(self, test_id: str, msg: str) -> None:
        """记录通过"""
        ok(test_id, msg)
        self.passed += 1

    def fail(self, test_id: str, msg: str) -> None:
        """记录失败"""
        fail(test_id, msg)
        self.failed += 1

    def summary(self) -> bool:
        """打印汇总并返回是否全部通过"""
        print(f"\n{'='*50}")
        print(f"测试完成: {G}{self.passed} 通过{RST}, {R}{self.failed} 失败{RST}")
        print(f"{'='*50}")
        return self.failed == 0

    def reset(self) -> None:
        """重置计数器"""
        self.passed = 0
        self.failed = 0
