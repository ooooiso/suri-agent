# Suri-Agent 可执行开发计划

> **依据**：开发规则框架（framework-rules.md）+ 架构设计原则（design-principles.md）+ 目录结构规范（directory-structure.md）
> **上下游对齐**：所有 PRD 文档已交叉审计并修复 P0 级不一致
> **总工时估算**：~21 开发日（P1 6天 + P2 15天）

---

## 一、开发规则总纲

### 1.1 架构约束

| 约束 | 规则说明 | 来源 |
|------|---------|------|
| 角色数据全在 `roles/`（Git管理） | 角色Soul/记忆/技能/产出全部在Git仓库内 | directory-structure.md, design-principles.md §6 |
| 系统配置在 `~/.suri/` | 仅存放API Key等敏感配置和运行时日志 | directory-structure.md |
| 插件被动不主动决策 | 插件只响应事件或角色调用，不主动决策 | framework-rules.md §1, plugins/README.md |
| 通信全走EventBus | 所有实体仅通过事件总线通信，禁止直接方法调用 | framework-rules.md §6 |
| 启动事件名统一 `system.started` | 代码 + 8个文档已全部对齐 | 本次审计修复 |
| 四维协同进化 | Skill/Soul/Plugin/Tool独立进化→事件广播→相关方响应 | coevolution.md |

### 1.2 核心流程序列

```
启动流程（startup.md） → 用户请求处理流（system-flow.md §1） → 
单角色任务执行流（system-flow.md §2） → 异常处理流（system-flow.md §6） → 
角色自学自增技能流（system-flow.md §4） → suri升级自身流（system-flow.md §5）
```

### 1.3 增量开发策略

每个迭代完成后运行 `python -m pytest tests/ -v` 确保已有测试不失败。

---

## 二、P1 当前迭代（6 天）— 代码-文档对齐 + 核心缺失功能

### 第1步：实现启动自检（healthcheck）— 2天

**对齐规则**：
- `startup.md` §4 定义了7项自检：环境自检、角色自检、项目自检、插件自检、数据库自检、配置自检、汇总报告
- `suri_core/plugin.py` 当前 `bootstrap()` 中缺少自检逻辑
- `framework-rules.md` §9 安全沙箱要求在动态加载前进行静态扫描

**实现交付**：
```
agent_framework/core/suri_core/plugin.py
  ├── def _healthcheck(self) → 执行7项自检
  ├── def _check_environment(self) → 目录完整性检查
  ├── def _check_role(self) → suri角色完整性检查
  ├── def _check_database(self) → SQLite可读写 + schema版本校验
  ├── def _check_config(self) → LLM配置/通道配置检查
  └── def _check_plugins(self) → 核心插件就绪状态
```

**测试**：`tests/unit/test_event_bus.py` 追加 healthcheck 相关断言

**验收标准**：
- [x] `bootstrap()` 最后一步执行 `_healthcheck()`
- [x] 自检通过后广播 `system.started`
- [x] 配置缺失时生成警告日志但不阻塞启动
- [x] suri角色文件缺失时自动从模板创建
- [x] 已有测试全部通过

---

### 第2步：PluginManager 依赖拓扑排序加载 — 1.5天

**对齐规则**：
- `startup.md` §3 定义了分层加载顺序（7层顺序依赖）
- `framework-rules.md` §5 生命周期中"按依赖顺序加载"是必须行为
- `plugins/README.md` 插件依赖图已明确定义上下游关系
- `agent_framework/plugin_manager/manager.py` 当前 `load_all()` 未实现拓扑排序

**实现交付**：
```
agent_framework/plugin_manager/manager.py
  ├── def _resolve_load_order(manifest_deps) → 拓扑排序算法
  ├── def _detect_cycle(deps_dict) → 循环依赖检测
  └── load_all() 改为按拓扑序加载
```

**测试**：
- `tests/unit/test_plugin_manager.py` 追加拓扑排序单元测试
- 测试循环依赖检测 → 抛出 `PluginDependencyCycleError`

**验收标准**：
- [x] `load_all()` 按 manifest.json dependencies 确定加载顺序
- [x] 循环依赖检测有效，抛出明确异常
- [x] 缺失依赖插件跳过加载并记录 warning
- [x] 已有测试全部通过

---

### 第3步：统一事件注册表规范 — 1天

**对齐规则**：
- `coevolution.md` §7 规定"变更后必须广播事件"
- `event-registry.md` 文档已存在但内容需规范化
- 当前6个文档中使用不同事件命名风格（已修复 `system.start` → `system.started`）

