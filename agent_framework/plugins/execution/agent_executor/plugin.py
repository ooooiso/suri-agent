"""agent_executor 插件 — Agent Loop 核心引擎。

8 步 Agent Loop（system-flow.md §2）：
1. 事件接收（攒批 + 优先级排序）
2. 调度决策（urgent=0ms, high=500ms, normal=2s, low=5s）
3. 构建 Context（5 层：system/session/task/history/memory）
4. 调 LLM（通过 llm_gateway）
5. 解析输出（function calling → tool_call → NL 降级 → 纯文本）
6. 执行动作（tool_call → code_tool/mcp / 分配子任务 / 回复用户）
7. 循环决策（continue / wait / stop / pause）
8. 记忆管理（异步存储）
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from agent_framework.shared.interfaces.plugin import PluginInterface, Agent, TaskStep
from agent_framework.shared.utils.event_types import Event, Priority


class AgentLoop:
    """单个 Agent 的执行循环实例。
    
    每个 Agent 拥有一个独立的 AgentLoop，负责该 Agent 的完整 8 步循环。
    由 AgentExecutorPlugin 管理生命周期。
    """

    # 攒批延迟（ms）
    BATCH_DELAYS = {
        "urgent": 0,
        "high": 0.5,
        "normal": 2.0,
        "low": 5.0,
    }

    def __init__(self, agent_id: str, role_id: str, event_bus):
        self.agent_id = agent_id
        self.role_id = role_id
        self._event_bus = event_bus
        
        # 事件队列
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        
        # Context 缓存
        self._system_context: Optional[str] = None       # 角色 Soul
        self._session_messages: List[Dict] = []           # 会话历史
        self._task_context: Optional[Dict] = None         # 当前任务
        self._history_context: List[Dict] = []            # 历史完成的任务
        self._memory_context: Optional[Dict] = None       # 记忆
        
        # 步骤状态
        self._current_step: Optional[TaskStep] = None
        self._step_results: List[Dict] = []
        
        # 攒批缓冲区
        self._batch_buffer: List[Event] = []
        self._batch_timer: Optional[asyncio.Task] = None
        
        # LLM 请求追踪
        self._pending_llm_requests: Dict[str, asyncio.Future] = {}
        
        # 通知 future（用于等待步骤完成）
        self._step_future: Optional[asyncio.Future] = None
        
    # ================================================================ #
    # 生命周期
    # ================================================================ #
    
    async def start(self) -> None:
        """启动循环。"""
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop())
    
    async def stop(self) -> None:
        """停止循环。"""
        self._running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        # 清理缓冲区
        self._batch_buffer.clear()
        if self._batch_timer and not self._batch_timer.done():
            self._batch_timer.cancel()
        # 清理待处理的 LLM 请求
        for future in self._pending_llm_requests.values():
            if not future.done():
                future.cancel()
    
    def push_event(self, event: Event) -> None:
        """向循环推送事件。"""
        if self._running:
            self._batch_buffer.append(event)
            self._schedule_batch()
    
    # ================================================================ #
    # 核心 8 步循环
    # ================================================================ #
    
    async def _run_loop(self) -> None:
        """主循环：Step 1 → Step 2 → ... → Step 8 → 回到 Step 1"""
        while self._running:
            try:
                # Step 1: 事件接收（攒批 + 优先级排序）
                events = await self._step1_receive_events()
                if not events:
                    continue
                
                for event in events:
                    if not self._running:
                        break
                    
                    # Step 2: 调度决策（优先级判定）
                    decision = self._step2_schedule_decision(event)
                    if decision == "skip":
                        continue
                    
                    # Step 3: 构建 Context（5 层）
                    context = await self._step3_build_context(event)
                    
                    # Step 4: 调用 LLM
                    llm_response = await self._step4_call_llm(context)
                    if not llm_response:
                        continue
                    
                    # Step 5: 解析输出
                    parsed = self._step5_parse_output(llm_response)
                    
                    # Step 6: 执行动作
                    action_result = await self._step6_execute_action(parsed, event)
                    
                    # Step 7: 循环决策
                    should_continue = await self._step7_loop_decision(action_result)
                    if not should_continue:
                        await self._notify_agent_complete(action_result)
                        break
                    
                    # Step 8: 记忆管理（异步）
                    asyncio.create_task(
                        self._step8_manage_memory(event, llm_response, action_result)
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AgentLoop:{self.agent_id}] ❌ Loop error: {e}")
                # 发布错误
                await self._event_bus.publish(Event(
                    event_type="agent.loop_error",
                    source="agent_executor",
                    payload={
                        "agent_id": self.agent_id,
                        "error": str(e),
                    },
                    priority=Priority.HIGH,
                ))
                await asyncio.sleep(1)
    
    # ------------------------------------------------------------------ #
    # Step 1: 事件接收（攒批 + 优先级排序）
    # ------------------------------------------------------------------ #
    async def _step1_receive_events(self) -> List[Event]:
        """接收并攒批事件，按优先级排序返回。"""
        # 从缓冲区获取
        if not self._batch_buffer:
            # 从队列等待
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.5)
                self._batch_buffer.append(event)
            except asyncio.TimeoutError:
                return []
        
        # 立即处理缓冲区中的事件
        events = list(self._batch_buffer)
        self._batch_buffer.clear()
        
        # 按优先级排序（urgent > high > normal > low）
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.NORMAL: 2,
            Priority.LOW: 3,
        }
        events.sort(key=lambda e: priority_order.get(e.priority, 99))
        
        return events
    
    def _schedule_batch(self) -> None:
        """安排攒批定时器（攒批延迟后处理缓冲区）。"""
        if self._batch_timer and not self._batch_timer.done():
            return  # 已有定时器
        
        async def flush():
            try:
                # 攒批延迟（500ms）
                await asyncio.sleep(0.5)
                # 将所有缓冲区事件放入队列
                while self._batch_buffer:
                    event = self._batch_buffer.pop(0)
                    await self._event_queue.put(event)
            except asyncio.CancelledError:
                pass
        
        self._batch_timer = asyncio.create_task(flush())
    
    # ------------------------------------------------------------------ #
    # Step 2: 调度决策
    # ------------------------------------------------------------------ #
    def _step2_schedule_decision(self, event: Event) -> str:
        """判断优先级，决定是否处理。"""
        # 总是处理 CRITICAL/HIGH 事件
        if event.priority in (Priority.CRITICAL, Priority.HIGH):
            return "process"
        
        # 当前有活跃步骤，跳过 NORMAL/LOW
        if self._current_step and self._current_step.status == "in_progress":
            return "skip"
        
        return "process"
    
    # ------------------------------------------------------------------ #
    # Step 3: 构建 Context（5 层）
    # ------------------------------------------------------------------ #
    async def _step3_build_context(self, event: Event) -> Dict[str, Any]:
        """构建五层 Context。"""
        context = {
            "system_prompt": self._system_context or "",
            "session": self._session_messages[-10:] if self._session_messages else [],
            "task": self._task_context or {},
            "history": self._history_context[-5:] if self._history_context else [],
            "memory": self._memory_context or {},
            "current_event": {
                "type": event.event_type,
                "payload": event.payload,
                "source": event.source,
            },
        }
        return context
    
    def set_system_context(self, system_prompt: str) -> None:
        """设置 system context（角色 Soul）。"""
        self._system_context = system_prompt
    
    def set_session_messages(self, messages: List[Dict]) -> None:
        """设置会话历史。"""
        self._session_messages = messages
    
    def set_task_context(self, task: Dict) -> None:
        """设置任务上下文。"""
        self._task_context = task
    
    # ------------------------------------------------------------------ #
    # Step 4: 调用 LLM
    # ------------------------------------------------------------------ #
    async def _step4_call_llm(self, context: Dict[str, Any]) -> Optional[str]:
        """调用 LLM 获取响应。"""
        # 如果没有当前步骤，创建一个默认步骤
        if not self._current_step:
            self._current_step = TaskStep(
                step_id=f"step_{uuid.uuid4().hex[:6]}",
                description=context.get("current_event", {}).get("payload", {}).get("content", "处理消息"),
                assignee=self.role_id,
            )
        
        request_id = f"llm_{self.agent_id}_{uuid.uuid4().hex[:8]}"
        future = asyncio.get_event_loop().create_future()
        self._pending_llm_requests[request_id] = future
        
        # 构建 messages
        messages = []
        
        # System prompt
        system = context.get("system_prompt", "")
        if system:
            messages.append({"role": "system", "content": system})
        
        # 任务描述
        task = context.get("task", {})
        if task:
            messages.append({
                "role": "system",
                "content": f"当前任务: {task.get('description', '')}",
            })
        
        # 历史
        history = context.get("history", [])
        for h in history[-5:]:
            role = h.get("role", h.get("type", "user"))
            content = h.get("content", h.get("message", ""))
            if content:
                messages.append({"role": role, "content": content})
        
        # 会话
        session = context.get("session", [])
        for m in session[-10:]:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        
        # 当前事件
        current = context.get("current_event", {})
        event_payload = current.get("payload", {})
        user_content = event_payload.get("content", event_payload.get("message", str(event_payload)))
        messages.append({"role": "user", "content": user_content})
        
        # 发布 LLM 请求
        await self._event_bus.publish(Event(
            event_type="llm.request",
            source=f"agent_executor.{self.agent_id}",
            payload={
                "request_id": request_id,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096,
                "agent_id": self.agent_id,
                "step_id": self._current_step.step_id,
            },
            priority=Priority.NORMAL,
        ))
        
        # 等待响应（超时 120s）
        try:
            response = await asyncio.wait_for(future, timeout=120)
            return response
        except asyncio.TimeoutError:
            print(f"[AgentLoop:{self.agent_id}] ⚠️ LLM 请求超时")
            await self._event_bus.publish(Event(
                event_type="task.timeout",
                source="agent_executor",
                payload={
                    "agent_id": self.agent_id,
                    "timeout_seconds": 120,
                },
                priority=Priority.HIGH,
            ))
            return None
        except Exception as e:
            print(f"[AgentLoop:{self.agent_id}] ⚠️ LLM 错误: {e}")
            return None
        finally:
            self._pending_llm_requests.pop(request_id, None)
    
    def on_llm_response(self, request_id: str, content: str) -> None:
        """处理 LLM 响应（由外部调用）。"""
        future = self._pending_llm_requests.get(request_id)
        if future and not future.done():
            future.set_result(content)
    
    def on_llm_error(self, request_id: str, error: str) -> None:
        """处理 LLM 错误（由外部调用）。"""
        future = self._pending_llm_requests.get(request_id)
        if future and not future.done():
            future.set_exception(Exception(error))
    
    # ------------------------------------------------------------------ #
    # Step 5: 解析输出
    # ------------------------------------------------------------------ #
    def _step5_parse_output(self, llm_response: str) -> Dict[str, Any]:
        """解析 LLM 输出。
        
        解析策略（按优先级）：
        1. function calling（JSON function_call 格式）
        2. tool_call（XML 或 JSON tool_call 格式）
        3. 自然语言降级（包含 tool/action 关键词）
        4. 纯文本回复
        """
        content = llm_response.strip()
        
        # 1. 尝试 function calling 格式（```json ... ``` 或纯 JSON）
        parsed = self._try_parse_json_function_call(content)
        if parsed:
            return parsed
        
        # 2. 尝试 tool_call XML 格式
        parsed = self._try_parse_tool_call(content)
        if parsed:
            return parsed
        
        # 3. 自然语言降级：包含动作关键词
        parsed = self._try_nl_fallback(content)
        if parsed:
            return parsed
        
        # 4. 纯文本回复
        return {"type": "text", "content": content, "reply": content}
    
    def _try_parse_json_function_call(self, content: str) -> Optional[Dict]:
        """尝试解析 JSON function call。"""
        # 提取 ```json ... ``` 块
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        json_str = json_match.group(1) if json_match else content
        
        # 尝试完整 JSON 解析
        if json_str.startswith("{") and json_str.endswith("}"):
            try:
                data = json.loads(json_str)
                if "function" in data or "tool" in data or "action" in data:
                    return {
                        "type": "function_call",
                        "function": data.get("function", data.get("tool", data.get("action"))),
                        "arguments": data.get("arguments", data.get("params", data.get("parameters", {}))),
                        "raw": content,
                    }
                if "reply" in data or "response" in data:
                    return {
                        "type": "text",
                        "content": data.get("reply", data.get("response", "")),
                        "raw": content,
                    }
            except json.JSONDecodeError:
                pass
        
        # 尝试提取 markdown code block 中的 JSON
        code_match = re.search(r'```(?:json)?\s*\n?(\{.*?\})\n?\s*```', content, re.DOTALL)
        if code_match:
            try:
                data = json.loads(code_match.group(1))
                if "function" in data or "tool" in data:
                    return {
                        "type": "function_call",
                        "function": data.get("function", data.get("tool")),
                        "arguments": data.get("arguments", data.get("params", {})),
                        "raw": content,
                    }
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _try_parse_tool_call(self, content: str) -> Optional[Dict]:
        """尝试解析 tool_call XML/特殊格式。"""
        import re
        
        # <tool>name</tool> 格式
        tool_match = re.search(r'<(?:tool|function|action)>(.*?)</(?:tool|function|action)>', content, re.DOTALL)
        if tool_match:
            tool_name = tool_match.group(1).strip()
            # 提取参数
            params = {}
            param_matches = re.findall(r'<(\w+)>(.*?)</\1>', content, re.DOTALL)
            for key, val in param_matches:
                if key.lower() not in ("tool", "function", "action"):
                    params[key.lower()] = val.strip()
            
            return {
                "type": "tool_call",
                "tool": tool_name,
                "arguments": params,
                "raw": content,
            }
        
        return None
    
    def _try_nl_fallback(self, content: str) -> Optional[Dict]:
        """自然语言降级：检测是否包含动作关键词。"""
        action_keywords = [
            "read", "write", "search", "create", "list", "stat",
            "读取", "写入", "搜索", "创建", "列出", "统计",
        ]
        
        has_action = any(kw in content.lower() for kw in action_keywords)
        
        if has_action:
            return {
                "type": "nl_action",
                "content": content,
                "raw": content,
            }
        
        return None
    
    # ------------------------------------------------------------------ #
    # Step 6: 执行动作
    # ------------------------------------------------------------------ #
    async def _step6_execute_action(self, parsed: Dict[str, Any], event: Event) -> Dict[str, Any]:
        """根据解析结果执行动作。"""
        action_type = parsed.get("type", "text")
        
        if action_type in ("function_call", "tool_call"):
            # 工具调用
            return await self._execute_tool_call(parsed, event)
        
        elif action_type == "nl_action":
            # 自然语言动作（解析后在代码工具中执行）
            return await self._execute_nl_action(parsed, event)
        
        else:
            # 纯文本回复
            reply = parsed.get("reply", parsed.get("content", ""))
            await self._event_bus.publish(Event(
                event_type="llm.response",
                source=f"agent_executor.{self.agent_id}",
                target=event.source,
                payload={
                    "content": reply,
                    "session_id": event.payload.get("session_id", "default"),
                    "agent_id": self.agent_id,
                },
                priority=Priority.NORMAL,
            ))
            
            return {
                "action": "reply",
                "content": reply,
                "completed": True,
            }
    
    async def _execute_tool_call(self, parsed: Dict, event: Event) -> Dict:
        """执行工具调用。"""
        tool_name = parsed.get("function", parsed.get("tool", ""))
        arguments = parsed.get("arguments", {})
        
        # 映射函数名到 MCP Framework 工具
        tool_map = {
            "read_file": "file_read",
            "write_file": "file_write",
            "append_file": "file_append",
            "create_file": "file_create",
            "list_dir": "file_list",
            "grep": "file_search",
            "search_code": "file_search",
            "stat_project": "file_stat",
            # 中文映射
            "读取文件": "file_read",
            "写入文件": "file_write",
            "搜索代码": "file_search",
            "列出目录": "file_list",
            "统计项目": "file_stat",
            # 扩展工具
            "shell": "shell_exec",
            "shell_exec": "shell_exec",
            "execute": "shell_exec",
            "web_fetch": "web_fetch",
            "web_search": "web_search",
            "fetch": "web_fetch",
            "search": "web_search",
        }
        
        mapped_tool = tool_map.get(tool_name, tool_name)
        
        # MCP Framework 是唯一的工具注册中心，所有工具请求都转发给它
        
        # 发布工具调用事件
        request_id = f"tool_{uuid.uuid4().hex[:8]}"
        session_id = event.payload.get("session_id", "default")
        
        # 修正参数路径（相对于项目根目录）
        if "path" in arguments and isinstance(arguments["path"], str):
            arguments["path"] = arguments["path"].lstrip("/")
        
        await self._event_bus.publish(Event(
            event_type="tool.call",
            source=f"agent_executor.{self.agent_id}",
            payload={
                "tool_name": mapped_tool,
                "params": arguments,
                "request_id": request_id,
                "session_id": session_id,
            },
            priority=Priority.NORMAL,
        ))
        
        # 等待 60s 获取结果（通过 tool.result 事件）
        try:
            future = asyncio.get_event_loop().create_future()
            self._pending_tool_future = future
            result = await asyncio.wait_for(future, timeout=60)
            
            # 将结果转发回用户
            result_str = json.dumps(result, ensure_ascii=False, indent=2)
            await self._event_bus.publish(Event(
                event_type="llm.response",
                source=f"agent_executor.{self.agent_id}",
                target=event.source,
                payload={
                    "content": f"工具调用结果: {result_str[:1000]}",
                    "session_id": session_id,
                    "agent_id": self.agent_id,
                    "is_tool_result": True,
                },
                priority=Priority.NORMAL,
            ))
            
            return {
                "action": "tool_call",
                "tool": tool_name,
                "result": result,
                "completed": True,
            }
            
        except asyncio.TimeoutError:
            return {
                "action": "tool_call",
                "tool": tool_name,
                "error": "timeout",
                "completed": True,
            }
    
    def on_tool_result(self, request_id: str, result: Any) -> None:
        """处理工具调用结果。"""
        if hasattr(self, "_pending_tool_future") and self._pending_tool_future:
            if not self._pending_tool_future.done():
                self._pending_tool_future.set_result(result)
    
    async def _execute_nl_action(self, parsed: Dict, event: Event) -> Dict:
        """执行自然语言动作（降级解析）。"""
        content = parsed.get("content", "")
        
        # 尝试用 LLM 重新解析成结构化的命令
        # 简单场景直接回复
        await self._event_bus.publish(Event(
            event_type="llm.response",
            source=f"agent_executor.{self.agent_id}",
            target=event.source,
            payload={
                "content": content,
                "session_id": event.payload.get("session_id", "default"),
                "agent_id": self.agent_id,
            },
            priority=Priority.NORMAL,
        ))
        
        return {
            "action": "reply",
            "content": content,
            "completed": True,
        }
    
    # ------------------------------------------------------------------ #
    # Step 7: 循环决策
    # ------------------------------------------------------------------ #
    async def _step7_loop_decision(self, action_result: Dict) -> bool:
        """决定是否继续循环。"""
        if not action_result:
            return False
        
        completed = action_result.get("completed", False)
        action = action_result.get("action", "")
        
        if completed:
            # 标记当前步骤完成
            if self._current_step:
                self._current_step.status = "completed"
                self._current_step.completed_at = datetime.now(timezone.utc).isoformat()
                self._current_step.result = json.dumps(action_result.get("result", action_result), ensure_ascii=False)
                
                # 记录步骤结果
                self._step_results.append({
                    "step_id": self._current_step.step_id,
                    "action": action,
                    "completed_at": self._current_step.completed_at,
                })
            
            self._current_step = None
            
            # 通知状态更新
            asyncio.create_task(self._event_bus.publish(Event(
                event_type="agent.status_update",
                source=f"agent_executor.{self.agent_id}",
                payload={
                    "agent_id": self.agent_id,
                    "step_completed": True,
                },
                priority=Priority.LOW,
            )))
            
            return True  # 继续等待下一个事件
        
        return True  # 继续循环
    
    async def _notify_agent_complete(self, action_result: Dict) -> None:
        """通知 Agent 完成。"""
        await self._event_bus.publish(Event(
            event_type="agent.status_update",
            source=f"agent_executor.{self.agent_id}",
            payload={
                "agent_id": self.agent_id,
                "status": "completed",
                "result": action_result,
            },
            priority=Priority.NORMAL,
        ))
    
    # ------------------------------------------------------------------ #
    # Step 8: 记忆管理（异步）
    # ------------------------------------------------------------------ #
    async def _step8_manage_memory(self, event: Event, llm_response: str, action_result: Dict) -> None:
        """异步管理记忆。"""
        try:
            # 推送到 memory_service
            await self._event_bus.publish(Event(
                event_type="memory.store",
                source=f"agent_executor.{self.agent_id}",
                payload={
                    "role_id": self.role_id,
                    "agent_id": self.agent_id,
                    "interaction": {
                        "event_type": event.event_type,
                        "input": event.payload.get("content", ""),
                        "output": llm_response[:200] if llm_response else "",
                        "action": action_result.get("action", ""),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                },
                priority=Priority.LOW,
            ))
            
            # 追加到历史
            self._history_context.append({
                "event": event.event_type,
                "action": action_result.get("action", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            # 裁剪历史（保留最近 50 条）
            if len(self._history_context) > 50:
                self._history_context = self._history_context[-50:]
                
        except Exception as e:
            print(f"[AgentLoop:{self.agent_id}] ⚠️ Memory management error: {e}")


class AgentExecutorPlugin(PluginInterface):
    """Agent 执行器插件。
    
    管理所有 AgentLoop 实例。
    事件分发入口：agent.loop_start → 创建/恢复 AgentLoop
    """

    def __init__(self):
        self.name = "agent_executor"
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        
        # 所有活跃的 AgentLoop: agent_id -> AgentLoop
        self._loops: Dict[str, AgentLoop] = {}
        
        # 等待回复的 tool 请求（request_id -> event 用于回调）
        self._pending_tool_results: Dict[str, str] = {}  # request_id -> agent_id

    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config

    def register_events(self) -> None:
        self._event_bus.subscribe("agent.loop_start", self._on_loop_start)
        self._event_bus.subscribe("agent.loop_resume", self._on_loop_resume)
        self._event_bus.subscribe("agent.loop_stop", self._on_loop_stop)
        self._event_bus.subscribe("llm.response", self._on_llm_response)
        self._event_bus.subscribe("llm.error", self._on_llm_error)
        self._event_bus.subscribe("tool.result", self._on_tool_result)
        self._event_bus.subscribe("role.context_ready", self._on_role_context_ready)
        self._event_bus.subscribe("user.input", self._on_user_input)

    async def start(self) -> None:
        pass

    async def pause(self) -> None:
        """暂停所有 AgentLoop。"""
        for loop in self._loops.values():
            await loop.stop()
        self._loops.clear()

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        """停止所有 AgentLoop。"""
        for loop in self._loops.values():
            await loop.stop()
        self._loops.clear()

    async def cleanup(self) -> None:
        self._loops.clear()
        self._pending_tool_results.clear()

    # ================================================================== #
    # 事件处理
    # ================================================================== #

    async def _on_role_context_ready(self, event: Event) -> None:
        """角色上下文就绪，为 suri 创建/更新 AgentLoop。"""
        payload = event.payload
        role_id = payload.get("role_id", "suri")
        session_id = payload.get("session_id", "default")
        soul_content = payload.get("soul_content", "")
        history = payload.get("history", [])
        
        # 查找或创建 AgentLoop
        agent_id = f"agent_{role_id}_{session_id}"
        
        if agent_id not in self._loops:
            loop = AgentLoop(agent_id, role_id, self._event_bus)
            self._loops[agent_id] = loop
            await loop.start()
        else:
            loop = self._loops[agent_id]
        
        # 更新 Context
        if soul_content:
            loop.set_system_context(soul_content)
        if history:
            loop.set_session_messages(history)
        
        # 刷新缓存的用户输入（解决 user.input 比 role.context_ready 先到达的问题）
        if hasattr(self, "_pending_user_inputs"):
            pending = list(self._pending_user_inputs)
            for ev in pending:
                if ev.payload.get("session_id", "default") == session_id:
                    loop.push_event(ev)
                    self._pending_user_inputs.remove(ev)
                    print(f"[agent_executor] ✅ 立即刷新缓存的用户输入到 {agent_id}")

    async def _on_user_input(self, event: Event) -> None:
        """用户输入 → 推送到 suri 的 AgentLoop。"""
        session_id = event.payload.get("session_id", "default")
        agent_id = f"agent_suri_{session_id}"
        
        loop = self._loops.get(agent_id)
        if loop:
            loop.push_event(event)
        else:
            # 等待 role.context_ready 先到达
            print(f"[agent_executor] ⚠️ AgentLoop {agent_id} not ready, buffering...")
            # 临时缓存，等待 role.context_ready
            if not hasattr(self, "_pending_user_inputs"):
                self._pending_user_inputs = []
            self._pending_user_inputs.append(event)
            
            # 设置定时器 5s 后重试
            async def retry():
                await asyncio.sleep(5)
                loop = self._loops.get(agent_id)
                if loop:
                    for ev in list(getattr(self, "_pending_user_inputs", [])):
                        if ev.payload.get("session_id", "default") == session_id:
                            loop.push_event(ev)
                            self._pending_user_inputs.remove(ev)
            
            asyncio.create_task(retry())

    async def _on_loop_start(self, event: Event) -> None:
        """启动 AgentLoop。"""
        agent_id = event.payload.get("agent_id", "")
        role_id = event.payload.get("role_id", "suri")
        
        if agent_id and agent_id not in self._loops:
            loop = AgentLoop(agent_id, role_id, self._event_bus)
            self._loops[agent_id] = loop
            await loop.start()

    async def _on_loop_resume(self, event: Event) -> None:
        """恢复 AgentLoop。"""
        agent_id = event.payload.get("agent_id", "")
        loop = self._loops.get(agent_id)
        if loop:
            await loop.start()

    async def _on_loop_stop(self, event: Event) -> None:
        """停止 AgentLoop。"""
        agent_id = event.payload.get("agent_id", "")
        loop = self._loops.pop(agent_id, None)
        if loop:
            await loop.stop()

    async def _on_llm_response(self, event: Event) -> None:
        """处理 LLM 响应 → 分发到对应的 AgentLoop。

        注意：LLM gateway 发布的 llm.response 的 source 是 "llm_gateway"，
        不是 "agent_executor.xxx"，所以需要通过 request_id 中的 agent_id
        来匹配对应的 AgentLoop。
        """
        payload = event.payload
        request_id = payload.get("request_id", "")
        content = payload.get("content", "")
        
        if not request_id:
            return
        
        # 方式1: 通过 source 查找（llm_gateway 直接响应时不可用）
        source = event.source
        if source and source.startswith("agent_executor."):
            agent_id = source[len("agent_executor."):]
            loop = self._loops.get(agent_id)
            if loop:
                loop.on_llm_response(request_id, content)
                return
        
        # 方式2: 通过 request_id 中的 agent_id 片段查找
        # request_id 格式: "llm_{agent_id}_{uuid}"
        for agent_id, loop in self._loops.items():
            if agent_id in request_id:
                loop.on_llm_response(request_id, content)
                return

    async def _on_llm_error(self, event: Event) -> None:
        """处理 LLM 错误 → 分发到对应的 AgentLoop。"""
        payload = event.payload
        request_id = payload.get("request_id", "")
        error = payload.get("error_message", "Unknown error")
        
        source = event.source
        if source and source.startswith("agent_executor."):
            agent_id = source[len("agent_executor."):]
            loop = self._loops.get(agent_id)
            if loop:
                loop.on_llm_error(request_id, error)

    async def _on_tool_result(self, event: Event) -> None:
        """处理工具调用结果 → 分发到对应的 AgentLoop。"""
        payload = event.payload
        request_id = payload.get("request_id", "")
        result = payload.get("result", {})
        
        # 从 source 找 agent_id
        target = event.target
        if target and target.startswith("agent_executor."):
            agent_id = target[len("agent_executor."):]
            loop = self._loops.get(agent_id)
            if loop:
                loop.on_tool_result(request_id, result)