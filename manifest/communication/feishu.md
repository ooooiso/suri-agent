---
adapter_id: feishu
name: 飞书通信配置
version: "0.1.0"
owner: config_admin
last_updated: 2026-04-30
status: reserved
---

# 飞书通信配置（预留）

## 状态

当前平台使用 **Telegram** 作为主要通信通道，飞书适配器暂未启用。

## 预留配置项

当需要切换到飞书时，在此填写：

```yaml
app_id: ""
app_secret: ""
webhook_url: ""
encrypt_key: ""
verification_token: ""
```

## 部门群组映射（预留）

| 部门 | 群组名称 | 群组 ID |
|------|---------|---------|
| 设计部 | （待填） | （待填） |
| 开发部 | （待填） | （待填） |
| 运维部 | （待填） | （待填） |
| 资源部 | （待填） | （待填） |
| 人力资源部 | （待填） | （待填） |

## 切换流程

1. `config_admin` 填写本文件配置项。
2. 更新 `config.yaml` 中 `gateway.default_interface` 为 `feishu`。
3. 重启通信适配器。
4. suri 在调度群通知所有角色通信通道已切换。
