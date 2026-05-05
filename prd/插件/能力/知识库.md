# 知识库管理

> 定义跨角色共享知识的存储和管理机制。

---

## 一、知识库定位

```
记忆（角色级）       知识库（共享级）
  ├─ 角色经验          ├─ 最佳实践
  ├─ 角色偏好          ├─ 代码规范
  ├─ 角色模式          ├─ 业务知识
  └─ 学习成果          ├─ 技术文档
                       └─ 领域知识
```

## 二、知识来源

1. **角色贡献** — 角色通过 role_learner 生成的知识片段，沉淀到 Global 层
2. **用户输入** — 用户直接添加的知识
3. **文档同步** — doc_sync 从代码仓库同步的知识
4. **系统内置** — 系统预设的通用知识

## 三、三层隔离的知识访问

知识库遵循三层上下文隔离原则：

| 上下文层 | 知识范围 | 生命周期 | 共享范围 |
|---------|---------|---------|---------|
| **Ad-hoc 层** | 临时会话产生的知识片段 | 7天自动清理 | 仅当前会话内的角色 |
| **Project 层** | 项目专属知识（业务规则、设计决策） | 项目存续期 + 30天 | 项目内的所有角色 |
| **Global 层** | 跨项目通用知识（最佳实践、编码规范） | 永久（受遗忘约束） | 所有角色 |

### 项目级知识隔离

```
项目"电商APP"的知识库：
┌─────────────────────────────────┐
│ projects/ecommerce_app/        │
│   ├── knowledge/               │
│   │   ├── business_rules.md    │  ← 电商业务规则
│   │   ├── design_decisions.md  │  ← 设计决策记录
│   │   ├── api_contracts/       │  ← API 契约
│   │   └── db_schema.md         │  ← 数据库设计
│   └── shared_insights/         │  ← 组内洞察
└─────────────────────────────────┘

项目"内部工具"的知识库：
┌─────────────────────────────────┐
│ projects/internal_tools/       │
│   ├── knowledge/               │
│   │   ├── business_rules.md    │  ← 完全不同
│   │   └── deployment_guide.md  │
│   └── shared_insights/         │
└─────────────────────────────────┘

两个项目的知识库完全隔离：
  → 电商项目的角色看不到内部工具的知识
  → 切换项目时知识库自动切换
  → 跨项目知识引用需要显式授权
```

### 全局知识库

```
~/.suri/data/knowledge/            ← Global 层
├── best_practices/                # 最佳实践（所有项目共享）
│   ├── python_coding_standards.md
│   ├── api_design_principles.md
│   └── test_strategies.md
├── code_standards/                # 代码规范
├── domain_knowledge/              # 领域知识
└── shared_patterns/               # 共享模式

Global 层知识入库规则：
  - 必须经 role_learner 提炼为跨项目通用
  - 必须去除项目特异性信息
  - 由 suri 确认后才能进入全局库
```

## 四、知识库的查询机制

```python
class KnowledgeBase:
    def query(
        self,
        role_id: str,
        query: str,
        project_id: Optional[str] = None,  # ★ 项目过滤
        scope: str = "project_only"         # project_only | global_only | all
    ) -> List[Knowledge]:
        """
        查询知识库，按上下文过滤。
        
        查询策略：
          1. project_id 提供 → 优先查 Project 层知识
          2. scope = "all" → 合并 Project + Global 层结果
          3. scope = "global_only" → 只查全局知识
          4. scope = "project_only" → 只查项目知识
        """
        if project_id:
            project_knowledge = self._query_project_kb(project_id, query)
            
        if scope in ("global_only", "all"):
            global_knowledge = self._query_global_kb(query)
            
        return self._merge_and_rank(project_knowledge, global_knowledge)
```

## 五、存储

知识库存储在以下目录结构中：

```
~/.suri/data/
├── knowledge/                      # Global 层（跨项目共享）
│   ├── best_practices/
│   ├── code_standards/
│   ├── domain_knowledge/
│   └── shared_patterns/
│
└── projects/{project_id}/
    └── knowledge/                  # Project 层（项目隔离）
        ├── business_rules.md
        ├── design_decisions.md
        └── ...
```

## 六、与三清单联动

知识库的变更通过三清单广播通知：

```
知识更新
    │
    ├─ 1. 更新 Plugin Registry（记录知识库版本）
    ├─ 2. 发布 knowledge.updated 事件（带 scope 信息）
    ├─ 3. suri 接收事件 → 通知可能受到影响的角色
    ├─ 4. 角色在下次 LLM 调用时获取最新知识
    └─ 5. 用户可见的通知（新增了哪些知识）