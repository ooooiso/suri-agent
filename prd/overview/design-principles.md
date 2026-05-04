# 解耦设计原则

> 定义 suri-agent 中插件间、角色间、插件与角色间的解耦设计原则，确保每个组件可独立优化和迭代。

---

## 一、核心原则

### 原则 1：插件间仅通过 EventBus 通信

```
✅ 正确: plugin_a → EventBus → plugin_b
❌ 错误: plugin_a → 直接调用 plugin_b.method()
```

**规则**：
- 插件禁止直接 import 其他插件的类并调用其方法
- 插件禁止共享可变状态（如全局变量、共享内存字典）
- 所有跨插件交互必须通过事件发布/订阅

**例外**：
- 测试场景：测试代码可以直接调用插件方法
- 共享接口：`agent_framework/shared/interfaces/` 中的接口定义可以被所有插件 import

### 原则 2：数据与逻辑分离

```
✅ 正确: 插件逻辑读取外部配置文件，处理数据
❌ 错误: 插件逻辑中硬编码数据（模板、关键词、路由等）
```

**规则**：
- 所有可变数据必须外部化到文件/数据库/配置中
- 插件代码只包含处理逻辑，不包含业务数据
- 数据变更通过事件通知，插件自动刷新

### 原则 3：每个插件可独立迭代

```
✅ 正确: 插件 A 升级到 v2.0，插件 B 无需修改
❌ 错误: 插件 A 升级需要同步修改插件 B、C、D
```

**规则**：
- 插件通过 manifest.json 声明版本和依赖
- 事件契约（发布/订阅的事件类型）是插件间的唯一协议
- 新增事件类型不影响现有插件（向后兼容）
- 修改事件 payload 必须大版本升级

### 原则 4：迭代通知机制

```
✅ 正确: 插件升级后发布 plugin.upgraded 事件，框架自动协调
❌ 错误: 插件升级后手动修改其他插件
```

**规则**：
- 插件升级后必须发布 `plugin.upgraded` 事件
- 依赖方订阅 `plugin.upgraded` 事件，自动检查兼容性
- 不兼容时发布 `plugin.incompatible` 事件，框架阻止升级

---

## 二、插件间解耦

### 2.1 事件契约

每个插件必须明确定义其事件契约：

```python
# 插件的事件契约（在 manifest.json 中声明）
{
  "event_contract": {
    "publishes": [
      {"event_type": "task.planned", "payload_schema": {...}, "version": "1.0"},
      {"event_type": "task.plan_updated", "payload_schema": {...}, "version": "1.0"}
    ],
    "subscribes": [
      {"event_type": "task.plan_requested", "version": ">=1.0"},
      {"event_type": "task.replan_requested", "version": ">=1.0"}
    ]
  }
}
```

**契约规则**：
- 发布的事件必须声明 payload schema
- 订阅的事件必须声明最低版本
- 事件类型变更必须大版本升级

### 2.2 依赖注入

插件通过 `init()` 方法接收依赖，不直接创建依赖：

```python
# ✅ 正确：依赖注入
class MyPlugin(PluginInterface):
    async def init(self, event_bus, config):
        self.event_bus = event_bus  # 由框架注入
        self.config = config        # 由框架注入

# ❌ 错误：直接创建依赖
class MyPlugin(PluginInterface):
    async def init(self, event_bus, config):
        self.db = sqlite3.connect("my_plugin.db")  # 应通过 config_service 获取
```

### 2.3 错误隔离

每个插件的异常不能影响其他插件：

```python
# EventBus 自动捕获订阅者异常
async def _dispatch(self, event):
    for handler in self._get_handlers(event.event_type):
        try:
            await handler(event)
        except Exception as e:
            # 发布 error.plugin_crash 事件，不影响其他订阅者
            await self.publish(Event(
                event_type="error.plugin_crash",
                source="event_bus",
                payload={"handler": handler.__name__, "error": str(e)}
            ))
```

---

## 三、角色与插件解耦

### 3.1 角色是数据，插件是逻辑

```
角色 (Role) = 数据（Soul 文件、技能、记忆）
插件 (Plugin) = 逻辑（处理事件、调用 LLM、操作文件）

角色不包含逻辑，插件不包含角色数据
```

**规则**：
- 角色数据存储在 `roles/{role_id}/` 目录下（Git 管理）
- 插件逻辑在 `agent_framework/plugins/{plugin_name}/` 目录下
- 插件通过 role_manager 获取角色数据，不直接读取角色文件

