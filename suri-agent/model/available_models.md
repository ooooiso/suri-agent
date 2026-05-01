# 可用模型配置文档

> 关联代码: `suri-agent/model/manager.py`
>
> 本文档记录 Suri 平台支持的所有预置模型品牌、型号、分类及使用说明。

## 模型分类体系

Suri 支持按 **模型类型** 对模型进行分类，便于未来扩展（如图片生成、语音等）。

| 类型 | 说明 | 典型场景 |
|------|------|---------|
| `text_chat` | 文本对话模型 | 日常聊天、问答、文本分析、任务调度 |
| `text_completion` | 文本补全模型 | 文本续写、代码补全、长文生成 |
| `image_generation` | 图片生成模型 | 文生图、图像编辑 |
| `vision` | 视觉理解模型 | 图片内容分析、OCR、图文混合任务 |
| `audio` | 语音模型 | 语音识别(ASR)、语音合成(TTS) |
| `embedding` | 嵌入模型 | 文本向量化、语义检索、RAG |

新增类型时，在 `manager.py` 的 `MODEL_TYPE_DESCRIPTIONS` 中注册即可。

---

## 预置品牌与型号

### 1. 智谱 AI (GLM)

| 型号 | 类型 | 能力 | 成本 | 说明 |
|------|------|------|------|------|
| GLM-4 | text_chat | chat, long_context, reasoning | standard | 旗舰对话模型，支持长上下文 |
| GLM-4V | vision | chat, vision | standard | 视觉理解模型，可分析图片 |
| GLM-4.7-Flash | text_chat | chat, fast | free | 轻量快速模型，免费额度 |
| GLM-4-Flash | text_chat | chat, fast | free | 另一款轻量模型，免费额度 |

**端点**: `https://open.bigmodel.cn/api/paas/v4`

### 2. OpenAI

| 型号 | 类型 | 能力 | 成本 | 说明 |
|------|------|------|------|------|
| GPT-4o | vision | chat, vision, reasoning | standard | 多模态旗舰，支持图文理解 |
| GPT-4o Mini | vision | chat, vision, fast | cheap | GPT-4o 轻量版，成本低 |
| GPT-4 Turbo | text_chat | chat, long_context, reasoning | premium | 长上下文旗舰 |

**端点**: `https://api.openai.com/v1`

### 3. Moonshot (Kimi)

| 型号 | 类型 | 能力 | 成本 | 说明 |
|------|------|------|------|------|
| Moonshot v1-8k | text_chat | chat | cheap | 标准对话，8k 上下文 |
| Moonshot v1-32k | text_chat | chat, long_context | standard | 长上下文，32k |
| Moonshot v1-128k | text_chat | chat, long_context | premium | 超长上下文，128k |

**端点**: `https://api.moonshot.cn/v1`

### 4. DeepSeek

| 型号 | 类型 | 能力 | 成本 | 说明 |
|------|------|------|------|------|
| DeepSeek Chat | text_chat | chat, reasoning | standard | 通用对话，推理能力强 |
| DeepSeek Coder | text_chat | chat, coding, reasoning | standard | 代码专用，编程能力强 |

**端点**: `https://api.deepseek.com/v1`

### 5. Anthropic (Claude)

| 型号 | 类型 | 能力 | 成本 | 说明 |
|------|------|------|------|------|
| Claude 3.5 Sonnet | text_chat | chat, coding, reasoning, long_context | premium | 编程和长文能力突出 |
| Claude 3 Opus | text_chat | chat, reasoning, long_context | premium | 旗舰推理模型 |
| Claude 3 Haiku | text_chat | chat, fast | cheap | 快速响应，成本低 |

**端点**: `https://api.anthropic.com/v1`

---

## 能力标签说明

| 标签 | 含义 |
|------|------|
| `chat` | 通用对话能力 |
| `coding` | 代码编写/分析 |
| `vision` | 图片理解 |
| `reasoning` | 推理/逻辑分析 |
| `long_context` | 长上下文支持 |
| `fast` | 快速响应 |

---

## 成本等级说明

| 等级 | 说明 |
|------|------|
| `free` | 免费或大量免费额度 |
| `cheap` | 低成本，适合高频调用 |
| `standard` | 标准成本 |
| `premium` | 高成本，高质量 |

智能路由 (`select_model_for_task`) 会优先选择成本更低的模型。

---

## 配置方式

### 方式一：交互式向导（推荐）

```
用户 > /model
>>> 启动模型配置向导...
请选择模型品牌：
  1) 智谱 AI (GLM)（首选: GLM-4）
  2) OpenAI（首选: GPT-4o）
  ...
输入选项 [0-5]: 4
请输入您的 DeepSeek API Key：
API Key: sk-xxx
正在验证 API Key 并测试可用型号...
✅ 模型配置完成！
```

### 方式二：手动添加

```
用户 > /model add
```

### 方式三：交互式浏览与切换

```
用户 > /models
已配置模型：

  [text_chat] 文本对话模型，适用于日常聊天、问答、文本分析
    1) DeepSeek Chat (deepseek-chat) ⭐默认
       品牌: deepseek | 能力: chat, reasoning | 成本: standard

输入编号切换默认模型，或按回车取消:
```

---

## 新增模型类型指南

当平台需要支持新的模型类型（如 `image_generation`）时：

1. 在 `manager.py` 的 `MODEL_TYPE_DESCRIPTIONS` 中注册新类型
2. 在 `DEFAULT_MODEL_TYPES` 中为对应 `model_id` 标注类型
3. 在本文档的"模型分类体系"表格中添加新类型
4. 在品牌表格中新增型号行
5. 如需专门的路由逻辑，在 `select_model_for_task()` 中扩展任务分析规则
