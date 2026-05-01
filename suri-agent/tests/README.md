# Suri 测试体系

> 关联代码: suri-agent/tests/ 下所有测试文件
>
> **运行方式:**
> ```bash
> # 运行全部测试
> python suri-agent/tests/run.py
>
> # 只跑单元测试（纯本地，无 API 调用，< 5s）
> python suri-agent/tests/run.py --unit
>
> # 只跑全量测试（调用模型或长时间运行）
> python suri-agent/tests/run.py --fullforce
>
> # 列出所有测试
> python suri-agent/tests/run.py --list
>
> # 用 pytest 运行 pytest 格式测试
> pytest suri-agent/tests/unit/ -v
> ```

---

## 目录结构

```
suri-agent/tests/
├── README.md              # 本文档
├── run.py                 # 统一测试入口
├── conftest.py            # pytest 共享 fixture
│
├── framework/             # 测试框架基础设施
│   ├── base.py            # BaseTest 基类（独立脚本测试继承）
│   ├── fixtures.py        # 共享 fixture 工厂
│   └── utils.py           # 工具函数（get_project_root, ok, fail）
│
├── unit/                  # 单元测试（纯本地，无 API 调用）
│   ├── test_model_manager.py
│   ├── test_task_dispatcher.py
│   ├── test_v3_comprehensive.py
│   ├── test_local_services.py
│   ├── test_terminal_startup.py
│   ├── test_output_framework.py
│   └── test_framework.py
│
└── fullforce/             # 全力量测试（调用模型或长时间运行）
    ├── test_100_roles.py
    ├── test_1000_rounds.py
    ├── test_concurrent_users.py
    ├── test_analyst_role.py
    ├── test_dispatch.py
    ├── test_integration.py
    ├── test_advanced.py
    ├── test_collaboration.py
    ├── test_stress.py
    └── test_comprehensive.py
```

---

## 测试分类

### 单元测试（unit/）

纯本地运行，不调用外部模型，无网络依赖，运行时间 < 5 秒。

| 测试文件 | 覆盖范围 | 格式 |
|----------|----------|------|
| `test_model_manager.py` | 配置加载/保存、模型选择、降级策略 | pytest |
| `test_task_dispatcher.py` | 任务创建、状态流转、调度匹配 | pytest |
| `test_v3_comprehensive.py` | V3.0 角色标识、昵称、状态卡片、Agent 并行、权限控制 | pytest |
| `test_local_services.py` | LoggerService、SecurityService、FileService | script |
| `test_terminal_startup.py` | 终端启动流程、角色发现、命令系统 | script |
| `test_output_framework.py` | OutputPayload、OutputRouter、Channel | script |
| `test_framework.py` | 框架机制：工具权限、上下文注入、规则摘要 | script |

### 全力量测试（fullforce/）


| 测试文件 | 覆盖范围 | 预估时间 |
|----------|----------|----------|
| `test_100_roles.py` | 100次模拟输入，验证调度逻辑正确性 | ~3-5min |
| `test_1000_rounds.py` | 500生活对话 + 500任务对话，多轮稳定性 | ~10-15min |
| `test_concurrent_users.py` | 多用户并发创建会话，验证隔离性 | < 1min |
| `test_analyst_role.py` | 统计角色（suri_stats）专项能力 | ~2-3min |
| `test_dispatch.py` | 模拟用户输入，测试四角色联动调度 | ~2-3min |
| `test_integration.py` | 终端交互模拟，测试完整对话闭环 | ~2-3min |
| `test_advanced.py` | 多轮对话记忆、能力边界、学习经验 | ~3-5min |
| `test_collaboration.py` | 复杂需求涉及多个角色的协作场景 | ~3-5min |
| `test_stress.py` | 快速连续调度多个角色 | ~2-3min |
| `test_comprehensive.py` | 综合批量测试，100+ 能力覆盖 | ~5-8min |

---

## 快速开始

### 列出所有测试

```bash
python suri-agent/tests/run.py --list
```

### 运行单元测试

```bash
# 方式1: 统一入口
python suri-agent/tests/run.py --unit

# 方式2: pytest 直接运行 pytest 格式测试
pytest suri-agent/tests/unit/ -v
```

### 运行全力量测试

```bash
# 需要已配置模型（model_config.json）
python suri-agent/tests/run.py --fullforce

# 跳过模型测试（只运行已通过的快速项）
python suri-agent/tests/run.py --fullforce --skip-model-tests
```

### 运行全部测试

```bash
python suri-agent/tests/run.py --all
```

### 运行单个测试

```bash
# pytest 格式
pytest suri-agent/tests/unit/test_model_manager.py -v

# 独立脚本格式
python suri-agent/tests/unit/test_local_services.py
python suri-agent/tests/fullforce/test_100_roles.py
```

---

## 测试框架基础设施

### 共享 Fixture（pytest）

`conftest.py` 提供以下 fixture：

```python
@pytest.fixture(scope="session")
def project_root(): ...

@pytest.fixture(scope="session")
def config(): ...

@pytest.fixture
def memory(project_root, config): ...

@pytest.fixture
def security(project_root, config): ...

@pytest.fixture
def logger(project_root): ...
```

### 共享基类（独立脚本）

独立脚本格式的测试可继承 `BaseTest`：

```python
from tests.framework import BaseTest

class MyTest(BaseTest):
    def run(self):
        # self.config, self.memory, self.security, self.logger 已可用
        self.ok("T01", "测试通过")
        return self.summary()

if __name__ == "__main__":
    sys.exit(0 if MyTest().run() else 1)
```

### 共享工具函数

```python
from tests.framework import get_project_root, ok, fail

project_root = get_project_root()  # 自动兼容 tests/unit/ 或 tests/fullforce/
```

---

## 测试环境要求

- **Python 3.9+**
- **模型配置**: 至少一个可用模型（用于全力量测试）
- **依赖**: `pip install -r requirements.txt`
- **环境变量**: `.env` 中的 API Key（如已有 model_config.json 则无需）

---

## 测试原则

1. **单元测试不调用模型**: `unit/` 下所有测试纯本地运行，无网络依赖
2. **全力量测试验证完整链路**: `fullforce/` 下测试调用实际模型，验证真实交互
3. **并发测试验证隔离性**: `test_concurrent_users.py` 确保多用户会话不混淆
4. **集成测试验证闭环**: `test_dispatch.py`、`test_integration.py` 验证 suri → 角色 → 结果回流完整链路

---

## 新增测试规范

新增测试文件时：
1. **选择目录**: 纯本地测试放 `unit/`，需模型测试放 `fullforce/`
2. **文件命名**: `test_<功能>.py`
3. **pytest 格式**: 优先使用 pytest（`def test_xxx():` + `assert`），自动被 `run.py` 识别
4. **独立脚本格式**: 如需自定义输出格式，继承 `BaseTest` 或使用 `ok()/fail()`
5. **路径处理**: 使用 `from tests.framework import get_project_root`，不要硬编码 `Path(__file__).parent.parent...`
6. **注册**: 无需手动注册，放对目录即可被 `run.py --list` 自动发现
