# doc_sync 插件 PRD

## 定位

文档同步服务。监控代码/配置变更，自动生成文档更新建议，保持代码与文档一致性。

**关键约束**：只生成建议，不直接修改文档。所有文档变更须经用户确认。

## 功能需求

### 1. 文件变更监控（FileWatcher）

通过 hooks_service 订阅文件变更事件：

```python
WATCH_PATTERNS = [
    "**/*.py",           # Python 代码
    "prd/**/*.md",       # PRD 文档
    "plugins/**/*.md",   # 插件 PRD
    "plugins/**/*.py",   # 插件代码
    "core/**/*.py",      # 核心代码
    "shared/**/*.py",    # 共享模块
]
```

### 2. 文档映射（DocMapping）

代码文件与对应文档的映射关系：

```python
DOC_MAPPING = {
    "plugins/{name}/{name}.py": "prd/plugins/{name}.md",
    "core/event_bus.py": "prd/framework.md",
    "core/plugin_manager.py": "prd/framework.md",
    "core/scheduler.py": "prd/plugins/task_scheduler.md",
    # ... 其他映射
}
```

### 3. 变更分析（ChangeAnalysis）

变更发生时：
1. 识别受影响的文档
2. 提取变更摘要（函数签名、配置项、接口变更）
3. LLM 分析变更对文档的影响
4. 生成具体的文档更新建议（行级定位）

### 4. 建议呈现（SuggestionPresentation）

向用户呈现格式：

```
📄 文档同步建议

检测到以下文件变更：
- plugins/task_scheduler.py （+45行 / -12行）

建议更新文档：prd/plugins/task_scheduler.md

变更摘要：
1. 新增 `pause()` / `resume()` 方法
2. 配置项新增 `auto_schedule` 字段
3. 生命周期增加 pause/resume 阶段

建议修改（第 45~50 行）：
- 在生命周期章节增加 pause/resume 说明
- 在配置项中增加 auto_schedule

是否确认应用这些更新？[确认] [查看详情] [忽略]
```

### 5. 应用确认（ApplyConfirmation）

- 用户确认后，生成文档补丁
- 通过 security_service 的文件变更审批（如配置启用）
- 应用后记录变更审计

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `hooks.file_changed` | hooks_service | 分析文件变更 |
| `hooks.file_created` | hooks_service | 分析新文件 |
| `hooks.file_deleted` | hooks_service | 分析文件删除 |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `doc_sync.suggestion_created` | access / suri 角色 | 生成文档更新建议 |
| `doc_sync.applied` | log_service | 已应用更新 |
| `doc_sync.ignored` | log_service | 用户忽略建议 |

### 方法

```python
class DocSync:
    def on_file_changed(self, file_path: str, change_type: str, diff: str)
    def _find_affected_docs(self, file_path: str) -> List[str]
    def _analyze_impact(self, file_path: str, diff: str, doc_path: str) -> str
    def _generate_suggestion(self, doc_path: str, impact: str) -> DocSuggestion
    def apply_suggestion(self, suggestion_id: str) -> bool
    def ignore_suggestion(self, suggestion_id: str) -> bool

@dataclass
class DocSuggestion:
    suggestion_id: str
    source_file: str
    target_doc: str
    change_summary: str
    suggested_changes: List[DocChange]
    confidence: float

@dataclass
class DocChange:
    location: str           # 章节/行号
    action: str             # add / modify / delete
    old_text: Optional[str]
    new_text: str
    reason: str
```

## 配置项

```yaml
doc_sync:
  watch_patterns:
    - "**/*.py"
    - "prd/**/*.md"
    - "plugins/**/*.md"
    - "plugins/**/*.py"
  enable_auto_suggest: true
  min_change_lines: 5             # 最小触发行数
  cooldown_seconds: 300           # 同一文件冷却期
  require_approval: true          # 是否需要 security_service 审批
  confidence_threshold: 0.7       # 建议置信度阈值
  llm_model: "gpt-4o-mini"        # 分析用轻量模型
```

## 依赖关系

- 上游：suri_core（EventBus）
- 上游：hooks_service（文件变更钩子）
- 上游：llm_gateway（生成文档更新建议）
- 上游：security_service（文件变更审批，如启用）
- 下游：access（向用户呈现建议）
- 下游：log_service（记录同步事件）

## 生命周期

1. `init()` → 加载文档映射、初始化建议缓存
2. `start()` → 标记就绪，等待文件变更事件
3. `stop()` → 停止处理新事件
4. `cleanup()` → 保存未处理建议、清空缓存

## 安全边界

- 不直接修改任何文档，只生成建议
- 所有应用操作需用户确认
- 冷却期内同一文件多次变更合并为一条建议
- 建议置信度低于阈值时不推送
- **核心原则**：建议驱动，不自动执行文档变更
