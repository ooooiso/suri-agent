# 部署指南

> 描述 suri-agent 的安装、配置、启动和升级流程。

---

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | macOS 12+（优先），Linux 兼容（预留） |
| Python | 3.11+ |
| 内存 | 最低 4GB，推荐 8GB |
| 磁盘 | 最低 1GB 可用空间 |
| 网络 | 可访问 LLM API（可选，支持本地模型） |

## 安装步骤

### 1. 下载

```bash
git clone https://github.com/xxx/suri-agent.git
cd suri-agent
```

### 2. 环境初始化

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖（零依赖设计，依赖极少）
pip install -r requirements.txt
```

**依赖清单**（`requirements.txt`）：
```
# 核心依赖（必选）
# Python 标准库即可运行核心功能

# 可选依赖
python-telegram-bot>=20.0  # Telegram 接入（可选）
aiohttp>=3.8.0             # Web/API 接入（可选）
requests>=2.28.0           # HTTP 调用（可选）
```

### 3. 目录结构检查

安装后应包含：
```
suri-agent/
├── .kimi/                 # AI 开发规范（开发时读取）
├── prd/                   # 产品文档（开发时读取）
├── agent_framework/       # 核心层代码
│   ├── __init__.py
│   ├── event_bus/
│   ├── plugin_manager/
│   └── suri_core_plugin.py
├── plugins/               # 插件目录
│   ├── suri_core/
│   ├── config_service/
│   ├── log_service/
│   ├── ...（20 个插件）
├── shared/                # 公共层
│   ├── interfaces/
│   └── utils/
├── roles/                 # 角色运行时数据
├── works/                 # 工作区
├── tests/                 # 测试
├── main.py                # 入口程序
└── requirements.txt
```

### 4. 配置文件初始化

首次运行前创建配置文件：

```bash
mkdir -p ~/.suri/data ~/.suri/runtime ~/.suri/backup
```

创建 `~/.suri/config.json`：

```json
{
  "suri_core": {
    "event_bus": {
      "queue_maxsize": 10000,
      "worker_count": 4,
      "persist": true
    },
    "plugin_manager": {
      "scan_dirs": ["plugins/"],
      "heartbeat_interval": 5,
      "heartbeat_timeout": 30
    }
  },
  "llm_gateway": {
    "default_model": "glm-4",
    "timeout": 60.0,
    "max_retries": 3
  },
  "access": {
    "channels": {
      "cli": { "enabled": true },
      "telegram": { "enabled": false, "bot_token": "" },
      "lark": { "enabled": false },
      "web": { "enabled": false },
      "api": { "enabled": false }
    }
  }
}
```

### 5. 环境变量（可选）

```bash
export SURI_DATA_DIR="~/.suri/data"
export SURI_LOG_LEVEL="INFO"
export TELEGRAM_BOT_TOKEN=""        # Telegram 接入时填写
export LARK_APP_ID=""               # 飞书接入时填写
export LARK_APP_SECRET=""
export LLM_API_KEY=""               # LLM 调用时填写
```

## 启动

### 首次启动

```bash
python main.py
# 或
suri
```

首次启动时（`~/.suri/config.json` 不存在）：
1. **弹出配置向导**（ConfigWizard）
   - 步骤 1：选择 LLM 厂商（DeepSeek / Kimi / ChatGLM / 通义 / 文心）
   - 步骤 2：输入 API Key（自动验证可用性）
   - 步骤 3：配置 Telegram Bot（可选，/skip 跳过）
   - 步骤 4：确认保存 → 生成 `~/.suri/config.json`
2. suri_core 自举注册
3. PluginManager 扫描并加载所有插件
4. 创建核心角色 suri（如不存在）
5. 初始化 SQLite 数据库
6. 启动 CLI（和 Telegram，如配置启用）

**跳过向导**：如不想走向导，可手动创建 `~/.suri/config.json`：
```json
{
  "llm_gateway": {
    "default_provider": "deepseek",
    "providers": {
      "deepseek": {
        "models": ["deepseek-v4-pro", "deepseek-v4-flash"],
        "base_url": "https://api.deepseek.com",
        "api_key": "YOUR_KEY_HERE"
      }
    }
  },
  "access": {
    "channels": {
      "cli": {"enabled": true},
      "telegram": {"enabled": false, "bot_token": ""}
    }
  }
}
```

### 开发模式启动

```bash
# 启用调试日志
SURI_LOG_LEVEL=DEBUG python main.py

