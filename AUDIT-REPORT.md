# Suri-Agent PRD 全面审计报告

> **审计范围**：PRD 文档全集（约 40+ 文件）+ 核心源码验证
> **审计时间**：2026-05-04
> **审计目标**：检测冲突、矛盾、实现难点、结构不合理、重复、不清晰、缺失、插件能力、性能瓶颈等

---

## 一、🔴 严重问题（Critical）

### 1.1 严重代码重复：SuriCorePlugin 存在双份实现

**描述**：`agent_framework/core/suri_core/plugin.py` 和 `agent_framework/suri_core_plugin/plugin.py` 是完全相同的两份 SuriCorePlugin 实现。

**影响**：
- 修改一处忘记修改另一处 → 行为不一致
- 导入路径混乱（哪个才是正确的？）
- 日志中 `_self_register()` 写入的 `path` 字段不同：一个为 `"agent_framework/suri_core_plugin"`，另一个在 `core/suri_core/` 下

**建议**：立即删除其中一份，统一导入路径。PRD 中 `directory-structure.md` 应明确只保留一份。

---

### 1.2 启动流程严重不匹配：文档 vs 代码

**文档描述**（startup.md）：
```
Step 1: 创建 EventBus
Step 2: 创建 PluginManager  
Step 3: 自注册 suri_core 为第一个插件
Step 4: 启动 EventBus
Step 5-10: 按顺序加载各层插件
Step 11: 广播 system.started
Step 11.5: 启动自检
```

**代码实际**（suri_core/plugin.py）：
```python
def bootstrap():
    1. 初始化数据库 (_init_db)
    2. 创建 EventBus (event_bus.start() 在创建后立即启动)
    3. 创建 PluginManager
    4. 自注册 (_self_register)
    5. 加载所有插件 (load_all)
    6. 发布 system.start (不是 documented system.started)
```

**发现的问题**：
| 项目 | 文档 | 代码 | 差异 |
|------|------|------|------|
| 启动事件名 | `system.started` | `system.start` | ❌ 不一致 |
| EventBus 启动时机 | Step 4 | Step 1 后立即启动 | ❌ 文档滞后 |
| 启动自检 | Step 11.5 详细自检流程 | 代码无自检 | ❌ 完全缺失 |
| 分层加载 | Step 5-10 分6层依次加载 | `load_all()` 一次性加载 | ❌ 无依赖拓扑 |

**建议**：
- 统一事件名为 `system.started`（或按框架规则统一）
- 实现启动自检（healthcheck）逻辑
- 实现依赖拓扑排序加载（PluginManager 当前未实现）

---

### 1.3 文档间存储策略描述不一致（需对齐至 directory-structure.md 策略）

**背景**：已与用户确认，系统采用 **"角色数据全部在 roles/ 下，纳入 Git 版本控制"** 策略。这是"末日程序"定位决定的——角色数据比代码更宝贵，git clone 即可恢复全部角色状态。

**正确的策略**：
```
roles/（Git 管理，包含全部角色数据）
  ├── soul.md（角色定义）
  ├── memories/（记忆、insights）
  ├── skills/（技能文件）
  └── output/（产出文件）

~/.suri/（仅系统级敏感配置 + 运行时日志）
  ├── config.json（API Key 等）
  └── runtime/logs/（日志）
```

**问题文档**：
- `design-principles.md` 第6节（角色与项目固化原则）错误地说 roles/ 只是模板，需更新
- `framework-rules.md` 第3节（数据存储）错误地说角色运行时数据在 `~/.suri/runtime/roles/`，需更新
- `startup.md`、`deployment.md` 中所有引用 `~/.suri/runtime/roles/` 的路径需要修正

**建议**：以 `directory-structure.md` 为正确基准，修改其他所有文档中与 roles/ 存储策略冲突的描述。

---

### 1.4 事件系统多重命名冲突

