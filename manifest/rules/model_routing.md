---
rule_id: model_routing
name: 模型路由规则
version: "0.1.0"
owner: config_admin
last_updated: 2026-04-30
---

# 模型路由规则

## 1. 模型池引用

本文件不重复定义模型池，模型清单的**唯一权威数据源**为 `manifest/models/model_pool.md`。

本文件仅定义路由策略与降级规则，实际模型参数以 `model_pool.md` 为准。

## 2. 自动降级策略

- 主模型响应超时（>30s）或返回错误时，自动切换至回退模型。
- 降级过程**不触发安全审批**，但记录降级事件到日志。
- 连续降级 3 次后，向 `config_admin` 和 `ops_admin` 发送告警。

## 3. 模型选择逻辑

- suri 调度时根据任务类型选择模型类别（chat/expert/text2image/image2image）。
- 同类别内按优先级选择，主模型不可用时自动降级。
- 角色可在自己的 `config.md` 中指定偏好模型，但不得违反全局优先级。

## 4. 维护与变更

- `config_admin` 负责维护本文件。
- 手动修改模型池配置（增删模型、调整优先级）需走 `security.md` 变更审批。
- 模型调用中间件读取本文件并缓存，变更后需重启缓存或等待缓存过期。
