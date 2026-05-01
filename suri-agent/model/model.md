# model/

模型管理模块：负责外部大模型的配置管理、API Key 管理、首次运行引导、API 调用，以及**智能模型路由**。

## 功能

- **模型配置管理**：添加、删除、列出模型配置，设置默认模型
- **首次运行引导**：检测是否首次运行，弹出交互式配置向导
- **API 调用**：通过 OpenAI 兼容格式或 Anthropic API 调用模型生成回复（httpx + 连接池 + 自动重试 + SSE 流式）
- **配置持久化**：模型配置保存至 `model_config.json`（项目根目录），环境变量同步写入 `.env`
- **智能模型路由**：根据任务内容自动选择最合适的模型，优先低成本方案

## 模块说明

| 文件 | 功能 |
|------|------|
| `__init__.py` | 模块入口，导出 `ModelManager`、`ModelConfig` |
| `manager.py` | 核心管理器：配置 CRUD、首次运行引导向导、API 调用、智能路由 |
| `presets.json` | 模型预置配置（能力标签、成本等级、模型类型） |
| `pool.yaml` | 模型池配置（降级候选模型列表） |

## 支持的提供商

输入模型 ID 时自动推断端点：

| 关键词 | 提供商 | 端点 |
|--------|--------|------|
| `glm` | GLM (智谱 AI) | `https://open.bigmodel.cn/api/paas/v4` |
| `moonshot` | Moonshot (Kimi) | `https://api.moonshot.cn/v1` |
| `deepseek` | DeepSeek | `https://api.deepseek.com/v1` |
| `gpt` | OpenAI | `https://api.openai.com/v1` |
| `claude` | Anthropic | `https://api.anthropic.com/v1` |
| 其他 | 自定义 | 手动输入 |

## ModelConfig 配置项

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 显示名称 |
| `model_id` | str | 模型唯一标识 |
| `api_key` | str | API Key |
| `base_url` | str | API 端点 |
| `provider` | str | 提供商名称 |
| `is_default` | bool | 是否为默认模型 |
| `priority` | int | 降级优先级（越小越优先） |
| `capabilities` | List[str] | 能力标签（chat / coding / vision / reasoning / long_context / fast） |
| `cost_tier` | str | 成本等级（free / cheap / standard / premium） |
| `model_type` | str | 模型类型（见下表） |

`capabilities`、`cost_tier` 和 `model_type` 会根据 `model_id` 自动从预置表推断，用户也可手动覆盖。

## 模型类型体系（可扩展）

| 类型 | 说明 | 典型用途 |
|------|------|---------|
| `text_chat` | 文本对话模型 | 日常聊天、问答、文本分析 |
| `text_completion` | 文本补全模型 | 续写、补全、代码生成 |
| `image_generation` | 图片生成模型 | 根据文本生成图片 |
| `vision` | 视觉理解模型 | 分析图片内容、图文混合任务 |
| `audio` | 语音模型 | 语音转文字、文字转语音 |
| `embedding` | 嵌入模型 | 文本向量化、语义检索 |

新增模型类型时，只需在 `DEFAULT_MODEL_TYPES` 和 `MODEL_TYPE_DESCRIPTIONS` 中注册即可。

## 模型池与降级策略

业务配置：`pool.yaml`

模型池定义了所有可用的降级候选模型。当主模型调用失败时，系统按优先级自动尝试备用模型。

降级策略示例：
- chat 类型：gpt-4o → gpt-4o-mini → claude-3-haiku
- text2image 类型：dall-e-3 → stable-diffusion-xl

## 可用模型列表

详见 `available_models.md`。

## 智能路由 API

```python
# 根据任务内容选择最佳模型
model = manager.select_model_for_task("帮我分析这张截图里的错误")
# → 返回具备 vision + chat 能力、成本最低的已配置模型
```

路由策略：
1. 分析任务所需能力（关键词匹配，支持中英双语）
2. 筛选具备所需能力的模型
3. 按成本等级排序（free → cheap → standard → premium）

## CLI 命令

终端 (`cli.py`) 和主程序 (`main.py`) 均支持以下命令：

| 命令 | 说明 |
|------|------|
| `/model` | 启动配置向导（品牌选择 → API Key → 自动测试） |
| `/model add` | 添加模型，同上流程 |
| `/model set` | 设置默认模型 |
| `/model del` | 删除模型 |
| `/model list` | 列出所有已配置模型（含类型、能力、成本） |
| `/models` | 交互式浏览模型：按类型分组展示，输入编号即可切换默认模型 |

**配置向导流程**：
1. 用户选择品牌（1-5：智谱/OpenAI/Moonshot/DeepSeek/Anthropic，或 0 自定义）
2. 用户输入 API Key
3. 系统自动测试该品牌下的首选型号，若限流/超时则自动 fallback 到备用型号
4. 返回第一个可用的 `(名称, model_id)`，并持久化配置

**失败自动引导**：当模型调用返回 401/403/429/503、连接超时或返回空时，终端会自动提示用户是否立即重新配置模型，避免卡死。

**交互式切换 (`/models`)**：
```
已配置模型：

  [text_chat] 文本对话模型，适用于日常聊天、问答、文本分析
    1) DeepSeek Chat (deepseek-chat) ⭐默认
       品牌: deepseek | 能力: chat, reasoning | 成本: standard
    2) GLM-4.7-Flash (glm-4.7-flash)
       品牌: glm | 能力: chat, fast | 成本: free

  [vision] 视觉理解模型，适用于分析图片内容、图文混合任务
    3) GPT-4o (gpt-4o)
       品牌: openai | 能力: chat, vision, reasoning | 成本: standard

输入编号切换默认模型，或按回车取消:
```
4. 无完全匹配时放宽到部分匹配，最后 fallback 到默认模型

## CLI 集成

- `cli.py` 初始化时加载 `ModelManager`
- 首次运行弹出 `setup_wizard()` 引导配置
- 未配置模型时阻止普通输入，引导用户配置
- `/model` 系列命令：add / set / del / list

## 事件记录

- 初始创建
- 新增 GLM (智谱 AI) 预设支持
- 简化配置流程：只需 API Key + 模型 ID，端点和提供商自动推断
- 调用层升级：urllib → httpx.AsyncClient + tenacity 重试 + SSE 流式输出
- **新增智能模型路由**：`select_model_for_task()` 自动按任务类型和成本选模
- **新增能力标签体系**：`capabilities` + `cost_tier`，支持 6 大能力标签和 4 级成本
