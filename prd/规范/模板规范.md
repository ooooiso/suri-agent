# 模板规范

> 定义 `tool_descriptions.yaml` 和 `task_templates.yaml` 两个模板的标准格式和使用规范。

---

## 一、模板概览

| 模板文件 | 位置 | 用途 | 谁来注册 |
|---------|------|------|---------|
| `tool_descriptions.yaml` | `~/.suri/data/templates/` | 记录**每个角色能做什么** | 角色创建/技能新增时自动注册 |
| `task_templates.yaml` | `~/.suri/data/templates/` | 记录**每个工具能做什么、怎么做** | 插件启动时自动注册 |

**核心规则**：
- 这两个模板由 `template_updater` 服务自动维护
- 任何角色/插件启动时通过事件注册技能/工具
- 不需要手动编辑

---

## 二、tool_descriptions.yaml 规范

**用途**：告诉 suri 和角色"当前系统有哪些角色，每个角色能做什么"

### 2.1 标准格式

```yaml
# tool_descriptions.yaml
# 记录所有角色的技能。由 template_updater 自动维护。

tools:
  - name: "component_generation"
    role_id: "frontend_dev"
    description: "根据需求生成前端组件代码，支持 React/Vue"
    triggers:
      - "生成组件"
      - "创建组件"
      - "开发组件"
    parameters:
      framework: ["React", "Vue"]
      style: ["CSS", "Styled Components"]
  
  - name: "document_writing"
    role_id: "doc_writer"
    description: "撰写产品文档、技术文档、API 文档"
    triggers:
      - "写文档"
      - "撰写文档"
      - "产品文档"
      - "技术文档"
    parameters:
      doc_type: ["产品文档", "技术文档", "API 文档", "用户手册"]
      format: ["Markdown", "Word", "PDF"]
  
  - name: "task_dispatch"
    role_id: "suri"
    description: "将任务分配给最合适的角色"
    triggers:
      - "分配任务"
      - "找人做"
      - "安排"
    parameters: {}
```

### 2.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 技能名称，全局唯一 |
| `role_id` | string | ✅ | 拥有该技能的角色 ID |
| `description` | string | ✅ | 技能描述，用于 LLM 理解 |
| `triggers` | string[] | ✅ | 触发词，帮助 suri 匹配用户需求 |
| `parameters` | object | ❌ | 技能参数，帮助 LLM 精确调用 |

### 2.3 注册方式

```python
# 角色创建时由 role_manager 自动注册
await self._event_bus.publish(Event(
    event_type="role.skill_registered",
    source="role_manager",
    payload={
        "role_id": "doc_writer",
        "skills": [
            {
                "name": "document_writing",
                "description": "撰写产品文档、技术文档、API 文档",
                "triggers": ["写文档", "撰写文档"],
                "parameters": {
                    "doc_type": ["产品文档", "技术文档"],
                }
            }
        ],
    },
))
```

---

## 三、task_templates.yaml 规范

**用途**：告诉 task_planner "每个工具能做什么、怎么做"

### 3.1 标准格式

```yaml
# task_templates.yaml
# 记录所有工具的功能模板。由 template_updater 自动维护。

templates:
  - template_id: "code_tool.read_file"
    plugin_id: "code_tool"
    name: "读取文件内容"
    description: "读取指定文件的内容并返回"
    keywords:
      - "读文件"
      - "查看文件"
      - "打开文件"
    steps:
      - description: "调用文件读取方法"
        tool_call: "code_tool.read_file"
        parameters:
          path: "{file_path}"
    priority: 10

  - template_id: "code_tool.search_files"
    plugin_id: "code_tool"
    name: "搜索文件内容"
    description: "在代码库中搜索指定模式"
    keywords:
      - "搜索"
      - "查找"
      - "搜索代码"
    steps:
      - description: "调用文件搜索方法"
        tool_call: "code_tool.search_files"
        parameters:
          pattern: "{search_pattern}"
          path: "{search_path}"
    priority: 10

  - template_id: "llm_gateway.chat"
    plugin_id: "llm_gateway"
    name: "调用大模型聊天"
    description: "向大模型发送消息并获取回复"
    keywords:
      - "聊天"
      - "询问"
      - "LLM"
    steps:
      - description: "发送 LLM 请求"
        tool_call: "llm_gateway.chat"
        parameters:
          model: "{model}"
          messages: "{messages}"
    priority: 10
```

