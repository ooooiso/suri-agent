# 工具进化（Tool Evolution）

> 定义 suri-agent 中 MCP 工具和插件工具的进化机制。suri 通过自然语言对话维护开发工具，变更后自动更新**Tool Registry**并广播通知。

---

## 一、工具定义

在 suri-agent 中，"工具"指角色可通过 mcp_framework 调用的一切能力：

| 工具类型 | 提供方 | 示例 |
|---------|--------|------|
| MCP 工具 | 外部 MCP 服务器 | 搜索、计算器、API 调用 |
| 插件工具 | 插件声明的 expose.tools | code_tool 的文件操作 |
| 内建工具 | suri_core 自带 | 事件总线查询、插件注册表查询 |

### ★ 核心原则：角色可用所有工具，Soul 约束行为

```
角色可以使用系统中所有已注册的工具，不做白名单控制。
约束来自角色的 Soul 定义：

设计师角色的 Soul:
  "我是设计师，我不应该直接修改生产代码。"
→ 自然约束设计师不会调用 code_tool.write_file

如果异常调用 → security_service 审计日志记录 → suri 提醒
```

## 二、工具归属：Tool Registry（三清单体系）

每个工具在 **Tool Registry** 中有一条完整记录：

```python
{
  "tool_id": "code_tool.read_file",
  "name": "读取文件",
  "description": "读取指定路径的文件内容并返回",
  "version": "1.0.0",
  "source_plugin": "code_tool",         # 提供方插件
  "source_type": "local",               # local / remote / builtin
  "input_schema": {
    "path": { "type": "string", "required": true },
    "encoding": { "type": "string", "default": "utf-8" }
  },
  "status": "active",                    # active / deprecated / removed
  "call_count": 8921,                    # 调用统计
  "unique_callers": ["suri", "designer_01", "dev_01"],
  "success_rate": 0.998,
  "avg_latency_ms": 12,
  "evolution_history": [                 # 进化历史
    { "version": "1.1.0", "change": "新增 encoding 参数" },
    { "version": "1.2.0", "change": "优化缓存" }
  ]
}

Tool Registry 维护者：mcp_framework 插件
存储：SQLite + 内存缓存
查询接口：list_tools / get_tool / search_tools / get_hot_tools / get_unused_tools
```

### 工具调用自动携带上下文元数据

```python
# 所有工具调用自动传递 _meta
class RoleAgent:
    async def call_tool(self, tool_name: str, params: dict):
        result = await self.mcp_server.call_tool(
            tool_name=tool_name,
            params={
                **params,
                "_meta": {  # ★ 自动附加
                    "role_id": self.role_id,
                    "project_id": self.current_project,
                    "task_id": self.current_task_id,
                    "session_id": self.current_session_id
                }
            }
        )
        return result
```

## 三、工具版本的动态管理

```
工具注册时声明：
  name: string           # 工具名（全局唯一）
  version: string        # semver 格式
  api_version: string    # 接口版本（向后兼容检查用）
  provider: string       # 提供方标识（plugin_id / mcp_server_id）

版本兼容规则：
  major 相同 → 向前兼容，直接升级
  major 不同 → 不兼容，需要迁移

版本管理由 Tool Registry 统一处理：
  自动记录每次变更到 evolution_history
  调用失败自动降低 success_rate 并告警
```

## 四、工具进化触发条件与流程

### 4.1 进化由 suri 通过自然语言驱动

```
suri 在日常工作中发现工具优化机会：
（或插件自我分析发现优化空间）
    │
    ▼
suri 通过自然语言对话与用户沟通：
  "我注意到开发者角色经常先搜索文件再批量读取，
  是否需要新增一个 batch_search_and_read 工具？"
    │
    ▼
用户确认 → suri 执行：
  1. 修改对应插件的代码
  2. 注册/更新工具（更新 Tool Registry）
  3. 广播 tool.registered / tool.updated / tool.deprecated
  4. 通知所有角色（特别是正在使用该工具的角色）
```

