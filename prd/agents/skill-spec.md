# Skill 开发规范

> 定义角色技能（Skill）的标准格式、注册方式和执行规范。
>
> **核心规则**：Skill 是角色的能力单元。每个 Skill 可独立开发、注册和升级。

---

## 一、Skill 文件格式

```json
{
  "skill_id": "document_writing",
  "name": "文档撰写",
  "version": "1.2.0",
  "description": "根据需求撰写产品文档和技术文档",
  "role_id": "doc_writer",
  "capabilities": [
    "撰写产品需求文档",
    "撰写技术文档",
    "撰写 API 文档",
    "文档格式转换"
  ],
  "triggers": ["写文档", "需求文档", "技术文档"],
  "parameters": {
    "doc_type": ["产品文档", "技术文档", "API 文档", "用户手册"],
    "format": ["Markdown", "Word", "PDF"]
  },
  "dependencies": ["code_tool", "llm_gateway"],
  "steps": [
    {
      "name": "分析需求",
      "tool_call": "llm_gateway.chat",
      "parameters": {}
    },
    {
      "name": "生成文档",
      "tool_call": null,
      "parameters": {}
    }
  ],
  "priority": 10
}
```

---

## 二、字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `skill_id` | string | ✅ | 全局唯一，格式：`{action}_{target}` |
| `name` | string | ✅ | 技能显示名称 |
| `version` | string | ✅ | 语义化版本 |
| `description` | string | ✅ | 技能描述 |
| `role_id` | string | ✅ | 所属角色 ID |
| `capabilities` | string[] | ✅ | 能力清单 |
| `triggers` | string[] | ✅ | 触发词，帮助匹配用户需求 |
| `parameters` | object | ❌ | 技能参数 |
| `dependencies` | string[] | ❌ | 依赖的插件 ID |
| `steps` | object[] | ✅ | 执行步骤序列 |
| `steps[].name` | string | ✅ | 步骤名称 |
| `steps[].tool_call` | string | ❌ | 对应的工具调用 |
| `steps[].parameters` | object | ❌ | 步骤参数 |
| `priority` | int | ❌ | 优先级（1-100，默认 50） |

---

## 三、Skill 命名规范

```
格式：{action}_{target}
示例：
- document_writing     → 撰写文档
- code_generation      → 生成代码
- data_analysis        → 数据分析
- api_testing          → API 测试
- code_review          → 代码审查
```

| 动词 | 目标 | Skill ID |
|------|------|----------|
| document | writing | `document_writing` |
| code | generation | `code_generation` |
| data | analysis | `data_analysis` |
| code | review | `code_review` |
| ui | design | `ui_design` |

---

## 四、Skill 注册流程

```
角色创建 / 技能新增
    │
    ▼
角色 / suri 发布 role.skill_registered 事件
    │
    ├─ payload: { role_id, skills: [...] }
    │
    ▼
template_updater 监听事件
    ├─ 读取 tool_descriptions.yaml
    ├─ 按 skill_id 去重（先注册优先）
    └─ 追加新技能 → 写回 YAML
    │
    ▼
发布 role_manager.templates_updated 事件
```

### 注册事件

```python
await self._event_bus.publish(Event(
    event_type="role.skill_registered",
    source="role_manager",
    payload={
        "role_id": "doc_writer",
        "skills": [
            {
                "skill_id": "document_writing",
                "name": "文档撰写",
                "description": "撰写产品文档和技术文档",
                "capabilities": ["产品文档", "技术文档"],
                "triggers": ["写文档"],
                "parameters": {},
            }
        ],
        "force": False,  # True 可强制覆盖
    },
))
```

---

## 五、Skill 升级流程

```
角色自学获得新能力
    │
    ▼
role_learner 生成升级建议
    ├─ aim: "新增 capability"
    ├─ type: "new_skill" / "upgrade_skill"
    ├─ proposal: { 新技能 / 技能改进的具体内容 }
    └─ confidence: 0-1
    │
    ▼
upgrade_manager 保存报告
    │
    ▼
suri 定期汇总 → 向用户提案
    │
    ▼
用户确认
    ├─ ✅ → role_manager.regist_skill()
    └─ ❌ → 丢弃提案
```

---

## 六、Skill 文件存储

```yaml
~/.suri/runtime/roles/{role_id}/skills/
├── document_writing.json
├── code_generation.json
└── ...
```

每个 Skill 文件是一个独立 JSON，可在角色间共享（通过 skill_id 引用）。
