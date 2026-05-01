# Suri 项目 Agent 规则

> 本文件对当前目录及所有子目录的 AI 代码助手具有最高约束力。
> 用户指令 > AGENTS.md 规则 > 通用最佳实践

---

## 绝对规则（不可违反）

### 1. 代码变更必须同步更新文档

**任何对代码的修改（新增、删除、重构、接口变更、行为变更），完成后必须立即检查并更新相关文档。**

这包括：
- 模块级 `.md` 文件（如 `model/model.md`, `core/core.md`）
- `wiki/` 目录下的架构/配置文档
- `README.md` / `AGENTS.md` 本身（如果规则需要调整）
- 代码内的 docstring / 注释（如果接口签名变更）

**不更新文档的代码提交视为不完整。**

### 2. 测试同步强制规则（不可违反）

**任何新功能实现或 Bug 修复，必须同时创建或更新对应的测试用例。**

这包括：
- **新功能**：新增功能代码的同时，必须在 `suri-agent/tests/` 下新增覆盖该功能的测试
- **Bug 修复**：修复 Bug 的同时，必须新增回归测试（regression test），确保同一 Bug 不会再次发生
- **接口变更**：修改公共 API 签名或行为时，必须同步更新所有调用该 API 的测试
- **测试文件**本身的策略或结构变更，需同步更新 `tests/README.md`

**未配套测试的代码提交视为不完整。**

### 2.1 回归测试要求

对于 Bug 修复，回归测试必须：
1. 在修复**前**能够复现该 Bug（即测试会因该 Bug 失败）
2. 在修复**后**通过（即验证修复有效）
3. 测试文件名建议包含 `regression` 或按模块分类放入 `tests/unit/`、`tests/fullforce/`

### 3. 新增代码文件必须同步创建/更新文档

当新增一个**核心代码文件**（位于 `suri-agent/` 下，非测试、非缓存）时：

1. 如果该文件属于已有模块目录（如 `suri-agent/core/`），必须在模块级 `.md` 文档中新增该文件的说明（功能描述、关键类/函数、使用示例）
2. 代码文件头部的 docstring 必须包含 `关联文档: <文档路径>`
3. 如果该文件引入了新概念或新架构，必须在 `wiki/` 或根目录文档中补充架构说明

### 3.1 文档是双向约束

文档变更（如需求调整、接口设计变更）同样必须同步更新代码。禁止出现"文档已改、代码未动"或"代码已改、文档未动"的状态。

### 4. 文档是代码的需求来源

文档不是事后装饰，而是代码的**需求规格说明书**。修改代码前，优先读取相关文档理解设计意图；修改代码后，确保文档与实际行为一致。

### 5. 建立反向索引

每个核心模块的 `.md` 文档必须在开头标注关联代码文件，每个核心代码文件必须在模块 docstring 中标注关联文档路径。

### 6. 角色目录管理规则（不可违反）

**`group/` 是部门空间，一级目录 = 部门，二级目录 = 角色。**

```
group/
├── <dept>/                    # 部门
│   ├── <dept>.md              # 部门说明（部门负责人维护）
│   ├── <role_1>/              # 角色
│   │   ├── <role_1>.md        # Soul 文件（suri_hr 管理）
│   │   ├── memories/          # 记忆（角色维护）
│   │   ├── skills/            # 技能（角色自建）
│   │   ├── scripts/           # 脚本（角色自建）
│   │   ├── reference/         # 参考资料（角色维护）
│   │   └── output/            # 输出文件（角色维护）
│   └── <role_2>/
└── <dept_2>/
```

#### 6.1 目录层级规则

- `group/` 下的一级目录 = **部门**（如 `central/`）
- `group/<dept>/` 下的二级目录 = **角色**（如 `suri/`、`suri_dev/`）
- `group/<dept>/<dept>.md` = 部门说明文件
- 每个角色的目录名 **必须等于** 其 `role_id`
- 别名（如 `suri-dev` → `suri_dev`）是逻辑映射，**不允许创建对应的物理目录**

#### 6.2 Canonical 目录唯一性

- 所有基础设施代码（`MemoryService`、文件操作等）必须通过 `ConfigService.resolve_role_id()` 将别名解析为 canonical id 后再操作文件系统

#### 6.3 角色重构/重命名迁移流程

当需要重命名角色或重构目录结构时，必须按以下顺序执行：

