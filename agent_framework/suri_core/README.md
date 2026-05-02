# /agent_framework/suri_core

## 功能

核心服务

## 说明

- 与 llm_gateway、log_service、role_manager、access、mcp 协同
- 职责：总调度、审批、消息路由、服务协调
- 说明：所有消息必经 suri_core 中转，决定路由或调用大模型处理

