# 测试指南

> suri-agent 测试框架使用指南。

---

## 一、测试目录结构

```
tests/
├── framework/base.py       # 测试基类（AsyncTestCase + EventCollector）
├── unit/                   # 单元测试（测试独立模块）
├── plugin/                 # 插件测试（测试事件驱动的插件）
└── integration/            # 集成测试（测试多插件协作）
```

---

## 二、编写测试

### 单元测试

```python
# tests/unit/test_my_module.py
import pytest

class TestMyModule:
    def test_basic(self):
        result = my_function("input")
        assert result == "expected"
```

### 插件测试

```python
# tests/plugin/test_my_plugin.py
from tests.framework.base import AsyncTestCase

class TestMyPlugin(AsyncTestCase):
    async def test_event_handler(self):
        """测试事件处理"""
        await self.plugin.init(self.event_bus, {})
        self.plugin.register_events()
        await self.plugin.start()
        
        # 发布事件并收集结果
        events = await self.publish_and_collect(
            event_type="my.event",
            payload={"key": "value"},
            expected_count=1
        )
        assert events[0].payload["result"] == "ok"
```

### 集成测试

```python
# tests/integration/test_my_flow.py
class TestMyFlow(AsyncTestCase):
    async def test_multi_plugin(self):
        """测试多插件协作"""
        await self.init_plugin(PluginA, {})
        await self.init_plugin(PluginB, {})
        
        events = await self.publish_and_collect(
            event_type="flow.start",
            payload={},
            expected_count=2  # 两个插件各响应一次
        )
```

---

## 三、运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试文件
python -m pytest tests/plugin/test_my_plugin.py -v

# 运行带日志的测试
python -m pytest tests/ -v --log-cli-level=INFO
```

---

## 四、测试规范

- 每个插件必须有独立测试文件
- 测试方法命名：`test_功能描述`
- 使用 `pytest` 作为测试框架
- 异步测试使用 `AsyncTestCase` 基类
- 插件测试不依赖真实外部服务