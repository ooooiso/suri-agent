# 模板自动更新机制

> 定义 suri-agent 中模板的自动更新规则。
>
> **核心原则**：需要自动更新的模板只有两个：
> 1. **角色能做什么**（`tool_descriptions.yaml`）— 每个角色注册自己的技能
> 2. **工具里有什么**（`task_templates.yaml`）— 每个工具注册自己的功能

---

## 一、问题域

当前模板内容需要**人工编辑**。当系统新增以下内容时，模板需要自动更新：

| 新增内容 | 影响的模板 | 当前状态 |
|---------|-----------|---------|
| 新角色创建 | `tool_descriptions.yaml` | ❌ 需手动编辑 |
| 新工具注册 | `task_templates.yaml` | ❌ 需手动编辑 |

**不需要自动更新的**：
- `soul_template.md` — 很少变，手动编辑即可
- 其他配置 — 各自插件管理

---

## 二、核心机制：事件驱动的模板自动更新

### 2.1 角色技能注册 → 自动更新 tool_descriptions.yaml

**用途**：告诉系统"每个角色能做什么"

```
新角色创建 / 角色新增技能
    │
    ├─ 角色/role_manager 发布 role.skill_registered 事件
    │   payload: {
    │       "role_id": "frontend_dev",
    │       "skills": [
    │           {
    │               "name": "component_generation",
    │               "description": "根据需求生成前端组件代码",
    │               "triggers": ["生成组件", "创建组件", "开发组件"],
    │               "parameters": {
    │                   "framework": ["React", "Vue"],
    │                   "style": ["CSS", "Styled Components"]
    │               }
    │           }
    │       ]
    │   }
    │
    ▼
template_updater 服务
    │
    ├─ 接收 role.skill_registered 事件
    ├─ 读取 ~/.suri/data/templates/tool_descriptions.yaml
    ├─ 检查技能是否已存在（按 name 去重）
    ├─ 追加新技能到 tools 列表
    └─ 写回 YAML 文件
    │
    ▼
发布 role_manager.templates_updated 事件
    │
    ▼
role_manager 重新加载模板
    ├─ 下次 LLM 请求自动包含新技能
    └─ 无需重启
```

### 2.2 工具功能注册 → 自动更新 task_templates.yaml

**用途**：告诉系统"每个工具能做什么、怎么做"

```
新插件启动 / 插件注册新工具
    │
    ├─ 插件发布 tool.registered 事件
    │   payload: {
    │       "plugin_id": "code_tool",
    │       "templates": [
    │           {
    │               "template_id": "code_tool.read_file",
    │               "name": "读取文件内容",
    │               "keywords": ["读文件", "查看文件", "打开文件"],
    │               "steps": [
    │                   {"description": "调用 reader.read_file()", "tool_call": "code_tool.read_file"}
    │               ],
    │               "priority": 10
    │           }
    │       ]
    │   }
    │
    ▼
template_updater 服务
    │
    ├─ 接收 tool.registered 事件／注册 事件
    ├─ 读取 ~/.suri/data/templates/task_templates.yaml
    ├─ 检查模板是否已存在（按 template_id 去重）
    ├─ 追加新模板到 templates 列表
    └─ 写回 YAML 文件
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

---

## 三、template_updater 服务

### 3.1 定位

`template_updater` 是一个**轻量级服务**，负责：

1. 监听角色技能注册事件 → 更新 `tool_descriptions.yaml`
2. 监听工具功能注册事件 → 更新 `task_templates.yaml`
3. 发布热更新事件通知相关插件刷新

### 3.2 接口设计

```python
class TemplateUpdater:
    """模板自动更新服务"""
    
    async def on_skill_registered(self, event: Event):
        """角色技能注册 → 更新 tool_descriptions.yaml"""
        role_id = event.payload["role_id"]
        skills = event.payload["skills"]
        
        yaml_path = self.TOOL_DESC_PATH
        existing = self._load_yaml(yaml_path)
        existing_skills = existing.get("tools", [])
        
        # 去重：按 name 去重
        existing_names = {s["name"] for s in existing_skills}
        new_skills = [s for s in skills if s["name"] not in existing_names]
        
        if new_skills:
            existing["tools"].extend(new_skills)
            self._save_yaml(yaml_path, existing)
            # 通知 role_manager 刷新
            await self._event_bus.publish(Event(
                event_type="role_manager.templates_updated",
                source="template_updater",
                payload={"updated_by": "skill_registered", "role_id": role_id},
            ))
    
    async def on_tool_registered(self, event: Event):
        """工具注册 → 更新 task_templates.yaml"""
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
                payload={"updated_by": "tool_registered", "plugin_id": plugin_id},
            ))
