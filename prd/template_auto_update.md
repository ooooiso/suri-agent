# 模板自动更新机制

> 定义 suri-agent 中所有模板如何根据新技能、新工具、新角色自动更新。

---

## 一、问题域

当前迭代 2 已完成模板外部化（YAML/Markdown 文件），但模板内容仍需要**人工编辑**。当系统新增以下内容时，模板需要自动更新：

| 新增内容 | 影响的模板 | 当前状态 |
|---------|-----------|---------|
| 新插件注册新工具 | `tool_descriptions.yaml` | ❌ 需手动编辑 |
| 新插件注册任务模板 | `task_templates.yaml` | ❌ 需手动编辑 |
| 新角色创建 | `soul_template.md`（不变） | ✅ 已自动 |
| 新中断类型 | `interrupt_keywords.yaml` | ❌ 需手动编辑 |

---

## 二、核心机制：事件驱动的模板自动更新

### 2.1 工具注册 → 自动更新 tool_descriptions.yaml

```
新插件启动时注册工具
    │
    ├─ 插件发布 tool.registered 事件
    │   payload: {
    │       "plugin_id": "my_plugin",
    │       "tools": [
    │           {
    │               "name": "my_plugin.do_something",
    │               "description": "执行某操作",
    │               "parameters": [...],
    │               "example": "..."
    │           }
    │       ]
    │   }
    │
    ▼
template_updater 服务（新增组件）
    │
    ├─ 接收 tool.registered 事件
    ├─ 读取 ~/.suri/data/templates/tool_descriptions.yaml
    ├─ 检查工具是否已存在（按 name 去重）
    ├─ 追加新工具到 tools 列表
    ├─ 写回 YAML 文件
    │
    ▼
发布 role_manager.templates_updated 事件
    │
    ▼
role_manager 重新加载模板
    ├─ 下次 LLM 请求自动包含新工具
    └─ 无需重启
```

### 2.2 插件注册任务模板 → 自动更新 task_templates.yaml

```
插件启动时注册任务模板
    │
    ├─ 插件发布 task_planner.register_rules 事件
    │   payload: {
    │       "plugin_id": "my_plugin",
    │       "templates": [
    │           {
    │               "template_id": "my_plugin.some_task",
    │               "name": "某任务",
    │               "keywords": ["关键词1", "关键词2"],
    │               "steps": [...],
    │               "priority": 10
    │           }
    │       ]
    │   }
    │
    ▼
template_updater 服务
    │
    ├─ 接收 register_rules 事件
    ├─ 读取 ~/.suri/data/templates/task_templates.yaml
    ├─ 检查模板是否已存在（按 template_id 去重）
    ├─ 追加新模板到 templates 列表
    ├─ 写回 YAML 文件
    │
    ▼
发布 task_planner.templates_updated 事件
    │
    ▼
task_planner 重新加载模板
    ├─ 保留内置模板（不可覆盖）
    ├─ 合并外部模板
    └─ 更新内存索引
```

### 2.3 新中断类型 → 自动更新 interrupt_keywords.yaml

```
插件注册新中断类型
    │
    ├─ 插件发布 interrupt_handler.register_keywords 事件
    │   payload: {
    │       "plugin_id": "my_plugin",
    │       "keywords": {
    │           "new_interrupt_type": ["关键词1", "关键词2"]
    │       }
    │   }
    │
    ▼
template_updater 服务
    │
    ├─ 接收 register_keywords 事件
    ├─ 读取 ~/.suri/data/configs/interrupt_keywords.yaml
    ├─ 检查类型是否已存在
    ├─ 追加新类型到 keywords 映射
    ├─ 写回 YAML 文件
    │
    ▼
发布 interrupt_handler.keywords_updated 事件
    │
    ▼
interrupt_handler 重新加载关键词
    ├─ 保留内置关键词（不可覆盖）
    ├─ 合并外部关键词
    └─ 更新内存索引
```

---

## 三、template_updater 服务设计

### 3.1 定位

`template_updater` 是一个**系统级服务**（非插件），负责：

1. 监听工具/模板/关键词注册事件
2. 自动更新对应的外部 YAML 文件
3. 发布热更新事件通知相关插件刷新

### 3.2 为什么不放在插件里？

| 方案 | 问题 |
|------|------|
| 放在 role_manager 里 | role_manager 职责膨胀，变成"万能管理器" |
| 放在 task_planner 里 | 只负责任务模板，不负责工具说明 |
| 放在 interrupt_handler 里 | 只负责关键词，不负责其他模板 |
| **独立 template_updater 服务** | **单一职责，统一管理所有模板的自动更新** |

### 3.3 接口设计

