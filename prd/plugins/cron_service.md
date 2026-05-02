# cron_service 插件 PRD

## 定位

定时事件触发插件，**只负责在指定时间触发事件，不定义事件内容，不执行任务**。事件由角色订阅并处理。程序无关，纯粹是时间驱动的消息投递器。

## 功能需求

### 1. 事件触发
- cron 表达式（`0 2 * * *`）
- 固定间隔（`interval: 3600`）
- 一次性延迟（`delay: 300`）

### 2. 触发规则（仅定义时间，不定义内容）
- 每个规则只配置：**何时触发** + **事件类型** + **目标角色**
- 事件 payload 由目标角色自己解释
- 示例：
  ```yaml
  - id: "daily_maintenance"
    cron: "0 2 * * *"
    event_type: "cron.daily_maintenance"
    target: "suri"   # 由 suri 角色决定做什么
  ```

### 3. 执行管理
- 任务错过补偿（misfire grace time）
- 并发控制（同一规则不重叠触发）
- 触发结果记录到 schedule 日志（仅记录"触发了事件"，不记录事件处理结果）

### 4. 动态管理
- 运行时添加/删除规则
- 规则状态查询（下次触发时间）
- 手动触发（立即发送一次事件）

## 接口定义

### 订阅事件
- `user.command`（/cron）→ 管理定时规则

### 发布事件
- `cron.{rule_id}` — 定时触发的事件，由目标角色订阅处理
- `upgrade.check_requested` — 定时触发升级报告检查（如配置）

## 配置项

```yaml
cron_service:
  rules:
    - id: "daily_maintenance"
      cron: "0 2 * * *"
      event_type: "cron.daily_maintenance"
      target: "suri"
      enabled: true
  misfire_grace_time: 3600
  max_instances: 1
```

## 事件 Payload Schema

### 订阅事件

本插件不订阅业务事件，内部定时器触发。

### 发布事件

#### `cron.{rule_id}`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `rule_id` | string | 是 | 规则 ID |
| `triggered_at` | string | 是 | 触发时间 |
| `payload` | object | 否 | 用户自定义 payload |
| `missed_count` | integer | 否 | 错过的触发次数（补偿时） |

## 依赖关系

- 上游：suri_core
- 下游：无（事件由角色订阅处理）

## 生命周期

1. `init()` → 加载规则配置
2. `start()` → 启动调度器、注册所有规则
3. `stop()` → 关闭调度器
4. `cleanup()` → 保存规则状态

## 安全边界

- 只触发事件，不执行业务逻辑
- 异常规则不阻塞其他规则
- **核心原则**：cron_service 不知道事件内容是什么，只负责按时投递
