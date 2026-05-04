# 程序工作流

> 描述 suri-agent 框架/程序层面的运转流程。所有流程由角色通过调用插件能力完成，和程序无关。

---

## 0. 三层上下文隔离总览

> 角色的上下文和记忆分为三层：Ad-hoc（临时会话）/ Project（项目工作）/ Global（全局记忆）。
> 所有流程中涉及角色上下文的地方，都遵循这三层隔离原则。
> **详细定义及完整存储路径见 `prd/overview/terminology.md §三层数据分离`。**
> 本文档仅说明各流程涉及上下文时如何应用这三层隔离。

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
  └─ 递归扫描插件目录（规则见下方说明）
    │
    ▼
按依赖拓扑顺序加载插件：
  1. 基础服务层（无依赖）
     config_service → log_service → security_service
  
  2. 能力层（依赖基础服务）
     llm_gateway → memory_service → role_manager
     → role_learner → mcp_framework → upgrade_manager
  
  3. 执行层（依赖能力层）
     task_scheduler → task_planner → agent_registry
     → role_comm → interrupt_handler → code_tool
  
  4. 接入层（依赖执行层）
     access（加载 CLI 和 Telegram 通道）
  
  5. 扩展层（可选依赖）
     cron_service → hooks_service → test_framework → doc_sync
    │
    ▼
发布 system.started 事件
    │
    ▼
系统就绪，等待用户输入
```

**说明**：加载顺序基于**依赖拓扑排序**而非固定层级。上图层级仅为视觉分组。依赖解析由 PluginManager 的拓扑排序算法自动完成。

### 插件扫描规则

```
PluginManager 扫描目录
    │
    ├── 扫描路径 1：agent_framework/plugins/{type}/{name}/
    │   └── 这是唯一的标准插件路径
    │
    ├── 扫描路径 2：~/.suri/runtime/agent_framework/plugins/{type}/{name}/
    │   └── 用户安装的自定义插件
    │   └── 优先级高于 agent_framework/plugins/（同名覆盖）
    │
    ├── 已废弃路径：plugins/（顶层目录）
    │   └── 旧代码过渡，新插件不要创建在此目录
    │
    ├── type 解析规则：
    │   └── type 从 manifest.json 的 "type" 字段读取
    │   └── 目录位置仅用于组织，不用于确定 type
    │
    ├── 同名冲突规则：
    │   └── runtime 目录的插件覆盖 agent_framework/ 的同名插件
    │   └── （用户自定义优先）
    │
    └── AST 安全扫描：
         ├── 发现危险操作 ──▶ 拒绝加载，发布 error.plugin 事件
         └── 通过 ──▶ 继续加载
```

---

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
    │       │       │
    │       │       └── 订阅者按 project_id 过滤（如需）
    │       │            事件 payload 中的 isolation_layer/project_id 用于隔离
    │       │            插件声明只接收特定 project_id 的事件
    │       │
    │       └── 无订阅者 ──▶ 记录丢弃日志（LOW 优先级可丢弃）
    │
    ├── 高优先级事件持久化到 SQLite
    │   （核心事件如 user.input/system.started 持久化，重启重放）
    │
    └── 心跳检测（核心插件 5s / 普通插件 30s）
            │
            └── 超时 ──▶ 标记 ERROR，发布 error.plugin 事件
```

### 事件隔离规则

```
当三层上下文隔离启用时：
  - 事件 payload 中的 project_id 用于路由
  - 插件可以声明只接收特定 project_id 的事件
  - 角色在 Ad-hoc 层只会收到 Ad-hoc 相关事件
  - Project A 的事件不会路由到 Project B
```

---

## 3. 插件加载流程

```
PluginManager 扫描目录
    │
    ▼
发现新插件目录（规则见上方"插件扫描规则"）
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
更新 Plugin Registry
    │
    ▼
插件进入运行状态
```

---

## 4. 插件卸载流程（含依赖检查）

```
卸载请求（系统关闭或动态卸载）
    │
    ▼
检查卸载前置条件：
    │
    ├── 1. 检查是否有其他插件依赖此插件
    │       ├── 有依赖 → 拒绝卸载，发布 error.unload_rejected
    │       │             通知用户：插件 B 依赖此插件
    │       └── 无依赖 → 继续
    │
    ├── 2. 检查是否有未完成的事件处理链
    │       ├── 有事件处理中 → 等待完成（或超时强制停止）
    │       └── 无事件处理中 → 继续
    │
    ├── 3. 检查是否有其他插件正在使用此插件的数据
    │       ├── 有使用中 → 标记为"待卸载"，依赖方结束后再卸载
    │       └── 无使用中 → 继续
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
从内存和 Plugin Registry 移除
    │
    ▼
发布 system.plugin_unloaded 事件
```

---

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
按依赖反向卸载所有插件（含依赖检查，见上方规范）
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

---

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

---

## 7. 错误处理流程

```
插件异常
    │
    ▼
EventBus 自动捕获异常（不扩散到其他插件）
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

---

## 8. 角色休眠/恢复流程

> 角色自动休眠：idle 30 分钟后自动暂停，释放资源。
> 恢复：收到消息时自动重建上下文。

```
角色持续 idle 30 分钟
    │
    ▼
发布 role.status_suspended 事件（状态标记为 suspended）
    │
    ▼
序列化当前上下文到 ~/.suri/runtime/roles/{role_id}/context/snapshot.json
    │
    ▼
关闭角色 DB 连接（资源释放）
    │
    ▼
------------------------（休眠中）------------------------
    │
收到角色相关事件（如 role.message_received）
    │
    ▼
发布 role.status_activating 事件（状态标记为 activating）
    │
    ▼
从 snapshot.json 恢复上下文
    │
    ▼
重新建立角色 DB 连接（定位到上次 session/project）
    │
    ▼
发布 role.status_ready 事件（状态恢复为 ready）
    │
    ▼
处理事件（LLM 调用、回复等）
```

**休眠与 archived/deleted 的区别**：

| 状态 | 触发条件 | 数据保留 | 可恢复 |
|------|----------|---------|--------|
| `suspended` | idle 30 分钟 | ✅ 全部保留 | ✅ 立即恢复 |
| `archived` | idle 30 天 | ✅ 数据保留 | ⚠️ 需手动恢复 |
| `deleted` | 用户手动 | ❌ 全部删除 | ❌ 不可恢复 |