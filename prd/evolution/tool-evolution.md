# 工具进化

> 定义 Tool 维度的进化机制 —— MCP 工具的注册、更新、废弃、自动同步。

---

## 一、工具来源

工具（Tool）是角色调用的能力单元，来源包括：

| 来源 | 说明 | 注册方式 |
|------|------|---------|
| **插件暴露** | 插件通过 manifest.json exposes.tools 声明 | 插件加载时自动注册 |
| **MCP 框架** | 通过 MCP 协议注册的外部工具 | mcp_framework 注册 |
| **suri 开发** | suri 为角色开发的专用工具 | suri 写入后注册 |
| **插件自进化** | 插件进化过程中新增的工具 | 自修改流程注册 |

---

## 二、工具生命周期

```
工具注册（tool.registered）
    │
    ▼
工具活跃（可使用）
    │
    ├── 被角色调用（tool.call / tool.result）
    │
    ├── 工具更新（tool.updated）
    │   ├── 参数变更
    │   ├── 逻辑优化
    │   └── 版本递进
    │
    ├── 工具废弃（tool.deprecated）
    │   └── 仍然可用，但建议迁移
    │
    └── 工具移除（tool.unregistered）
        └── 不再可用
```

---

## 三、工具注册

```
工具注册流程：
  1. 来源方生成工具定义（名称/描述/参数/返回格式）
  2. 写入 ~/.suri/data/templates/tool_descriptions.yaml
  3. 广播 tool.registered 事件
  4. 自动更新 tool_descriptions.yaml 索引
  5. 所有角色在下一次 llm.request 时获取最新工具列表

工具定义格式（YAML）：
  tool_name:
    description: "工具的用途描述"
    input_schema:
      type: object
      properties:
        param1:
          type: string
          description: "参数说明"
      required: ["param1"]
    output:
      type: object
      description: "返回值说明"
    visibility: "all | role:{role_type} | private"
    source: "plugin:{plugin_name} | mcp | suri"
```

---

## 四、工具更新

| 变更类型 | 兼容性 | 影响 |
|---------|--------|------|
| 新增可选参数 | 兼容 | 自动生效 |
| 修改参数描述 | 兼容 | 自动生效 |
| 新增必填参数 | 中断性变更 | 通知所有使用该工具的角色 |
| 删除参数 | 不兼容 | 回滚或用户决策 |
| 修改返回值格式 | 中断性变更 | 通知所有使用该工具的角色 |

**更新流程**：
1. 来源方提交工具更新
2. 更新 tool_descriptions.yaml 中的定义
3. 广播 tool.updated 事件（含变更摘要和兼容性评估）
4. 使用该工具的角色收到事件后：
   - 兼容：自动使用新定义
   - 中断性变更：当前步骤继续使用旧定义，新步骤使用新定义
   - 不兼容：suri 介入评估

---

## 五、工具废弃与移除

### 废弃流程

```
suri 或来源方决定废弃某个工具
    │
    ├── 标记 tool_descriptions.yaml 中为 deprecated
    ├── 广播 tool.deprecated（含替代方案和迁移期限）
    ├── 角色收到后在指定期限内迁移
    └── 过期后自动移除
```

### 移除流程

```
1. 确认无角色使用该工具（或已全部迁移）
2. 从 tool_descriptions.yaml 移除
3. 广播 tool.unregistered
4. 清理能力索引
```

---

## 六、tool_descriptions.yaml 自动同步

`~/.suri/data/templates/tool_descriptions.yaml` 是系统统一的工具描述文件，所有角色的工具列表从中读取。

**同步机制**：

```
工具变更（注册/更新/废弃/移除）
    │
    ▼
更新 tool_descriptions.yaml
    │
    ▼
广播相应事件（tool.registered / tool.updated 等）
    │
    ▼
各角色在下一次 llm.request 前
    ├── 重新读取 tool_descriptions.yaml
    └── 获取最新工具列表
```

**注意**：tool_descriptions.yaml 的变更不会影响正在执行的 tool call。当前步骤的工具调用使用步骤开始时加载的工具定义。新步骤使用最新的工具定义。

---

## 七、工具进化与四维协同

| 工具进化事件 | 触发方 | 影响方 |
|-------------|--------|--------|
| `tool.registered` | 插件/suri/MCP | 所有角色的工具列表更新 |
| `tool.updated` | 插件/suri/MCP | 使用该工具的角色 |
| `tool.deprecated` | suri | 使用该工具的角色 |
| `tool.unregistered` | suri | 能力索引清理 |
| `tool.call_failed` | 角色 | 工具来源方（分析改进） |

**工具进化 → 技能进化**：
- 新工具注册后，role_learner 可能检测到角色使用新工具的模式 → 生成新技能
- 工具废弃后，引用该工具的技能需要标记为需更新

**工具进化 → Soul 进化**：
- 大量新工具注册后，角色的 Soul 能力边界描述可能需要更新
- suri 主动检查和更新受影响角色的 Soul