**实现交付**：
```
prd/schema/event-registry.md
  └── 完整规范：事件名 / 发布者 / 订阅者 / Payload Schema / 触发条件

检查清单（确保所有事件名在代码中真实存在）：
  ├── system.started, system.shutdown, system.config_changed
  ├── user.input, user.command
  ├── llm.request, llm.response, llm.error
  ├── tool.call, tool.result, error.tool
  ├── task.* (8个)
  ├── agent.* (4个)
  ├── role.* (6个)
  ├── plugin.* (2个)
  ├── interrupt.* (2个)
  └── upgrade.* (6个)
```

**与代码对齐**：
- `shared/utils/event_types.py` 中 EventType 枚举对齐事件注册表
- 代码缺失的事件类型定义补充到 `event_types.py`

**验收标准**：
- [x] event-registry.md 与 event_types.py 完全对齐
- [x] 每个事件有明确的 Payload Schema
- [x] 无冗余/未使用的事件定义

---

### 第4步：消除文档重复 — 0.5天

**对齐规则**：
- DRY 原则：每个主题只有一份权威文档
- 当前重复组：startup.md vs program-flow.md, framework-rules.md vs architecture.md

**实现交付**：
- **startup.md** = 唯一启动流程权威文档
- **program-flow.md** 第1节改为引用 startup.md（`见 startup.md §2-4`），自身只保留术语定义
- **architecture.md** 和 **framework-rules.md**：删除或合并重叠的架构分层、核心原则、数据存储章节

**验收标准**：
- [x] startup.md vs program-flow.md 启动描述无重复
- [x] architecture.md vs framework-rules.md 内容无重复（<30% 重合度）

---

### 第5步：填充 skill/soul/tool-evolution.md 已有内容 — 0.5天

**当前状态**：已填充（本次审计已补充内容）
- skill-evolution.md（75行）— 触发条件、生成流程、版本管理、生命周期
- soul-evolution.md（81行）— 触发条件、进化流程、影响评估、版本回滚
- tool-evolution.md（103行）— 工具定义、版本管理、注册/废弃流程、发现机制、与code_tool边界确认

**验收标准**：无需额外工作 ✅

---

### 第6步：补充缺失的文档引用修复 — 0.5天

**对齐规则**：
- 当前 3 处文档引用路径错误（skill-spec.md → template-spec.md 等）

**实现交付**：
- 检查所有 `.md` 文件的交叉引用，修复失效路径
- 使用 `grep -rn "prd/" --include="*.md" . | grep -E "\[.*\]\(.*\)"` 扫描引用

**验收标准**：
- [x] 所有文档间引用路径有效
- [x] 无指向不存在的文件的引用

---

## 三、P2 下个迭代（15 天）— 缺失插件实现

### 第7步：role_comm 插件实现 — 3天

**对齐规则**：
- `system-flow.md` §7 多角色协作流依赖 role_comm
- `coevolution.md` 四维协同进化中 Skill/Soul 变更需通知其他角色
- `plugins/README.md` 依赖图中 role_comm 被所有角色使用

**实现交付**：
```
plugins/role_comm/
  ├── __init__.py
  ├── manifest.json
  ├── plugin.py        # 消息发送/接收/查询/广播完整链路
  └── store.py         # SQLite 持久化队列
```

**接口**：`role.message` / `role.message_received` / `role.messages_query` / `role.messages_consume` 事件

**测试**：
- `tests/plugin/test_role_comm.py`
- 多角色消息发送-接收-确认完整链路

---

### 第8步：memory_service 插件实现 — 3天

**对齐规则**：
- `directory-structure.md` roles/{role_id}/memories/role.db 是角色级SQLite
- `schema/database.md` 定义了完整的表结构
- `system-flow.md` §4 角色学习需要读写记忆

**实现交付**：
```
plugins/memory_service/
  ├── __init__.py
  ├── manifest.json
  ├── plugin.py        # 事实/经验/模式存储CRUD + 洞察管理
  └── store.py         # SQLite WAL模式封装
```

**订阅**：`system.started` → 初始化所有角色的数据库表
**接口**：get_messages / get_insights / get_facts / set_fact / store_experience / add_insight

**测试**：
- `tests/plugin/test_memory_service.py`
- 角色隔离测试（禁止跨角色读写）
- 路径注入防护测试

---

### 第9步：agent_registry SQLite 持久化 — 1天

**对齐规则**：
- 当前 agent_registry 使用内存存储，重启后数据丢失
- `system-flow.md` §2 单角色任务执行流依赖 agent_registry.create_agent()

**实现交付**：
```
plugins/agent_registry/plugin.py
  └── 原有内存存储改为 SQLite 持久化
      ├── agents 表 CRUD
      ├── agent_steps 表追加记录
      └── 启动时恢复所有 Agent 状态
```

**测试**：
- 重启后 Agent 状态正确恢复
- 内存→SQLite 数据迁移正确

---

### 第10步：role_learner + upgrade_manager 插件实现 — 5天