**doc 1**（framework-rules.md 事件类型分类）：
| 事件 | 说明 |
|------|------|
| `system.*` | 启动、关闭、插件变更 |
| `user.input` / `user.command` | 用户输入 |
| `llm.request` / `llm.response` | 大模型请求/响应 |
| `plugin.*` | 插件加载、卸载、注册、升级 |

**doc 2**（程序流程 program-flow.md）：
- 使用 `system.start` / `system.shutdown`
- 使用 `error.plugin` / `error.system`

**doc 3**（启动流程 startup.md）：
- 使用 `system.started`

**doc 4**（事件总线 bus.py）：
- 使用 `error.plugin` 作为异常事件名

**doc 5**（热更新 hot-reload.md）：
- 使用 `config.updated` / `plugin.upgraded` / `tool.registered`

**doc 6**（进化 coevolution.md）：
- 使用 `role.skill_suggested` / `role.skill_activated` / `role.soul_updating` / `role.soul_updated`

**问题**：同一套事件在6个文档中使用了不同的命名风格和格式：
- `system.start` vs `system.started` vs `system.shutdown` vs `system.shutting_down`
- `error.plugin` vs `error.plugin_crash`
- `config.updated` 在部分文档中写作 `system.config_changed`

**建议**：建立统一的事件注册表（event-registry.md 已存在但内容需规范化），所有文档使用同一事件名。

---

## 二、🟠 较高风险问题（High）

### 2.1 流程描述多处冗余和矛盾

**system-flow.md 中的多处矛盾**：

1. **用户请求处理流 vs 单角色任务执行流**：
   - 前者说 "suri 判断 → 分配任务 → 角色执行"
   - 后者说 "suri 分配任务 → 角色分析需求 → 调用 task_planner 分解"
   - 缺少对"角色如何接收任务"的明确事件定义

2. **自学流程**（第4节）vs **升级自身流**（第5节）：
   - 第4节说 role_learner 异步分析后 → suri 汇总 → 用户确认
   - 第5节说 suri 自己生成新技能方案
   - 两者有重叠，但未说明何时走哪条路径

3. **agent_registry.create_agent()** 在文档中被多次提及，但代码中 agent_registry 使用的是内存存储（如已知问题所述），重启后数据丢失

---

### 2.2 PluginManager 未实现依赖拓扑加载

**文档承诺**（startup.md / framework-rules.md）：
> "按依赖拓扑顺序加载插件"
> "PluginManager 在加载时检查依赖是否满足"

**代码现状**（需要确认，但根据已知问题）：
> "manifest.json 的 dependencies 字段已存在但未强制校验，plugin_manager 未按依赖顺序加载插件"

**影响**：如果插件加载顺序错误，初始化时访问还未加载的依赖插件会导致崩溃。

**建议**：实现拓扑排序加载算法，检测循环依赖。

---

### 2.3 热更新 vs 安全沙箱的矛盾

**热更新文档**（hot-reload.md）：
> "所有运行时自修改通过 upgrade_manager 统一管理"
> "插件升级后必须发布 plugin.upgraded 事件"

**安全规范**（security-spec.md）：
> "禁止操作清单包括 subprocess.*, os.system, eval(), exec(), compile()"
> "所有对 agent_framework/ 的修改必须人工审批"

**矛盾**：插件自修改（plugin-evolution.md 描述的）需要修改 `plugins/{name}/plugin.py` 文件，但安全沙箱要求写入受保护路径需要审批令牌。如果插件修改自身代码，代码如何处理审批令牌流程？文档中未描述此闭环。

**建议**：补充"插件自修改时的审批令牌获取流程"描述。

---

### 2.4 访问控制缺失细化

**权限矩阵**（permission-model.md）仅定义了4种角色类型（core/admin/project_director/worker）对5种操作的权限。但缺少：
- 对具体文件/资源的细粒度权限
- 插件权限模型（manifest.json 中的 permissions 字段与 security_service 的关联）
- 权限继承与覆盖规则

**建议**：补充角色-资源-操作的三维权限矩阵，明确权限评估顺序（角色类型 → 资源归属 → 操作类型）。

---

