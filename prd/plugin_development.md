# 插件开发指南

> 描述如何在 suri-agent 中开发新插件。所有插件遵循统一规范，通过事件总线通信。

---

## 1. 插件目录结构

```
plugins/{plugin_name}/
├── __init__.py            # 插件入口，导出 Plugin 类
├── plugin.py              # 主实现类，继承 PluginInterface
├── manifest.json          # 插件元数据声明
├── config.yaml            # 默认配置（可选）
├── tests/                 # 插件测试（可选）
│   ├── __init__.py
│   └── test_plugin.py
└── README.md              # 插件说明（可选）
```

## 2. manifest.json 规范

```json
{
  "manifest_version": "1.0",
  "name": "my_plugin",
  "version": "1.0.0",
  "entry_point": "plugin.py",
  "min_suri_version": "1.0.0",
  "type": "capability",
  "description": "插件一句话描述",
  "author": "",
  "permissions": ["system.*", "user.input"],
  "event_subscriptions": ["task.completed", "user.command"],
  "fs_permissions": {
    "read": ["plugins/my_plugin/", "~/.suri/runtime/my_plugin/"],
    "write": ["~/.suri/runtime/my_plugin/"]
  },
  "runtime_mutable": true,
  "dependencies": ["suri_core", "llm_gateway"],
  "config_schema": {
    "my_plugin": {
      "enabled": { "type": "boolean", "default": true },
      "timeout": { "type": "integer", "default": 30, "min": 1, "max": 3600 }
    }
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 插件唯一标识，只能包含字母、数字、下划线 |
| `version` | string | 是 | 语义化版本，如 "1.0.0" |
| `type` | string | 是 | `core` / `service` / `capability` / `access` / `extension` |
| `description` | string | 是 | 一句话描述 |
| `permissions` | array | 否 | 所需事件权限，使用通配符 |
| `event_subscriptions` | array | 否 | 订阅的事件列表 |
| `runtime_mutable` | boolean | 否 | 是否允许运行时自修改，默认 true |
| `dependencies` | array | 否 | 依赖的插件名称列表 |
| `config_schema` | object | 否 | 配置项 schema，支持 type/default/min/max/required/enum |
| `manifest_version` | string | 是 | manifest 格式版本，当前 "1.0" |
| `entry_point` | string | 否 | 入口文件，默认 "plugin.py" |
| `min_suri_version` | string | 否 | 最低兼容 suri 版本 |
| `author` | string | 否 | 作者信息 |
| `fs_permissions` | object | 否 | 文件系统权限声明，`read` / `write` 路径列表 |
| `self_registration` | boolean | 否 | 内核插件专用，默认 false |

## 3. PluginInterface 实现

```python
# plugins/my_plugin/plugin.py
from shared.interfaces import PluginInterface
from shared.utils.event_types import Event, EventType

class MyPlugin(PluginInterface):
    """插件主类"""
    
    def __init__(self):
        self.name = "my_plugin"
        self.event_bus = None
        self.config = {}
    
    def init(self, event_bus, config):
        """初始化，传入 EventBus 实例和配置子树"""
        self.event_bus = event_bus
        self.config = config
        return True
    
    def register_events(self):
        """注册事件订阅"""
        self.event_bus.subscribe("task.completed", self.on_task_completed)
        self.event_bus.subscribe("user.command", self.on_user_command)
    
    def start(self):
        """启动插件"""
        # 启动后台任务、连接资源等
        pass
    
    def pause(self):
        """暂停插件"""
        # 暂停事件处理，保留状态
        pass
    
    def resume(self):
        """恢复插件"""
        pass
    
    def stop(self):
        """停止插件"""
        # 停止后台任务
        pass
    
    def cleanup(self):
        """清理资源"""
        # 释放连接、保存状态
        pass
    
    # --- 事件处理回调 ---
    
    async def on_task_completed(self, event: Event):
        """处理 task.completed 事件"""
        task_id = event.payload.get("task_id")
        result = event.payload.get("result")
        # 业务逻辑...
        
        # 发布新事件
        await self.event_bus.publish(Event(
            event_type="my_plugin.result",
            source="my_plugin",
            payload={"task_id": task_id, "processed": True}
        ))
    
    async def on_user_command(self, event: Event):
        """处理用户命令"""
        command = event.payload.get("command")
        if command == "/my_plugin":
            # 处理命令...
            pass
```

## 4. 事件订阅与发布

### 订阅事件

```python
# 精确匹配
self.event_bus.subscribe("task.completed", self.handler)

# 通配符匹配
self.event_bus.subscribe("task.*", self.handle_all_task_events)
self.event_bus.subscribe("error.*", self.handle_errors)
```

### 发布事件

```python
from shared.utils.event_types import Event, Priority

event = Event(
    event_type="my_plugin.status",
    source="my_plugin",
    target="role_manager",      # 可选，指定接收者
    payload={
        "status": "ready",
        "timestamp": "2026-05-02T15:51:00+08:00"
    },
    priority=Priority.NORMAL
)