### 4.2 进化触发条件

| 触发条件 | 触发方 | 说明 |
|---------|--------|------|
| suri 分析角色调用模式 | suri | 检测到重复操作 → 建议封装新工具 |
| 角色通过 role.skill_need 申请 | 角色 | 能力缺口 → 申请新工具 |
| 用户直接提出需求 | 用户 | 自然语言对话 → suri 分析开发 |
| 插件升级 | plugin_manager | 插件升级时更新声明工具 |
| 工具废弃 | suri | 工具不再被使用 → 标记 DEPRECATED |
| 自我性能分析 | 插件 | 检测到瓶颈 → 优化工具 |

## 五、工具注册流程（含广播）

```
新工具准备就绪
    │
    ▼
suri 或插件注册工具到 mcp_framework
    │
    ▼
mcp_framework 做三件事：
  1. 写入 Tool Registry（含 input_schema + call_count 初始化）
  2. 更新内存缓存
  3. 发布 tool.registered 事件（含完整 tool_catalog）
    │
    ▼
所有订阅方接收事件：
  ├── suri 评估：是否需要更新角色技能映射
  ├── 插件刷新可用工具列表
  └── 用户可见的通知（通过 access 层）
```

## 六、工具废弃流程（含迁移）

```
suri 发现工具不再被使用（或用户要求废弃）
    │
    ▼
工具标记为 DEPRECATED
    │
    ▼
mcp_framework：
  1. 更新 Tool Registry（status=deprecated）
  2. 发布 tool.deprecated 事件（含替代工具名）
  3. 保留但标记 DEPRECATED（角色查询可见）

版本迁移周期：
  1. DEPRECATED 标记保留 2 个主版本
  2. 2 个主版本后自动移除（从 Tool Registry 删除）
  3. 移除前发布 tool.removed 事件
```

## 七、工具发现机制

```
角色需要某工具时：
  1. 查询 mcp_framework 能力索引
  2. 按 name、tags、capability 过滤
  3. 获取匹配的工具元数据（参数 schema、描述）
  4. 优先推荐调用统计高、成功率高的工具

mcp_framework 提供以下查询接口：
  list_tools():                  # 列出所有可用工具
  list_tools_by_plugin(id):     # 按插件查询
  find_tool(name):               # 按名称查找
  search_tools(keywords):        # 按关键词搜索
  get_tool_schema(tool_name):    # 获取工具参数 schema
  get_hot_tools(n):             # 热工具排行榜
  get_unused_tools(days):        # 废弃候选列表
```

## 八、工具与 code_tool 的边界

| 维度 | code_tool | mcp_framework 工具 |
|------|-----------|-------------------|
| 用途 | 文件系统操作 | 通用能力调用 |
| 调用方式 | 插件内部方法 | 事件驱动 tool.call |
| 注册方式 | 插件内固定 | 动态注册/发现 |
| 版本管理 | 随插件版本 | 独立版本管理 in Tool Registry |
| 外部依赖 | 无 | 可依赖外部 MCP 服务 |
| 调用统计 | 无 | Tool Registry 自动记录 |
| 广播通知 | 无 | 变更时自动广播 |

> code_tool 是 mcp_framework 的特殊实现：它是文件系统操作的内建工具，注册到 mcp_framework 的 Tool Registry 中，因此角色可通过统一的 tool.call 事件调用 code_tool。

## 九、四维协同进化中的工具维度

工具进化与其他三个维度的互动：

```
工具进化（新增 search_files）
    │
    ▼
更新 Tool Registry
    │
    ▼
广播 tool.registered
    │
    ├──→ 角色层：skill 匹配新工具 → 自动在能力范围内使用
    ├──→ 插件层：提供该工具的插件记录调用统计
    └──→ Soul 层：无需变更（Soul 不感知具体工具）
```