```python
class TemplateUpdater:
    """模板自动更新服务"""
    
    async def on_tool_registered(self, event: Event):
        """工具注册 → 更新 tool_descriptions.yaml"""
        plugin_id = event.payload["plugin_id"]
        tools = event.payload["tools"]
        
        yaml_path = self.TOOL_DESC_PATH
        existing = self._load_yaml(yaml_path)
        existing_tools = existing.get("tools", [])
        
        # 去重：按 name 去重
        existing_names = {t["name"] for t in existing_tools}
        new_tools = [t for t in tools if t["name"] not in existing_names]
        
        if new_tools:
            existing["tools"].extend(new_tools)
            self._save_yaml(yaml_path, existing)
            # 通知 role_manager 刷新
            await self._event_bus.publish(Event(
                event_type="role_manager.templates_updated",
                source="template_updater",
                payload={"updated_by": "tool_registered", "plugin_id": plugin_id},
            ))
    
    async def on_rules_registered(self, event: Event):
        """规则注册 → 更新 task_templates.yaml"""
        plugin_id = event.payload["plugin_id"]
        templates = event.payload["templates"]
        
        yaml_path = self.TASK_TEMPLATES_PATH
        existing = self._load_yaml(yaml_path)
        existing_templates = existing.get("templates", [])
        
        # 去重：按 template_id 去重
        existing_ids = {t["template_id"] for t in existing_templates}
        new_templates = [t for t in templates if t["template_id"] not in existing_ids]
        
        if new_templates:
            existing["templates"].extend(new_templates)
            self._save_yaml(yaml_path, existing)
            # 通知 task_planner 刷新
            await self._event_bus.publish(Event(
                event_type="task_planner.templates_updated",
                source="template_updater",
                payload={"updated_by": "rules_registered", "plugin_id": plugin_id},
            ))
    
    async def on_keywords_registered(self, event: Event):
        """关键词注册 → 更新 interrupt_keywords.yaml"""
        plugin_id = event.payload["plugin_id"]
        keywords = event.payload["keywords"]
        
        yaml_path = self.INTERRUPT_KEYWORDS_PATH
        existing = self._load_yaml(yaml_path)
        existing_keywords = existing.get("keywords", {})
        
        # 去重：按类型去重
        new_keywords = {
            k: v for k, v in keywords.items()
            if k not in existing_keywords
        }
        
        if new_keywords:
            existing["keywords"].update(new_keywords)
            self._save_yaml(yaml_path, existing)
            # 通知 interrupt_handler 刷新
            await self._event_bus.publish(Event(
                event_type="interrupt_handler.keywords_updated",
                source="template_updater",
                payload={"updated_by": "keywords_registered", "plugin_id": plugin_id},
            ))
```

### 3.4 事件订阅

```python
def register_events(self):
    self._event_bus.subscribe("tool.registered", self.on_tool_registered)
    self._event_bus.subscribe("task_planner.register_rules", self.on_rules_registered)
    self._event_bus.subscribe("interrupt_handler.register_keywords", self.on_keywords_registered)
```

---

## 四、插件注册新技能的标准流程

### 4.1 插件开发规范

每个插件在 `start()` 方法中注册自己的工具、模板和关键词：

```python
class MyNewPlugin(PluginInterface):
    async def start(self):
        # 1. 注册工具 → 自动更新 tool_descriptions.yaml
        await self._event_bus.publish(Event(
            event_type="tool.registered",
            source=self.name,
            payload={
                "plugin_id": self.name,
                "tools": [
                    {
                        "name": "my_plugin.do_something",
                        "description": "执行某操作",
                        "parameters": [
                            {"name": "param1", "description": "参数1", "required": True}
                        ],
                        "example": "tool my_plugin.do_something param1=value",
                    }
                ],
            },
        ))
        
        # 2. 注册任务模板 → 自动更新 task_templates.yaml
        await self._event_bus.publish(Event(
            event_type="task_planner.register_rules",
            source=self.name,
            payload={
                "plugin_id": self.name,
                "templates": [
                    {
                        "template_id": "my_plugin.some_task",
                        "name": "某任务",
                        "keywords": ["关键词1", "关键词2"],
                        "steps": [
                            {"description": "步骤1", "assignee": "suri"},
                            {"description": "步骤2", "assignee": "suri"},
                        ],
                        "default_role": "suri",
                        "priority": 10,
                    }
                ],
            },
        ))
        
        # 3. 注册中断关键词 → 自动更新 interrupt_keywords.yaml
        await self._event_bus.publish(Event(
            event_type="interrupt_handler.register_keywords",
            source=self.name,
            payload={
                "plugin_id": self.name,
                "keywords": {
                    "my_plugin_specific_error": ["特定错误", "specific error"],
                },
            },
        ))
```

### 4.2 完整流程

