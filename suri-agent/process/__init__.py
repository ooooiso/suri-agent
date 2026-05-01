"""
流程执行层

所有平台级流程已代码化，运行时自动扫描发现并实例化。
角色内部流程由角色在 group/<role>/ 中自行定义，不通过此处管理。

自动扫描机制：
1. 扫描 process/ 目录下所有 .py 文件（排除 base.py、__init__.py）
2. 查找继承 BaseProcess 的类
3. 按类属性 process_id 注册到 ProcessEngine
4. 新增流程只需创建文件，无需修改本文件
"""

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, Type

from process.base import BaseProcess


class ProcessEngine:
    """流程引擎：自动扫描并管理所有平台级流程"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._processes: Dict[str, BaseProcess] = {}
        self._load_all()
    
    def _discover_process_classes(self) -> Dict[str, Type[BaseProcess]]:
        """自动扫描 process/ 目录，发现所有流程类"""
        process_dir = self.project_root / "suri-agent" / "process"
        discovered: Dict[str, Type[BaseProcess]] = {}
        
        if not process_dir.exists():
            return discovered
        
        for py_file in process_dir.glob("*.py"):
            if py_file.name in ("base.py", "__init__.py"):
                continue
            
            try:
                spec = importlib.util.spec_from_file_location(
                    f"process.{py_file.stem}", py_file
                )
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"process.{py_file.stem}"] = module
                spec.loader.exec_module(module)
                
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BaseProcess)
                        and obj is not BaseProcess
                        and obj.process_id):
                        discovered[obj.process_id] = obj
            except Exception as e:
                print(f"[ProcessEngine] 扫描流程文件 {py_file.name} 失败: {e}")
        
        return discovered
    
    def _load_all(self):
        """自动发现并实例化所有流程"""
        classes = self._discover_process_classes()
        for process_id, ProcessClass in classes.items():
            try:
                self._processes[process_id] = ProcessClass()
            except Exception as e:
                print(f"[ProcessEngine] 加载流程 {process_id} 失败: {e}")
    
    def get(self, process_id: str) -> BaseProcess:
        """获取指定流程实例"""
        return self._processes.get(process_id)
    
    def list_processes(self) -> list:
        """列出所有已加载的流程 ID"""
        return list(self._processes.keys())
    
    def list_process_descriptions(self) -> list:
        """列出所有流程的描述信息"""
        return [proc.describe() for proc in self._processes.values()]
    
    def execute(self, process_id: str, context: dict) -> dict:
        """执行指定流程"""
        process = self._processes.get(process_id)
        if not process:
            return {"success": False, "error": f"process_not_found: {process_id}"}
        return process.execute(context)


__all__ = ["BaseProcess", "ProcessEngine"]
