# 全局文件使用说明

## 目录结构总览

```
项目根目录
├── config.yaml              # Hermes 框架主配置（config_admin）
├── .env                     # 敏感环境变量（config_admin，权限 600）
├── .SOUL.md                 # suri 核心人格（config_admin）
├── state.db                 # SQLite 数据库（suri）
│
├── manifest/                    # 【平台配置根目录】（config_admin）
│   ├── suri.md              # 平台主配置
│   ├── function_index.md    # 部门职能索引
│   ├── rules/               # 全局规则（security_admin / 各规则 owner）
│   ├── process/             # 标准流程（workflow_admin）
│   ├── communication/       # 通信配置（config_admin）
│   ├── models/              # 模型池（config_admin）
│   ├── memory/              # 记忆策略（config_admin）
│   ├── templates/           # 模板文件（hr_admin）
│   └── docs/                # 文档（config_admin / git_admin）
│
├── profiles/                # 【角色实例根目录】（hr_admin / 角色自身）
│   ├── <role_id>/           # 单个角色文件夹
│   │   ├── <role_id>.md     # Soul 文件
│   │   ├── skills/          # 技能包
│   │   ├── memories/        # 私人长期记忆
│   │   └── reference/       # 个人文件权限地图
│   └── _archived/           # 已注销角色存档（file_admin）
│
├── skills/                  # 【suri 专属技能库】（suri）
│   ├── skills.md            # 技能索引
│   └── <skill_name>/        # 具体技能包
│
├── tools/                   # 【公共工具库】（config_admin / 开发部）
│   ├── tool_registry.md     # 工具注册索引
│   └── <tool_name>/         # 具体工具包
│
├── hooks/                   # 事件钩子（ops_admin）
├── cron/                    # 定时任务（ops_admin）
├── logs/                    # 运行日志（file_admin）
├── sessions/                # 会话记录（suri）
├── memories/                # 全局长期记忆（suri）
├── cache/                   # 缓存（file_admin）
└── temp/                    # 临时文件（file_admin）
```

## 管理角色与权限速查

| 目录/文件 | 控制角色 | 说明 |
|-----------|---------|------|
| `manifest/` | config_admin | 平台主配置 |
| `manifest/rules/` | security_admin | 安全规则 |
| `manifest/process/` | workflow_admin | 流程定义 |
| `profiles/<role>/` | 角色自身 / hr_admin | 角色管理 |
| `profiles/<role>/memories/` | 角色自身 | 私人记忆 |
| `skills/` | suri | suri 专属技能 |
| `tools/` | config_admin | 公共工具库 |
| `hooks/` | ops_admin | 事件钩子 |
| `logs/`, `cache/`, `temp/` | file_admin | 资源管理 |
| `config.yaml`, `.env`, `.SOUL.md` | config_admin | 框架核心配置 |
| `state.db` | suri | 数据库 |

## 文件操作审批

所有对上述目录的修改均需走 `manifest/process/change_approval.md` 流程：
准备报告 → security_admin 审核 → suri 请求用户确认 → 执行 → 记录 changelog。