# 仅加载指定插件
python main.py --plugins suri_core,config_service,log_service,access,llm_gateway

# 跳过 AST 扫描（开发调试用，生产禁用）
python main.py --skip-ast-scan
```

### 后台运行

```bash
# 使用 nohup
nohup python main.py > ~/.suri/runtime/suri.log 2>&1 &

# 或使用 systemd（Linux）
sudo systemctl start suri-agent
```

## 升级

### 代码升级

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 更新依赖（如有变化）
pip install -r requirements.txt

# 3. 重启服务
# 系统会自动执行插件 AST 扫描和加载
```

### 配置升级

```bash
# 配置变更自动热更新，无需重启
# 手动触发配置重载：
echo "/reload" | python main.py
```

### 数据库迁移

迁移策略：
1. **Schema 版本控制**：`~/.suri/runtime/schema_version` 记录当前数据库 schema 版本
2. **迁移脚本位置**：`agent_framework/migrations/{version}_{description}.sql`
3. **自动迁移流程**：`python main.py --migrate` 读取当前版本 → 按序执行缺失的 SQL 脚本 → 更新版本号
4. **回滚**：每个迁移脚本需包含对应的 `{version}_{description}_rollback.sql`

```bash
# 自动迁移
python main.py --migrate

# 查看当前 schema 版本
python main.py --schema-version

# 回滚到指定版本（谨慎操作）
python main.py --rollback-to 1.0.0
```

### systemd 服务（macOS/Linux）

```ini
# /etc/systemd/system/suri-agent.service
[Unit]
Description=Suri Agent
After=network.target

[Service]
Type=simple
User=suri
WorkingDirectory=/opt/suri-agent
Environment=PYTHONPATH=/opt/suri-agent
EnvironmentFile=/opt/suri-agent/.env
ExecStart=/usr/local/bin/python main.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 健康检查

```bash
# 内置健康检查端点（如启用 web 通道）
curl http://127.0.0.1:8080/health

# 返回示例
{"status":"healthy","plugins_loaded":20,"event_queue_depth":3,"last_heartbeat":"2024-01-15T10:00:00Z"}
```

### Graceful Restart

```
1. 发送 SIGTERM / systemctl reload suri-agent
2. 停止接收新输入（access 暂停）
3. 等待运行中任务完成（默认 30s 超时）
4. 卸载插件（逆依赖序）
5. 重启 suri_core（如需）
6. 重新加载插件
7. 恢复输入通道
```

## 运维规范

### 备份策略

| 数据 | 备份频率 | 保留期 | 命令 |
|------|----------|--------|------|
| 角色记忆 | 每日 | 30 天 | `tar czf backup/roles_$(date +%F).tar.gz ~/.suri/runtime/roles/` |
| 中央数据库 | 每日 | 30 天 | `cp ~/.suri/runtime/suri.db backup/suri_$(date +%F).db` |
| 配置 | 每次变更 | 10 份 | `cp ~/.suri/config.json backup/config_$(date +%F).json` |
| 升级报告 | 每次生成 | 永久 | 已存于 `~/.suri/data/upgrade_reports/` |

### 恢复流程

```bash
# 1. 停止服务
systemctl stop suri-agent

# 2. 恢复数据
cp backup/suri_2024-01-15.db ~/.suri/runtime/suri.db
tar xzf backup/roles_2024-01-15.tar.gz -C ~/.suri/runtime/

# 3. 验证 schema 版本
python main.py --schema-version

# 4. 启动服务
systemctl start suri-agent
```

### 监控指标

| 指标 | 采集方式 | 告警阈值 |
|------|----------|----------|
| 插件心跳间隔 | system.heartbeat 事件 | > 120s |
| EventBus 队列深度 | suri_core 内部计数 | > 8000 |
| 任务失败率 | task.failed / task.completed | > 10% |
| LLM 响应时间 | llm_gateway 内部统计 | > 30s |
| 磁盘使用率 | OS 监控 | > 85% |

### 日志轮转

```yaml
# log_service 配置
log_service:
  retention_days: 30
  max_file_size_mb: 100
  max_files_per_category: 10