```
新插件 my_plugin 启动
    │
    ├─ start() 发布 tool.registered
    │   └─ template_updater → 更新 tool_descriptions.yaml → 通知 role_manager
    │
    ├─ start() 发布 task_planner.register_rules
    │   └─ template_updater → 更新 task_templates.yaml → 通知 task_planner
    │
    └─ start() 发布 interrupt_handler.register_keywords
        └─ template_updater → 更新 interrupt_keywords.yaml → 通知 interrupt_handler
    │
    ▼
所有模板自动更新完成
    ├─ 下次用户输入 → role_manager 加载新工具说明 → LLM 知道新工具
    ├─ 下次任务规划 → task_planner 加载新模板 → 匹配新任务类型
    └─ 下次中断 → interrupt_handler 加载新关键词 → 识别新中断类型
```

---

## 五、去重与冲突处理

### 5.1 去重规则

| 模板类型 | 去重键 | 冲突处理 |
|---------|--------|---------|
| 工具说明 | `name` | 已存在则跳过（先注册优先） |
| 任务模板 | `template_id` | 已存在则跳过（先注册优先） |
| 中断关键词 | 类型名（如 `missing_tool`） | 已存在则跳过（先注册优先） |

### 5.2 优先级覆盖

如果插件需要覆盖已有模板，可以设置 `force=True`：

```python
await self._event_bus.publish(Event(
    event_type="tool.registered",
    source=self.name,
    payload={
        "plugin_id": self.name,
        "force": True,  # 强制覆盖已有工具
        "tools": [...],
    },
))
```

`template_updater` 处理 `force=True` 时，直接替换同名条目。

### 5.3 冲突告警

当检测到关键词重叠时（如两个插件注册了相同的关键词），`template_updater` 打印告警：

```
[template_updater] ⚠️ 关键词冲突检测：
  - 类型 "missing_tool" 的关键词 "timeout" 也与 "dependency_failed" 重叠
  - 来源插件: my_plugin, interrupt_handler
  - 建议: 使用更精确的关键词避免误判
```

---

## 六、与现有架构的关系

### 6.1 新增组件

```
suri-agent/
├── plugins/
│   ├── template_updater/          # 新增：模板自动更新服务
│   │   ├── __init__.py
│   │   ├── plugin.py              # 服务实现
│   │   └── manifest.json
│   └── ...其他插件
├── ~/.suri/data/templates/        # 已有：外部模板目录
│   ├── tool_descriptions.yaml     # 自动更新
│   ├── task_templates.yaml        # 自动更新
│   └── soul_template.md           # 手动编辑（角色模板很少变）
└── ~/.suri/data/configs/
    └── interrupt_keywords.yaml    # 自动更新
```

### 6.2 不修改现有插件

`template_updater` 是**新增服务**，不修改任何现有插件的代码。现有插件只需在 `start()` 中按规范发布注册事件即可。

### 6.3 事件流总图

```
新插件启动
    │
    ├─ tool.registered ──→ template_updater ──→ 更新 tool_descriptions.yaml
    │                                                │
    │                                                ▼
    │                                         role_manager.templates_updated
    │                                                │
    │                                                ▼
    │                                         role_manager 重新加载
    │
    ├─ task_planner.register_rules ──→ template_updater ──→ 更新 task_templates.yaml
    │                                                          │
    │                                                          ▼
    │                                                   task_planner.templates_updated
    │                                                          │
    │                                                          ▼
    │                                                   task_planner 重新加载
    │
    └─ interrupt_handler.register_keywords ──→ template_updater ──→ 更新 interrupt_keywords.yaml
                                                                       │
                                                                       ▼
                                                                interrupt_handler.keywords_updated
                                                                       │
                                                                       ▼
                                                                interrupt_handler 重新加载
```

---

## 七、迭代计划

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **迭代 3** | 实现 template_updater 服务 | 迭代 2 的模板外部化已完成 |
| 迭代 3 | 现有插件按规范注册工具/模板/关键词 | 迭代 3 的 template_updater |
| 迭代 4 | 支持 force 覆盖和冲突告警 | 迭代 3 |
| 迭代 5 | 可视化模板管理（CLI 命令） | 迭代 4 |

---

## 八、总结

| 场景 | 当前（迭代 2） | 目标（迭代 3+） |
|------|--------------|----------------|
| 新插件注册工具 | 手动编辑 tool_descriptions.yaml | 自动更新 |
| 新插件注册任务模板 | 手动编辑 task_templates.yaml | 自动更新 |
| 新中断类型 | 手动编辑 interrupt_keywords.yaml | 自动更新 |
| 新角色创建 | 自动使用 soul_template.md | 不变（已自动） |
| 去重 | 无 | 按 name/template_id/类型去重 |
| 冲突检测 | 仅 interrupt_handler 有 | 统一在 template_updater 中 |