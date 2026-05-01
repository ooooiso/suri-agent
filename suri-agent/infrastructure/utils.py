"""
通用工具函数
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Tuple, Optional


def parse_markdown_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    解析 Markdown 文件的 YAML Frontmatter + Markdown 正文
    
    Args:
        content: 文件原始内容
        
    Returns:
        (metadata_dict, markdown_body)
    """
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return meta, body
            except yaml.YAMLError:
                pass
    return {}, content


def load_markdown_file(path: Path) -> Tuple[Dict[str, Any], str]:
    """加载并解析单个 Markdown 文件"""
    content = path.read_text(encoding='utf-8')
    return parse_markdown_frontmatter(content)


def scan_markdown_files(directory: Path, pattern: str = "**/*.md") -> Dict[str, Tuple[Dict[str, Any], str]]:
    """
    扫描目录下所有 Markdown 文件
    
    Returns:
        {相对路径: (metadata, body)}
    """
    results = {}
    for file_path in directory.glob(pattern):
        rel_path = file_path.relative_to(directory)
        try:
            meta, body = load_markdown_file(file_path)
            results[str(rel_path)] = (meta, body)
        except Exception as e:
            # 解析失败，信息不打印到终端
            pass
    return results


def find_file_by_meta_key(
    files: Dict[str, Tuple[Dict[str, Any], str]],
    key: str,
    value: Any
) -> Optional[Tuple[str, Dict[str, Any], str]]:
    """在已加载的文件中按元信息键值查找"""
    for rel_path, (meta, body) in files.items():
        if meta.get(key) == value:
            return rel_path, meta, body
    return None
