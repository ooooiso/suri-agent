# 迭代 5：热更新 + 解耦重构

> 消除所有硬编码，实现数据与逻辑分离，建立插件版本协商和升级通知机制，确保每个插件可独立迭代。

**重要说明**：热更新不是新插件功能，而是对**已有插件的改造**。迭代 5 不新增任何插件，所有任务都是改造已有插件和基础设施。

---

## 目标

1. **零硬编码** — 所有可变数据外部化到文件/配置/数据库中
2. **事件驱动热更新** — 数据变更后通过 EventBus 发布事件，相关插件自动刷新
3. **插件版本协商** — manifest.json 声明版本和依赖，启动时校验
4. **升级通知机制** — 插件升级后发布 `plugin.upgraded` 事件，框架自动协调
5. **角色与插件解耦** — role_manager 不再代理 suri 角色，改为纯数据服务

---

## 包含任务（6 个已有插件改造 + 2 个基础设施改造）

| # | 任务 | 说明 | 优先级 |
|---|------|------|--------|
| 1 | **role_manager 解耦** | 消除 SOUL_TEMPLATE 硬编码，工具说明外部化，不再代理 suri | 🔴 |
| 2 | **task_planner 热更新** | 任务模板外部化，支持热更新 | 🔴 |
| 3 | **interrupt_handler 热更新** | 关键词外部化，支持热更新 | 🟡 |
| 4 | **access 解耦** | 通道路由外部化，通道与逻辑分离 | 🟡 |
| 5 | **manifest.json 版本协商** | PluginManager 按依赖顺序加载，版本校验 | 🔴 |
| 6 | **plugin.upgraded 事件** | 升级通知机制，自动协调 | 🔴 |
| 7 | **EventBus 全局异常捕获** | 统一错误处理，发布 error.plugin_crash | 🟡 |
| 8 | **agent_registry SQLite 持久化** | 从内存存储迁移到 SQLite | 🟢 |

---

## 详细任务分解

### Week 1：基础设施 + role_manager 解耦

#### 任务 1.1：manifest.json 版本协商（PluginManager）

**文件**：`agent_framework/plugin_manager/manager.py`

**变更**：
1. 解析 manifest.json 的 `dependencies` 字段
2. 按拓扑排序加载插件，检测循环依赖
3. 缺少依赖时抛出明确错误
4. 支持 `optional_dependencies` 字段
5. 版本校验（`>=`, `~=`, `==` 语义）

**测试**：
- 正常依赖顺序加载
- 循环依赖检测
- 缺少依赖报错
- 版本不匹配报错

#### 任务 1.2：plugin.upgraded 事件

**文件**：`agent_framework/plugin_manager/manager.py` + `shared/utils/event_types.py`

**变更**：
1. 新增 `plugin.upgraded` 事件类型
2. PluginManager 在插件升级后自动发布事件
3. 新增 `plugin.incompatible` 事件类型
4. 依赖方订阅 `plugin.upgraded`，自动检查兼容性

**事件定义**：
```python
# plugin.upgraded
{
  "plugin_id": "task_planner",
  "old_version": "1.1.0",
  "new_version": "1.2.0",
  "changes": ["新增外部模板支持"],
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

#### 任务 1.3：role_manager 解耦

**文件**：`plugins/role_manager/plugin.py` + `plugins/role_manager/soul_parser.py`

**变更**：
1. **消除 SOUL_TEMPLATE 硬编码**：
   - 创建 `~/.suri/data/templates/soul_template.md`
   - `create_role()` 从外部文件读取模板
   - 保留代码内 fallback（仅当外部文件不存在时）

2. **工具说明外部化**：
   - 创建 `~/.suri/data/templates/tool_descriptions.yaml`
   - `_get_system_prompt()` 从外部文件读取工具说明
   - 新增工具时只需修改 YAML 文件

3. **不再代理 suri 角色**：
   - `_on_user_input()` 改为只提供角色数据，不构建 system prompt
   - 发布 `role.context_ready` 事件，由 suri 角色自己订阅
   - suri 角色通过 `role.context_ready` 事件获取 Soul 数据

**外部文件格式**：

```yaml
# ~/.suri/data/templates/tool_descriptions.yaml
tools:
  - name: "code_tool.read_file"
    description: "读取文件内容"
    params:
      - name: "path"
        required: true
        description: "文件路径"
      - name: "offset"
        required: false
        description: "起始行"
      - name: "limit"
        required: false
        description: "最多行数"
    example: "tool code_tool.read_file path=main.py offset=0 limit=50"
  
  - name: "code_tool.list_dir"
    description: "列出目录内容"
    params:
      - name: "path"
        required: true
        description: "目录路径"
    example: "tool code_tool.list_dir path=plugins/"
