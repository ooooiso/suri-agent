# 技能开发指南

> 指导如何为角色开发新技能。

---

## 一、开发流程

```
1. 确定技能目标
   └─ 角色需要什么能力？
       │
       ▼
2. 定义 Skill 文件
   └─ 参考 skill_spec.md 格式
       │
       ▼
3. 实现执行逻辑
   └─ 确定需要调用的插件/MCP 工具
       │
       ▼
4. 注册技能
   └─ 发布 role.skill_registered 事件
       │
       ▼
5. 验证技能
   └─ 角色执行测试任务
```

## 二、技能开发原则

1. **单一职责** — 每个技能只做一件事
2. **明确触发词** — 让 suri 能准确匹配用户需求
3. **声明依赖** — 明确需要的插件/MCP 工具
4. **版本可控** — 使用语义化版本
5. **可组合** — 技能间不应有硬编码依赖

## 三、示例

### 创建一个"前端组件生成"技能

```json
{
  "skill_id": "component_generation",
  "name": "前端组件生成",
  "version": "1.0.0",
  "description": "根据需求生成前端组件代码，支持 React/Vue",
  "role_id": "frontend_dev",
  "capabilities": ["React 组件", "Vue 组件", "CSS 样式"],
  "triggers": ["生成组件", "创建组件", "开发组件"],
  "parameters": {
    "framework": ["React", "Vue"],
    "style": ["CSS", "Styled Components"]
  },
  "dependencies": ["code_tool", "llm_gateway"],
  "steps": [
    {"name": "分析组件需求", "tool_call": "llm_gateway.chat", "parameters": {}},
    {"name": "生成组件代码", "tool_call": null, "parameters": {}},
    {"name": "写入文件", "tool_call": "code_tool.write_file", "parameters": {}}
  ],
  "priority": 10
}
