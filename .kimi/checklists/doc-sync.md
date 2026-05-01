# 文档同步检查清单

> 每次代码变更完成后，逐项检查。任何一项为"是"，必须同步更新对应文档。
> 检查完成后，在变更摘要中标注 `[文档已同步]`。

---

## 模块级变更检查

### 接口变更
- [ ] 是否新增/删除/重命名了公共函数或类？
- [ ] 是否修改了函数签名（参数、返回值、类型注解）？
- [ ] 是否修改了配置文件结构（新增/删除/重命名字段）？

**若勾选 → 更新模块 `.md` 文档中的 API/配置说明**

### 行为变更
- [ ] 是否改变了现有功能的执行逻辑或输出格式？
- [ ] 是否新增或修改了错误处理/降级/重试策略？
- [ ] 是否改变了数据结构或状态机流转？

**若勾选 → 更新模块 `.md` 文档中的功能说明和流程图**

### 新增功能
- [ ] 是否新增了模块、子系统或功能点？
- [ ] 是否新增了配置项、环境变量或 CLI 命令？
- [ ] 是否新增了核心代码文件（`.py` 文件位于 `suri-agent/` 下）？

**若勾选 → 在模块 `.md` 中新增功能章节，在事件记录中标注；新增文件需在 docstring 中标注关联文档路径**

---

## 架构级变更检查

- [ ] 是否新增/删除了模块目录？
- [ ] 是否改变了模块间的依赖关系或调用链？
- [ ] 是否新增/修改了外部集成（API、数据库、消息队列）？

**若勾选 → 更新 `wiki/` 下对应架构文档，必要时更新根目录 `AGENTS.md`**

---

## 测试同步检查（强制）

> 规则来源: `AGENTS.md` 绝对规则 #2

### 新功能
- [ ] 是否实现了新功能或新增子系统？

**若勾选 → 必须在 `suri-agent/tests/` 下新增覆盖该功能的测试用例**

### Bug 修复
- [ ] 是否修复了 Bug 或处理了边界情况？

**若勾选 → 必须新增回归测试（regression test），确保同一 Bug 不会再次发生**
- 回归测试要求：修复前测试应失败（复现 Bug），修复后测试应通过（验证修复）
- 测试文件名建议包含 `regression` 或按模块分类放入 `tests/unit/`、`tests/fullforce/`

### 接口变更
- [ ] 是否修改了公共 API 签名或行为？

**若勾选 → 必须同步更新所有调用该 API 的测试用例**

### 测试基础设施变更
- [ ] 是否新增/修改了测试框架、fixtures 或共享工具？

**若勾选 → 同步更新 `tests/README.md` 或相关模块文档中的测试说明**

---

## 角色目录完整性检查（强制）

> 规则来源: `AGENTS.md` 绝对规则 #6

- [ ] 是否新增/删除/重命名了角色？
- [ ] 是否修改了 `ConfigService._ROLE_ALIASES` 或角色解析逻辑？
- [ ] 是否修改了 `group/` 下的目录结构？

**若任一勾选 → 必须执行以下检查：**
1. 运行 `python -m pytest suri-agent/tests/unit/test_role_directory_integrity.py -v`
2. 确认 `group/central/` 下子目录数 = `list_roles(include_aliases=False)` 返回的角色数
3. 确认不存在 `analyst/`、`document-review/`、`suri-dev/`、`suri-hr/` 等遗留别名目录
4. 确认 `MemoryService._get_role_dir()` 对别名返回 canonical 目录

---

## 空间分离检查（强制）

> 规则来源: `AGENTS.md` 绝对规则 #7

- [ ] 是否新增/修改了 `group/` 或 `suri-agent/` 下的目录？
- [ ] 是否涉及角色数据或主程序代码的位置变更？

**若任一勾选 → 必须执行以下检查：**
1. 运行 `python -m pytest suri-agent/tests/unit/test_space_separation.py -v`
2. 确认 `suri-agent/` 下不存在 `group/` 子目录
3. 确认 `group/` 下不存在 `.py` 文件或 `suri-agent/` 子目录
4. 确认角色工作目录只在 `group/` 下

---

## 技能管理检查（强制）

> 规则来源: `AGENTS.md` 绝对规则 #8

- [ ] 是否新增/删除/修改了角色技能？
- [ ] 是否进行了角色迁移或重命名？

**若任一勾选 → 必须执行以下检查：**
1. 确认 `group/<dept>/<role>/skills/` 目录结构完整
2. 若角色迁移：确认 `skills/` 数据已同步迁移到 canonical 目录
3. 确认 `skills.md` 中的 `owner` 字段已更新为 canonical role_id

---

## 快速定位关联文档

| 代码路径 | 关联文档 |
|----------|----------|
| `suri-agent/model/` | `suri-agent/model/model.md`, `wiki/models/model_pool.md` |
| `suri-agent/core/` | `suri-agent/core/core.md` |
| `suri-agent/core/task_plan.py` | `suri-agent/core/core.md` § 任务规划器 |
| `suri-agent/core/task_state.py` | `suri-agent/core/core.md` § 任务状态中心 |
| `suri-agent/core/agent_registry.py` | `suri-agent/core/core.md` § Agent 注册表 |
| `suri-agent/core/state_card.py` | `suri-agent/core/core.md` § 状态卡片渲染器 |
| `suri-agent/core/department_registry.py` | `suri-agent/core/core.md` § 部门扩展机制 |
| `suri-agent/core/interrupt_handler.py` | `suri-agent/core/core.md` § 中断处理 |
| `suri-agent/core/message_bus.py` | `suri-agent/core/core.md` § 消息总线 |
| `suri-agent/access/tui/` | `suri-agent/access/tui/tui.md` |
| `suri-agent/access/output/` | `suri-agent/access/output/output.md` |
| `suri-agent/access/telegram/` | `wiki/communication/telegram.md` |
| `suri-agent/memory/` | `wiki/memory/memory_config.md` |
| `suri-agent/infrastructure/` | `suri-agent/infrastructure/infrastructure.md` |
| `suri-agent/main.py` | `suri-agent/core/core.md`（入口流程） |
| `group/` | `suri-agent/role/role.md` |
| `scripts/` | 相关模块 `.md` |
| 根目录配置 | `wiki/state_schema.md`, `AGENTS.md` |

---

## 自检问题（改代码前必问）

1. 这个改动会影响哪些文档？
2. 如果 3 个月后我回来看这段代码，文档能让我快速理解吗？
3. 新用户读了文档后能正确使用这个功能吗？

如果任一答案为"否"或"不确定"，先补文档再提交。
