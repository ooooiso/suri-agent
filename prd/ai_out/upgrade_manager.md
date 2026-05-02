# upgrade_manager 插件 PRD

## 定位

升级报告的完整生命周期管理。提供状态机、闭环检查、结构化数据模型和持久化存储。

**关键约束**：只管理报告，不执行升级。升级实施需用户确认后由对应插件/角色执行。

## 功能需求

### 1. 报告状态机（ReportStateMachine）

```
PENDING ──▶ SUBMITTED ──▶ ACKNOWLEDGED ──▶ DISPATCHED ──▶ IMPLEMENTED
   │            │              │                 │
   └────────────┴──────────────┴─────────────────┴──▶ REJECTED
   │
   └──▶ DEFERRED
```

| 状态 | 说明 |
|------|------|
| PENDING | 刚生成，未提交 |
| SUBMITTED | 已提交给 suri |
| ACKNOWLEDGED | suri 已确认收到 |
| DISPATCHED | 已分发给相关方（模块/角色） |
| IMPLEMENTED | 已实施完成 |
| REJECTED | 被拒绝 |
| DEFERRED | 延期处理 |

### 2. 报告数据模型

**Finding**：单个发现项

```python
@dataclass
class Finding:
    finding_id: str
    category: FindingCategory      # PERFORMANCE / ACCURACY / USABILITY / SECURITY / INTEGRATION / DESIGN / RELIABILITY
    description: str
    evidence: str
    suggestion: str
    estimated_impact: str
    confidence: float              # 0.0 ~ 1.0
```

**UpgradeReport**：模块/插件级报告

```python
@dataclass
class UpgradeReport:
    report_id: str
    module_id: str                 # 插件/角色/框架 ID
    module_type: ModuleType        # plugin | tool | role | framework
    findings: List[Finding]
    summary: str
    priority: Priority             # CRITICAL / HIGH / MEDIUM / LOW
    status: ReportStatus
    submitted_to: str = "suri"
    trigger_type: TriggerType      # user_wake | auto_threshold | scheduled | post_task | escalation
    created_at: str = ""
    updated_at: str = ""
```

**FrameworkImprovementReport**：框架级报告

```python
@dataclass
class FrameworkImprovementReport:
    report_id: str
    findings: List[Finding]
    analysis_scope: str
    common_issues: List[str]
    framework_risks: List[str]
    estimated_change_difficulty: str   # 简单 / 中等 / 困难 / 架构级重构
```

### 3. 报告管理（ReportManagement）

- `save_report(report)` → 保存到文件系统（`~/.suri/data/upgrade_reports/`）
- `update_status(report_id, status, reason)` → 状态变更
- `get_pending_reports()` → 获取所有待处理报告
- `get_summary_for_suri()` → 为 suri 角色生成汇总视图
- `list_reports(filters)` → 按 module_id / status / priority / module_type 筛选

### 4. 闭环检查（ClosedLoopCheck）

由 task_scheduler 或 suri 角色在任务调度末尾自动调用：

```python
def check_and_notify():
    pending = upgrade_manager.get_pending_reports()
    by_module = group_by_module(pending)
    for module_id, reports in by_module.items():
        event_bus.publish("upgrade.reports_pending", {
            "module_id": module_id,
            "count": len(reports),
            "report_ids": [r.report_id for r in reports]
        })
```

### 5. 优先级自动推导

| 条件 | 优先级 |
|------|--------|
| Security 类别 | CRITICAL |
| Performance + confidence > 0.8 | HIGH |
| Reliability + 失败率 > 30% | HIGH |
| 其他 | MEDIUM 或 LOW（由 confidence 决定） |

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `learning.report_generated` | role_learner / PluginSelfLearning / ProgramLearner | 保存报告 |
| `upgrade.status_change_requested` | suri 角色 / 用户 | 变更报告状态 |
| `upgrade.check_requested` | task_scheduler / cron_service | 执行闭环检查 |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `upgrade.report_saved` | log_service | 报告已保存 |
| `upgrade.status_changed` | log_service / suri 角色 | 状态已变更 |
| `upgrade.reports_pending` | suri 角色 | 有待处理报告需汇总 |
| `upgrade.implemented` | log_service / 相关插件 | 报告已实施 |

### 方法

```python
class UpgradeManager:
    def save_report(self, report: Union[UpgradeReport, FrameworkImprovementReport]) -> bool
    def update_status(self, report_id: str, status: ReportStatus, reason: str = "") -> bool
    def get_pending_reports(self) -> List[UpgradeReport]
    def get_summary_for_suri(self) -> Dict[str, Any]
    def list_reports(self, module_id: str = None, status: ReportStatus = None,
                     priority: Priority = None, module_type: ModuleType = None) -> List[UpgradeReport]
    def check_and_notify(self) -> int          # 返回通知的报告数
    def get_report(self, report_id: str) -> Optional[UpgradeReport]
```

## 配置项

```yaml
upgrade_manager:
  storage_path: "~/.suri/data/upgrade_reports/"
  check_interval: 3600              # 闭环检查周期（秒）
  auto_derive_priority: true
  priority_rules:
    CRITICAL: ["category == SECURITY"]
    HIGH: ["category == PERFORMANCE and confidence > 0.8", "category == RELIABILITY and failure_rate > 0.3"]
  retention_days: 365               # 报告保留天数
  max_findings_per_report: 10       # 单报告最大发现数
```

## 依赖关系

- 上游：suri_core（EventBus）
- 上游：role_learner / PluginSelfLearning / ProgramLearner（报告来源）
- 下游：suri 角色（汇总、决策）
- 下游：log_service（记录状态变更）

## 文件存储结构

```
~/.suri/data/upgrade_reports/
├── ur_{id}.json              # 模块/插件级报告
├── framework_{id}.json       # 框架级报告
└── index.json                # 索引文件（加速查询）
```

## 生命周期

1. `init()` → 创建存储目录、加载索引
2. `start()` → 启动定时闭环检查协程（如配置）
3. `stop()` → 停止检查协程
4. `cleanup()` → 保存索引、关闭文件句柄

## 安全边界

- 报告文件只读（状态变更通过事件驱动）
- 索引文件定期备份
- 存储路径不可被普通插件直接写入（通过事件接口操作）
- **核心原则**：只管理报告生命周期，不执行升级操作
