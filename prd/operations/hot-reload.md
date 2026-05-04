# 热更新基础规则

> 定义 suri-agent 中所有"新建角色、新增数据、新增文件"等操作的自动维护和热更新机制。

---

## 一、核心原则

1. **零硬编码** — 所有可变数据必须外部化到文件/数据库/配置中，禁止硬编码在 Python 代码中
2. **事件驱动热更新** — 数据变更后通过 EventBus 发布事件，相关插件自动刷新
3. **版本协商** — 插件间通过 manifest.json 声明兼容版本，启动时校验
4. **统一升级通道** — 所有运行时自修改通过 upgrade_manager 统一管理

---

## 二、数据外部化清单

### 2.1 当前硬编码问题

| # | 位置 | 硬编码内容 | 应外部化到 | 优先级 |
|---|------|-----------|-----------|--------|
| 1 | `plugins/role_manager/plugin.py` | `SOUL_TEMPLATE` 字符串 | `~/.suri/data/templates/soul_template.md` | 🔴 高 |
| 2 | `plugins/role_manager/plugin.py` | `_get_system_prompt()` 中的工具调用说明 | `~/.suri/data/templates/tool_descriptions.yaml` | 🔴 高 |
| 3 | `plugins/task_planner/plugin.py` | `_load_builtin_templates()` 中的内置模板 | `~/.suri/data/templates/task_templates.yaml` | 🔴 高 |
| 4 | `plugins/interrupt_handler/plugin.py` | `_classify_reason()` 中的关键词列表 | `~/.suri/data/configs/interrupt_keywords.yaml` | 🟡 中 |
| 5 | `plugins/access/plugin.py` | 通道路由逻辑 | `~/.suri/data/configs/channel_routes.yaml` | 🟡 中 |
| 6 | `plugins/role_manager/plugin.py` | `_create_suri()` 中的 fallback 文本 | `~/.suri/data/templates/suri_fallback.md` | 🟢 低 |

### 2.2 外部化数据目录结构

```
~/.suri/data/
├── templates/                    # 模板文件
│   ├── soul_template.md          # 角色 Soul 模板
│   ├── tool_descriptions.yaml    # 工具调用说明
│   ├── task_templates.yaml       # 任务规划模板
│   └── suri_fallback.md          # suri 角色 fallback
├── configs/                      # 配置文件
│   ├── interrupt_keywords.yaml   # 中断关键词
│   └── channel_routes.yaml       # 通道路由
└── plugins/                      # 插件数据
    └── {plugin_name}/
        └── data.yaml
```

---

## 三、热更新事件流

### 3.1 配置热更新

```
用户/角色修改配置文件
    │
    ▼
config_service 检测文件变更
    │
    ▼
config_service 发布 config.updated 事件
    │   payload: { "plugin_id": "task_planner", "config_key": "templates", ... }
    ▼
相关插件订阅 config.updated
    │
    ├── 重新加载配置
    ├── 更新内存状态
    └── 继续处理新请求（不影响正在进行的任务）
```

### 3.2 模板热更新

```
用户/角色新增任务模板
    │
    ▼
code_tool 写入 ~/.suri/data/templates/task_templates.yaml
    │
    ▼
hooks_service 检测文件变更
    │
    ▼
发布 task_planner.templates_updated 事件
    │
    ▼
task_planner 重新加载模板
    ├── 保留内置模板（不可覆盖）
    ├── 合并外部模板
    └── 更新内存索引
```

### 3.3 角色热更新

```
用户/角色创建新角色
    │
    ▼
role_manager.create_role()
    ├── 生成角色目录 ~/.suri/runtime/roles/{role_id}/
    ├── 写入 soul.md（使用外部模板）
    ├── 写入 meta.json
    └── 发布 role.created 事件
    │
    ▼
其他插件订阅 role.created
    ├── task_planner → 更新角色能力索引
    ├── agent_registry → 更新可用角色列表
    └── access → 更新角色路由
```

### 3.4 工具热更新

```
新增工具（通过 mcp_framework 或 code_tool）
    │
    ▼
工具注册到 ~/.siri/data/tools/{tool_name}.json
    │
    ▼
发布 tool.registered 事件
    │
    ▼
role_manager 更新工具调用说明
    ├── 重新生成 _get_system_prompt()
    └── 下次 LLM 请求自动包含新工具
```

---

## 四、插件版本协商

### 4.1 manifest.json 版本声明

```json
{
  "name": "task_planner",
  "version": "1.2.0",
  "min_suri_version": "1.0.0",
  "api_version": "1.0",
  "provides_interfaces": ["TaskPlanner"],
  "requires_interfaces": {
    "llm_gateway": ">=1.0.0",
    "role_manager": ">=1.0.0"
  },
  "event_contract": {
    "publishes": ["task.planned", "task.plan_updated"],
    "subscribes": ["task.plan_requested", "task.replan_requested"]
  }
}
```