```

## 故障排查

| 现象 | 排查步骤 |
|------|---------|
| 启动失败 | 检查 `~/.suri/` 目录权限；检查 config.json 格式 |
| 插件加载失败 | 查看 `~/.suri/runtime/logs/` 错误日志；检查插件 manifest.json |
| 事件不响应 | 检查 EventBus worker 状态；检查插件订阅事件是否正确 |
| 内存溢出 | 减少并发数；清理旧的 Agent 状态 |
| 数据库锁定 | 检查是否有其他进程占用 SQLite；启用 WAL 模式 |

## 迁移场景

> suri-agent 的核心优势：**角色（roles/）+ 项目（works/）与主程序完全解耦**，迁移只需复制业务数据。

### 迁移原则

```
主程序（框架 + 插件）= 可替换，可升级
角色数据（roles/）= 随 Git 管理，可迁移可回溯（含记忆/技能/Soul）
项目数据（works/）= 可迁移，可复制（含交付物/会话记录）
敏感配置（~/.suri/config.json）= 单独迁移
```

### 标准迁移步骤

```bash
# ═══════════════════════════════════════════════
# 场景 A：从旧机器迁移到新机器
# ═══════════════════════════════════════════════

# 【旧机器上】打包运行时数据
tar czf suri-runtime.tar.gz ~/.suri/runtime/

# 【新机器上】部署主程序
git clone https://github.com/xxxx/suri-agent.git
cd suri-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 【新机器上】还原运行时数据
mkdir -p ~/.suri/runtime
tar xzf suri-runtime.tar.gz -C ~/.suri/

# 【新机器上】启动（自动检测角色和项目）
python main.py

# ═══════════════════════════════════════════════
# 场景 B：整机迁移（含配置 + 记忆 + 升级记录）
# ═══════════════════════════════════════════════

# 打包整个 ~/.suri/
tar czf suri-full.tar.gz ~/.suri/

# 在新机器上解压到相同路径
tar xzf suri-full.tar.gz -C ~/

# 启动
python main.py

# ═══════════════════════════════════════════════
# 场景 C：只迁移特定角色
# ═══════════════════════════════════════════════

# 旧机器打包单个角色
tar czf suri-role-dev.tar.gz ~/.suri/runtime/roles/dev_writer/

# 新机器解压到对应目录
mkdir -p ~/.suri/runtime/roles/
tar xzf suri-role-dev.tar.gz -C ~/.suri/runtime/roles/

# 启动
python main.py
# suri 启动时自动检测到 dev_writer 角色 → 直接可用
```

### 迁移后自检

迁移完成后，suri 启动时自动执行：

```
suri 启动自检流程
    │
    ├── 检查 ~/.suri/runtime/roles/ 目录
    │   ├── 发现角色 → 验证 Soul 文件完整性
    │   └── 检查角色技能引用的插件是否已安装
    │       ├── 全部有 → 继续
    │       └── 有缺失 → 自动安装 / 通知用户
    │
    ├── 检查 ~/.suri/runtime/works/ 目录
    │   ├── 发现项目 → 验证元数据完整性
    │   └── 检查项目关联的角色是否存在
    │
    ├── 检查 ~/.suri/config.json
    │   └── 如果缺失 LLM 配置 → 弹出配置向导
    │
    └── 系统就绪
```

### 迁移注意事项

| 事项 | 说明 |
|------|------|
| Python 版本 | 确保新机器 Python ≥ 3.11 |
| SQLite 版本 | suri 使用 SQLite WAL 模式，无需额外数据库 |
| 插件版本 | 主程序插件版本可能更新，角色技能兼容性问题由 upgrade_manager 处理 |
| 网络环境 | 新机器需能访问 LLM API（或配置本地模型） |
| 文件权限 | `~/.suri/` 目录需要读写权限 |

### 回滚

```bash
# 如果新机器运行异常
# 1. 停止新机器上的服务
pkill -f "python main.py"

# 2. 检查旧机器是否还在运行
# 旧机器的数据不受影响，可直接继续使用

# 3. 排查问题
# 查看日志：~/.suri/runtime/logs/
# 常见问题：LLM API Key 未配置、插件版本不兼容
```

---

## 卸载

```bash
# 停止服务
pkill -f "python main.py"

# 删除数据（谨慎操作）
rm -rf ~/.suri/
rm -rf /tmp/suri-agent/
```