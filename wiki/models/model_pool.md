# 模型池配置

---
model_pool:
  version: "1.0"
  default_model: "gpt-4o"
---

## 可用模型

| 模型 ID | 提供商 | 类型 | 状态 |
|---------|--------|------|------|
| gpt-4o | openai | chat | active |
| gpt-4o-mini | openai | chat | active |
| claude-3-opus | anthropic | chat | active |
| claude-3-haiku | anthropic | chat | active |
| moonshot-v1-8k | moonshot | chat | active |
| deepseek-chat | deepseek | chat | active |
| glm-4 | glm | chat | active |

## 降级策略

- chat 类型：gpt-4o → gpt-4o-mini → claude-3-haiku
- text2image 类型：dall-e-3 → stable-diffusion-xl