await self.event_bus.publish(event)
```

### 事件 Payload 规范

所有事件 payload 必须符合 JSON 可序列化格式：

```python
# ✅ 正确
payload = {
    "task_id": "task_123",
    "count": 42,
    "enabled": True,
    "items": ["a", "b"],
    "nested": {"key": "value"}
}

# ❌ 错误（不可序列化）
payload = {
    "callback": lambda x: x,  # 函数不可序列化
    "datetime": datetime.now()  # datetime 对象不可序列化
}
```

## 5. 配置读取

```python
# 插件只接收自己的配置子树
config = {
    "enabled": True,
    "timeout": 30,
    "items": ["a", "b"]
}

# 配置热更新时，PluginManager 自动调用重新加载
```

## 6. 数据库使用

```python
from shared.utils.db import get_plugin_db

# 获取插件专属 SQLite 连接
async with get_plugin_db("my_plugin") as db:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS my_records (
            id TEXT PRIMARY KEY,
            data TEXT,
            created_at TEXT
        )
    """)
    await db.commit()
```

**规则**：
- 插件只能读写自己的数据库文件（`~/.suri/data/plugins/{plugin_name}.db`）
- 禁止直接访问其他插件的数据库
- 使用 WAL 模式支持并发读写

## 7. 日志记录

```python
from shared.utils.log import get_plugin_logger

logger = get_plugin_logger("my_plugin")

logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告")
logger.error("错误：%s", error_msg)
```

日志自动输出到：`~/.suri/runtime/logs/{plugin_name}/{YYYYMMDD}.log`

## 8. 共享模块规范

以下模块由框架提供，所有插件可复用。

### AgentContext

> 归属：agent_registry（定义）/ framework（基础接口）

构建 LLM 请求的完整上下文：

```python
class AgentContext:
    agent_id: str
    role_id: str
    soul: Soul              # 解析后的 Soul 对象
    insights: List[Insight] # 最近 30 天洞察（≤2000 字符）
    skills: List[Skill]     # 角色已激活技能
    memory_summary: str     # 记忆摘要
    
    def build_chat_messages(self, task_hint: str) -> List[Message]:
        """构建 system prompt + 历史消息 + 任务消息"""
        # 1. system prompt = Soul.definition + Soul.methodology
        # 2. 注入 insights（按 task_hint 关键词粗排，总字符 ≤2000）
        # 3. 注入 skills（按 relevance 排序）
        # 4. 附加 memory_summary
        # 5. 返回 [system, user/assistant history..., current task]
```

### TaskStep / TaskStateService

> 归属：task_scheduler（状态服务）/ agent_registry（步骤跟踪）

```python
@dataclass
class TaskStep:
    step_id: str
    name: str
    status: StepStatus      # pending / in_progress / completed / blocked
    depends_on: List[str]   # 前置 step_id 列表
    result: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]

class TaskStateService:
    async def transition(self, task_id: str, from_state: TaskState, to_state: TaskState) -> bool
    async def get_dependency_chain(self, step_id: str) -> List[TaskStep]
```

### PluginSelfLearning

> 归属：role_learner（模块）/ upgrade_manager（消费）

插件自分析触发器。当插件检测到自身可优化时：

```python
class PluginSelfLearning:
    async def analyze(self, plugin_id: str, event_logs: List[Event]) -> UpgradeReport:
        """分析插件调用模式，生成升级建议"""
        
    async def propose_upgrade(self, report: UpgradeReport) -> None:
        """发布 plugin.upgrade_proposed 事件"""
```

**触发条件**：
- 插件被调用次数达到阈值（默认 100 次）
- 错误率超过阈值（默认 5%）
- 用户主动触发 `/learn plugin {plugin_id}`

### EventBusFixture

> 归属：test_framework

测试用的内存事件总线 mock：

```python
class EventBusFixture:
    async def publish(self, event: Event) -> None
    async def subscribe(self, pattern: str, handler: Callable) -> None
    def get_published_events(self, event_type: str = None) -> List[Event]
    def clear(self) -> None
```

### TestBase

> 归属：test_framework

所有测试的基类，提供隔离的运行环境：

```python
class TestBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bus = EventBusFixture()
        self.tmp_dir = tempfile.mkdtemp()
        self.db = await get_plugin_db("test", path=f"{self.tmp_dir}/test.db")
    
    async def asyncTearDown(self):
        shutil.rmtree(self.tmp_dir)
```

### RoleFixture

> 归属：test_framework

角色环境 mock，创建临时角色目录和数据库：

```python
class RoleFixture:
    def __init__(self, role_id: str = "test_role"):
        self.tmp_dir = tempfile.mkdtemp()
        self.role_dir = f"{self.tmp_dir}/roles/{role_id}"
        os.makedirs(f"{self.role_dir}/memories/insights", exist_ok=True)
        os.makedirs(f"{self.role_dir}/skills", exist_ok=True)
        self.soul_path = f"{self.role_dir}/soul.md"
    
    def write_soul(self, content: str) -> None
    def get_insights_dir(self) -> str
    def cleanup(self) -> None
```

### PluginTestHarness

> 归属：test_framework

插件加载和生命周期测试工具：

```python
class PluginTestHarness:
    async def load_plugin(self, manifest_path: str) -> PluginInterface
    async def run_lifecycle(self, plugin: PluginInterface) -> None
    def assert_events_published(self, *event_types: str) -> None
```

## 9. 测试要求

每个插件必须包含测试文件：

```python
# plugins/my_plugin/tests/test_plugin.py
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.my_plugin.plugin import MyPlugin
from shared.utils.event_types import Event, Priority

class TestMyPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = MyPlugin()
        # 如需 EventBus，可创建 mock 或使用实际 EventBus
    
    def test_on_task_completed(self):
        event = Event(
            event_type="task.completed",
            source="test",
            payload={"task_id": "test_1", "result": "success"}
        )
        # 如需异步测试，使用 unittest.IsolatedAsyncioTestCase (Python 3.8+)
        # await self.plugin.on_task_completed(event)
        # 断言...
```

**测试要求**：
- 至少 5 个核心功能测试用例
- 至少 3 个异常/边界测试用例
- 必须通过 AST 安全扫描（无 socket/subprocess/eval/exec/__import__）
- 使用 Python 内置 `unittest`，零外部依赖

## 9. PRD 编写规范

开发新插件前必须编写 PRD 文档，保存到 `prd/plugins/{plugin_name}.md`：

```markdown
# {plugin_name} 插件 PRD

## 定位
一句话描述插件职责。

## 功能需求
### 1. 功能模块 A
- 需求描述...

### 2. 功能模块 B
- 需求描述...

## 接口定义
### 订阅事件
| 事件 | 来源 | 处理 |
|------|------|------|
| event.type | 来源 | 说明 |

### 发布事件
| 事件 | 目标 | 说明 |
|------|------|------|
| event.type | 目标 | 说明 |

## 事件 Payload Schema
### 订阅事件
#### `event.type`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| field | string | 是 | 说明 |

### 发布事件
#### `event.type`
...

## 配置项
```yaml
plugin_name:
  key: value
```

## 依赖关系
- 上游：xxx
- 下游：xxx

## 数据模型
### SQLite 表
...

## 生命周期
1. init()
2. register_events()
3. start()
4. pause()
5. resume()
6. stop()
7. cleanup()

## 安全边界
- 约束 1
- 约束 2

## 错误码
| 错误码 | 错误类型 | 说明 |
|--------|---------|------|
| 5001 | my_plugin.invalid_config | 配置无效 |
```

## 10. 调试指南

### 本地调试模式

```bash
# 跳过 AST 扫描（仅开发环境）
python main.py --skip-ast-scan

# 只加载指定插件
python main.py --plugins suri_core,my_plugin,log_service

# 提高日志级别
SURI_LOG_LEVEL=DEBUG python main.py
```

### 常见调试问题

| 问题 | 排查方法 |
|------|----------|
| 事件未触发 | 检查 EventBusFixture 的 get_published_events()；确认 subscribe 模式匹配 |
| 配置读取失败 | 确认 config_schema 与 manifest.json 一致；检查 config_service 加载日志 |
| 数据库锁 | 确保使用 `get_plugin_db()` 的 async context manager；检查 WAL 模式 |
| 插件加载失败 | 检查 manifest.json 的 dependencies 是否全部满足；检查 Python 语法错误 |

### 热重载开发

```bash
# 监视插件目录变更，自动重载（开发模式）
python main.py --watch-plugins

# 重载行为：
# 1. 检测 plugins/my_plugin/ 文件变更
# 2. 调用 plugin.stop() → plugin.cleanup()
# 3. 重新 import 模块
# 4. 调用 plugin.init() → plugin.start()
# 5. 已运行任务不受影响
```

### 插件脚手架

```bash
# 创建新插件模板
python scripts/create_plugin.py --name my_plugin --type capability

# 生成文件结构：
# plugins/my_plugin/
# ├── manifest.json
# ├── plugin.py
# ├── config.yaml
# └── tests/
#     └── test_plugin.py
```

## 11. 开发检查清单

提交新插件前确认：

- [ ] manifest.json 格式正确，所有必填字段已填写
- [ ] plugin.py 正确实现 PluginInterface 所有方法
- [ ] 事件订阅/发布逻辑正确
- [ ] 配置读取使用自己的子树
- [ ] 数据库操作使用插件专属连接
- [ ] 日志使用 get_plugin_logger
- [ ] 测试用例覆盖核心功能和异常场景
- [ ] PRD 文档已编写并同步更新 plugins/README.md
- [ ] 通过 AST 安全扫描（无危险操作）
- [ ] 依赖关系已声明，无循环依赖
