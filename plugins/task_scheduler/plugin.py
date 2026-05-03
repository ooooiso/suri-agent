"""task_scheduler 插件 — 任务调度中心"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.interfaces.plugin import (
    PluginInterface, TaskStep, TaskPlan
)
from shared.utils.event_types import Event, Priority


class TaskSchedulerPlugin(PluginInterface):
    """任务调度中心插件。
    
    负责任务分发、执行跟踪、状态管理。
    接收 task_planner 的规划结果，按步骤调度执行。
    """
    
    def __init__(self):
        self.name = "task_scheduler"
        self.event_bus = None
        self.config = {}
        self._tasks: Dict[str, Dict] = {}  # task_id -> task info
        self._running_tasks: Dict[str, asyncio.Task] = {}  # task_id -> asyncio task
        self._retry_counts: Dict[str, int] = {}  # task_id -> retry count
    
    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        """初始化插件"""
        self.event_bus = event_bus
        self.config = config.get("task_scheduler", {})
    
    def register_events(self) -> None:
        """注册事件订阅"""
        self.event_bus.subscribe("task.planned", self._on_task_planned)
        self.event_bus.subscribe("task.step_ready", self._on_step_ready)
        self.event_bus.subscribe("task.plan_updated", self._on_plan_updated)
        self.event_bus.subscribe("llm.response", self._on_llm_response)
        self.event_bus.subscribe("llm.error", self._on_llm_error)
        self.event_bus.subscribe("interrupt.retry_requested", self._on_retry_requested)
        self.event_bus.subscribe("interrupt.cancelled", self._on_task_cancelled)
    
    async def start(self) -> None:
        """启动插件"""
        pass
    
    async def pause(self) -> None:
        """暂停插件"""
        # 暂停所有运行中的任务
        for task_id, task in self._running_tasks.items():
            if not task.done():
                task.cancel()
    
    async def resume(self) -> None:
        """恢复插件"""
        pass
    
    async def stop(self) -> None:
        """停止插件"""
        for task_id, task in self._running_tasks.items():
            if not task.done():
                task.cancel()
        self._running_tasks.clear()
    
    async def cleanup(self) -> None:
        """清理资源"""
        self._tasks.clear()
        self._running_tasks.clear()
        self._retry_counts.clear()
    
    # --- 事件处理 ---
    
    async def _on_task_planned(self, event: Event) -> None:
        """任务规划完成，开始调度"""
        payload = event.payload
        plan_id = payload.get("plan_id", "")
        task_name = payload.get("task_name", "")
        steps_data = payload.get("steps", [])
        
        # 注册任务
        self._tasks[plan_id] = {
            "plan_id": plan_id,
            "task_name": task_name,
            "steps": [TaskStep(**s) for s in steps_data],
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "retry_count": 0,
        }
        
        # 开始执行
        asyncio_task = asyncio.create_task(
            self._execute_task(plan_id)
        )
        self._running_tasks[plan_id] = asyncio_task
    
    async def _on_step_ready(self, event: Event) -> None:
        """步骤就绪，可以执行"""
        plan_id = event.payload.get("plan_id", "")
        step_id = event.payload.get("step_id", "")
        
        task_info = self._tasks.get(plan_id)
        if not task_info:
            return
        
        # 找到步骤并执行
        for step in task_info["steps"]:
            if step.step_id == step_id and step.status == "pending":
                await self._execute_step(plan_id, step)
                break
    
    async def _on_plan_updated(self, event: Event) -> None:
        """规划更新"""
        plan_id = event.payload.get("plan_id", "")
        updated_steps = event.payload.get("updated_steps", [])
        
        task_info = self._tasks.get(plan_id)
        if not task_info:
            return
        
        # 更新步骤
        task_info["steps"] = [TaskStep(**s) for s in updated_steps]
        task_info["status"] = "pending"
        
        # 重新执行
        asyncio_task = asyncio.create_task(
            self._execute_task(plan_id)
        )
        self._running_tasks[plan_id] = asyncio_task
    
    async def _on_llm_response(self, event: Event) -> None:
        """LLM 响应"""
        # 由具体执行步骤处理
        pass
    
    async def _on_llm_error(self, event: Event) -> None:
        """LLM 错误"""
        request_id = event.payload.get("request_id", "")
        error_message = event.payload.get("error_message", "")
        
        # 查找关联的任务
        for task_id, task_info in self._tasks.items():
            if task_info.get("current_request_id") == request_id:
                # 标记步骤失败
                current_step = task_info.get("current_step")
                if current_step:
                    current_step.status = "blocked"
                    current_step.block_reason = error_message
                
                # 发布任务失败事件
                await self.event_bus.publish(Event(
                    event_type="task.failed",
                    source=self.name,
                    payload={
                        "task_id": task_id,
                        "error_code": 5001,
                        "error_message": error_message,
                        "retry_count": task_info.get("retry_count", 0),
                    }
                ))
                break
    
    async def _on_retry_requested(self, event: Event) -> None:
        """重试请求"""
        task_id = event.payload.get("task_id", "")
        retry_number = event.payload.get("retry_number", 1)
        
        task_info = self._tasks.get(task_id)
        if not task_info:
            return
        
        task_info["retry_count"] = retry_number
        task_info["status"] = "pending"
        
        # 重新执行
        asyncio_task = asyncio.create_task(
            self._execute_task(task_id)
        )
        self._running_tasks[task_id] = asyncio_task
    
    async def _on_task_cancelled(self, event: Event) -> None:
        """任务取消"""
        task_id = event.payload.get("task_id", "")
        
        task_info = self._tasks.get(task_id)
        if task_info:
            task_info["status"] = "cancelled"
        
        # 取消运行中的 asyncio task
        running = self._running_tasks.get(task_id)
        if running and not running.done():
            running.cancel()
    
    # --- 核心执行逻辑 ---
    
    async def _execute_task(self, plan_id: str) -> None:
        """执行任务的所有步骤"""
        task_info = self._tasks.get(plan_id)
        if not task_info:
            return
        
        task_info["status"] = "running"
        
        # 发布任务开始事件
        await self.event_bus.publish(Event(
            event_type="task.started",
            source=self.name,
            payload={
                "task_id": plan_id,
                "task_name": task_info["task_name"],
                "steps_count": len(task_info["steps"]),
            }
        ))
        
        try:
            # 按顺序执行步骤
            for step in task_info["steps"]:
                if task_info["status"] == "cancelled":
                    break
                
                # 检查依赖
                if not self._dependencies_met(plan_id, step):
                    continue
                
                # 执行步骤
                await self._execute_step(plan_id, step)
                
                # 检查超时
                timeout = self.config.get("default_timeout", 300)
                step_start = datetime.now()
                
                # 等待步骤完成（通过事件驱动）
                while step.status == "in_progress":
                    elapsed = (datetime.now() - step_start).total_seconds()
                    if elapsed > timeout:
                        step.status = "blocked"
                        step.block_reason = "timeout"
                        
                        # 发布超时事件
                        await self.event_bus.publish(Event(
                            event_type="task.timeout",
                            source=self.name,
                            payload={
                                "task_id": plan_id,
                                "timeout_seconds": timeout,
                            }
                        ))
                        break
                    await asyncio.sleep(0.1)
            
            # 检查是否全部完成
            all_completed = all(
                s.status == "completed" for s in task_info["steps"]
            )
            if all_completed:
                task_info["status"] = "completed"
                await self.event_bus.publish(Event(
                    event_type="task.completed",
                    source=self.name,
                    payload={
                        "task_id": plan_id,
                        "task_name": task_info["task_name"],
                        "result": "success",
                    }
                ))
            elif task_info["status"] != "cancelled":
                task_info["status"] = "blocked"
                
        except asyncio.CancelledError:
            task_info["status"] = "cancelled"
        except Exception as e:
            task_info["status"] = "failed"
            await self.event_bus.publish(Event(
                event_type="task.failed",
                source=self.name,
                payload={
                    "task_id": plan_id,
                    "error_code": 5000,
                    "error_message": str(e),
                    "retry_count": task_info.get("retry_count", 0),
                }
            ))
        finally:
            self._running_tasks.pop(plan_id, None)
    
    async def _execute_step(self, plan_id: str, step: TaskStep) -> None:
        """执行单个步骤"""
        step.status = "in_progress"
        step.started_at = datetime.now().isoformat()
        
        # 发布步骤开始事件
        await self.event_bus.publish(Event(
            event_type="task.step_started",
            source=self.name,
            payload={
                "task_id": plan_id,
                "step_id": step.step_id,
                "description": step.description,
                "assignee": step.assignee,
            }
        ))
        
        # 根据 assignee 分发
        if step.assignee == "suri":
            # suri 角色执行（通过 LLM）
            await self._dispatch_to_llm(plan_id, step)
        else:
            # 其他角色执行
            await self._dispatch_to_role(plan_id, step, step.assignee)
    
    async def _dispatch_to_llm(self, plan_id: str, step: TaskStep) -> None:
        """分发到 LLM 执行"""
        request_id = f"task_{plan_id}_{step.step_id}_{uuid.uuid4().hex[:6]}"
        
        task_info = self._tasks.get(plan_id)
        if task_info:
            task_info["current_request_id"] = request_id
            task_info["current_step"] = step
        
        # 发布 LLM 请求
        await self.event_bus.publish(Event(
            event_type="llm.request",
            source=self.name,
            payload={
                "request_id": request_id,
                "messages": [
                    {"role": "system", "content": f"你正在执行任务步骤：{step.description}"},
                    {"role": "user", "content": f"请执行：{step.description}"},
                ],
                "temperature": 0.7,
            }
        ))
    
    async def _dispatch_to_role(self, plan_id: str, step: TaskStep,
                                role_id: str) -> None:
        """分发到指定角色"""
        await self.event_bus.publish(Event(
            event_type="task.step_assigned",
            source=self.name,
            target=role_id,
            payload={
                "task_id": plan_id,
                "step_id": step.step_id,
                "description": step.description,
            }
        ))
    
    def _dependencies_met(self, plan_id: str, step: TaskStep) -> bool:
        """检查步骤依赖是否满足"""
        if not step.depends_on:
            return True
        
        task_info = self._tasks.get(plan_id)
        if not task_info:
            return False
        
        for dep_id in step.depends_on:
            dep_step = next(
                (s for s in task_info["steps"] if s.step_id == dep_id),
                None
            )
            if not dep_step or dep_step.status != "completed":
                return False
        
        return True
    
    # --- 公共方法 ---
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task_info = self._tasks.get(task_id)
        if not task_info:
            return None
        
        return {
            "task_id": task_id,
            "task_name": task_info["task_name"],
            "status": task_info["status"],
            "steps": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "status": s.status,
                    "assignee": s.assignee,
                }
                for s in task_info["steps"]
            ],
            "retry_count": task_info.get("retry_count", 0),
            "created_at": task_info.get("created_at", ""),
        }
    
    def list_tasks(self, status: str = None) -> List[Dict]:
        """列出任务"""
        tasks = []
        for task_id, task_info in self._tasks.items():
            if status and task_info["status"] != status:
                continue
            tasks.append({
                "task_id": task_id,
                "task_name": task_info["task_name"],
                "status": task_info["status"],
                "steps_count": len(task_info["steps"]),
            })
        return tasks
    
    async def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        task_info = self._tasks.get(task_id)
        if not task_info:
            return False
        task_info["status"] = "paused"
        return True
    
    async def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        task_info = self._tasks.get(task_id)
        if not task_info:
            return False
        task_info["status"] = "running"
        return True
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task_info = self._tasks.get(task_id)
        if not task_info:
            return False
        task_info["status"] = "cancelled"
        
        running = self._running_tasks.get(task_id)
        if running and not running.done():
            running.cancel()
        
        return True