```

### 3.3 事件订阅

```python
def register_events(self):
    self._event_bus.subscribe("role.skill_registered", self.on_skill_registered)
    self._event_bus.subscribe("tool.registered", self.on_tool_registered)
```

---

## 四、注册流程

### 4.1 角色创建时注册技能

```python
class RoleManager:
    async def create_role(self, role_id, soul_content):
        # 创建角色...
        
        # 注册角色技能
        await self._event_bus.publish(Event(
            event_type="role.skill_registered",
            source=self.name,
            payload={
                "role_id": role_id,
                "skills": [
                    {
                        "name": soul_content["capabilities"][0],
                        "description": "根据角色 Soul 生成",
                        "triggers": soul_content["keywords"],
                    }
                ],
            },
        ))
```

### 4.2 插件启动时注册工具

```python
class MyPlugin(PluginInterface):
    async def start(self):
        # 注册工具功能
        await self._event_bus.publish(Event(
            event_type="tool.registered",
            source=self.name,
            payload={
                "plugin_id": self.name,
                "templates": [
                    {
                        "template_id": "my_plugin.do_something",
                        "name": "执行某操作",
                        "keywords": ["关键词1", "关键词2"],
                        "steps": [
                            {"description": "步骤1"},
                        ],
                        "priority": 10,
                    }
                ],
            },
        ))
```

### 4.3 完整事件流

```
新角色/新插件启动
    │
    ├─ role.skill_registered ──→ template_updater ──→ 更新 tool_descriptions.yaml
    │                                                      │
    │                                                      ▼
    │                                               role_manager.templates_updated
    │                                                      │
    │                                                      ▼
    │                                               role_manager 重新加载
    │
    └─ tool.registered ──→ template_updater ──→ 更新 task_templates.yaml
                                                         │
                                                         ▼
                                                  task_planner.templates_updated
                                                         │
                                                         ▼
                                                  task_planner 重新加载
```

---

## 五、去重与冲突处理

### 5.1 去重规则

| 模板类型 | 去重键 | 冲突处理 |
|---------|--------|---------|
| 角色技能 | `name` | 已存在则跳过（先注册优先） |
| 工具模板 | `template_id` | 已存在则跳过（先注册优先） |

### 5.2 优先级覆盖

如果插件需要覆盖已有模板，可以设置 `force=True`：

```python
await self._event_bus.publish(Event(
    event_type="tool.registered",
    source=self.name,
    payload={
        "plugin_id": self.name,
        "force": True,  # 强制覆盖已存在的模板
        "templates": [...],
    },
))
```

`template_updater` 处理 `force=True` 时，直接替换同名条目。

---

## 六、与现有架构的关系

### 6.1 新增组件

```
agent_framework/
└── template_updater/           # 新增：模板自动更新服务
    ├── __init__.py
    └── plugin.py               # 服务实现

~/.suri/data/templates/         # 已有：外部模板目录
├── tool_descriptions.yaml      # 角色技能 → 自动更新
├── task_templates.yaml         # 工具功能 → 自动更新
└── soul_template.md            # 手动编辑（很少变）
```

### 6.2 不修改现有插件

`template_updater` 是**新增服务**，不修改任何现有插件的代码。现有插件只需在创建角色/启动时按规范发布注册事件即可。
