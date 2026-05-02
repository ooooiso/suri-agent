# test_framework 插件 PRD

## 定位

测试框架插件，为系统提供自动化测试发现、执行、报告能力。覆盖单元测试、集成测试、插件测试，支持运行时通过命令触发测试，保障代码质量和回归安全。

## 功能需求

### 1. 测试发现

- 自动扫描 `tests/` 目录下的测试文件
- 支持标准 unittest 格式（`test_*.py`）和脚本格式（`*_test.py`）
- 按模块分类：unit（单元）、integration（集成）、plugin（插件）、fullforce（压力）
- 发现结果缓存，增量更新

### 2. 测试执行
- 通过 `/test` 命令或 `user.command` 事件触发
- 支持全量执行、按模块执行、按文件执行
- 异步执行，不阻塞主事件循环
- 并发控制（默认 4  worker）

### 3. 测试基础设施
- `TestBase` — 测试基类，提供 mock event_bus、mock plugin、临时数据库
- `PluginTestHarness` — 插件测试专用夹具，模拟插件生命周期
- `EventBusFixture` — 事件总线 mock，支持断言事件发布/订阅
- `RoleFixture` — 角色环境 mock，创建临时角色目录和数据库

### 4. 测试报告
- 实时输出到终端（unittest 风格）
- 生成结构化报告（JSON / Markdown）
- 存储于 `resources/test_reports/`
- 历史结果对比（通过/失败趋势）

### 5. 回归触发
- 代码变更后自动检测受影响的测试
- 支持 `/test regression` 快速运行相关用例
- 失败时通过 event_bus 广播 `error.test`

### 6. 插件专属测试
- 每个插件可声明自己的测试目录（`manifest.test_dir`）
- 插件加载时自动运行 smoke test
- 插件卸载前运行 cleanup test

## 接口定义

### 订阅事件
- `user.command`（/test）→ 执行测试
- `system.config_changed` → 清除测试缓存
- `system.plugin_loaded` → 触发插件 smoke test

### 发布事件
- `test.completed` — 测试执行完成（含 summary）
- `error.test` — 测试失败告警

## 事件 Payload Schema

### 订阅事件

#### `user.command`（/test）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户 ID |
| `command` | string | 是 | 命令名 |
| `args` | object | 是 | 参数（test_type, target_plugin 等） |
| `channel` | string | 是 | 通道 |

#### `system.config_changed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config_key` | string | 是 | 变更的配置项 |
| `old_value` | any | 是 | 旧值 |
| `new_value` | any | 是 | 新值 |

#### `system.plugin_loaded`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 加载的插件 ID |
| `manifest` | object | 是 | 插件 manifest |

### 发布事件

#### `test.completed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `test_suite` | string | 是 | 测试套件名称 |
| `total` | integer | 是 | 总用例数 |
| `passed` | integer | 是 | 通过数 |
| `failed` | integer | 是 | 失败数 |
| `skipped` | integer | 是 | 跳过数 |
| `duration_ms` | integer | 否 | 总耗时 |
| `failures` | array | 否 | 失败的用例详情 |

#### `error.test`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 被测插件 |
| `error_code` | integer | 是 | 错误码 |
| `error_message` | string | 是 | 错误描述 |

## 配置项

```yaml
test_framework:
  test_dir: "tests/"
  report_dir: "resources/test_reports/"
  default_workers: 4
  auto_smoke_test: true  # 插件加载后自动 smoke test
  categories:
    unit: "tests/unit/"
    integration: "tests/integration/"
    plugin: "tests/plugin/"
    fullforce: "tests/fullforce/"
  fail_fast: false
```

## 依赖关系

- 上游：suri_core、config_service
- 下游：所有被测试的插件

## 目录结构
iteration plan
```
tests/
├── __init__.py
├── framework/
│   ├── base.py            # TestBase 基类
│   ├── fixtures.py        # 共享夹具
│   ├── utils.py           # 测试工具函数
│   └── plugin_harness.py  # 插件测试 harness
├── unit/                  # 单元测试
├── integration/           # 集成测试
├── plugin/                # 插件测试
└── fullforce/             # 压力/并发测试
```

## 生命周期

1. `init()` → 扫描测试目录、加载测试基类
2. `register_events()` → 订阅 /test 命令
3. `start()` → 标记就绪
4. `stop()` → 中断正在运行的测试
5. `cleanup()` → 清理临时测试数据

## 安全边界

- 测试在隔离环境运行（临时目录、临时数据库）
- 禁止测试直接操作生产数据目录
- 压力测试默认限制并发数，防止资源耗尽