1. **创建新目录**：创建 canonical 目录（如 `group/central/suri_dev/`），放入 Soul 文件
2. **迁移数据**：将旧目录中的 `memories/`、`skills/`、`reference/` 等数据复制到新目录
3. **更新硬编码路径**：搜索项目中所有硬编码的旧目录路径（如 `group/central/suri-dev/`），替换为新路径
4. **添加别名映射**：在 `ConfigService._ROLE_ALIASES` 中添加旧名 → 新名的映射
5. **验证测试**：确保 `test_role_directory_integrity.py` 通过（目录数 = 角色数，无遗留别名目录）
6. **删除旧目录**：确认数据已迁移且测试通过后，删除旧目录
7. **更新文档**：在 `AGENTS.md` 事件记录中标注迁移日志

**禁止在旧目录未清理的情况下声明迁移完成。**

#### 6.4 目录一致性监控

- 每次涉及角色变更的代码提交前，必须运行 `test_role_directory_integrity.py`
- `group/central/` 下的子目录数必须等于 `list_roles(include_aliases=False)` 返回的角色数
- 发现 `analyst/`、`document-review/`、`suri-dev/`、`suri-hr/` 等旧格式目录应立即清理

### 7. 空间分离规则（不可违反）

**`group/`（角色空间）与 `suri-agent/`（主程序空间）必须严格分离。**

#### 7.1 空间边界

| 空间 | 内容 | 写入者 |
|------|------|--------|
| `group/` | 角色 Soul、技能、记忆、资源 | 各角色自身 / suri_hr（管理） |
| `suri-agent/` | 核心代码、工具、规则、基础设施 | suri_dev（维护者） |
| `resources/` | 共享资源、会话、缓存、日志 | 平台统一管理 |
| `wiki/` | 架构文档、配置说明 | 所有角色（文档同步规则） |

#### 7.2 禁止行为

- **严禁**在 `suri-agent/` 下创建 `group/` 子目录或任何角色数据
- **严禁**在 `group/` 下创建 `suri-agent/` 子目录或任何主程序代码
- **严禁**角色直接修改 `suri-agent/` 下的代码（除非该角色类型为 maintainer 且通过 SecurityService 授权）
- **严禁**主程序代码直接写入 `group/<role>/`（除非通过 MemoryService 等基础设施代理）

#### 7.3 角色数据边界

- 每个角色只能修改自己的 `group/<department>/<role_id>/` 目录下的内容
- `suri_hr`（admin 类型）可以管理所有 `group/` 下的路径（角色创建、部门调整、技能模板更新）
- `suri_dev`（maintainer 类型）管理 `suri-agent/` 下的代码，无权直接修改角色 Soul 文件

#### 7.4 防止路径计算错误

- **严禁**出现同名目录嵌套（如 `suri-agent/suri-agent/`、`group/group/`）
- 所有涉及 `mkdir -p`、路径拼接、相对路径解析的代码必须经过 `test_space_separation.py` 验证
- 发现嵌套目录立即删除并追溯产生原因

### 9. 资源管理规则

**`resources/` 是平台资源空间，按生命周期和资源类型分类管理。**

#### 9.1 资源目录结构

```
resources/
├── temp/              # 短期临时资源（可自动清理）
├── cache/             # 缓存资源
├── sessions/          # 会话数据
├── uploads/           # 用户上传（长期）
├── exports/           # 角色导出成果（长期）
└── archives/          # 归档资源
```

#### 9.2 资源类型归属

| 目录 | 生命周期 | 管理角色 | 说明 |
|------|---------|---------|------|
| `temp/` | 短期 | file_admin | 临时文件，可定期清理 |
| `cache/` | 短期 | file_admin | 缓存数据 |
| `sessions/` | 会话级 | scheduler | 用户会话持久化 |
| `uploads/` | 长期 | file_admin | 用户上传的文件 |
| `exports/` | 长期 | file_admin | 角色导出的成果文件 |
| `archives/` | 长期 | file_admin | 归档的历史数据 |

#### 9.3 角色输出路径

- 角色 Soul 中 `output_path` 应优先使用角色自有目录（`group/<role>/output/`）
- 若需写入 `resources/`，必须通过 FileService 并遵守所有权规则

### 10. 工具、技能与脚本的定义与边界

#### 10.1 工具（Tool）— 通用基础设施

- **归属**：平台公共，由 `suri_dev`（maintainer）维护
- **位置**：`suri-agent/tools/<tool_id>/`
- **用途**：所有角色均可调用的通用能力（文件读写、数据库查询、网络请求、Shell 执行等）
- **管理**：`suri_dev` 负责工具的开发、维护、版本升级
- **调用**：角色通过 `ToolService` 调用工具，受 `tools:` 白名单权限控制

#### 10.2 技能（Skill）— 角色专属能力

