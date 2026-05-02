# 迭代 4：学习提炼 + 经验驱动进化

> 角色能够从经验中学习，持续提炼技能，让进化从"人工触发"变为"自动驱动"。

---

## 目标

1. 角色任务完成后自动分析记忆，生成洞察
2. 重复工具模式自动检测，建议技能
3. 洞察自动注入后续任务上下文
4. 代码变更后自动建议文档更新
5. 学习闭环无需用户手动触发

---

## 包含插件（2 个新增）

| # | 插件 | 说明 |
|---|------|------|
| 1 | **role_learner**（完整版） | RoleLearner 经验提取、洞察生成、技能检测 |
| 2 | **doc_sync** | 代码变更监控、LLM 生成文档更新建议、用户确认写入 |

## 完善（1 个）

| # | 插件 | 说明 |
|---|------|------|
| 3 | **hooks_service**（简化版） | 文件变更钩子，触发 doc_sync 和 role_learner |

---

## 核心功能链路

### 1. 角色学习闭环

```
角色完成任务 → 发布 task.completed
    │
    ▼
role_learner 订阅 → 异步分析角色记忆
    │
    ├─ 读取 experiences 表（最近 7 天）
    ├─ LLM 分析生成洞察（success_pattern / improvement / pitfall / preference）
    ├─ 保存到 roles/{role_id}/memories/insights/
    └─ 检测重复工具模式（≥3 次）
        │
        └── 生成技能建议 → 发布 role.skill_suggested → role_manager
    │
    ▼
角色下次任务时 ← role_learner.get_recent_insights_for_context()
    │
    ▼
洞察注入系统提示（≤2000 字符）
```

### 2. 技能提升闭环

```
role_manager 订阅 role.skill_suggested
    │
    ▼
评估技能建议
    │
    ├── 置信度 < 0.7 ──▶ 暂存，等待更多数据
    │
    └── 置信度 ≥ 0.7
        │
        ▼
    生成技能模板草案
        ├─ 技能名称
        ├─ 触发条件
        ├─ 工具组合
        ├─ 参数模板
        └─ 使用示例
        │
        ▼
    向用户呈现（access）
        │
        ├── 用户拒绝 ──▶ 标记为 ignored
        │
        └── 用户确认
            │
            ▼
        code_tool 写入 skill 文件
            └─ roles/{role_id}/skills/{skill_name}.json
            │
            ▼
        更新角色 Soul 的 skills 列表
            │
            ▼
        发布 role.skill_invoked（首次激活）
```

### 3. 文档同步

```
hooks_service 监控文件变更
    │
    ▼
代码变更 → doc_sync 分析变更内容
    │
    ▼
LLM 判断是否需要更新文档
    │
    ▼
生成文档更新建议 → 向用户呈现
    │
    ├── 用户拒绝 ──▶ 记录忽略
    │
    └── 用户确认
        │
        ▼
    code_tool 写入更新后的文档
```

---

## 开发任务分解

### Week 1：role_learner（完整版）

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| role_learner 插件 | `plugins/role_learner/plugin.py` | role_learner.md |
| 经验提取器 | `plugins/role_learner/extractor.py` | role_learner.md §经验提取 |
| 洞察生成器 | `plugins/role_learner/insight_generator.py` | role_learner.md §洞察生成 |
| 技能检测器 | `plugins/role_learner/skill_detector.py` | role_learner.md §技能形成 |
| 上下文注入 | `plugins/role_learner/context_injector.py` | learning_flow.md §上下文注入 |
| 技能模板格式 | `shared/utils/skill_schema.py` | learning_flow.md §技能提升流程 |

### Week 2：doc_sync + hooks_service

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| doc_sync 插件 | `plugins/doc_sync/plugin.py` | doc_sync.md |
| 文件监控 | `plugins/doc_sync/watcher.py` | doc_sync.md §文件变更监控 |
| 建议生成 | `plugins/doc_sync/suggester.py` | doc_sync.md §LLM 生成建议 |
| hooks_service 插件（简化） | `plugins/hooks_service/plugin.py` | hooks_service.md |
| 文件变更钩子 | `plugins/hooks_service/file_hooks.py` | hooks_service.md §文件钩子 |
| 事件拦截器 | `plugins/hooks_service/interceptor.py` | hooks_service.md §事件拦截 |

---

## 测试矩阵

| 测试项 | 通过标准 |
|--------|----------|
| 洞察生成 | 任务完成后自动生成洞察文件 |
| 上下文注入 | 洞察正确注入下次任务的系统提示 |
| 技能检测 | 重复工具模式 ≥3 次触发 skill_suggested |
| 技能提升 | 用户确认后 skill 文件正确写入并激活 |
| 文档同步 | 代码变更后生成对应的文档更新建议 |
| 自动触发 | 学习流程无需用户手动触发，事件驱动 |