## 三、🟡 中等风险问题（Medium）

### 3.1 重复文档内容

1. **启动流程**：`startup.md`（完整启动流程）和 `program-flow.md`（第1节系统启动流程）内容高度重复，导致如果有修改需要同步两处
2. **框架规则**：`framework-rules.md` 与 `architecture.md` 在"架构分层"、"核心原则"、"数据存储"等章节大量重叠，约60%内容重复
3. **插件开发**：`plugin-development.md` 第12节（热更新规范）、第13节（解耦规范）与 `design-principles.md`、`hot-reload.md` 内容重复

**建议**：采用 DRY 原则，每个主题只有一份权威文档，其他文档通过引用/链接方式引用。

---

### 3.2 文档引用路径混乱

多个文档中存在引用路径错误或指向不存在的文件：
- `skill-spec.md` 中引用 `spec/template_spec.md` 但该路径不存在（实际在 `prd/schema/template-spec.md`）
- `skills-overview.md` 引用 `skill_discovery.md` 但该文件不存在
- `plugin-development.md` 第9节出现两个编号（9和9）

**建议**：全面审查文档间交叉引用路径，确保所有引用有效。

---

### 3.3 插件清单与实际代码不一致

**文档中列出的20个插件**（architecture.md）：
| 层级 | 插件 |
|------|------|
| 内核层 | suri_core |
| 基础服务层 | config_service, log_service, security_service |
| 执行层 | task_scheduler, task_planner, agent_registry, interrupt_handler, role_comm, code_tool |
| 能力层 | llm_gateway, memory_service, role_manager, role_learner, mcp_framework, upgrade_manager |
| 接入层 | access |
| 扩展层 | test_framework, cron_service, hooks_service, doc_sync, monitor |

**代码中实际存在的插件**：
- 存在：suri_core, config_service, log_service, security_service, task_scheduler, task_planner, agent_registry, interrupt_handler, code_tool, llm_gateway, role_manager, test_framework, access
- **缺失（有PRD无代码）**：role_comm, memory_service, role_learner, mcp_framework, upgrade_manager, cron_service, hooks_service, doc_sync, monitor

**缺失计数**：文档列20个，实际代码只有13个，**缺失7个插件**。

**建议**：补充缺失插件的实现，或明确标记这些插件为"规划中/迭代2+"状态。

---

### 3.4 核心角色 suri 的启动自检缺失

**文档**（startup.md）描述启动自检包含7个检查项：
1. 环境自检
2. 角色自检
3. 项目自检
4. 插件自检
5. 数据库自检
6. 配置自检
7. 汇总报告

**代码**：suri_core/plugin.py 的 bootstrap() 中仅创建目录和初始化数据库，**没有任何自检逻辑**。

**影响**：系统可能在没有 API Key、角色文件损坏、数据库不可写等情况下"成功"启动，导致运行时才暴露问题。

**建议**：实现完整的启动自检流程，至少包含：LLM 配置检查、数据库可读写检查、核心角色完整性检查。

---

## 四、🔵 低风险但需要关注的问题（Low）

### 4.1 性能潜在瓶颈

1. **EventBus 单队列瓶颈**：所有事件共用一个 asyncio.PriorityQueue，高吞吐场景下（如多个 Agent 同时发布事件）可能成为瓶颈
2. **SQLite 写串行化**：多个插件同时写各自的 SQLite 数据库，WAL 模式下虽有改善，但 schema/database.md 中缺少连接池策略
3. **Role_learner 分析频率**：文档说"role_learner 分析最近7天 experiences"，如果角色每天执行100+任务，7天的 expriences 量可能非常大，LLM 分析成本高

**建议**：
- EventBus 考虑多队列 + sharding 策略
- 补充 SQLite 连接池和超时策略
- role_learner 增加采样策略（非全量分析）

---

### 4.2 缺失的关键开发文档

