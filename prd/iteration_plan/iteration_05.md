# 迭代 5：工具扩展 + 运维完善

> 接入完整工具框架，完善运维能力，系统达到生产可用。

---

## 目标

1. 角色可调用丰富的外部工具（文件读写、网络搜索、数据库查询、命令执行）
2. 定时任务调度
3. 完整的事件钩子拦截扩展
4. 生产级监控、备份、恢复、热重载
5. 支持第三方插件开发

---

## 包含插件（3 个新增）

| # | 插件 | 说明 |
|---|------|------|
| 1 | **mcp_framework** | MCP 工具服务框架、内置工具注册、远程服务调用 |
| 2 | **cron_service** | 定时任务调度、crontab 风格规则、补偿触发 |
| 3 | **hooks_service**（完整版） | 事件钩子拦截、文件操作回调、任务钩子、扩展点 |

## 完善（多项）

| # | 能力 | 说明 |
|---|------|------|
| 4 | **完整 security_service** | AST 扫描器完善、文件沙箱 enforcement、资源限制、审批令牌 |
| 5 | **完整 deployment** | systemd、备份/恢复自动化、监控指标、告警规则、日志轮转 |
| 6 | **数据库迁移** | migration 脚本完整、版本控制、回滚 |
| 7 | **插件热重载** | 开发模式 watch、运行时动态加载/卸载 |
| 8 | **plugin_development.md 验证** | 所有共享模块、脚手架、调试工具可用 |

---

## 核心功能链路

### 1. 完整工具调用

```
角色需要查询数据库
    │
    ▼
调用 mcp_framework.tool.call(db_query, sql="SELECT ...")
    │
    ▼
mcp_framework 校验权限（security_service）
    │
    ▼
路由到具体工具执行 → 返回结果
    │
    ▼
记录调用审计日志
```

### 2. 定时任务

```
用户配置定时规则（或 role 自动配置）
    │
    ▼
cron_service 加载规则
    │
    ▼
按时触发 cron.{rule_id} 事件
    │
    ▼
目标角色订阅并执行
    │
    ├─ 定时备份
    ├─ 定时健康检查
    ├─ 定时全局分析（ProgramLearner）
    └─ 定时清理旧日志
```

### 3. 完整事件钩子

```
hooks_service 订阅所有系统事件（通配符）
    │
    ▼
关键操作前后插入钩子
    │
    ├─ 文件变更前 → security_service 审批检查
    ├─ 任务完成后 → doc_sync 文档检查
    ├─ 插件加载后 → test_framework smoke test
    ├─ 代码写入前 → lint 检查
    └─ 错误发生后 → 自动告警通知
```

---

## 开发任务分解

### Week 1：mcp_framework + cron_service

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| mcp_framework 插件 | `plugins/mcp_framework/plugin.py` | mcp_framework.md |
| MCP Server | `plugins/mcp_framework/server.py` | mcp_framework.md §MCP Server |
| MCP Client | `plugins/mcp_framework/client.py` | mcp_framework.md §MCP Client |
| 工具注册中心 | `plugins/mcp_framework/registry.py` | mcp_framework.md §Registry |
| 内置工具 | `plugins/mcp_framework/services/` | mcp_framework.md §内置服务 |
| 远程服务连接 | `plugins/mcp_framework/remote.py` | mcp_framework.md §远程 Server |
| cron_service 插件 | `plugins/cron_service/plugin.py` | cron_service.md |
| 定时调度器 | `plugins/cron_service/scheduler.py` | cron_service.md §定时调度 |
| 规则存储 | `plugins/cron_service/store.py` | cron_service.md §规则持久化 |

### Week 2：hooks_service + 运维完善

| 任务 | 输出文件 | 参考 PRD |
|------|----------|----------|
| hooks_service 插件（完整） | `plugins/hooks_service/plugin.py` | hooks_service.md |
| 钩子注册器 | `plugins/hooks_service/registry.py` | hooks_service.md §钩子注册 |
| 拦截器 | `plugins/hooks_service/interceptor.py` | hooks_service.md §拦截语义 |
| 扩展点定义 | `plugins/hooks_service/extension_points.py` | hooks_service.md §扩展点 |
| 完整 AST 扫描器 | `plugins/security_service/ast_scanner.py` | security_spec.md §AST 扫描器 |
| 文件沙箱 enforcement | `plugins/security_service/sandbox.py` | security_spec.md §文件沙箱 |
| 资源限制 | `plugins/security_service/resource_limiter.py` | security_spec.md §资源限制 |
| 审批令牌 | `plugins/security_service/token_manager.py` | security_spec.md §审批令牌 |
| systemd unit | `deployment.md §systemd` | deployment.md |
| 备份脚本 | `scripts/backup.py` | deployment.md §备份策略 |
| 恢复脚本 | `scripts/restore.py` | deployment.md §恢复流程 |
| 监控端点 | `plugins/access/health.py` | deployment.md §健康检查 |
| 热重载 | `agent_framework/plugin_manager/hot_reload.py` | plugin_development.md §热重载 |
| 数据库迁移 CLI | `scripts/migrate.py` | database_schema.md §迁移策略 |
| 插件脚手架 | `scripts/create_plugin.py` | plugin_development.md §插件脚手架 |

---

## 测试矩阵

| 测试项 | 通过标准 |
|--------|----------|
| 工具调用 | 角色能调用文件读写、搜索、数据库查询等工具 |
| 权限控制 | 禁止工具越权访问沙箱外目录 |
| 远程服务 | 能连接远程 MCP Server 并调用工具 |
| 定时任务 | crontab 规则按时触发，支持补偿 |
| 事件钩子 | 钩子能在关键事件前后正确执行，可阻止事件传播 |
| 备份恢复 | 自动备份能完整恢复系统状态 |
| 健康检查 | `/health` 端点返回正确状态 |
| 热重载 | 插件文件变更后自动重载，不影响运行中任务 |
| 迁移回滚 | 数据库迁移和回滚脚本正确执行 |
| 脚手架 | `create_plugin.py` 能生成完整插件模板 |

---

## 迭代 5 结束时系统状态

- 20 个插件全部可用，代码能力完整（读/写/执行/分析/升级）
- 所有 PRD 文档已实现并回归验证
- suri 具备完整的自我进化能力：
  - 读取自身代码和 PRD
  - 分析瓶颈、生成优化方案
  - 执行代码变更、测试验证、失败回滚
  - 从经验学习、技能形成、持续进化
- 具备生产部署能力（systemd、监控、备份）
- 插件开发规范完整，支持第三方开发
