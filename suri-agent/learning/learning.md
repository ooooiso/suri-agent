---
module_id: learning
name: 自学习模块
version: "1.0.0"
owner: suri-dev
---

# 自学习模块

## 定位

Suri 平台的经验积累与进化系统，包含角色自学习和主程序自学习两个子系统。

## 子模块

| 文件 | 职责 |
|------|------|
| `base.py` | 学习器抽象基类 |
| `feedback_collector.py` | 收集任务反馈数据 |
| `experience_extractor.py` | Prompt 工程 + LLM 调用 + 结果解析 |
| `role_learner.py` | 角色级经验提取、去重、存储 |
| `platform_learner.py` | 平台级统计与策略优化（框架预留） |

## 触发时机

1. 任务完成后（RoleLearner，异步）
2. 用户显式反馈后（FeedbackCollector，即时）
3. 夜间定时复盘（PlatformLearner，cron 触发）

## 存储位置

- 角色经验：`group/<dept>/<role>/memories/insights/*.md`
- 角色模式：`group/<dept>/<role>/memories/patterns/*.md`
- 平台经验：`suri-agent/memory/platform-learning/*.md`

> 注：`insights/` 和 `patterns/` 子目录在角色创建时由 `RoleBuilder` 自动建立，现有角色已补全。

## 接口

```python
# 主入口
from learning import RoleLearner

# 初始化
learner = RoleLearner(memory_service, model_service, logger_service)

# 触发学习（异步，不等待结果）
asyncio.create_task(learner.learn_from_task(role_id, task_id))
```

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-04-30 | 初始化模块 |
| 2026-05-01 | 完成基础实现（v1.0.0） |
