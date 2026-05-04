# 启动流程

> 描述 suri-agent 从 main.py 入口到系统就绪的完整启动流程。

---

## 一、入口文件（main.py）

```python
# main.py（极简入口，< 20 行）
from agent_framework.core.suri_core.plugin import SuriCorePlugin

async def main():
    core = SuriCorePlugin()
    await core.bootstrap()
    await core.wait_until_shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

**main.py 的设计原则**：
- 极简入口，不包含任何业务逻辑
- 不做配置读取、环境检测、参数解析
- 将这些职责交给 suri_core 处理
- 只负责实例化 SuriCorePlugin 并调用 bootstrap

---

## 二、启动序列（SuriCorePlugin.bootstrap）

```
main.py
    │
    ▼
SuriCorePlugin.__init__()
  ├── 加载自身配置（manifest.json）
  ├── 初始化基础数据
  └── 准备 EventBus 和 PluginManager
    │
    ▼
SuriCorePlugin.bootstrap()
  Step 1: 创建 EventBus
  │   └── 初始化 asyncio.Queue，准备内部订阅分发
  │
  Step 2: 创建 PluginManager
  │   └── 初始化插件目录（agent_framework/plugins/ + ~/.suri/runtime/agent_framework/plugins/）
  │
  Step 3: 自注册 suri_core 为第一个插件
  │   └── 通过 PluginManager.register_plugin() 注册自身
  │
  Step 4: 启动 EventBus
  │   └── 开始事件循环，监听和分发事件
  │
  Step 5: 加载基础服务插件
  │   ├── config_service（配置读取 + 热加载）
  │   ├── log_service（日志初始化）
  │   └── security_service（安全策略加载）
  │
  Step 6: 加载核心能力插件
  │   ├── llm_gateway（LLM 连接初始化）
  │   ├── role_manager（角色数据加载）
  │   └── agent_registry（Agent 状态恢复）
  │
  Step 7: 加载执行层插件
  │   ├── task_planner（任务模板加载）
  │   ├── task_scheduler（调度队列初始化）
  │   └── interrupt_handler（中断策略加载）
  │
  Step 8: 恢复角色状态
  │   ├── 读取 roles/ 中的角色数据（Soul 文件、技能、记忆）
  │   ├── 恢复 suri 的会话上下文
  │   └── 重置所有角色状态为 ready
  │
  Step 9: 加载接入层
  │   └── access（CLI / Telegram 通道初始化）
  │
  Step 10: 加载扩展层
  │   └── test_framework, cron_service, hooks_service, doc_sync
  │
  Step 11: 广播 system.started
  │   └── 通知所有插件：系统已就绪
  │
  ▼
