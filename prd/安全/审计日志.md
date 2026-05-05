# 审计追溯

> 定义系统操作日志和审计追溯机制。

---

## 一、审计事件

| 事件类型 | 记录内容 |
|----------|---------|
| `role.created` | 角色创建：谁创建了哪个角色 |
| `role.deleted` | 角色删除：谁删除了哪个角色 |
| `role.upgraded` | 角色升级：升级了什么技能 |
| `task.*` | 任务执行：谁执行了什么任务 |
| `config.changed` | 配置变更：谁修改了什么配置 |
| `plugin.*` | 插件操作：谁安装了/卸载了插件 |
| `security.*` | 安全事件：权限越界、失败尝试 |

## 二、审计存储

审计日志存储在 `~/.suri/data/audit/`：

```yaml
~/.suri/data/audit/
├── YYYY-MM-DD.jsonl    # 每日审计日志（JSONL 格式）
└── index.db            # SQLite 索引，快速查询
```

## 三、审计查询

```python
# 查询某个角色的所有操作
audit.query(role_id="doc_writer")

# 查询某个时间范围
audit.query(start="2024-01-01", end="2024-06-01")

# 查询特定事件类型
audit.query(event_type="role.created")
