"""Soul 解析器 — YAML frontmatter + Markdown body。"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


def parse_soul(content: str) -> Optional[Dict[str, Any]]:
    """解析 Soul 文件内容。
    
    格式：
    ---
    yaml_frontmatter
    ---
    markdown_body
    
    返回 dict 包含 frontmatter (dict) 和 body (str)。
    """
    content = content.strip()
    if not content.startswith("---"):
        # 无 frontmatter，视为纯文本
        return {"frontmatter": {}, "body": content}
    
    # 找到第二个 ---
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {"frontmatter": {}, "body": content}
    
    yaml_text = parts[1].strip()
    body = parts[2].strip()
    
    frontmatter = _parse_simple_yaml(yaml_text)
    return {"frontmatter": frontmatter, "body": body}


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """极简 YAML 解析（仅支持迭代1所需的标量和列表）。"""
    result: Dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    current_key = None
    current_list = None
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        
        # 列表项
        if stripped.startswith("- "):
            if current_list is not None:
                current_list.append(stripped[2:].strip())
            i += 1
            continue
        
        # 键值对
        if ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip()
            
            # 检查下一行是否是列表
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("- "):
                current_key = key
                current_list = []
                result[key] = current_list
            elif val == "":
                result[key] = ""
            elif val.lower() == "true":
                result[key] = True
            elif val.lower() == "false":
                result[key] = False
            elif val.startswith('"') and val.endswith('"'):
                result[key] = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                result[key] = val[1:-1]
            else:
                try:
                    result[key] = int(val)
                except ValueError:
                    try:
                        result[key] = float(val)
                    except ValueError:
                        result[key] = val
            i += 1
            continue
        
        i += 1
    
    return result


def build_system_prompt(soul_path: Path) -> str:
    """从 Soul 文件构建 system prompt。"""
    if not soul_path.exists():
        return "You are Suri, an AI assistant."
    
    content = soul_path.read_text(encoding="utf-8")
    parsed = parse_soul(content)
    if not parsed:
        return "You are Suri, an AI assistant."
    
    fm = parsed.get("frontmatter", {})
    body = parsed.get("body", "")
    
    parts = []
    nickname = fm.get("nickname", "Suri")
    parts.append(f"You are {nickname}.")
    
    if "identity" in fm:
        parts.append(f"Identity: {fm['identity']}")
    
    # 从 body 提取 Identity / Responsibilities / Constraints / Skills
    for section in ["Identity", "Responsibilities", "Constraints", "Skills"]:
        if f"## {section}" in body:
            start = body.find(f"## {section}")
            end = body.find("## ", start + 1)
            if end == -1:
                section_text = body[start:]
            else:
                section_text = body[start:end]
            parts.append(section_text.strip())
    
    return "\n\n".join(parts)