系统就绪，等待用户事件
```

---

## 三、插件加载顺序

| 阶段 | 加载的插件 | 依赖关系 |
|------|-----------|---------|
| 0 | suri_core（自注册） | 无，自举 |
| 1 | config_service, log_service, security_service | 无 |
| 2 | llm_gateway, role_manager, agent_registry | 依赖 config_service |
| 3 | task_planner, task_scheduler, interrupt_handler | 依赖 role_manager |
| 4 | memory_service, role_learner, mcp_framework | 依赖 agent_registry |
| 5 | role_comm, code_tool | 无特殊依赖 |
| 6 | access | 依赖所有上层 |
| 7 | test_framework, cron_service, hooks_service, doc_sync | 无特殊依赖 |

**依赖检查**：每个插件在 init 时通过 manifest.json 的 requires_interfaces 声明依赖，PluginManager 在加载时检查依赖是否满足。

---

## 四、启动自检（Post-bootstrap Healthcheck）

suri_core 在 bootstrap() 完成后、广播 system.started 之前，执行启动自检：

```
自检流程（bootstrap Step 11.5）
    │
    ├── 1) 环境自检
    │   ├── 检查 ~/.suri/ 目录完整性
    │   ├──   ├── config.json 是否存在
    │   │   └── 缺失 → 创建配置向导
    │   ├── 检查 ~/.suri/runtime/ 目录
    │   │   ├── roles/ 目录是否存在
    │   │   ├── works/ 目录是否存在
    │   │   └── 缺失 → 自动创建
    │   └── 检查 ~/.suri/backup/ 目录是否存在
    │
    ├── 2) 角色自检
    │   ├── 扫描 roles/ 目录
    │   ├── 检查 suri 角色是否存在
    │   │   ├── 存在 → 验证 Soul 文件完整性
    │   │   └── 不存在 → 创建默认 suri 角色
    │   ├── 检查每个角色的技能文件是否存在（skills/ 目录）
    │   └── 检查角色技能引用的插件是否已安装
    │       ├── 全部已加载 → 通过
    │       └── 有缺失 → 记录 warning，suri 启动后自动处理
    │
    ├── 3) 项目自检
    │   ├── 扫描 works/ 目录
    │   └── 检查每个项目的元数据完整性
    │       ├── 项目关联的角色是否存在
    │       └── 项目文件完整性
    │
    ├── 4) 插件自检
    │   ├── 统计已加载插件数量
    │   ├── 检查核心插件是否全部就绪（config/log/security/llm/role_manager）
    │   └── 检查每个插件的心跳是否正常
    │
    ├── 5) 数据库自检
    │   ├── 检查 SQLite 文件可读写
    │   ├── 检查 schema 版本（~/.suri/runtime/schema_version）
    │   │   ├── 版本一致 → 通过
    │   │   └── 版本落后 → 自动执行迁移脚本
    │   └── 检查数据库是否锁定
    │
    ├── 6) 配置自检
    │   ├── LLM 配置检查
    │   │   ├── config.json 有 API Key → 通过
    │   │   └── 无 Key / Key 无效 → 弹出配置向导 / 通知用户
    │   ├── 接入通道检查
    │   │   ├── CLI 通道默认启用
    │   │   └── Telegram 通道若配置则验证 bot token
    │   └── 资源限制检查
    │       └── 磁盘空间、内存可用性
    │
    ├── 7) 汇总报告
    │   ├── 生成健康报告
    │   └── 如果有任何警告/错误 → 记录日志
    │
    ▼
广播 system.started → 系统就绪
```

### 自检结果处理

```
健康报告等级：
  ├── ✅ 全部通过 → 直接进入就绪状态
  ├── ⚠️ 有警告（非关键问题）→ 进入就绪状态，suri 自动处理
  │   ├── 缺失非核心插件
  │   ├── 角色技能引用缺失插件
  │   └── 项目元数据不完整
  └── ❌ 有致命错误 → 阻止启动，向用户报告
      ├── LLM 配置完全缺失
      ├── suri 角色文件损坏且无模板可用
      ├── SQLite 无法读写
      └── suri_core 内核插件加载失败
```

---

## 五、热重启

```python
SuriCorePlugin.hot_restart()
  ├── 暂停事件分发
  ├── 通知所有插件：system.restarting
  ├── 逐一执行插件的 prepare_restart()
  ├── 重新加载配置（config_service 热读取）
  ├── 逐一执行插件的 hot_restart()
  ├── 恢复事件分发
  └── 广播 system.restarted
```

**热重启 vs 冷启动**：
| 特性 | 热重启 | 冷启动 |
|------|--------|--------|
| 角色状态 | 保留 | 恢复 |
| 会话上下文 | 保留 | 重新加载 |
| 插件状态 | 保留 | 重新初始化 |
| 内存数据 | 保留 | 重建 |
| 耗时 | < 1s | 1-5s |

---

## 六、关闭流程

```python
SuriCorePlugin.shutdown()
  ├── 广播 system.shutting_down
  ├── 逐一切换插件状态：运行 → 暂停
  │   └── 等待当前事务完成（warm）或立即停止（cold）
  ├── 保存角色运行时状态
  │   ├── 序列化角色上下文
  │   ├── 写入 roles/{role_id}/memories/
  │   └── 关闭 SQLite 连接
  ├── 停止 EventBus
  └── 广播 system.shutdown_complete