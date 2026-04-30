# logs/

日志总目录：存放 suri 平台各类运行日志，按模块分类存储，按天轮转文件。

## 子目录

| 目录 | 用途 | 记录内容 |
|------|------|---------|
| `runtime/` | 程序运行日志 | 用户交互、模型调用、命令执行 |
| `error/` | 错误日志 | 异常、崩溃、API 调用失败 |
| `schedule/` | 调度日志 | 任务创建、角色间调度、任务状态变更 |
| `role/` | 角色通信日志 | 角色间消息、任务关联通信 |
| `system/` | 系统日志 | 启动、关闭、代码变更、服务重载 |

## 文件命名规则

每个子目录下按天创建文件：
```
logs/runtime/suri-2026-05-01.log
logs/error/suri-2026-05-01.log
logs/schedule/suri-2026-05-01.log
logs/role/suri-2026-05-01.log
logs/system/suri-2026-05-01.log
```

## 日志格式

```
[YYYY-MM-DD HH:MM:SS] [级别] [模块] 消息内容
```

级别：信息 / 警告 / 错误 / 调试

## 事件记录

- 初始创建，从 resources/logs/ 迁移至此
- 新增分类子目录：runtime、error、schedule、role、system
