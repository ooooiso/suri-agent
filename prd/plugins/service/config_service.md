# config_service 插件 PRD

## 定位

统一配置中心插件，为所有插件提供配置读取、热更新、校验能力。配置优先级：环境变量 > `~/.suri/config.json` > 默认值。

## 功能需求

### 1. 配置加载
- 三层优先级合并：环境变量（SURI_* 前缀）> `~/.suri/config.json` > 代码默认值
- 支持点分路径访问：`platform.debug`、`event_bus.queue_maxsize`
- 环境变量自动类型解析：bool/int/float/str
- 启动时检查必填项，缺失则警告

### 2. 配置热更新
- 运行时修改 `config.json` 后，通过 `/reload` 或事件触发重新加载
- 插件无需重启即可获取新配置
- 变更事件广播：`system.config_changed`

### 3. 角色与插件配置扫描
- 扫描 `role/` 目录下所有 Soul 文件（YAML frontmatter + Markdown）
- 扫描 `~/.suri/runtime/plugins/` 下动态插件的 manifest
- 提供角色查询 API：list_roles / get_role_soul / resolve_role_id
- 别名映射系统（如旧名 → canonical id）

### 4. 路径管理
- 统一提供数据目录路径：`~/.suri/data/`、`~/.suri/runtime/`、`/tmp/suri-agent/`
- 确保目录存在

## 接口定义

### 订阅事件
- `system.config_changed` → 触发重新加载
- `user.command`（command=reload）→ 重新加载配置
- `user.command`（command=config.get）→ 查询配置项
- `user.command`（command=config.set）→ 设置配置项并保存

### 发布事件
- `system.config_changed` → 广播配置变更

### 命令处理

#### `/config [key]`
| 参数 | 说明 |
|------|------|
| `key` | 可选。点分路径，如 `llm_gateway.default_provider`。省略时返回全部配置 |

**示例**：
```bash
/config                    # 查看全部配置
/config llm_gateway.default_provider
```

**说明**：`/config` 命令为只读查询。配置修改通过 `/setkey`（修改 API Key）和 `/reconfig`（配置菜单）完成。

## 配置项

```yaml
config_service:
  config_path: "~/.suri/config.json"
  auto_reload: true
  required_paths:
    - "platform.name"
```

## 事件 Payload Schema

### 订阅事件

#### `system.started`
触发配置加载，无特定 payload。

### 发布事件

#### `system.config_changed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 配置变更影响的插件 ID，"*" 表示全局 |
| `changed_keys` | array | 是 | 变更的配置键列表 |
| `source` | string | 是 | 变更来源：user / auto / plugin |
| `timestamp` | string | 是 | 变更时间 |

## 依赖关系

- 上游：suri_core（通过 event_bus 通信）
- 下游：所有需要配置的插件

## 数据模型

### 文件存储
- `~/.suri/config.json` — 用户配置持久化
- 环境变量 `SURI_*` — 运行时覆盖

### 内存结构
- `_config: Dict[str, Any]` — 合并后的完整配置树
- `_defaults: Dict[str, Any]` — 代码内置默认值

### 配置示例（向导生成）

```json
{
  "llm_gateway": {
    "default_provider": "deepseek",
    "providers": {
      "deepseek": {
        "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-v4-pro", "deepseek-v4-flash"]
      }
    }
  },
  "access": {
    "channels": {
      "cli": {"enabled": true},
      "telegram": {
        "enabled": false,
        "bot_token": ""
      }
    }
  }
}
```

## 生命周期

1. `init()` → 读取默认值、加载文件配置、解析环境变量
2. `register_events()` → 订阅 config_changed
3. `start()` → 完成首次加载，广播配置就绪
4. `stop()` → 持久化待保存的变更
5. `cleanup()` → 清空内存配置

## 安全边界

- 禁止插件直接写 `config.json`，修改需通过本插件 API
- 敏感配置（API Key）不通过事件广播明文传输