### 3.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `template_id` | string | ✅ | 模板 ID，全局唯一，格式：`{plugin_id}.{action}` |
| `plugin_id` | string | ✅ | 提供该工具的插件 ID |
| `name` | string | ✅ | 模板名称 |
| `description` | string | ✅ | 功能描述 |
| `keywords` | string[] | ✅ | 关键词，帮助 task_planner 匹配任务类型 |
| `steps` | object[] | ✅ | 执行步骤序列 |
| `steps[].description` | string | ✅ | 步骤描述 |
| `steps[].tool_call` | string | ❌ | 对应的工具调用（如有） |
| `steps[].parameters` | object | ❌ | 步骤参数模板 |
| `priority` | int | ❌ | 优先级（1-100，默认 50） |

### 3.3 注册方式

```python
# 插件启动时由插件自动注册
await self._event_bus.publish(Event(
    event_type="tool.registered",
    source="code_tool",
    payload={
        "plugin_id": "code_tool",
        "templates": [
            {
                "template_id": "code_tool.read_file",
                "name": "读取文件内容",
                "description": "读取指定文件的内容并返回",
                "keywords": ["读文件", "查看文件", "打开文件"],
                "steps": [
                    {
                        "description": "调用文件读取方法",
                        "tool_call": "code_tool.read_file",
                        "parameters": {"path": "{file_path}"}
                    }
                ],
                "priority": 10,
            }
        ],
    },
))
```

---

## 四、模板更新规则

### 4.1 自动更新流程

```
新角色创建 / 新技能注册 → role.skill_registered → template_updater
  → 读取 tool_descriptions.yaml
  → 去重（按 name 检查）
  → 追加新技能 → 写回 YAML
  → 发布 role_manager.templates_updated

新插件启动 / 新工具注册 → tool.registered → template_updater
  → 读取 task_templates.yaml
  → 去重（按 template_id 检查）
  → 追加新模板 → 写回 YAML
  → 发布 task_planner.templates_updated
```

### 4.2 去重规则

| 模板 | 去重键 | 规则 |
|------|--------|------|
| tool_descriptions.yaml | `name` | 先注册优先 |
| task_templates.yaml | `template_id` | 先注册优先 |

### 4.3 强制覆盖

当需要强制覆盖时，注册事件携带 `force: True` 参数：

```python
payload = {
    "plugin_id": "code_tool",
    "force": True,   # 强制覆盖已存在条目
    "templates": [...]
}
```

---

## 五、文件位置

```
~/.suri/data/templates/
├── tool_descriptions.yaml    # 角色技能 → 自动更新
├── task_templates.yaml       # 工具功能 → 自动更新
└── soul_template.md          # 角色 Soul 模板 → 手动编辑
```

### 仓库中的模板副本

代码仓库 `~/.suri/data/templates/` 下的 YAML 文件作为**初始种子数据**和**显式参考**存在。运行时自动更新以该路径下的文件为准。

### soul_template.md（手动编辑）

`soul_template.md` 是角色灵魂的模板文件，用于 suri 创建新角色时生成 Soul 草案。由于角色类型相对固定，此模板变动频率低，手动编辑即可。

---

## 六、常见问题

### Q: 如果两个角色注册了相同名称的技能怎么办？
A: 按先注册优先原则，后注册的会被跳过。建议使用 `{role_id}.{skill_name}` 命名避免冲突。

### Q: 如果工具改名了怎么更新？
A: 使用 `force=True` 注册新模板替代旧的。

### Q: 模板文件被人为修改后会被覆盖吗？
A: 不会。template_updater 会检查去重，不会覆盖已有条目。如果手动增加了条目，template_updater 会保留它们。

### Q: 如何查看当前已注册的所有技能？
A: 直接查看 `~/.suri/data/templates/tool_descriptions.yaml`。
