"""EventBus — 基于 asyncio.Queue 的事件总线。"""

import asyncio
import fnmatch
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent_framework.shared.utils.event_types import Event, Priority


class EventBus:
    """事件总线。
    
    - 基于 asyncio.Queue
    - 4 个 worker 协程处理事件
    - 支持通配符订阅
    - CRITICAL/HIGH 事件持久化到 SQLite
    """

    WORKER_COUNT = 4
    QUEUE_MAXSIZE = 10000

    def __init__(self, db_path: Optional[str] = None):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=self.QUEUE_MAXSIZE
        )
        self._subscribers: Dict[str, List[Callable]] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._db_path = db_path
        self._counter = 0

    async def start(self) -> None:
        """启动 EventBus，启动 worker 协程。"""
        self._running = True
        for i in range(self.WORKER_COUNT):
            worker = asyncio.create_task(
                self._worker_loop(i),
                name=f"event_bus_worker_{i}"
            )
            self._workers.append(worker)

    async def stop(self) -> None:
        """停止 EventBus。"""
        self._running = False
        # 发送停止信号（空事件）
        for _ in self._workers:
            self._counter += 1
            await self._queue.put((0, self._counter, None))
        # 等待所有 worker 结束
        for worker in self._workers:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        self._workers.clear()

    async def publish(self, event: Event) -> None:
        """发布事件。"""
        if not self._running:
            return
        
        # 持久化 CRITICAL/HIGH 事件
        if event.priority in (Priority.CRITICAL, Priority.HIGH):
            self._persist_event(event)
        
        # 入队：(priority_value, event)
        self._counter += 1
        try:
            await self._queue.put((event.priority.value, self._counter, event))
        except asyncio.QueueFull:
            # 队列满时丢弃 LOW 优先级事件
            if event.priority == Priority.LOW:
                return
            # 其他优先级等待
            await self._queue.put((event.priority.value, self._counter, event))

    def subscribe(self, pattern: str, handler: Callable[[Event], Any]) -> None:
        """订阅事件。支持通配符，如 'system.*'、'task.*'。
        
        注意：这是同步方法，handler 可以是同步或异步函数。
        如果 handler 是 coroutine，EventBus 会在 _safe_call 中自动 await。
        """
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(handler)

    def subscribe_sync(self, pattern: str, handler: Callable[[Event], Any]) -> None:
        """同步订阅事件（别名，与 subscribe 行为一致）。
        
        供 register_events() 等同步上下文使用，避免误以为 subscribe 是异步方法。
        """
        self.subscribe(pattern, handler)

    def unsubscribe(self, pattern: str, handler: Callable[[Event], Any]) -> None:
        """取消订阅。"""
        if pattern in self._subscribers:
            if handler in self._subscribers[pattern]:
                self._subscribers[pattern].remove(handler)

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker 协程主循环。"""
        while self._running:
            try:
                _, _, event = await self._queue.get()
                if event is None:
                    break
                await self._dispatch(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # worker 异常不退出，记录错误
                print(f"[EventBus Worker {worker_id}] Error: {e}")

    async def _dispatch(self, event: Event) -> None:
        """分发事件到匹配的订阅者。"""
        handlers: List[Callable] = []
        
        for pattern, subs in self._subscribers.items():
            if fnmatch.fnmatch(event.event_type, pattern):
                handlers.extend(subs)
        
        # 去重
        seen = set()
        unique_handlers = []
        for h in handlers:
            if id(h) not in seen:
                seen.add(id(h))
                unique_handlers.append(h)
        
        # 并发调用所有处理器
        if unique_handlers:
            await asyncio.gather(
                *[self._safe_call(h, event) for h in unique_handlers],
                return_exceptions=True
            )

    async def _safe_call(self, handler: Callable, event: Event) -> None:
        """安全调用处理器，异常隔离。"""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            # 插件异常不扩散，发布 error.plugin 事件
            error_event = Event(
                event_type="error.plugin",
                source="event_bus",
                payload={
                    "error_type": type(e).__name__,
                    "message": str(e),
                    "original_event": event.event_type,
                },
                priority=Priority.HIGH,
            )
            await self.publish(error_event)

    def _persist_event(self, event: Event) -> None:
        """持久化事件到 SQLite。
        
        使用自增 ID 作为主键，避免 request_id 重复导致事件丢失。
        """
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT INTO events 
                   (event_type, source, target, payload, priority, timestamp, consumed)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_type,
                    event.source,
                    event.target,
                    str(event.payload),
                    event.priority.name,
                    event.timestamp,
                    0,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
