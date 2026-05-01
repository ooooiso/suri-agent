# Suri Agent Platform — 产品需求文档（PRD）

> **版本**: V3.0 综合需求文档  
> **生成日期**: 2026-05-01  
> **说明**: 本文档集覆盖自项目启动至 V3.0 的全部需求，由 8 份归档规格文档重组而成  

---

## 文档结构

| 文件 | 内容 | 页数（约） |
|------|------|-----------|
| `00.overview.md` | 项目总览、架构总图、术语表、核心原则、版本演进、冲突解决汇总 | ~200 行 |
| `01.infrastructure.md` | ConfigService、MemoryService、LoggerService、SecurityService、FileService、ModelManager | ~150 行 |
| `02.core.md` | 任务调度、任务规划、任务状态、Agent 注册表、部门注册表、上下文服务、消息总线、中断处理、审批服务、文档同步、工具执行器 | ~200 行 |
| `03.access.md` | CLI 终端、CreationDialog、JSON-RPC 服务、Telegram Bot、投影服务、输出路由 | ~150 行 |
| `04.role.md` | 角色命名规范、五大核心角色、角色空间结构、昵称系统、角色保护、创建流程、通信管理、进化机制 | ~200 行 |
| `05.learning.md` | 反馈收集器、经验提取器、角色学习器、平台学习器、MemoryService/ContextService/LoggerService 扩展 | ~100 行 |
| `06.rules.md` | 安全审批、文件所有权、调度规则、通信规则、文档同步规则、工具同步规则、代码提交规则、角色管理规则、模型路由规则、开发态/运行态分离 | ~150 行 |
| `07.tools.md` | 8 个公共工具、工具权限体系、工具注册表、MCP 框架、技能管理流程 | ~120 行 |
| `08.testing.md` | 测试框架结构、509 项测试统计、覆盖矩阵、已知问题、测试开发计划 | ~120 行 |
| `09.web_ui.md` | Web UI 仪表盘（Dashboard、Kanban、角色面板、组织架构、审批中心、交互终端、SSE、Tauri） | ~80 行 |

---

## 需求状态图例

| 标记 | 含义 |
|------|------|
| ✅ | 已完成实现 |
| 🔄 | 部分实现或待完善 |
| ❌ | 待开发 |

---

## 重组说明

### 来源归档文档

本文档集由以下 8 份归档文档重组而成：

1. `1.SELF_LEARNING_SPEC.md` — 自学习模块 → 分散到 `05.learning.md`、`02.core.md`
2. `1.md` — Agent 创建流程 → 分散到 `04.role.md`、`06.rules.md`
3. `2.TELEGRAM_INTEGRATION_SPEC.md` — Telegram 集成 → 分散到 `03.access.md`
4. `3.md` — 开发态与运行态分离 → 分散到 `06.rules.md`、`00.overview.md`
5. `3.细节处理.md` — 9 项细节 → 分散到 `03.access.md`、`06.rules.md`、`07.tools.md`、`08.testing.md`
6. `4多智能体优化.md` — V3.0 多 Agent 协同 → 分散到 `02.core.md`、`04.role.md`、`07.tools.md`
7. `基础设施搭建完成.md` — V1.0 基础设施 → 分散到 `01.infrastructure.md`、`02.core.md`
8. `多角色智能体框架初始化.md` — V2.0 角色体系 → 分散到 `04.role.md`

### 重组原则

1. **不删减** — 所有原始需求均保留
2. **去重** — 同一需求在多个文档中出现时，只保留一份完整描述
3. **去矛盾** — 冲突需求标注冲突点并给出最优解（见 `00.overview.md` 第 7 节）
4. **补遗漏** — 已做但未在原始归档中记录的内容已补充（见 `00.overview.md` 第 8 节）
5. **状态标注** — 每个需求标注当前实现状态（✅/🔄/❌）

### 主要冲突及解决方案

| # | 冲突 | 解决方案 |
|---|------|---------|
| 1 | 经验存储路径层级不一致 | 采用 `group/<dept>/<role>/` 格式 |
| 2 | 统计角色名称 `analyst` vs `suri_stats` | 统一为 `suri_stats`，保留别名兼容 |
| 3 | Telegram 配置存储位置 | 实际配置存 `groups.yaml`，wiki 仅作说明 |
| 4 | MCP 完整分层 vs 当前占位符 | 保留架构设计，标注为"框架预留" |
| 5 | 部门经理角色未实现 | 保留需求，当前由 suri 直接承担规划职责 |
| 6 | 记忆系统 Redis/向量库 vs SQLite WAL | 当前采用 SQLite WAL，未来可按需升级 |
| 7 | 开发态/运行态 vs `suri_dev` 代码修改权 | `suri_dev` 通过 SecurityService 审批后操作，符合规则 |
| 8 | 输出路径早期写错 | 已修复为 `group/central/<role>/` |

---

## 待开发需求总览

| # | 需求 | 优先级 | 文档 |
|---|------|--------|------|
| 1 | Web UI 仪表盘 | P1 | `09.web_ui.md` |
| 2 | SSE 实时推送 | P2 | `09.web_ui.md` |
| 3 | Tauri 桌面封装 | P3 | `09.web_ui.md` |
| 4 | PlatformLearner LLM 分析 | P2 | `05.learning.md` |
| 5 | 部门经理角色 `suri_dept_manager` | P2 | `04.role.md` |
| 6 | MCP 服务完整实现 | P2 | `07.tools.md` |
| 7 | 记忆归档/遗忘策略 | P3 | `01.infrastructure.md` |
| 8 | 日志级别动态过滤 | P3 | `01.infrastructure.md` |
| 9 | Agent 消息持久化到 DB | P2 | `02.core.md` |
| 10 | 离线代理自动审批 | P3 | `01.infrastructure.md` |
| 11 | 缺失模块测试覆盖（~30 个模块） | 中 | `08.testing.md` |

---

## 维护指南

当新增需求或修改现有需求时：

1. **找到对应 PRD 文件** — 按主题归类到正确文档
2. **标注需求来源** — 在需求前标注来源文档或用户指令
3. **更新状态** — 新增需求默认标记为 🔄 或 ❌
4. **同步 `00.overview.md`** — 若涉及架构变更或新增待开发项，更新总览文档
5. **遵循 AGENTS.md** — 代码变更必须同步更新文档（包括 PRD）