### 3.2 角色切换不影响插件

```
✅ 正确: 切换角色 → role_manager 更新 system prompt → 插件继续工作
❌ 错误: 切换角色 → 需要重新加载插件
```

**规则**：
- 插件不绑定特定角色
- 角色切换只影响 system prompt 和上下文，不影响插件运行
- 新增角色不需要修改任何插件代码

### 3.3 角色能力通过事件暴露

```
✅ 正确: 角色需要某能力 → 发布事件 → 对应插件处理
❌ 错误: 角色直接调用插件方法
```

**规则**：
- 角色通过发布事件来表达需求
- 插件通过订阅事件来提供服务
- 角色不需要知道哪个插件在处理

---

## 四、数据与逻辑分离

### 4.1 外部化数据分类

| 数据类型 | 存储位置 | 示例 | 热更新 |
|----------|---------|------|--------|
| 配置 | `~/.suri/config.json` | 模型选择、超时时间 | ✅ |
| 模板 | `~/.suri/data/templates/` | Soul 模板、任务模板 | ✅ |
| 关键词 | `~/.suri/data/configs/` | 中断关键词 | ✅ |
| 角色数据 | `roles/{role_id}/` | Soul 文件、技能、记忆 | ✅ |
| 插件数据 | `~/.suri/data/plugins/` | 各插件专属数据 | ✅ |
| 代码逻辑 | `agent_framework/plugins/{name}/plugin.py` | 事件处理、业务逻辑 | ❌（需升级流程）|

### 4.2 数据加载模式

```python
# ✅ 正确：从外部文件加载数据
class TaskPlannerPlugin:
    def _load_templates(self):
        # 从外部 YAML 文件加载模板
        templates_path = Path("~/.suri/data/templates/task_templates.yaml")
        if templates_path.exists():
            with open(templates_path) as f:
                return yaml.safe_load(f)
        return self._default_templates()

# ❌ 错误：硬编码数据在代码中
class TaskPlannerPlugin:
    def _load_builtin_templates(self):
        return {
            "builtin.code": TaskTemplate(
                name="代码开发",
                keywords=["实现", "编写", "开发"],
                steps=[...],  # 硬编码
            )
        }
```

---

## 五、独立迭代能力

### 5.1 插件迭代检查清单

每个插件在迭代前必须确认：

- [ ] 是否修改了事件契约（发布/订阅的事件类型）？
  - 是 → 大版本升级，通知依赖方
  - 否 → 小版本升级
- [ ] 是否修改了 manifest.json 的依赖版本？
  - 是 → 确保依赖方已升级
- [ ] 是否新增了外部化数据？
  - 是 → 更新 hot_reload_rules.md
- [ ] 是否新增了测试？
  - 是 → 确保测试覆盖新增功能

### 5.2 迭代通知流程

```
插件开发者完成迭代
    │
    ▼
更新 manifest.json 版本号
    │
    ▼
运行全量测试
    │
    ▼
发布 plugin.upgraded 事件
    │
    ▼
框架自动通知所有依赖方
    │
    ├── 兼容 → 自动适配
    └── 不兼容 → 阻止升级，通知用户
```

### 5.3 插件独立迭代示例

```python
# 迭代前：task_planner v1.0.0
# - 模板硬编码在代码中
# - 无法热更新

# 迭代后：task_planner v1.1.0
# - 模板从外部 YAML 文件加载
# - 支持热更新（订阅 config.updated 事件）
# - 向后兼容（v1.0.0 的调用方无需修改）

# 变更内容：
# 1. 新增 _load_templates_from_file() 方法
# 2. 新增 _on_config_updated() 事件处理
# 3. 保留 _load_builtin_templates() 作为 fallback
# 4. manifest.json 版本从 "1.0.0" 改为 "1.1.0"
```

---

## 六、角色与项目固化原则

### 关键原则：角色数据全部在 roles/ 下，纳入版本控制

**设计定位**：suri-agent 是"末日程序"，角色数据（Soul 定义、记忆、技能、产出）比代码更宝贵。Git clone 即可恢复全部角色状态。

**策略**：

```
roles/（Git 管理，包含全部角色数据，可迁移可回溯）
  ├── soul.md         ← 角色定义与职责描述
  ├── memories/       ← 角色记忆、insights
  ├── skills/         ← 角色技能文件
  └── output/         ← 角色产出文件

代码仓库（仅存放代码逻辑）
  ├── agent_framework/plugins/        ← 插件代码
  ├── agent_framework/ ← 框架代码
  └── main.py         ← 入口

~/.suri/（仅系统级敏感配置 + 运行时日志，不纳入 Git）
  ├── config.json    ← API Key、模型选择等敏感配置
  └── runtime/logs/  ← 运行时日志
```

