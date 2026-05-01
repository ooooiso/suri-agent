"""
model_manager 工具

职责：
- 列出已配置模型（按类型分组）
- 切换默认模型
- 为模型自动分类
- 生成/更新可用模型配置文档

调用方：所有角色（通过 ToolService）
"""

from pathlib import Path
import sys

# 定位项目根目录
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "suri-agent"))

from model.manager import ModelManager, MODEL_TYPE_DESCRIPTIONS, DEFAULT_MODEL_TYPES


def execute(params: dict) -> dict:
    """
    模型管理工具入口

    Args:
        params:
            action: str 操作类型
                - "list":      列出所有模型（按类型分组）
                - "switch":    切换默认模型
                    model_id: str 目标模型 ID
                - "get_default": 获取当前默认模型
                - "classify":  为所有模型重新分类并写入配置
                - "generate_docs": 生成可用模型配置文档
                    output_path: str 可选，文档输出路径

    Returns:
        dict: {'success': bool, 'data': Any, 'error': str}
    """
    action = params.get('action', 'list')

    mm = ModelManager(PROJECT_ROOT)

    try:
        if action == 'list':
            return _list_models(mm)
        elif action == 'switch':
            return _switch_model(mm, params.get('model_id'))
        elif action == 'get_default':
            return _get_default(mm)
        elif action == 'classify':
            return _classify_models(mm)
        elif action == 'generate_docs':
            output_path = params.get('output_path', str(PROJECT_ROOT / 'suri-agent' / 'model' / 'available_models.md'))
            return _generate_docs(mm, output_path)
        else:
            return {'success': False, 'data': None, 'error': f'未知操作: {action}'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}


def _list_models(mm: ModelManager) -> dict:
    """列出所有已配置模型，按类型分组"""
    from collections import defaultdict

    models = mm.list_models()
    if not models:
        return {'success': True, 'data': {'groups': {}, 'count': 0}, 'error': ''}

    groups = defaultdict(list)
    for m in models:
        groups[m.model_type].append({
            'name': m.name,
            'model_id': m.model_id,
            'provider': m.provider,
            'is_default': m.is_default,
            'capabilities': m.capabilities,
            'cost_tier': m.cost_tier,
        })

    result = {
        'groups': dict(groups),
        'count': len(models),
        'type_descriptions': {k: v for k, v in MODEL_TYPE_DESCRIPTIONS.items() if k in groups},
    }
    return {'success': True, 'data': result, 'error': ''}


def _switch_model(mm: ModelManager, model_id: str) -> dict:
    """切换默认模型"""
    if not model_id:
        return {'success': False, 'data': None, 'error': '缺少参数 model_id'}

    ok = mm.set_default(model_id)
    if ok:
        m = mm._models.get(model_id)
        return {
            'success': True,
            'data': {
                'model_id': model_id,
                'name': m.name if m else model_id,
            },
            'error': ''
        }
    return {'success': False, 'data': None, 'error': f'模型 {model_id} 不存在'}


def _get_default(mm: ModelManager) -> dict:
    """获取当前默认模型"""
    m = mm.get_default_model()
    if not m:
        return {'success': True, 'data': None, 'error': ''}
    return {
        'success': True,
        'data': {
            'name': m.name,
            'model_id': m.model_id,
            'provider': m.provider,
            'model_type': m.model_type,
            'capabilities': m.capabilities,
        },
        'error': ''
    }


def _classify_models(mm: ModelManager) -> dict:
    """
    为所有已配置模型重新分类

    根据 DEFAULT_MODEL_TYPES 预置表，为每个模型更新 model_type。
    如果模型不在预置表中，保持现有类型或标记为 "text_chat"。
    """
    models = mm.list_models()
    updated = []

    for m in models:
        old_type = m.model_type
        new_type = DEFAULT_MODEL_TYPES.get(m.model_id, old_type)
        if new_type != old_type:
            m.model_type = new_type
            updated.append({
                'model_id': m.model_id,
                'name': m.name,
                'old_type': old_type,
                'new_type': new_type,
            })

    if updated:
        mm._save()

    return {
        'success': True,
        'data': {'updated': updated, 'total': len(models)},
        'error': ''
    }


def _generate_docs(mm: ModelManager, output_path: str) -> dict:
    """
    生成可用模型配置文档

    读取所有已配置模型和预置品牌信息，生成 Markdown 文档。
    """
    from collections import defaultdict

    models = mm.list_models()

    # 按类型分组
    by_type = defaultdict(list)
    for m in models:
        by_type[m.model_type].append(m)

    lines = [
        "# 可用模型配置文档",
        "",
        "> 本文档由 model_manager 工具自动生成，记录当前已配置的所有模型。",
        "",
        "## 模型分类",
        "",
    ]

    for type_key in sorted(by_type.keys()):
        desc = MODEL_TYPE_DESCRIPTIONS.get(type_key, type_key)
        lines.append(f"### {type_key} — {desc}")
        lines.append("")
        for m in by_type[type_key]:
            marker = " ⭐默认" if m.is_default else ""
            caps = ", ".join(m.capabilities or [])
            lines.append(f"- **{m.name}** ({m.model_id}){marker}")
            lines.append(f"  - 品牌: {m.provider} | 成本: {m.cost_tier}")
            lines.append(f"  - 能力: {caps}")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## 新增模型类型指南",
        "",
        "当平台需要支持新的模型类型（如 `image_generation`）时：",
        "",
        "1. 在 `suri-agent/model/manager.py` 的 `MODEL_TYPE_DESCRIPTIONS` 中注册新类型",
        "2. 在 `DEFAULT_MODEL_TYPES` 中为对应 `model_id` 标注类型",
        "3. 运行 `model_manager` 工具的 `classify` 操作更新现有模型",
        "4. 运行 `generate_docs` 操作更新本文档",
        "",
    ])

    content = "\n".join(lines)
    Path(output_path).write_text(content, encoding="utf-8")

    return {
        'success': True,
        'data': {'output_path': output_path, 'model_count': len(models)},
        'error': ''
    }
