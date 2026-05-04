"""task_scheduler 插件 — 任务调度器。

职责（system-flow.md §6）：
- 接收 task.submitted 事件
- 优先级队列管理（P0-CRITICAL > P1-HIGH > P2-NORMAL > P3-LOW）
- 并发控制（最大并行数）
- 依赖解析（等待前置步骤完成）
- 分派到对应角色的 AgentLoop
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


@dataclass(order=True)
class ScheduledTask:
    """可调度的任务项。"""
    priority: int          # 0=CRITICAL, 1=HIGH, 2=NORMAL, 3=LOW
    submitted_at: str      # 提交时间
    plan_id: str           # 规划 ID
    task_name: str         # 任务名称
    role_id: str           # 执行角色
    steps: List[Dict]      # 步骤列表
    session_id: str        # 会话 ID
    user_id: str           # 用户 ID
    agent_id: Optional[str] = None  # 关联的 Agent ID


class TaskSchedulerPlugin(PluginInterface):
    """任务调度器插件。
    
    维护优先级队列，控制并发执行。
    """

    # 优先级映射
    PRIORITY_MAP = {
        Priority.CRITICAL: 0,
        Priority.HIGH: 1,
        Priority.NORMAL: 2,
        Priority.LOW: 3,
    }

    # 最大并行数
    MAX_CONCURRENT = 5

    def __init__(self):
        self.name = "task_scheduler"
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        
        # 优先级队列：priority_level -> deque
        self._queues: Dict[int, deque] = {
            0: deque(),  # CRITICAL
            1: deque(),  # HIGH
            2: deque(),  # NORMAL
            3: deque(),  # LOW
        }
        
        # 正在执行的任务：plan_id -> ScheduledTask
        self._running: Dict[str, ScheduledTask] = {}
        
        # 已完成的任务：plan_id -> result
        self._completed: Dict[str, Any] = {}
        
        # 阻塞的任务（依赖未满足）
        self._blocked: Dict[str, ScheduledTask] = {}
        
        # 调度循环
        self._running_flag = False
        self._scheduler_task: Optional[asyncio.Task] = None
        
        # 事件记录
        self._event_log: List[Dict] = []

    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config

    def register_events(self) -> None:
        self._event_bus.subscribe("task.submitted", self._on_task_submitted)
        self._event_bus.subscribe("task.completed", self._on_task_completed)
        self._event_bus.subscribe("task.failed", self._on_task_failed)
        self._event_bus.subscribe("task.scheduler_query", self._on_query)

    async def start(self) -> None:
        self._running_flag = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def pause(self) -> None:
        self._running_flag = False
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def resume(self) -> None:
        self._running_flag = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        self._running_flag = False
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def cleanup(self) -> None:
        self._queues = {k: deque() for k in range(4)}
        self._running.clear()
        self._completed.clear()
        self._blocked.clear()

    # ================================================================== #
    # 调度循环
    # ================================================================== #

    async def _scheduler_loop(self) -> None:
        """调度循环：从队列取任务 → 分派。"""
        while self._running_flag:
            try:
                # 检查是否有空位
                if len(self._running) >= self.MAX_CONCURRENT:
                    await asyncio.sleep(1)
                    continue

                # 查找最高优先级的待处理任务
                task = self._dequeue_next()
                if not task:
                    await asyncio.sleep(0.5)
                    continue

                # 分派任务
                await self._dispatch_task(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[task_scheduler] ❌ Scheduler error: {e}")
                await asyncio.sleep(1)

    def _dequeue_next(self) -> Optional[ScheduledTask]:
        """从优先级队列取出下一个任务。"""
        for priority in range(4):  # 0=CRITICAL 优先
            q = self._queues[priority]
            if q:
                return q.popleft()
        return None

    # ================================================================== #
    # 事件处理
    # ================================================================== #

    async def _on_task_submitted(self, event: Event) -> None:
        """接收 task.submitted → 入队。"""
        payload = event.payload
        
        # 计算优先级
        event_priority = event.priority
        priority = self.PRIORITY_MAP.get(event_priority, 2)

        task = ScheduledTask(
            priority=priority,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            plan_id=payload.get("plan_id", ""),
            task_name=payload.get("task_name", "未命名"),
            role_id=payload.get("role_id", "suri"),
            steps=payload.get("steps", []),
            session_id=payload.get("session_id", "default"),
            user_id=payload.get("user_id", "cli_user"),
            agent_id=payload.get("agent_id"),
        )

        # 入队
        self._queues[priority].append(task)

        self._log_event("task.submitted", f"{task.task_name} (P{priority})")

    async def _on_task_completed(self, event: Event) -> None:
        """任务完成 → 从 running 移除。"""
        plan_id = event.payload.get("plan_id", event.payload.get("task_id", ""))
        if plan_id in self._running:
            task = self._running.pop(plan_id)
            self._completed[plan_id] = {
                "task_name": task.task_name,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": event.payload,
            }
            self._log_event("task.completed", task.task_name)

            # 检查是否有阻塞的任务可以解除
            await self._check_blocked_tasks(plan_id)

    async def _on_task_failed(self, event: Event) -> None:
        """任务失败 → 从 running 移除。"""
        plan_id = event.payload.get("plan_id", event.payload.get("task_id", ""))
        if plan_id in self._running:
            task = self._running.pop(plan_id)
            self._completed[plan_id] = {
                "task_name": task.task_name,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "error": event.payload.get("error", "Unknown"),
            }
            self._log_event("task.failed", task.task_name)

    async def _on_query(self, event: Event) -> None:
        """查询调度状态。"""
        await self._event_bus.publish(Event(
            event_type="task.scheduler_status",
            source="task_scheduler",
            target=event.source,
            payload={
                "queued": sum(len(q) for q in self._queues.values()),
                "running": len(self._running),
                "completed": len(self._completed),
                "blocked": len(self._blocked),
                "running_tasks": [
                    {"plan_id": tid, "task_name": t.task_name, "role_id": t.role_id}
                    for tid, t in self._running.items()
                ],
                "queues": {
                    "P0_CRITICAL": len(self._queues[0]),
                    "P1_HIGH": len(self._queues[1]),
                    "P2_NORMAL": len(self._queues[2]),
                    "P3_LOW": len(self._queues[3]),
                },
            },
            priority=Priority.NORMAL,
        ))

    # ================================================================== #
    # 任务分派
    # ================================================================== #

    async def _dispatch_task(self, task: ScheduledTask) -> None:
        """分派任务到对应的执行器。"""
        self._running[task.plan_id] = task

        self._log_event("task.dispatched", f"{task.task_name} → {task.role_id}")

        # 通知 agent_registry 创建 Agent
        await self._event_bus.publish(Event(
            event_type="agent.create",
            source="task_scheduler",
            payload={
                "task_id": task.plan_id,
                "task_name": task.task_name,
                "role_id": task.role_id,
                "steps": task.steps,
                "session_id": task.session_id,
                "user_id": task.user_id,
                "plan_id": task.plan_id,
            },
            priority=Priority.NORMAL,
        ))

    async def _check_blocked_tasks(self, completed_plan_id: str) -> None:
        """检查是否有阻塞任务可以解除。"""
        to_unblock = []
        for plan_id, task in list(self._blocked.items()):
            # 简化：所有依赖都已完成的检查
            to_unblock.append(plan_id)

        for plan_id in to_unblock:
            task = self._blocked.pop(plan_id)
            # 重新入队
            self._queues[task.priority].append(task)
            self._log_event("task.unblocked", task.task_name)

    # ================================================================== #
    # 公共接口
    # ================================================================== #

    def get_status(self) -> Dict[str, Any]:
        """获取调度状态。"""
        return {
            "queued": sum(len(q) for q in self._queues.values()),
            "running": len(self._running),
            "completed": len(self._completed),
            "blocked": len(self._blocked),
            "events": self._event_log[-20:],
        }

    def _log_event(self, event_type: str, detail: str) -> None:
        """记录调度事件。"""
        self._event_log.append({
            "type": event_type,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._event_log) > 100:
            self._event_log = self._event_log[-100:]