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
> tool code_tool.list_dir path=plugins/
> exit
```

## 架构

- **内核层**：`agent_framework/` — EventBus + PluginManager + SuriCorePlugin
- **插件层**：`plugins/` — 21 个插件，通过事件总线通信
- **共享层**：`shared/` — PluginInterface + Event 类型定义
- **角色层**：`roles/` — 角色 Soul 模板（运行时复制到 `~/.suri/runtime/roles/`）

## 迭代 1 功能

- 终端 CLI 接入
- 5 家国内 LLM 路由（DeepSeek / ChatGLM / Kimi / 通义 / 文心）
- 只读代码工具（read_file / list_dir / grep / stat_project）
- 配置服务、日志服务、安全沙箱
- 核心角色 suri 自动创建

## 测试

```bash
python -m unittest discover tests -v
```

## 零依赖

仅使用 Python 标准库：asyncio、sqlite3、pathlib、urllib、ssl、ast、unittest。
