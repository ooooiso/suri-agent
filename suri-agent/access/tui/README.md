# UI Gateway

Suri 图形化终端界面（TUI）的 JSON-RPC 后端服务。

## 启动

```bash
# 默认端口 8080
python -m ui_gateway.server

# 指定端口
python -m ui_gateway.server --port 9000

# 启用 Token 认证
python -m ui_gateway.server --port 9000 --token your_secret_token
```

## 接口规范

### 传输

- 协议：HTTP POST
- 路径：`/rpc`
- 内容类型：`application/json`
- 编码：UTF-8

### JSON-RPC 2.0 请求格式

```json
{
  "jsonrpc": "2.0",
  "method": "suri.getRoles",
  "params": {},
  "id": 1
}
```

### JSON-RPC 2.0 响应格式

成功：
```json
{
  "jsonrpc": "2.0",
  "result": [...],
  "id": 1
}
```

错误：
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "方法不存在",
    "data": {...}
  },
  "id": 1
}
```

## 可用方法

### 平台状态

| 方法 | 参数 | 说明 |
|------|------|------|
| `suri.getStatus` | `{}` | 获取平台整体状态 |
| `suri.getVersion` | `{}` | 获取版本信息 |
| `suri.reloadConfig` | `{}` | 热重载所有外部配置 |

### 角色管理

| 方法 | 参数 | 说明 |
|------|------|------|
| `suri.getRoles` | `{}` | 获取所有角色列表 |
| `suri.getRoleDetail` | `{"role_id": "art_director"}` | 获取角色 Soul 详情 |
| `suri.getRoleSkills` | `{"role_id": "art_director"}` | 获取角色技能列表 |
| `suri.getRoleMemories` | `{"role_id": "art_director", "limit": 10}` | 获取角色私人记忆 |

### 任务管理

| 方法 | 参数 | 说明 |
|------|------|------|
| `suri.getTasks` | `{"status": "pending", "limit": 50}` | 获取任务列表 |
| `suri.getTaskDetail` | `{"task_id": "task_xxx"}` | 获取任务详情 |
| `suri.getTaskMessages` | `{"task_id": "task_xxx", "limit": 50}` | 获取任务消息历史 |
| `suri.sendMessage` | `{"to": "art_director", "content": "...", "msg_type": "text"}` | 发送消息 |

### 审批管理

| 方法 | 参数 | 说明 |
|------|------|------|
| `suri.getPendingApprovals` | `{}` | 获取待审批列表 |
| `suri.getApprovalDetail` | `{"approval_id": "approval_xxx"}` | 获取审批详情 |
| `suri.approve` | `{"approval_id": "approval_xxx"}` | 批准请求 |
| `suri.reject` | `{"approval_id": "approval_xxx"}` | 拒绝请求 |

### 文件浏览

| 方法 | 参数 | 说明 |
|------|------|------|
| `suri.getDirectoryTree` | `{"root": ".", "depth": 3}` | 获取目录树 |
| `suri.readFile` | `{"rel_path": "suri-agent/rules/security.md"}` | 读取文件（只读） |
| `suri.writeFile` | `{"rel_path": "...", "content": "...", "operator": "suri", "approval_token": "..."}` | 写入文件（需审批） |

### 日志与规则

| 方法 | 参数 | 说明 |
|------|------|------|
| `suri.getLogs` | `{"limit": 100, "level": "INFO"}` | 获取运行日志 |
| `suri.getRules` | `{}` | 获取所有规则 |
| `suri.getProcesses` | `{}` | 获取所有流程 |
| `suri.getModelPool` | `{}` | 获取模型池配置 |

## 调用示例

### curl

```bash
curl -X POST http://localhost:8080/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "suri.getRoles",
    "params": {},
    "id": 1
  }'
```

### Python

```python
import requests

response = requests.post('http://localhost:8080/rpc', json={
    "jsonrpc": "2.0",
    "method": "suri.getRoleDetail",
    "params": {"role_id": "art_director"},
    "id": 2
})
print(response.json())
```

## 架构

```
ui_gateway/
├── server.py          # HTTP 服务端入口
├── rpc_methods.py     # RPC 方法集合
├── middleware.py      # 认证/日志/异常处理
└── README.md          # 接口文档
```

`server.py` 初始化与 `suri-agent` 相同的核心服务（Config、Memory、Security 等），
`rpc_methods.py` 通过注入这些服务实例，为 TUI 提供查询和操作能力。

写操作（如 `suri.writeFile`）会经过 `SecurityService` 的权限与审批校验，与主程序的安全策略保持一致。
