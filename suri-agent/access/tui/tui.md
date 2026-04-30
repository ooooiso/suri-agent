# tui/

终端用户界面（Terminal User Interface）：命令行交互入口。

## 功能

- `cli.py` — 终端命令行客户端，直接调用 suri-agent 核心服务
- `server.py` — JSON-RPC 服务端，供后台 daemon 调用
- `rpc_methods.py` — RPC 方法定义
- `middleware.py` — 请求中间件

## 事件记录

- 新增模型管理集成（model_manager 初始化、首次运行引导）
- 新增 /model 系列命令（add/set/del/list）
- 新增 /sync 文档同步命令
- 新增 /reload 服务重载命令
- 新增代码变更检测机制（_compute_code_snapshot / _check_code_change）
- 未配置模型时阻止普通输入，引导用户配置