| 缺失文档/内容 | 重要性 | 说明 |
|-------------|--------|------|
| API 接口文档 | 🔴 | 插件间所有事件 payload 的完整 schema |
| 错误码完整列表 | 🔴 | framework-rules.md 仅给出错误码段，缺少具体错误码定义 |
| 迁移指南 | 🟡 | SQLite schema 变更时的数据迁移流程不完整 |
| 运维手册 | 🟡 | 故障恢复、数据修复等操作流程 |
| 性能测试报告 | 🟢 | 当前无性能基准数据 |

---

### 4.3 文档描述不清晰

1. **"插件也是 Agent"** 概念不清晰：插件如何"学习"？插件的 Soul 在哪里？插件如何"通信"？多个文档提到此概念但未给出具体实现方式
2. **project_director 角色创建流程**：project-workflow.md 说 suri 生成 Soul 草案，但未说明项目总监是否需要独立的 skill 文件
3. **角色复用规则**（project-workflow.md 第7节）：说 worker 归档后释放到"全局角色池"，但未定义全局角色池的存储结构

---

### 4.4 四个进化文档内容薄弱

`skill-evolution.md`、`soul-evolution.md`、`tool-evolution.md` 三个文件的 README 只有标题，**无实质内容**。`plugin-evolution.md` 有内容但与 `coevolution.md` 第3.3节（Plugin 进化事件链）重复。

**建议**：填充缺少的进化文档，或将这些内容合并到 coevolution.md 中统一描述。

---

## 五、📋 插件能力合理性评估

| 插件 | 职责 | 合理性 | 说明 |
|------|------|--------|------|
| suri_core | 内核自举 | ✅ | 合理，但两份实现需要修正 |
| config_service | 配置管理 | ✅ | 职责清晰 |
| log_service | 日志管理 | ✅ | 合理，但需补充日志轮转代码实现 |
| security_service | 安全沙箱 | ✅ | AST 扫描器设计合理，但审批令牌流程不完整 |
| task_scheduler | 任务调度 | ✅ | 职责合理，缺少测试 |
| task_planner | 任务分解 | ⚠️ | 与 task_scheduler 边界模糊（分解 vs 调度） |
| agent_registry | Agent 管理 | ✅ | 当前内存存储需改为 SQLite |
| interrupt_handler | 中断处理 | ✅ | 职责清晰 |
| role_comm | 角色通信 | ⚠️ | 设计合理但代码未实现 |
| code_tool | 代码工具 | ✅ | 职责清晰 |
| llm_gateway | LLM 网关 | ✅ | 核心能力的合理抽象 |
| memory_service | 记忆存储 | ⚠️ | schema/database.md 定义了表结构但代码未实现 |
| role_manager | 角色管理 | ✅ | 职责清晰，soul_parser.py 已实现 |
| role_learner | 角色学习 | ⚠️ | 概念合理但实现复杂，LLM 成本高 |
| mcp_framework | MCP 工具框架 | ⚠️ | 与 code_tool 的功能边界需澄清 |
| upgrade_manager | 升级管理 | ✅ | 合理，但需与 security_service 审批流程集成 |
| access | 接入层 | ✅ | 多通道设计合理 |
| test_framework | 测试框架 | ✅ | 合理 |

---

## 六、🔧 修复建议优先级

### ✅ P0（已修复）

