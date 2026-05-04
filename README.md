# Suri Agent

> 单进程插件化 AI Agent 框架。零外部依赖，macOS 优先。

## 快速开始

```bash
# 1. 配置 API Key（至少填一个）
cp .env.example .env
# 编辑 .env 填入 SURI_DEEPSEEK_API_KEY 或其他

# 2. 启动
python main.py

# 3. CLI 交互
> help          # 查看命令
> llm.list      # 列出模型
> llm.switch deepseek deepseek-chat
> tool code_tool.list_dir path=agent_framework/
> exit
```

## 架构

- **内核层**：`agent_framework/core/` — EventBus + PluginManager + SuriCorePlugin
- **插件层**：`agent_framework/plugins/` — 12 个插件，通过事件总线通信
- **共享层**：`agent_framework/shared/` — PluginInterface + Event 类型定义
- **角色层**：`roles/` — 角色 Soul 模板（Git 管理，换设备 git clone 全回来）

```
agent_framework/
├── core/suri_core/          ← 自举内核
├── event_bus/               ← 异步事件总线
├── plugin_manager/          ← 插件生命周期管理
├── shared/                  ← 接口定义 + 事件类型
├── migrations/              ← SQLite 迁移脚本
└── plugins/                 ← 12 个插件实现
    ├── access/              # CLI/Telegram 接入
    ├── code_tool/           # 文件读写/搜索
    ├── llm_gateway/         # 5 家国内 LLM 路由
    ├── role_manager/        # 角色 CRUD/Soul 解析
    ├── task_planner/        # 任务分解
    ├── task_scheduler/      # 任务调度
    ├── security_service/    # 权限沙箱
    ├── config_service/      # 配置管理
    ├── log_service/         # 日志记录
    ├── agent_registry/      # Agent 生命周期
    ├── interrupt_handler/   # 中断/重试
    └── test_framework/      # 测试基础设施
```

## 迭代 1 功能

- 终端 CLI 接入
- 5 家国内 LLM 路由（DeepSeek / ChatGLM / Kimi / 通义 / 文心）
- 代码工具（read_file / list_dir / grep / stat_project / write_file）
- 配置服务、日志服务、安全沙箱
- 核心角色 suri 自动创建

## 测试

```bash
# 运行全部 169 个测试
python3 -m pytest tests/ -v

# 或使用 unittest
python3 -m unittest discover tests -v
```

## 零依赖

仅使用 Python 标准库：asyncio、sqlite3、pathlib、urllib、ssl、ast、unittest。