"""
文档监控钩子

职责：
- 监控 suri-agent/、group/、wiki/ 下的文件变更
- 代码文件保存时，自动检测对应的同名 .md 是否需要更新
- 将违规项加入待同步队列，供 DocSyncRule 处理

设计原则：
- 轻量级：只记录变更事件，不阻塞主程序
- 延迟检测：文件保存后延迟 1 秒检测，避免临时文件干扰
- 去重：同一目录的多次变更只记录一次
"""

import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime


class DocWatcher:
    """
    文档变更监控器
    
    使用方式：
        watcher = DocWatcher(project_root)
        watcher.start()  # 启动后台监控
        
        # 主循环中定期检查
        pending = watcher.get_pending()
        if pending:
            print(f"检测到 {len(pending)} 个目录需要同步文档")
    """
    
    WATCH_DIRS = ["suri-agent", "group", "wiki"]
    
    def __init__(self, project_root: Path, callback: Optional[Callable] = None):
        self.project_root = project_root
        self.callback = callback
        self._pending: Dict[str, float] = {}  # 目录路径 -> 变更时间
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_snapshot: Dict[str, float] = {}
        
    def _take_snapshot(self) -> Dict[str, float]:
        """获取监控目录下所有文件的状态快照"""
        snapshot = {}
        for rel_dir in self.WATCH_DIRS:
            base = self.project_root / rel_dir
            if not base.exists():
                continue
            for f in base.rglob("*"):
                if f.is_file() and not any(
                    part.startswith(".") or part == "__pycache__"
                    for part in f.parts
                ):
                    try:
                        snapshot[str(f.relative_to(self.project_root))] = f.stat().st_mtime
                    except Exception:
                        pass
        return snapshot
    
    def _detect_changes(self) -> List[str]:
        """检测变更的目录路径列表"""
        current = self._take_snapshot()
        changed_dirs = set()
        
        # 新增或修改的文件
        for path, mtime in current.items():
            prev_mtime = self._last_snapshot.get(path)
            if prev_mtime is None or mtime > prev_mtime:
                # 记录该文件所在目录
                dir_path = str(Path(path).parent)
                changed_dirs.add(dir_path)
        
        # 删除的文件
        for path in self._last_snapshot:
            if path not in current:
                dir_path = str(Path(path).parent)
                changed_dirs.add(dir_path)
        
        self._last_snapshot = current
        return list(changed_dirs)
    
    def _watch_loop(self, interval: float = 2.0) -> None:
        """监控循环（在后台线程运行）"""
        # 初始快照
        self._last_snapshot = self._take_snapshot()
        
        while self._running:
            time.sleep(interval)
            if not self._running:
                break
            
            try:
                changed = self._detect_changes()
                for dir_path in changed:
                    self._pending[dir_path] = time.time()
                
                if changed and self.callback:
                    self.callback(changed)
            except Exception:
                pass
    
    def start(self, interval: float = 2.0) -> None:
        """启动后台监控线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop,
            args=(interval,),
            daemon=True,
            name="DocWatcher"
        )
        self._thread.start()
    
    def stop(self) -> None:
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
    
    def get_pending(self) -> Dict[str, float]:
        """获取待同步的目录路径及其变更时间"""
        # 过滤掉已处理超过 30 秒的旧事件
        now = time.time()
        self._pending = {
            k: v for k, v in self._pending.items()
            if now - v < 300  # 5 分钟内有效
        }
        return dict(self._pending)
    
    def clear_pending(self, dir_path: str = "") -> None:
        """清空待同步队列"""
        if dir_path:
            self._pending.pop(dir_path, None)
        else:
            self._pending.clear()
    
    def has_pending(self) -> bool:
        """是否有待同步项"""
        return len(self.get_pending()) > 0