```

**测试**：
- 从外部文件加载模板
- 从外部文件加载工具说明
- 外部文件不存在时使用 fallback
- 角色数据提供（不再代理 suri）

---

### Week 2：task_planner + interrupt_handler + access 改造

#### 任务 2.1：task_planner 热更新

**文件**：`plugins/task_planner/plugin.py`

**变更**：
1. **任务模板外部化**：
   - 创建 `~/.suri/data/templates/task_templates.yaml`
   - `_load_builtin_templates()` 改为从外部文件加载
   - 保留内置模板作为 fallback

2. **支持热更新**：
   - 订阅 `config.updated` 事件
   - 订阅 `task_planner.templates_updated` 事件
   - 重新加载模板时保留内置模板（不可覆盖）

3. **模板注册事件**：
   - 新增 `task_planner.templates_updated` 事件类型
   - 其他插件可通过发布此事件通知 task_planner 刷新

**外部文件格式**：

```yaml
# ~/.suri/data/templates/task_templates.yaml
templates:
  - template_id: "custom.code"
    name: "代码开发"
    keywords: ["实现", "编写", "开发", "code"]
    steps:
      - description: "理解需求"
        assignee: "suri"
      - description: "设计"
        assignee: "suri"
      - description: "编码"
        assignee: "suri"
      - description: "自测"
        assignee: "suri"
    default_role: "suri"
    priority: 10
    description: "标准代码开发流程"
```

**测试**：
- 从外部文件加载模板
- 热更新后模板生效
- 内置模板不可覆盖
- 外部模板优先级高于内置模板

#### 任务 2.2：interrupt_handler 热更新

**文件**：`plugins/interrupt_handler/plugin.py`

**变更**：
1. **关键词外部化**：
   - 创建 `~/.suri/data/configs/interrupt_keywords.yaml`
   - `_classify_reason()` 从外部文件加载关键词
   - 保留代码内 fallback

2. **支持热更新**：
   - 订阅 `config.updated` 事件
   - 重新加载关键词映射

3. **关键词冲突检测**：
   - 加载时检测关键词重叠并告警
   - 支持优先级权重（精确匹配 > 子串匹配）

**外部文件格式**：

```yaml
# ~/.suri/data/configs/interrupt_keywords.yaml
keywords:
  missing_tool:
    - "缺少工具"
    - "没有接口"
    - "不支持"
    - "need tool"
    - "missing"
    - "not supported"
    - "unavailable"
  knowledge_gap:
    - "不会"
    - "不了解"
    - "不清楚"
    - "unknown"
    - "don't know"
    - "not sure"
  permission_denied:
    - "权限不足"
    - "拒绝访问"
    - "无权限"
    - "forbidden"
    - "denied"
    - "access denied"
    - "403"
  dependency_failed:
    - "依赖失败"
    - "上游错误"
    - "调用失败"
    - "unavailable"
    - "dependency"
    - "connection refused"
  timeout:
    - "超时"
    - "无响应"
    - "hang"
    - "timeout"
    - "no response"
    - "stuck"
  resource_exhausted:
    - "内存不足"
    - "OOM"
    - "quota"
    - "exhausted"
    - "rate limit"
    - "429"
    - "too many requests"
```

**测试**：
- 从外部文件加载关键词
- 热更新后关键词生效
- 关键词冲突检测告警
- 精确匹配优先于子串匹配

#### 任务 2.3：access 解耦

**文件**：`plugins/access/plugin.py`

**变更**：
1. **通道路由外部化**：
   - 创建 `~/.suri/data/configs/channel_routes.yaml`
   - 通道选择逻辑从代码中分离

2. **通道与逻辑分离**：
   - 每个通道（CLI/Telegram）独立文件
   - 通道注册通过事件机制

**外部文件格式**：

```yaml
# ~/.suri/data/configs/channel_routes.yaml
channels:
  cli:
    enabled: true
    module: "plugins.access.cli"
    description: "命令行交互"
  telegram:
    enabled: true
    module: "plugins.access.telegram"
    description: "Telegram 机器人"
    config:
      bot_token_env: "TELEGRAM_BOT_TOKEN"