**迁移到新机器的标准步骤**：

```
1. git clone <repo-url>              # 代码 + 角色数据一次性拉取
2. 复制 ~/.suri/config.json          # 单独复制敏感配置
3. 运行 main.py → 系统直接就绪       # 角色数据无需额外操作
```

**与代码仓库的关系**：
- ✅ 角色数据在 `roles/` 下随 Git 一起管理版本
- ✅ 可单独使用 `roles/` 子目录做角色备份恢复
- ❌ 不是"模板复制到运行时"模式——角色数据自包含、自解释
- ❌ 敏感配置（API Key）不进入 Git，保持在 `~/.suri/config.json`

---

## 八、解耦度评估矩阵

| 维度 | 当前评分 | 目标评分 | 关键措施 |
|------|---------|---------|---------|
| 插件间通信 | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐⭐ | 强化事件契约校验 |
| 数据与逻辑分离 | ⭐⭐☆☆☆ | ⭐⭐⭐⭐⭐ | 外部化所有硬编码数据 |
| 角色与插件解耦 | ⭐⭐⭐☆☆ | ⭐⭐⭐⭐⭐ | role_manager 不再代理 suri |
| 独立迭代能力 | ⭐⭐⭐☆☆ | ⭐⭐⭐⭐⭐ | 版本协商 + 升级通知 |
| 错误隔离 | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐⭐ | EventBus 全局异常捕获 |
| 测试独立性 | ⭐⭐⭐☆☆ | ⭐⭐⭐⭐⭐ | 每个插件独立测试套件 |

---

## 九、常见反模式

### 反模式 1：插件间直接调用

```python
# ❌ 错误
class RoleManagerPlugin:
    async def _on_user_input(self, event):
        llm_plugin = LLMGatewayPlugin()  # 直接创建其他插件实例
        await llm_plugin.process(event)  # 直接调用

# ✅ 正确
class RoleManagerPlugin:
    async def _on_user_input(self, event):
        await self._event_bus.publish(Event(
            event_type="llm.request",  # 通过事件通信
            source="role_manager",
            payload={...}
        ))
```

### 反模式 2：数据硬编码

```python
# ❌ 错误
class InterruptHandlerPlugin:
    KEYWORDS = {
        "missing_tool": ["缺少工具", "没有接口"],
        "timeout": ["超时", "timeout"],
    }

# ✅ 正确
class InterruptHandlerPlugin:
    def _load_keywords(self):
        path = Path("~/.suri/data/configs/interrupt_keywords.yaml")
        if path.exists():
            return yaml.safe_load(path.read_text())
        return self._default_keywords()
```

### 反模式 3：角色绑定插件

```python
# ❌ 错误
class RoleManagerPlugin:
    async def _on_user_input(self, event):
        # 直接代理 suri 角色，与 suri 逻辑耦合
        soul = self._read_soul("suri")
        prompt = self._build_prompt(soul)
        await self._event_bus.publish(Event(
            event_type="llm.request",
            payload={"messages": [{"role": "system", "content": prompt}]}
        ))

# ✅ 正确
class RoleManagerPlugin:
    async def _on_user_input(self, event):
        # 只提供角色数据，不代理角色逻辑
        role_id = event.payload.get("role_id", "suri")
        soul = self.get_soul(role_id)
        await self._event_bus.publish(Event(
            event_type="role.context_ready",  # 角色上下文就绪事件
            payload={
                "role_id": role_id,
                "soul": soul,
                "session_id": event.payload.get("session_id"),
            }
        ))
        # suri 角色自己订阅 role.context_ready 事件
```

### 反模式 4：共享可变状态

```python
# ❌ 错误
# global_state.py
agent_contexts = {}  # 全局可变字典，多个插件共享

# plugin_a.py
from global_state import agent_contexts
agent_contexts["agent_001"] = {...}  # 直接修改

# plugin_b.py
from global_state import agent_contexts
data = agent_contexts["agent_001"]  # 依赖其他插件的修改

# ✅ 正确
# 通过 EventBus 传递状态变更事件
# plugin_a 发布 agent.context_updated 事件
# plugin_b 订阅 agent.context_updated 事件