# Suri 智能体平台

## 简介

Suri 是一个基于角色（Agent）和技能（Skill）的自动化工作流智能体平台。所有配置采用 Markdown + YAML 元信息格式，人类可读、程序可解析。

## 架构概览

```
项目根目录
├── config.yaml          # Hermes 框架主配置
├── .env                 # 敏感环境变量
├── .SOUL.md             # suri 核心人格
├── state.db             # SQLite 会话与记忆数据库
├── manifest/                # 平台配置根目录
│   ├── rules/           # 全局规则（调度、安全、通信、模型等）
│   ├── process/         # 标准流程（工作流、变更审批）
│   ├── communication/   # 通信适配器配置
│   ├── models/          # 模型池
│   ├── memory/          # 记忆策略
│   ├── templates/       # 文件模板
│   └── docs/            # 文档
├── profiles/            # 角色实例根目录
│   ├── manifest/            # suri 自身配置
│   ├── art_director/    # 设计部
│   ├── dev_lead/        # 开发部
│   ├── ops_admin/       # 运维部
│   ├── file_admin/      # 资源部
│   ├── hr_admin/        # 人力资源部
│   └── _archived/       # 已注销角色存档
├── skills/              # suri 专属技能库
├── tools/               # 公共自定义工具库
├── hooks/               # 事件钩子
├── cron/                # 定时任务
├── logs/                # 运行日志
├── sessions/            # 会话记录
├── memories/            # 全局长期记忆
├── cache/               # 缓存
└── temp/                # 临时文件
```

## 快速入门

1. 配置 `.env` 中的 API Key 和 Telegram Bot Token。
2. 在 `manifest/models/model_pool.md` 中确认可用模型。
3. 配置 `manifest/communication/telegram.md` 中的群组 ID。
4. 运行启动命令（由主程序提供）。

## 核心规则概要

- **调度唯一入口**：所有需求由 suri 接收，下发给部门总监。
- **安全审批**：文件修改需变更报告 → security_admin 审核 → 用户确认。
- **通信纪律**：跨部门协作必须总监对总监，抄送调度群。
- **文件即真相**：调度、安全、权限均通过读取配置文件实现。

## 角色列表

见 `manifest/docs/roles_mapping.md` 和 `manifest/function_index.md`。
