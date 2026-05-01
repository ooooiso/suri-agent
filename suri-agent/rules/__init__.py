"""
规则执行层

所有业务规则从 Markdown 描述迁移为可执行 Python 代码。
规则不再通过解析 .md 文件加载，而是运行时自动扫描发现并实例化。

自动扫描机制：
1. 扫描 rules/ 目录下所有 .py 文件（排除 base.py、__init__.py）
2. 查找继承 BaseRule 的类
3. 按类属性 rule_id 注册到 RuleEngine
4. 新增规则只需创建文件，无需修改本文件
"""

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, Type

from rules.base import BaseRule


class RuleEngine:
    """规则引擎：自动扫描并管理所有规则"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._rules: Dict[str, BaseRule] = {}
        self._load_all()
    
    def _discover_rule_classes(self) -> Dict[str, Type[BaseRule]]:
        """自动扫描 rules/ 目录，发现所有规则类"""
        rules_dir = self.project_root / "suri-agent" / "rules"
        discovered: Dict[str, Type[BaseRule]] = {}
        
        if not rules_dir.exists():
            return discovered
        
        for py_file in rules_dir.glob("*.py"):
            if py_file.name in ("base.py", "__init__.py"):
                continue
            
            try:
                spec = importlib.util.spec_from_file_location(
                    f"rules.{py_file.stem}", py_file
                )
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"rules.{py_file.stem}"] = module
                spec.loader.exec_module(module)
                
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BaseRule) 
                        and obj is not BaseRule 
                        and obj.rule_id):
                        discovered[obj.rule_id] = obj
            except Exception as e:
                print(f"[RuleEngine] 扫描规则文件 {py_file.name} 失败: {e}")
        
        return discovered
    
    def _load_all(self):
        """自动发现并实例化所有规则"""
        classes = self._discover_rule_classes()
        for rule_id, RuleClass in classes.items():
            try:
                if rule_id in ["security", "file_ownership"]:
                    instance = RuleClass(self.project_root)
                else:
                    instance = RuleClass()
                self._rules[rule_id] = instance
            except Exception as e:
                print(f"[RuleEngine] 加载规则 {rule_id} 失败: {e}")
    
    def get(self, rule_id: str) -> BaseRule:
        """获取指定规则实例"""
        return self._rules.get(rule_id)
    
    def list_rules(self) -> list:
        """列出所有已加载的规则 ID"""
        return list(self._rules.keys())
    
    def list_rule_descriptions(self) -> list:
        """列出所有规则的描述信息"""
        return [rule.describe() for rule in self._rules.values()]
    
    def execute(self, rule_id: str, context: dict) -> dict:
        """执行指定规则"""
        rule = self._rules.get(rule_id)
        if not rule:
            return {"success": False, "error": f"rule_not_found: {rule_id}"}
        
        if not rule.validate(context):
            return {"success": False, "error": "validation_failed"}
        
        return rule.execute(context)


__all__ = ["BaseRule", "RuleEngine"]
