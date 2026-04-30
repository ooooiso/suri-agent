# model/

模型管理模块：负责外部大模型的配置管理、API Key 管理、首次运行引导和 API 调用。

## 功能

- **模型配置管理**：添加、删除、列出模型配置，设置默认模型
- **首次运行引导**：检测是否首次运行，弹出交互式配置向导
- **API 调用**：通过 OpenAI 兼容格式或 Anthropic API 调用模型生成回复
- **配置持久化**：模型配置保存至 `model_config.json`（项目根目录），环境变量同步写入 `.env`

## 模块说明

| 文件 | 功能 |
|------|------|
| `__init__.py` | 模块入口，导出 `ModelManager`、`ModelConfig` |
| `manager.py` | 核心管理器：配置 CRUD、首次运行引导向导、API 调用 |

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

## CLI 集成

- `cli.py` 初始化时加载 `ModelManager`
- 首次运行弹出 `setup_wizard()` 引导配置
- 未配置模型时阻止普通输入，引导用户配置
- `/model` 系列命令：add / set / del / list

## 事件记录

- 初始创建
- 新增 GLM (智谱 AI) 预设支持
- 简化配置流程：只需 API Key + 模型 ID，端点和提供商自动推断
