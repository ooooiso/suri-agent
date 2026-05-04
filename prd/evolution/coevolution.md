# 四维协同进化机制

> 定义系统中四个核心维度（Skill / Soul / Plugin / Tool）在各自独立进化时，如何互相感知、联动热更新、保证运行时一致性。
>
> **核心原则**：每个维度可独立进化，但进化后必须通过事件广播通知相关方，由相关方自行决定是否和如何响应。

---

## 一、四维定义

| 维度 | 实体 | 进化方式 | 存储位置 | 变更效果 |
|------|------|---------|---------|---------|
| **Skill** | 角色的技能 | role_learner 检测 → 用户确认 → 热激活 | `roles/{role_id}/skills/{name}.json` | 角色能做更多事 |
| **Soul** | 角色的身份定义 | suri 修改 → 用户确认 → 热生效 | `roles/{role_id}/soul.md` | 角色职责/能力边界变化 |
| **Plugin** | 系统插件能力 | suri 开发/升级 → 用户确认 → 热注册 | `agent_framework/plugins/{plugin_name}/` | 系统有新的能力提供者 |
| **Tool** | MCP 工具库 | suri 为角色开发 → 用户确认 → 热注册 | mcp_framework Registry | 角色有新的工具可用 |

---

## 二、协同架构总览

```
                    ┌─────────────────────────────┐
                    │      事件总线 EventBus       │
                    │    广播所有进化变更事件       │
                    └──────────┬──────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
    │  Skill 进化  │   │  Soul 更新   │   │ Plugin/Tool  │
    │              │   │              │   │   新增       │
    └──────┬──────┘   └──────┬───────┘   └──────┬───────┘
           │                 │                  │
           ▼                 ▼                  ▼
    ┌──────────────────────────────────────────────┐
    │           变更通知与自动响应层                   │
    │                                                │
    │  ├─ tool_descriptions.yaml 自动更新            │
    │  ├─ 能力索引自动重建                          │
    │  ├─ 相关角色 system prompt 热刷新              │
    │  ├─ 权限矩阵自动同步                          │
    │  └─ 运行时上下文策略决策（继续/切换/等待）      │
    └──────────────────────────────────────────────┘
```

---

## 三、各维度进化的事件链

### 3.1 Skill 进化事件链

```
role_learner 检测到技能模式（≥3次重复）
    │
    ▼
发布 role.skill_suggested
    │
    ▼
suri 汇总评估 → 向用户呈现
    │
    ▼
用户确认
    │
    ▼
写入 roles/{role_id}/skills/{name}.json
    │
    ▼
发布 role.skill_activated → 通知链：
    ├── template_updater → 更新 tool_descriptions.yaml
    ├── role_manager → 更新能力索引
    ├── 角色自身 → 标记新技能可用（下次 task 生效）
    ├── 项目总监（如存在）→ 通知"我有新能力了"
    └── suri → 更新全局能力索引
```

**Skill 进化通知范围**：

| 通知对象 | 通知方式 | 响应动作 |
|---------|---------|---------|
| 角色自身 | `role.skill_activated` + event | 下次任务时 system prompt 包含新技能 |
| 项目总监 | `role_comm.send` | 重新评估角色能力，调度时考虑新技能 |
| suri | `role.skill_activated` | 更新能力索引，调度时考虑 |
| 其他角色 | 不直接通知（按需查询） | 可通过 role_manager 查询角色能力 |

### 3.2 Soul 更新事件链

```
suri 分析需要更新角色 Soul
    │
    ▼
suri 调用 llm_gateway 生成新 Soul 草案
    │
    ▼
向用户呈现 Soul 变更对比
    │
    ▼
用户确认
    │
    ▼
发布 role.soul_updating（状态：角色进入 upgrading 状态）
    │
    ▼
写入 roles/{role_id}/soul.md（新版本）
    │
    ▼
发布 role.soul_updated → 通知链：
    ├── role_manager → 更新索引，版本管理
    ├── agent_registry → 更新角色运行时 context
    ├── 角色自身 → 收到新 Soul 决策策略
    └── 项目总监（如存在）→ Soul 变化摘要
```

