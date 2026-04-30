---
config_id: model_pool
name: 全局模型池清单
version: "0.1.0"
owner: config_admin
last_updated: 2026-04-30
---

# 全局模型池清单

## 对话模型 (chat)

| 模型 ID | 名称 | 优先级 | 端点 | 回退模型 | 状态 |
|---------|------|--------|------|---------|------|
| gpt-4o | GPT-4o | 1 | openai/gpt-4o | gpt-4o-mini | active |
| gpt-4o-mini | GPT-4o Mini | 2 | openai/gpt-4o-mini | claude-3-haiku | active |
| claude-3-opus | Claude 3 Opus | 3 | anthropic/claude-3-opus | gpt-4o | active |
| claude-3-haiku | Claude 3 Haiku | 4 | anthropic/claude-3-haiku | gpt-4o-mini | active |

## 专家模型 (expert)

| 模型 ID | 领域 | 优先级 | 端点 | 回退模型 | 状态 |
|---------|------|--------|------|---------|------|
| gpt-4o | 通用专家 | 1 | openai/gpt-4o | claude-3-opus | active |

## 文生图模型 (text2image)

| 模型 ID | 优先级 | 端点 | 回退模型 | 状态 |
|---------|--------|------|---------|------|
| dall-e-3 | 1 | openai/dall-e-3 | stable-diffusion-xl | active |
| stable-diffusion-xl | 2 | stablility/sd-xl | dall-e-3 | standby |

## 图生图模型 (image2image)

| 模型 ID | 优先级 | 端点 | 回退模型 | 状态 |
|---------|--------|------|---------|------|
| stable-diffusion-xl | 1 | stability/sd-xl | （无） | active |

## 维护说明

- 由 `config_admin` 维护，模型调用中间件读取并缓存。
- 变更需触发 `security.md` 审批流程。
- 降级事件记录于 `logs/model_routing.log`。