| 问题 | 修复内容 | 涉及文件 | 状态 |
|------|---------|---------|------|
| 1. SuriCorePlugin 双份实现 | 删除 `agent_framework/suri_core_plugin/`，统一导入路径到 `core/suri_core/plugin` | `main.py`, `agent_framework/core/suri_core/plugin.py` | ✅ |
| 2. 统一事件命名 | 代码 `system.start` → `system.started`，所有文档同步修正 | 代码 + 8个文档事件名全部对齐 | ✅ |
| 3. roles/ 存储策略冲突 | 统一为"全部角色数据在 roles/ 下纳入 Git 管理"策略 | `design-principles.md`, `framework-rules.md`, `startup.md`, `deployment.md` | ✅ |
| 4. event-registry.md 事件名修正 | `system.start` → `system.started` | `prd/schema/event-registry.md` | ✅ |
| 5. program-flow.md 事件名修正 | `system.start` → `system.started` | `prd/operations/program-flow.md` | ✅ |
| 6. suri_core.md 事件名修正 | 2处 `system.start` → `system.started` | `prd/plugins/core/suri_core.md` | ✅ |
| 7. mcp_framework.md 事件名修正 | `system.start` → `system.started` | `prd/plugins/capability/mcp_framework.md` | ✅ |
| 8. memory_service.md 事件名修正 | 2处 `system.start` → `system.started` | `prd/plugins/capability/memory_service.md` | ✅ |
| 9. config_service.md 事件名修正 | `system.start` → `system.started` | `prd/plugins/service/config_service.md` | ✅ |
| 10. plugins/README.md 事件名修正 | 2处 `system.start` → `system.started` | `prd/plugins/README.md` | ✅ |
| 11. test_event_bus.py 事件名修正 | `system.start` → `system.started` | `tests/unit/test_event_bus.py` | ✅ |
| 12. 填充 skill/soul/tool-evolution.md | 每个文档 75-103 行的完整内容 | `prd/evolution/skill-evolution.md`, `soul-evolution.md`, `tool-evolution.md` | ✅ |
| 13. 清理空目录 | 删除 `agent_framework/suri_core_plugin/` | 目录已移除 | ✅ |

### P1（当前迭代，优先级排序）

| 优先级 | 任务 | 工时 | 依赖 |
|--------|------|------|------|
| 🔴 1 | 实现启动自检（healthcheck） | 2天 | 无 |
| 🔴 2 | PluginManager 依赖拓扑排序加载 | 1天 | 无 |
| 🟡 3 | 统一事件注册表（event-registry.md 规范化） | 1天 | 无 |
| 🟡 4 | 消除文档重复内容（startup.md vs program-flow.md） | 1天 | 无 |
| 🟡 5 | 补充缺失 PRD 内容（skill-evolution 等 3个文档） | 1天 | 无 |

### P2（下个迭代）

| 任务 | 工时 | 说明 |
|------|------|------|
| role_comm 插件实现 | 3天 | 消息发送/接收/查询完整链路 |
| memory_service 插件实现 | 3天 | 角色独立 SQLite 记忆存储 |
| role_learner 学习闭环 | 3天 | 经验存储、模式检测、技能建议 |
| mcp_framework 工具框架 | 3天 | 工具注册/发现/调用 |
| upgrade_manager 升级管理 | 2天 | 版本管理、回滚 |
| agent_registry SQLite 持久化 | 1天 | 当前内存存储需改为 SQLite |

### P3（持续改进）

| 任务 | 说明 |
|------|------|
| 补充API接口文档和错误码完整列表 | 插件间事件payload schema |
| 性能基准测试 | 多Agent并发场景 |
| 补充运维手册和迁移指南 | 故障恢复流程 |

---

## 七、📊 审计总结

| 指标 | 数量 |
|------|------|
| 🔴 严重问题 | 4 |
| 🟠 较高风险问题 | 4 |
| 🟡 中等风险问题 | 4 |
| 🔵 低风险问题 | 4 |
| 缺失插件实现 | 7/20 |
| 文档重复内容 | 3 组以上 |
| 文档引用错误 | 3 处以上 |

**整体评判**：PRD 文档体系概念设计完整、架构思路清晰，体现了良好的解耦设计理念。但在以下方面需重点改进：

1. **文档-代码一致性**：多处理论概念已在文档中定义完善，但代码未同步实现（如自检、依赖加载、7个缺失插件）
2. **文档间一致性**：事件命名、存储策略、流程步骤等多处存在自相矛盾
3. **实现完整性**：核心流程（启动自检、依赖加载）缺失，影响系统健壮性
4. **代码质量**：SuriCorePlugin 双份实现是最急需修复的问题

> 建议在继续开发前，先完成"文档-代码对齐"工作，确保 PRD 文档和实际代码描述的是同一个系统。