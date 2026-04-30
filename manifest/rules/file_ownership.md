---
rule_id: file_ownership
name: 文件所有权映射
version: "0.1.0"
owner: security_admin
last_updated: 2026-04-30
---

# 文件所有权映射

## 所有权清单

| 路径 | 控制角色 | 说明 |
|------|---------|------|
| `profiles/<role>/` | 角色自身 / hr_admin | 角色自身管理 Soul、技能、记忆；hr_admin 管理创建/注销 |
| `profiles/<role>/memories/` | 角色自身 | 私人长期记忆，修改需审批 |
| `profiles/<role>/skills/` | 角色自身 | 技能定义与脚本，修改需审批 |
| `profiles/<role>/reference/` | 角色自身 | 个人文件权限地图 |
| `profiles/_archived/` | file_admin | 已注销角色存档（保留30天） |
| `skills/` | suri | suri 专属技能库 |
| `tools/` | config_admin（维护） | 公共工具库，开发部可提议创建 |
| `tools/tool_registry.md` | config_admin | 工具注册索引 |
| `manifest/` | config_admin | 平台主配置 |
| `manifest/rules/` | security_admin | 安全规则 |
| `manifest/process/` | workflow_admin | 流程定义 |
| `manifest/communication/` | config_admin | 通信配置 |
| `manifest/models/` | config_admin | 模型池配置 |
| `manifest/memory/` | config_admin | 记忆策略配置 |
| `manifest/templates/` | hr_admin | 模板文件 |
| `manifest/docs/` | config_admin / git_admin | 文档与变更日志 |
| `suri-agent/` | config_admin | **主程序根目录（受保护，不可外部编辑）** |
| `suri-agent/access/` | config_admin | **接入层（受保护，不可外部编辑）** |
| `suri-agent/mcp/base.py` | config_admin | **MCP 框架基类（受保护）** |
| `suri-agent/mcp/registry.py` | config_admin | **MCP 注册中心（受保护）** |
| `suri-agent/mcp/services/` | 各服务开发者 | **MCP 具体服务（可自增长，可通过外部会话编辑补充）** |
| `hooks/` | ops_admin | 事件钩子 |
| `config.yaml` | config_admin | 框架主配置 |
| `.env` | config_admin | 环境变量（敏感信息） |
| `.SOUL.md` | config_admin | suri 核心人格 |
| `state.db` | suri | 会话与记忆数据库 |
| `logs/` | file_admin | 运行日志 |
| `sessions/` | suri | 会话记录 |
| `memories/`（全局） | suri | 全局长期记忆 |
| `cache/` | file_admin | 缓存目录 |
| `temp/` | file_admin | 临时文件 |
| `cron/` | ops_admin | 定时任务 |

## 校验规则

- 修改必须由**控制角色**发起或授权。
- 跨角色操作需获得目标文件控制角色的书面授权（在变更报告中明确）。
- 安全钩子实时校验，无权限操作被阻断并告警。