**Soul 更新时正在执行的任务处理策略**：

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| **继续旧 Context**（默认）| 当前任务继续使用旧 Soul，新任务使用新 Soul | 任务执行中，Soul 变化不影响当前任务逻辑 |
| **切换新 Context** | 立即中断任务，用新 Soul 重新理解后继续 | Soul 核心职责变化，旧 Context 不再适用 |
| **等待完成** | 标记 Soul 待更新，当前任务完成后切换 | 任务接近完成，中断成本高 |

**策略选择规则**：
- Soul 变化只涉及权限/边界扩展 → 切换新 Context
- Soul 变化涉及职责缩减 → 等待完成
- 默认 → 继续旧 Context

```python
# 运行时决策伪代码
if soul_diff.affects_current_task(task):
    if task.progress > 0.8:  # 任务接近完成
        strategy = "wait_complete"
    elif soul_diff.is_core_change:  # 核心变更
        strategy = "switch_new_context"
    else:
        strategy = "continue_old_context"
else:
    strategy = "continue_old_context"
```

### 3.3 Plugin 进化事件链

```
suri 开发/升级插件
    │
    ▼
向用户呈现插件变更
    │
    ▼
用户确认
    │
    ▼
发布 plugin.registering
    │
    ▼
plugin_manager 注册插件
    ├── 加载插件代码
    ├── 调用 plugin.init() / register_events()
    └── 调用 plugin.start()
    │
    ▼
发布 plugin.registered → 通知链：
    ├── mcp_framework → 扫描新插件暴露的工具
    ├── 所有角色 → 发布 "新能力可用" 广播
    ├── suri → 更新可用能力列表
    └── config_service → 更新配置索引
```

**Plugin 热更新暴露的接口规范**：

每个插件启动时必须明确声明自己的暴露方式：

```yaml
# 每个 plugin 的 manifest.json 必须包含
{
  "exposes": {
    "events": ["event.type1", "event.type2"],     # 订阅的事件
    "tools": ["tool_name1", "tool_name2"],          # 公开的 MCP 工具
    "commands": ["/cmd1"],                          # CLI 命令
    "apis": {                                       # 方法调用接口
      "method_name": {
        "params": {...},
        "returns": "..."
      }
    }
  },
  "hot_reload": "hot | warm | cold",               # 热更新级别
  "notify_on_change": ["role_type:worker"]          # 变更时通知的角色
}
```

### 3.4 Tool（MCP 工具）进化事件链

```
suri 为角色开发新 MCP 工具（或角色请求新工具）
    │
    ▼
向用户呈现工具方案
    │
    ▼
用户确认
    │
    ▼
mcp_framework 注册工具
    ├── 写入工具定义
    ├── 设置权限级别
    └── 注册到 Registry
    │
    ▼
发布 tool.registered → 通知链：
    ├── template_updater → 更新 tool_descriptions.yaml
    ├── 授权角色 → 收到"你有新工具可用"
    ├── suri → 确认工具就绪
    └── 其他角色 → 广播"新工具可用"（按权限过滤展示）
```

---

## 四、运行时热生效机制

### 4.1 角色 system prompt 热刷新

当角色的 Skill / Soul / Tool 任一维度变更时，角色的 system prompt 需要刷新：

```
变更事件触发
    │
    ▼
role_manager 标记角色 system prompt 为"待刷新"
    │
    ▼
角色下一次发布 llm.request 前：
    ├── 检查 system prompt 是否待刷新
    ├── 是 → 重新构建 system prompt（含新技能/新 Soul/新工具）
    └── 否 → 继续使用当前 prompt
```

**关键规则**：system prompt 在 llm.request 之前重新构建，**不中断正在进行的 LLM 调用**。

### 4.2 tool_descriptions.yaml 自动更新

所有维度变更最终反映到 `tool_descriptions.yaml`：

```yaml
# 自动更新的触发条件
tools:
  - name: "generate_component"      # Skill 进化新增
    role: "frontend_dev"
    triggers: ["创建组件", "生成组件"]
    description: "根据描述生成 React 组件代码"
  
  - name: "call_new_plugin_api"     # Plugin 新增暴露
    role: "suri"
    triggers: ["新插件功能"]
    description: "调用新注册的插件能力"
  
  - name: "mcp_custom_tool"         # Tool 新增
    role: "suri"
    triggers: ["自定义工具"]
    description: "通过 MCP 调用自定义工具"
```

### 4.3 能力索引自动重建

role_manager 维护全局能力索引，以下事件触发索引重建：