**对齐规则**：
- `system-flow.md` §4 角色自学流程定义完整
- `system-flow.md` §9 自优化上报流定义完整
- `coevolution.md` §3.1 Skill 进化事件链定义完整
- `coevolution.md` §6 版本管理策略（可追溯可回滚）

**实现交付**：
```
plugins/role_learner/
  ├── __init__.py
  ├── manifest.json
  ├── plugin.py        # 异步学习引擎：经验分析→LLM生成洞察→技能模式检测
  └── learner.py       # 采样策略（非全量分析，减少LLM成本）

plugins/upgrade_manager/
  ├── __init__.py
  ├── manifest.json
  ├── plugin.py        # 升级报告状态机 + 版本回滚
  └── store.py         # SQLite 持久化升级报告
```

**测试**：
- role_learner：经验采样/模式检测/洞察生成闭环
- upgrade_manager：报告创建→审批→实施→回滚全流程

---

### 第11步：mcp_framework + cron_service + hooks_service + doc_sync 实现 — 3天

**对齐规则**：
- `coevolution.md` §3.4 Tool 进化事件链定义完整
- `plugins/README.md` 依赖图定义清晰
- Plugin 与 Tool 边界：code_tool 处理文件操作，mcp_framework 处理外部工具

**实现交付**：
```
plugins/mcp_framework/
  ├── __init__.py
  ├── manifest.json
  ├── plugin.py        # 工具注册/发现/调用/废弃
  ├── registry.py      # 工具注册表（SQLite持久化）
  └── services/        # 内置工具（filesystem/shell_exec/web_search）

plugins/cron_service/
  ├── __init__.py
  ├── manifest.json
  └── plugin.py        # 定时触发 cron.* 事件

plugins/hooks_service/
  ├── __init__.py
  ├── manifest.json
  └── plugin.py        # 文件变更事件钩子

plugins/doc_sync/
  ├── __init__.py
  ├── manifest.json
  └── plugin.py        # 文档同步/代码变更监控
```

**测试**：
- mcp_framework：工具注册→发现→调用→废弃全流程
- cron_service：定时触发准确度测试
- hooks_service：文件变更→事件触发→响应闭环
- doc_sync：代码变更→文档更新建议生成

---

## 四、P3 持续改进（无严格工时）

| 任务 | 说明 | 对齐规则 |
|------|------|---------|
| 补充API接口文档和错误码完整列表 | 插件间事件payload schema + 错误码定义 | framework-rules.md §7 错误码规范 |
| 性能基准测试 | 多Agent并发场景：EventBus吞吐、SQLite并发、LLM请求排队 | AUDIT-REPORT.md §4.1 |
| 补充运维手册和迁移指南 | 故障恢复、数据修复、版本迁移 | 缺失关键文档 |
| 细化权限模型 | 角色-资源-操作三维权限矩阵 | permission-model.md 缺少细节 |
| 插件自修改审批令牌闭环 | 热更新 vs 安全沙箱的矛盾描述 | AUDIT-REPORT.md §2.3 |

---

## 五、迭代验收标准

### 每次迭代完成后检查清单

```bash
# 1. 测试覆盖
python -m pytest tests/ -v --tb=short
# 预期：全部通过，无新失败

# 2. 事件命名一致性
grep -rn "system\.start[^e]" --include="*.py" --include="*.md" . | 
  grep -v "system\.started" | grep -v "\.git"
# 预期：空输出（无残留）

# 3. 角色数据路径一致性
grep -rn "runtime/roles" --include="*.md" . | grep -v "\.git" | grep -v "AUDIT-REPORT"
# 预期：空输出（全部改为 roles/）

# 4. 代码可运行
python main.py --help 2>&1 || echo "not yet" 
# 预期：至少不报 import 错误
```

---

## 六、依赖关系图

```
P1-1 启动自检 ←── P1-2 依赖拓扑加载
  │                    │
  └─── 都需要 ────────┘
        │
        ▼
P1-3 事件注册表规范（基于已修复的事件名）
        │
        ▼
P1-4 消除文档重复 + P1-5 进化文档（已完成） + P1-6 修复引用
        │
        ▼
P2-7 role_comm ──→ P2-8 memory_service
  │                      │
  │                      ▼
  │              P2-9 agent_registry SQLite
  │                      │
  └────── P2-10 ────────┘
    role_learner + upgrade_manager
          │
          ▼
   P2-11 mcp_framework + cron/hooks/doc_sync
          │
          ▼
        P3 持续改进
```

> **关键路径**：P1-1 → P1-2 → P1-3 → P2-7 → P2-8 → P2-9 → P2-10 → P2-11
> **并行可执行**：P1-4、P1-5（已完成）、P1-6 可与 P1-1、P1-2 并行