- **归属**：角色私有，由角色自身维护
- **位置**：`group/<dept>/<role>/skills/<skill_id>/`
- **用途**：角色专属的能力模块，可调用工具来完成特定任务
- **内容**：`skill.md`（定义）+ 可选的 `script.py` + `resources/`
- **调用**：角色在执行任务时，根据需求匹配自身技能，调用技能中定义的流程和脚本
- **同步**：新技能创建后上报 `suri_hr`，同步到 `group_function.md` 能力清单

**工具 vs 技能的核心区别：**
| | Tool | Skill |
|--|------|-------|
| 归属 | 平台公共 | 角色私有 |
| 维护者 | `suri_dev` | 角色自身 |
| 位置 | `suri-agent/tools/` | `group/<role>/skills/` |
| 调用范围 | 所有有权限的角色 | 仅所属角色 |
| 内容 | 通用函数/接口 | 业务流程 + 脚本 + 资源 |

#### 10.3 脚本（Script）— 角色自编程资产

- **归属**：角色私有，由角色自身维护
- **位置**：`group/<dept>/<role>/scripts/`
- **用途**：角色为技能编写的可执行脚本，加速能力覆盖
- **规范**：版本记录、功能说明、触发条件等元数据（通过 `skill.md` 关联）

#### 10.4 技能管理流程

1. 角色在自身 `skills/` 下创建技能
2. 技能优先调用统一工具库中的现有工具来兑现
3. 无现成工具时，提醒 `suri_dev` 进行工具开发（MCP 或独立工具）
4. 涉及外部调用、文件写入、网络访问的技能需用户授权
5. 新技能信息上报 `suri_hr`，同步到能力清单
6. 安全敏感技能需 `suri_review` 审核

### 11. 角色自治与 Soul 文件保护

#### 11.1 角色自治范围

- 每个角色**全权维护** `group/<dept>/<role>/` 下的所有内容（除 Soul 文件外）
- 角色可自由创建、修改、删除自己的 memories、skills、scripts、reference、output
- 角色之间**不可**互相修改对方的文件夹

#### 11.2 Soul 文件专属保护

- **Soul 文件**（`group/<dept>/<role>/<role>.md`）由 **suri_hr（admin）专属管理**
- 其他角色（包括角色自己）**无权**修改自己的 Soul 文件
- 修改 Soul 文件必须通过 suri_hr 审批流程
- 核心角色的 Soul 文件在 SecurityService 中额外保护，任何非 admin 操作直接拒绝

### 8. 技能管理规则（不可违反）

**角色的技能是角色能力的延伸，受角色自主管理和 suri_hr 监督。**

#### 8.1 技能创建流程

1. **角色发起**：角色在自身 `skills/` 目录下创建技能文件夹和说明文档
2. **用户同意**：涉及外部调用、文件系统操作、网络访问的技能，必须获得用户明确授权
3. **上报 hr**：角色将新技能信息（技能 ID、功能描述、脚本路径、权限需求）上报 suri_hr
4. **hr 同步**：suri_hr 更新 `group_function.md` 和角色能力清单，确保调度系统知晓新技能
5. **document-review 审核**：涉及安全敏感操作（文件写入、命令执行、网络请求）的技能需审核

#### 8.2 技能目录结构

```
group/<dept>/<role_id>/
├── skills/
│   ├── skills.md              # 技能索引（由角色维护）
│   └── <skill_id>/
│       ├── skill.md           # 技能定义（YAML frontmatter + 说明）
│       ├── script.py          # 技能脚本（可选）
│       └── resources/         # 技能资源（可选）
```

#### 8.3 技能迁移要求

- 角色重命名/重构时，`skills/` 目录必须作为**首要迁移项**同步迁移到新目录
- 技能索引 `skills.md` 中的 `owner` 字段必须同步更新为 canonical role_id
- 技能脚本中硬编码的路径必须同步更新

#### 8.4 全局技能目录（已弃用）

根目录 `skills/` 在 `ba94b9c` 重构中已废弃，所有技能收归角色私有。禁止恢复根目录 `skills/`。

---

## 执行机制

每次完成代码改动后，必须按以下检查清单执行文档同步：

```
.kimi/checklists/doc-sync.md
```

如果检查清单中的任何一项为"是"，则必须更新对应文档。

---

## 事件记录