| 触发事件 | 重建范围 | 重建方式 |
|---------|---------|---------|
| `role.skill_activated` | 该角色索引 | 增量更新 |
| `role.soul_updated` | 该角色索引 | 全量重建 |
| `plugin.registered` | 全局索引 | 增量更新 |
| `tool.registered` | 全局索引 | 增量更新 |
| 系统启动 | 全局索引 | 全量重建 |

---

## 五、四维协作场景示例

### 场景一：项目进行中 worker 学会新技能

```
【电商网站项目】
    │
    ├── 项目总监 @ecommerce_director 调度中
    │
    ├── worker frontend_dev 执行 UI 任务
    │       │
    │       ├── 完成任务 ✓
    │       ├── role_learner 异步分析
    │       │   └── 检测到 "组件生成" 模式 ≥3 次
    │       │
    │       ├── → 技能建议 → suri 评估 → 用户确认
    │       │
    │       ├── → skill_activated → 通知链
    │       │   ├── tool_descriptions.yaml 更新
    │       │   ├── role_manager 更新索引
    │       │   └── role_comm → 项目总监
    │       │
    │       └── 项目总监收到通知：
    │           "frontend_dev 学会了新技能：组件生成"
    │           → 下次分配 UI 任务时自动使用新技能
```

### 场景二：suri 更新角色 Soul

```
suri 发现 doc_writer 的职责需要扩展
    │
    ├── 生成 Soul 新版本（v1.1）
    │   └── 变化：新增 "API 文档撰写" 能力
    │
    ├── 用户确认
    │
    ├── → soul_updated
    │   ├── doc_writer 当前无任务 → 直接切换新 Soul
    │   ├── role_manager 更新索引
    │   └── suri 通知用户：更新完成
    │
    └── 下次任务：doc_writer 用新 Soul 理解任务
```

### 场景三：suri 开发新插件

```
程序运行中，suri 发现缺少"图片处理"能力
    │
    ├── suri 开发 image_processor 插件
    │   ├── 创建 plugin.py
    │   ├── 创建 manifest.json（声明暴露的工具/事件）
    │   └── 测试
    │
    ├── 用户确认安装
    │
    ├── → plugin.registered
    │   ├── mcp_framework 注册新工具
    │   ├── 广播给所有角色："新能力：图片处理"
    │   ├── 角色可立即在 task 中调用
    │   └── tool_descriptions.yaml 自动更新
    │
    └── 项目总监收到通知，可在项目中使用新能力
```

### 场景四：suri 帮角色创建 MCP 工具库

```
worker data_analyst 执行任务时受阻
    │
    ├── data_analyst → role_comm → suri
    │   "我需要一个能查询数据库的工具"
    │
    ├── suri 分析需求
    │   ├── 是否需要新插件？→ 需要 → 调用 mcp_framework 注册
    │   └── 设置权限：仅 data_analyst 可用
    │
    ├── 用户确认
    │
    ├── → tool.registered
    │   ├── data_analyst system prompt 刷新
    │   ├── data_analyst 继续任务（使用新工具）
    │   └── 工具描述写入 tool_descriptions.yaml
    │
    └── 完成后，suri 记录工具到能力索引
```

---

## 六、四维协同的版本管理

每个维度的变更都应当有版本追踪：

| 维度 | 版本标识 | 存储位置 | 回滚方式 |
|------|---------|---------|---------|
| Skill | `skill_{name}_v{major}.{minor}.json` | `roles/{id}/skills/` | upgrade_manager 版本恢复 |
| Soul | `soul.md` 中 `version` 字段 | `roles/{id}/soul.md` | git revert + soul_updated |
| Plugin | plugin 本身的版本控制 | `agent_framework/plugins/{name}/` | plugin_manager 版本切换 |
| Tool | Registry 中的注册记录 | mcp_framework | 注销 + 重新注册旧版本 |

---

## 七、协同规则总结

1. **每个维度独立进化，不阻塞其他维度**
2. **变更后必须广播事件** — 由 EventBus 承载
3. **接收方自主决策响应方式** — 不强制统一行为
4. **运行时 context 切换有策略** — 默认继续旧 Context
5. **system prompt 在 llm.request 前刷新** — 不中断进行中的调用
6. **能力索引增量重建** — 避免全量扫描开销
7. **所有变更须用户确认** — 但确认后自动完成通知链
8. **版本可追溯可回滚** — upgrade_manager 统一管理