```

**测试**：
- 从外部文件加载通道配置
- 启用/禁用通道
- 新增通道无需修改代码

#### 任务 2.4：EventBus 全局异常捕获

**文件**：`agent_framework/event_bus/bus.py`

**变更**：
1. `_dispatch()` 方法自动捕获订阅者异常
2. 异常转为 `error.plugin_crash` 事件发布
3. 不影响其他订阅者

**测试**：
- 订阅者抛出异常不影响其他订阅者
- `error.plugin_crash` 事件正确发布
- 异常信息包含 handler 名称和错误详情

#### 任务 2.5：agent_registry SQLite 持久化

**文件**：`plugins/agent_registry/plugin.py`

**变更**：
1. 从内存字典迁移到 SQLite
2. 启动时从数据库恢复活跃 Agent
3. 定期持久化 Agent 状态变更
4. 使用 `agent_framework/migrations/002_agents.sql` 表结构

**测试**：
- Agent 创建后持久化到数据库
- 重启后恢复活跃 Agent
- 状态变更正确持久化
- 清理过期 Agent

---

## 测试矩阵

### 基础设施测试

| 测试项 | 通过标准 |
|--------|----------|
| 版本协商 | 依赖顺序正确加载，循环依赖检测 |
| 版本校验 | 版本不匹配时拒绝加载 |
| 升级通知 | 插件升级后自动发布 plugin.upgraded |
| 不兼容检测 | 依赖方检测到不兼容并阻止升级 |
| 全局异常捕获 | 订阅者异常不影响其他订阅者 |

### 插件改造测试

| 测试项 | 通过标准 |
|--------|----------|
| role_manager 解耦 | Soul 模板从外部文件加载，工具说明从外部文件加载 |
| role_manager 不再代理 suri | 发布 role.context_ready 事件，suri 自己订阅 |
| task_planner 热更新 | 模板从外部文件加载，热更新后立即生效 |
| interrupt_handler 热更新 | 关键词从外部文件加载，热更新后立即生效 |
| access 解耦 | 通道路由从外部文件加载，新增通道无需改代码 |
| agent_registry 持久化 | Agent 数据持久化到 SQLite，重启后恢复 |

### 回归测试

| 测试项 | 通过标准 |
|--------|----------|
| 全量测试 | 所有现有测试通过（59+ 新增） |
| 热更新不影响运行中任务 | 热更新时正在处理的任务不受影响 |
| 外部文件不存在时 fallback | 外部文件缺失时使用代码内默认值 |

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent_framework/plugin_manager/manager.py` | 修改 | 版本协商、拓扑排序、升级通知 |
| `agent_framework/event_bus/bus.py` | 修改 | 全局异常捕获 |
| `shared/utils/event_types.py` | 修改 | 新增事件类型 |
| `plugins/role_manager/plugin.py` | 修改 | 解耦、外部化、不再代理 suri |
| `plugins/role_manager/soul_parser.py` | 修改 | 支持外部模板 |
| `plugins/task_planner/plugin.py` | 修改 | 模板外部化、热更新 |
| `plugins/interrupt_handler/plugin.py` | 修改 | 关键词外部化、热更新 |
| `plugins/access/plugin.py` | 修改 | 通道路由外部化 |
| `plugins/agent_registry/plugin.py` | 修改 | SQLite 持久化 |
| `~/.suri/data/templates/soul_template.md` | 新增 | Soul 模板 |
| `~/.suri/data/templates/tool_descriptions.yaml` | 新增 | 工具调用说明 |
| `~/.suri/data/templates/task_templates.yaml` | 新增 | 任务模板 |
| `~/.suri/data/configs/interrupt_keywords.yaml` | 新增 | 中断关键词 |
| `~/.suri/data/configs/channel_routes.yaml` | 新增 | 通道路由 |
| `tests/plugin/test_plugin_manager.py` | 新增 | 版本协商测试 |
| `tests/plugin/test_event_bus_error.py` | 新增 | 全局异常捕获测试 |
| `tests/plugin/test_role_manager_hot_reload.py` | 新增 | 热更新测试 |
| `tests/plugin/test_task_planner_hot_reload.py` | 新增 | 热更新测试 |
| `tests/plugin/test_interrupt_handler_hot_reload.py` | 新增 | 热更新测试 |
| `tests/plugin/test_agent_registry_persistence.py` | 新增 | 持久化测试 |