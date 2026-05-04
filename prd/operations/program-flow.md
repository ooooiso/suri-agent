# 程序工作流

> 描述 suri-agent 框架/程序层面的运转流程。所有流程由角色通过调用插件能力完成，和程序无关。

---

## 1. 系统启动流程

```
用户执行 suri-agent
    │
    ▼
解压运行时文件到 /tmp/suri-agent/
    │
    ▼
main.py 入口执行
    │
    ▼
实例化 SuriCorePlugin
    │
    ▼
bootstrap()：
  ├─ 创建 EventBus
  ├─ 创建 PluginManager
  ├─ 自注册 suri_core
  └─ 扫描 plugins/ 和 ~/.suri/runtime/plugins/
    │
    ▼
按依赖拓扑顺序加载插件：
  1. 基础服务层（config_service / log_service / security_service）
  2. 执行层（task_scheduler / task_planner / agent_registry / role_comm / interrupt_handler）
  3. 能力层（llm_gateway / memory_service / role_manager / role_learner / mcp_framework / upgrade_manager）
  4. 接入层（access）
  5. 扩展层（cron_service / hooks_service / test_framework / doc_sync）
    │
    ▼
发布 system.started 事件
    │
    ▼
系统就绪，等待用户输入
```

## 2. 事件处理主循环

```
EventBus 运行中
    │
    ├── 接收事件（publish）
    │       │
    │       ▼
    │   匹配订阅者（通配符支持）
    │       │
    │       ├── 有订阅者 ──▶ 分发给所有匹配订阅者（4 worker 并行）
    │       │
    │       └── 无订阅者 ──▶ 记录丢弃日志
    │
    ├── 高优先级事件持久化到 SQLite
    │
    └── 心跳检测（核心插件 5s / 普通插件 30s）
            │
            └── 超时 ──▶ 标记 ERROR，发布 error.plugin 事件
```

## 3. 插件加载流程

```
PluginManager 扫描目录
    │
    ▼
发现新插件目录
    │
    ▼
读取 manifest.json
    │
    ▼
AST 安全扫描
    │
    ├── 发现危险操作 ──▶ 拒绝加载，发布 error.plugin 事件
    │
    └── 通过 ──▶ 继续
    │
    ▼
检查依赖是否已加载
    │
    ├── 依赖缺失 ──▶ 延迟加载（等待依赖就绪）
    │
    └── 依赖就绪 ──▶ 继续
    │
    ▼
调用 plugin.init(event_bus, config)
    │
    ▼
插件注册订阅事件
    │
    ▼
调用 plugin.start()
    │
    ▼
发布 system.plugin_loaded 事件
    │
    ▼
插件进入运行状态
```

## 4. 插件卸载流程

```
卸载请求（系统关闭或动态卸载）
    │
    ▼
按依赖反向顺序卸载
    │
    ▼
调用 plugin.stop()
    │
    ▼
注销事件订阅
    │
    ▼
调用 plugin.cleanup()
    │
    ▼
从内存和 SQLite 注册表移除
    │
    ▼
发布 system.plugin_unloaded 事件
```

## 5. 系统关闭流程

```
关闭信号（用户退出或 system.shutdown 事件）
    │
    ▼
停止接收新用户输入
    │
    ▼
等待运行中任务完成（或超时强制终止）
    │
    ▼
按依赖反向卸载所有插件
    │
    ▼
关闭 EventBus
    │
    ▼
归档会话日志
    │
    ▼
清理临时文件（/tmp/suri-agent/）
    │
    ▼
系统退出
```

## 6. 配置热更新流程

```
用户或插件修改配置
    │
    ▼
config_service 检测变更
    │
    ▼
发布 system.config_changed 事件
    │
    ▼
各插件订阅接收
    │
    ▼
插件按需重新加载配置子树
    │
    ▼
无需重启生效
```

## 7. 错误处理流程

```
插件异常
    │
    ▼
捕获异常，隔离影响范围
    │
    ▼
发布 error.plugin / error.system 事件
    │
    ▼
log_service 记录详细错误信息
    │
    ▼
suri_core 判断处理策略：
  ├─ 可恢复 ──▶ 插件自动重启 / 降级运行
  ├─ 严重错误 ──▶ 标记插件 ERROR，停止事件分发
  └─ 系统级 ──▶ 触发 system.shutdown
```