### 4.2 版本校验规则

| 场景 | 行为 |
|------|------|
| 插件版本 < 最低要求 | 拒绝加载，报错 "plugin X requires version >= Y" |
| 插件版本 >= 最低要求 | 正常加载 |
| 缺少依赖插件 | 拒绝加载，报错 "plugin X requires Y, but Y is not loaded" |
| 事件契约不匹配 | 警告但不阻止加载（兼容模式） |

### 4.3 接口版本化

```python
# agent_framework/shared/interfaces/plugin.py

class PluginInterface:
    """插件基类"""
    API_VERSION = "1.0"  # 插件接口版本
    
    async def init(self, event_bus, config): ...
    def register_events(self): ...
    async def start(self): ...
    async def pause(self): ...
    async def resume(self): ...
    async def stop(self): ...
    async def cleanup(self): ...
```

**版本升级规则**：
- 新增方法 → 小版本升级（如 1.0 → 1.1），向后兼容
- 修改方法签名 → 大版本升级（如 1.0 → 2.0），不向后兼容
- 删除方法 → 大版本升级

---

## 五、插件升级通知机制

### 5.1 升级事件流

```
插件代码变更（通过 upgrade_manager）
    │
    ▼
upgrade_manager 执行验证
    ├── 运行测试
    ├── 检查 manifest.json 版本
    └── 发布 plugin.upgraded 事件
    │
    ▼
其他插件订阅 plugin.upgraded
    ├── 检查依赖版本是否满足
    ├── 如有不兼容 → 发布 plugin.incompatible 事件
    └── 框架自动协调（回滚或通知用户）
```

### 5.2 事件定义

```python
# plugin.upgraded
{
  "plugin_id": "task_planner",
  "old_version": "1.1.0",
  "new_version": "1.2.0",
  "changes": [
    "新增外部模板支持",
    "修复 depends_on 自引用 bug"
  ],
  "breaking_changes": false,
  "requires_restart": false
}

# plugin.incompatible
{
  "plugin_id": "task_scheduler",
  "dependency_id": "task_planner",
  "required_version": ">=1.1.0",
  "actual_version": "1.0.0",
  "action_required": "upgrade_dependency"
}
```

### 5.3 自动协调策略

| 场景 | 策略 |
|------|------|
| 依赖插件升级（兼容） | 自动适配，无需操作 |
| 依赖插件升级（不兼容） | 阻止升级，通知用户手动协调 |
| 被依赖插件降级 | 阻止降级，通知用户 |
| 新增插件 | 正常加载，通知相关插件刷新索引 |

---

## 六、运行时自修改规则

### 6.1 允许的自修改

| 操作 | 允许 | 说明 |
|------|------|------|
| 修改自身配置 | ✅ | 通过 config_service |
| 注册新模板 | ✅ | 通过 task_planner.register_template() |
| 注册新工具 | ✅ | 通过 mcp_framework |
| 创建新角色 | ✅ | 通过 role_manager.create_role() |
| 修改自身代码 | ⚠️ | 必须通过 upgrade_manager，用户确认 |
| 修改其他插件代码 | ❌ | 禁止 |
| 删除其他插件数据 | ❌ | 禁止 |

### 6.2 自修改流程

```
插件检测到优化机会
    │
    ▼
生成升级方案（含变更原因、具体变更、回滚策略、风险评估）
    │
    ▼
发布 plugin.upgrade_proposed 事件
    │
    ▼
upgrade_manager 接收
    ├── 创建 UpgradeReport
    ├── 状态: PENDING
    └── 向用户呈现
    │
    ▼
用户确认 → APPROVED
    │
    ▼
upgrade_manager 执行
    ├── 备份当前代码
    ├── 应用变更
    ├── 运行测试验证
    ├── 成功 → 标记 IMPLEMENTED
    └── 失败 → 回滚
```

---

## 七、各插件热更新适配清单

| 插件 | 需外部化数据 | 热更新事件 | 适配优先级 | 状态 |
|------|-------------|-----------|-----------|------|
| role_manager | Soul 模板、工具说明 | `config.updated`, `role_manager.templates_updated` | 🔴 迭代 2 | ✅ 已完成 |
| task_planner | 任务模板 | `config.updated`, `task_planner.templates_updated` | 🔴 迭代 2 | ✅ 已完成 |
| interrupt_handler | 关键词列表 | `config.updated`, `interrupt_handler.keywords_updated` | 🟡 迭代 2 | ✅ 已完成 |
| access | 通道路由 | `config.updated` | 🟡 迭代 5 | ⏳ 待适配 |
| llm_gateway | 模型配置 | `config.updated` | 🟢 迭代 5 | ⏳ 待适配 |
| agent_registry | — | `role.created` | 🟢 迭代 5 | ⏳ 待适配 |
| code_tool | — | `tool.registered` | 🟢 迭代 5 | ⏳ 待适配 |