- 2026-05-01: 建立文档同步强制规则（因用户提醒后补文档， unacceptable）
- 2026-05-01: 多角色并行调度架构升级 — `_detect_dispatch_target()` 返回 `List[str]`，`suri_process()` 支持多角色依次调度 + `_summarize_multi_result()` 统一汇总
- 2026-05-01: 安全服务修复 — `pre_file_change_check()` 豁免路径优先于权限检查，修复 resources/temp/ 等临时目录被误拦截
- 2026-05-01: 本地服务测试覆盖（20/20 通过）：日志服务、安全服务、文件系统服务
- 2026-05-01: 测试角色清理 — 删除 qa-tester、data-analyst、content-writer 及对应部门目录
- 2026-05-01: 文件所有权规则修复 — `can_modify()` 中 `suri-hr` 对 `group/` 的权限检查优先级提升至 `role_self` 之前，`role_self` 逻辑支持 `group/<dept>/<role>/` 路径格式
- 2026-05-01: 工具文档修复 — 为 model_manager、web_fetch 补全 YAML frontmatter，ConfigService 正确索引全部 11 个工具
- 2026-05-01: **1000轮记忆系统压力测试通过**（48/48 全通过）— 修复消息ID冲突、JSON解析异常处理、数据库连接管理、insight触发计数、suri硬编码提示
- 2026-05-01: **多用户并发隔离** — SQLite WAL 模式、session 级消息过滤、`suri_process(user_id)` 支持、`_get_or_create_session()` 自动会话管理、上下文按 session 隔离
- 2026-05-01: **性能优化** — `_get_rule_summary()` 缓存加速 4.1x、`list_role_memories()` 按时间排序
- 2026-05-01: **V3.0 多 Agent 任务管理架构**：TaskPlan + TaskStateService + AgentRegistry + StateCardRenderer + DepartmentRegistry + MessageBus + InterruptHandler，从"单次函数调用"升级为"长期任务管理器"
- 2026-05-01: **V3.0 集成测试**：46 项测试全部通过（44 passed, 2 skipped），覆盖角色标识、昵称、消息流、状态卡片、Agent 并行、部门扩展、核心保护、权限控制、经验日志
- 2026-05-01: **V3.0 代码修复**：agent_id/task_id 添加随机熵避免冲突，MemoryService LIKE 查询格式修复，原有测试回归修复（5/5 通过）
- 2026-05-01: **文档同步**：core.md / output.md / tui.md / infrastructure.md / AGENTS.md 全部更新，7 个新增代码文件 docstring 已标注关联文档路径
- 2026-05-01: **测试框架重构**：建立 unit/ + fullforce/ 子目录，4 个 framework/ 基础设施文件（base.py/fixtures.py/utils.py/conftest.py），run.py 统一入口自动发现 pytest/script 格式，17 项测试全部归位
- 2026-05-01: **cli.py 导入修复**：补充 `typing.Dict` 缺失导入，解决 V3.0 模块无法加载问题
- 2026-05-01: **代码变更自动刷新**：`suri_process()` 任务完成后自动检测 `_check_code_change()`，若核心代码变更则自动调用 `_perform_reload()`（os.execv 热重载），无需用户手动 /reload
- 2026-05-01: **100次角色能力测试** — 103/105 通过（98.1%），关键词覆盖从 9/5/5 扩展至 21/11/14
- 2026-05-01: **角色目录清理与别名解析修复**：清理 `group/central/` 下 4 个遗留别名目录，修复 `MemoryService._get_role_dir()` 未解析别名导致数据写入旧目录的 Bug，新增 `test_role_directory_integrity.py`（5 项）
- 2026-05-01: **空间分离与技能恢复**：删除错误的 `suri-agent/group/`，恢复 `suri_hr/skills/` 模板库，建立 AGENTS.md 规则 #7「空间分离」和 #8「技能管理」，新增 `test_space_separation.py`（5 项）
- 2026-05-01: **创建流程基础设施补全**：动态部门匹配（从角色 Soul 推导 keywords）、DepartmentRegistry 自动扫描 `group/` 目录、技能内容解析（`get_skill_detail()`）、工具参数校验（`validate_params()`）、6 个工具补全代码（file_read/write/list, shell_exec, db_query/insert）
- 2026-05-01: **Agent 计划步骤执行**：`_execute_step()` 按步骤逐个调用模型、更新状态、保存结果；`_execute_dispatch()` 过滤角色步骤并顺序执行；`TaskStep` 新增 `depends_on`/`result` 字段；`task_plan.py` 生成步骤时自动添加线性依赖；新增 `test_agent_plan_execution.py`（6 项）
- 2026-05-01: **用户确认机制（CreationDialog）**：`suri_process()` 添加三个检查点（部门匹配→角色匹配→技能匹配），任一缺失触发多轮对话；`run()` 主循环支持创建对话模式；`CreationDialog` 状态机管理 3 种创建流程（部门/角色/技能）；`_execute_creation()` 实际写入目录和文件；新增 `test_creation_dialog.py`（8 项）
