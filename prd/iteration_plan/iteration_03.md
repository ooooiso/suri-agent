# 迭代 3：自我进化 + 升级自身代码

> 让 suri 能够**自我分析、发现瓶颈、生成升级方案、执行代码变更**，实现自我进化。

---

## 目标

1. suri 能分析自身运行数据，发现性能瓶颈和优化点
2. 生成系统优化报告和代码升级方案
3. 用户确认后，suri 能**自动执行代码变更、测试验证、回滚失败**
4. 支持多角色协作和项目级工作流
5. Telegram 项目群支持

---

## 包含插件（3 个新增）+ 角色能力

| # | 插件/角色 | 说明 |
|---|----------|------|
| 1 | **upgrade_manager** | 升级报告状态机、闭环检查、备份回滚 |
| 2 | **role_comm** | 角色间点对点/广播消息、SQLite 持久队列 |
| 3 | **Project Director 角色** | 自动创建，负责项目调度、进度播报 |
| 4 | **work_flow 流程** | 项目创建→执行→归档完整流程 |

## 完善（1 个）

| # | 插件 | 说明 |
|---|------|------|
| 5 | **role_learner**（简化版） | ProgramLearner 全局分析模块，触发自我分析 |

## 明确不包含

完整角色学习（迭代 4）、doc_sync（迭代 4）、mcp_framework（迭代 5）

---

## 核心功能链路

### 1. 自我分析链路

```
suri 主动触发或定时触发（通过 cron_service 简化版）
    │
    ▼
role_learner / ProgramLearner 执行全局分析
    │
    ├─ 读取全局事件日志（events 表）
    ├─ 分析插件调用频率和延迟
    ├─ 分析任务成功/失败率
    ├─ 分析角色协作效率
    └─ 识别性能瓶颈和代码异味
    │
    ▼
生成系统优化报告 → 发布 learning.report_generated
    │
    ▼
upgrade_manager 接收报告
    │
    ├─ 解析报告中的 Finding 列表
    ├─ 每个 Finding 生成 UpgradeReport
    └─ 进入状态机：PENDING → PRESENTED
    │
    ▼
suri 向用户呈现升级方案
    │
    ├─ 问题描述
    ├─ 建议变更（含代码 diff）
    ├─ 风险评估
    └─ 回滚策略
    │
    ▼
用户确认 → upgrade_manager 状态变为 APPROVED
```

### 2. 代码升级执行链路（迭代 3 核心新增）

```
upgrade_manager 执行升级
    │
    ▼
备份当前代码 → ~/.suri/backup/{timestamp}/
    │
    ▼
code_tool 应用代码变更
    │
    ├─ 写入修改后的文件
    ├─ 新增文件
    └─ 删除过时文件（需用户额外确认）
    │
    ▼
运行测试验证
    │
    ├─ test_framework 执行全量测试
    ├─ 执行冒烟测试（EventBus + PluginManager 基础分发）
    └─ 执行相关回归测试
    │
    ▼
测试通过 → 标记 IMPLEMENTED → 发布 upgrade.implemented
    │
    ▼
清理备份（保留最近 10 份）

测试失败 → 执行回滚
    │
    ▼
从备份恢复代码
    │
    ▼
标记 FAILED → 记录原因 → 通知用户
```

### 3. 项目协作链路

```
用户在 Telegram 输入 "创建一个新项目，开发一个电商网站"
    │
    ▼
access 路由到 suri
    │
    ▼
suri 分析需求 → 建议项目类型和所需角色
    │
    ▼
用户确认 → suri 调用 work_flow 创建项目
    │
    ├─ 创建 works/{project_id}/ 目录
    ├─ 生成 .meta.json、prd.md
    ├─ 创建 Telegram 项目群
    └─ 自动创建 Project Director 角色
    │
    ▼
Project Director 加入项目群，开始调度
    │
    ├─ 分解任务 → 通过 role_comm 发送给 worker 角色
    ├─ worker 并行执行（调用 code_tool 生成代码）
    ├─ 每 N 分钟播报进度
    └─ 全部完成 → 汇总交付
```

---

## upgrade_manager 设计

### UpgradeReport 状态机

```
PENDING ──▶ PRESENTED ──▶ APPROVED ──▶ IMPLEMENTING ──▶ IMPLEMENTED
                  │              │              │
                  ▼              ▼              ▼
              REJECTED       DEFERRED       FAILED ──▶ ROLLED_BACK
```

### 核心组件

```python
class UpgradeManager:
    async def create_report(self, finding: Finding) -> UpgradeReport
    async def present_to_user(self, report_id: str) -> None  # 发布事件让 access 呈现
    async def approve(self, report_id: str) -> None
    async def implement(self, report_id: str) -> bool  # 执行变更并验证
    async def rollback(self, report_id: str) -> bool   # 从备份恢复
    async def validate(self, report_id: str) -> bool   # 运行测试验证
```

---

## 开发任务分解

### Week 1：upgrade_manager + role_learner（ProgramLearner）

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| upgrade_manager 插件 | `plugins/upgrade_manager/plugin.py` | upgrade_manager.md |
| 报告状态机 | `plugins/upgrade_manager/state_machine.py` | upgrade_manager.md §状态机 |
| Finding 模型 | `plugins/upgrade_manager/models.py` | upgrade_manager.md §Finding |
| 备份恢复 | `plugins/upgrade_manager/backup.py` | upgrade_manager.md §回滚策略 |
| 闭环检查 | `plugins/upgrade_manager/validator.py` | upgrade_manager.md §闭环检查 |
| ProgramLearner | `plugins/role_learner/program_learner.py` | learning_flow.md §ProgramLearner |
| 全局分析引擎 | `plugins/role_learner/global_analyzer.py` | learning_flow.md §全局分析 |
| 备份脚本 | `scripts/backup.py` | deployment.md §备份策略 |

### Week 2：role_comm + Project Director + work_flow

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| role_comm 插件 | `plugins/role_comm/plugin.py` | role_comm.md |
| SQLite 消息队列 | `plugins/role_comm/queue.py` | role_comm.md §持久化队列 |
| 通信权限矩阵 | `plugins/role_comm/permissions.py` | role_comm.md §权限规则 |
| Project Director Soul | `roles/project_director/soul.md` | work_flow.md §Project Director |
| 项目创建流程 | `plugins/role_manager/project_creator.py` | work_flow.md §项目创建 |
| Telegram 群管理 | `plugins/access/telegram_group.py` | access.md §项目群 |
| 项目归档 | `plugins/role_manager/archiver.py` | work_flow.md §项目归档 |

---

## 测试矩阵

### 自我进化测试

| 测试项 | 通过标准 |
|--------|----------|
| 全局分析 | ProgramLearner 能生成包含 Finding 的报告 |
| 升级方案 | upgrade_manager 能将 Finding 转为可执行的 UpgradeReport |
| 用户呈现 | 升级方案以可读格式呈现给用户 |
| 备份恢复 | 升级前自动备份，升级失败能完整恢复 |
| 代码变更 | 用户确认后 code_tool 正确应用代码 diff |
| 验证闭环 | 变更后自动运行测试，通过才标记 IMPLEMENTED |
| 回滚机制 | 测试失败时自动回滚并通知用户 |

### 项目协作测试

| 测试项 | 通过标准 |
|--------|----------|
| 项目创建 | 用户一句话创建项目，目录和群正确生成 |
| Project Director | 自动创建，能分解任务并调度角色 |
| 角色通信 | 角色间能收发点对点消息和广播 |
| 进度播报 | 项目群中定时收到进度更新 |
| 缺失角色 | Project Director 能检测并请求创建新角色 |
