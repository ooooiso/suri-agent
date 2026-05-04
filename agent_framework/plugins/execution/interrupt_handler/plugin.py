"""interrupt_handler 插件 — 中断与错误恢复处理器。

支持六种中断类型分类与对应的恢复策略：
  - missing_tool / knowledge_gap / permission_denied / dependency_failed / timeout / resource_exhausted / unknown
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework.shared.interfaces.plugin import InterruptResult, PluginInterface
from agent_framework.shared.utils.event_types import Event


# 内置关键词规则
BUILTIN_KEYWORDS = {
    "missing_tool": [
        "缺少工具", "无法执行", "没有权限使用", "not available", "need tool",
        "missing tool", "tool not found",
    ],
    "knowledge_gap": [
        "我不知道", "不了解", "不会", "不懂", "没有相关知识", "超出我的能力",
        "I don't know", "I don't understand", "not familiar", "knowledge gap",
    ],
    "permission_denied": [
        "权限不足", "拒绝访问", "无权限", "forbidden", "403", "permission denied",
        "access denied", "unauthorized",
    ],
    "dependency_failed": [
        "依赖失败", "调用失败", "服务不可用", "连接失败", "connection refused",
        "dependency failed", "service unavailable", "call failed",
    ],
    "timeout": [
        "超时", "无响应", "timeout", "timed out", "no response", "deadline exceeded",
    ],
    "resource_exhausted": [
        "内存不足", "磁盘满", "资源耗尽", "rate limit", "429", "oom", "out of memory",
        "resource exhausted", "quota exceeded",
    ],
}


class InterruptHandlerPlugin(PluginInterface):
    """中断处理插件。"""

    EXTERNAL_KEYWORDS_PATH = str(Path.home() / ".suri" / "config" / "interrupt_keywords.yaml")
    
    def __init__(self):
        self._event_bus = None
        self._status = "stopped"
        self._keywords: Dict[str, List[str]] = {}
        self._retry_counts: Dict[str, int] = {}
        self._pending_decisions: Dict[str, dict] = {}
        self.config: Dict[str, Any] = {
            "enable_auto_retry": False,
            "auto_retry_types": [],
            "max_auto_retries": 2,
        }

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        if config:
            self.config.update(config.get("interrupt_handler", {}))
        self._reload_keywords()
        self._status = "initialized"

    async def start(self) -> None:
        self._status = "running"

    async def pause(self) -> None:
        self._status = "paused"

    async def resume(self) -> None:
        self._status = "running"

    async def stop(self) -> None:
        self._status = "stopped"

    async def cleanup(self) -> None:
        self._status = "stopped"

    def register_events(self) -> None:
        self._event_bus.subscribe("agent.blocked", self._on_agent_blocked)
        self._event_bus.subscribe("task.failed", self._on_task_failed)
        self._event_bus.subscribe("user.decision", self._on_user_decision)
        self._event_bus.subscribe("config.updated", self._on_config_updated)
        self._event_bus.subscribe("interrupt_handler.keywords_updated", self._on_keywords_updated)

    # ── 分类引擎 ──

    def _classify_reason(self, reason: str) -> str:
        """根据错误信息分类中断类型。"""
        reason_lower = reason.lower()
        for reason_type, keywords in self._keywords.items():
            for kw in keywords:
                if kw.lower() in reason_lower:
                    return reason_type
        return "unknown"

    def _should_auto_retry(self, reason_type: str, retry_count: int) -> bool:
        """判断是否应该自动重试。"""
        if not self.config.get("enable_auto_retry", False):
            return False
        if reason_type not in self.config.get("auto_retry_types", []):
            return False
        max_retries = self.config.get("max_auto_retries", 2)
        return retry_count < max_retries

    # ── 处理函数 ──

    async def handle(self, agent_id: str, reason: str) -> InterruptResult:
        """完整处理流程。"""
        reason_type = self._classify_reason(reason)
        
        handlers = {
            "missing_tool": self._handle_missing_tool,
            "knowledge_gap": self._handle_knowledge_gap,
            "permission_denied": self._handle_permission_denied,
            "dependency_failed": self._handle_dependency_failed,
            "timeout": self._handle_timeout,
            "resource_exhausted": self._handle_resource_exhausted,
        }
        
        handler = handlers.get(reason_type, self._handle_unknown)
        result = await handler(agent_id, reason)
        result.handled = True
        return result

    async def _handle_missing_tool(self, agent_id: str, reason: str) -> InterruptResult:
        return InterruptResult(
            handled=True, action="escalate", reason="missing_tool",
            suggestion=f"Agent {agent_id} 缺少必要工具，已通知 suri 处理。",
            escalation_target="suri",
        )

    async def _handle_knowledge_gap(self, agent_id: str, reason: str) -> InterruptResult:
        return InterruptResult(
            handled=True, action="escalate", reason="knowledge_gap",
            suggestion=f"Agent {agent_id} 知识不足，已通知 suri 处理。",
            escalation_target="suri",
        )

    async def _handle_permission_denied(self, agent_id: str, reason: str) -> InterruptResult:
        return InterruptResult(
            handled=True, action="escalate", reason="permission_denied",
            suggestion=f"Agent {agent_id} 权限不足，已通知 suri 处理。",
            escalation_target="suri",
        )

    async def _handle_dependency_failed(self, agent_id: str, reason: str) -> InterruptResult:
        retry_count = self._retry_counts.get(agent_id, 0)
        if self._should_auto_retry("dependency_failed", retry_count):
            self._retry_counts[agent_id] = retry_count + 1
            return InterruptResult(
                handled=True, action="retry", reason="dependency_failed",
                suggestion=f"依赖失败，正在进行第 {retry_count + 1} 次重试...",
            )
        return InterruptResult(
            handled=True, action="wait", reason="dependency_failed",
            suggestion="依赖服务不可用，等待用户决策。",
        )

    async def _handle_timeout(self, agent_id: str, reason: str) -> InterruptResult:
        retry_count = self._retry_counts.get(agent_id, 0)
        if self._should_auto_retry("timeout", retry_count):
            self._retry_counts[agent_id] = retry_count + 1
            return InterruptResult(
                handled=True, action="retry", reason="timeout",
                suggestion=f"操作超时，正在进行第 {retry_count + 1} 次重试...",
            )
        return InterruptResult(
            handled=True, action="wait", reason="timeout",
            suggestion="操作超时，等待用户决策。",
        )

    async def _handle_resource_exhausted(self, agent_id: str, reason: str) -> InterruptResult:
        return InterruptResult(
            handled=True, action="wait", reason="resource_exhausted",
            suggestion="资源耗尽，等待资源释放。",
        )

    async def _handle_unknown(self, agent_id: str, reason: str) -> InterruptResult:
        return InterruptResult(
            handled=True, action="escalate", reason="unknown",
            suggestion=f"遇到未知错误，已升级到 suri 处理。",
            escalation_target="suri",
        )

    # ── 事件处理 ──

    async def _on_agent_blocked(self, event: Event) -> None:
        """处理 agent.blocked 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        agent_id = payload.get("agent_id", "")
        reason = payload.get("reason", "")
        result = await self.handle(agent_id, reason)
        
        await self._event_bus.publish(Event(
            event_type="interrupt.handled",
            source="interrupt_handler",
            payload={
                "agent_id": agent_id,
                "action": result.action,
                "reason": result.reason,
                "suggestion": result.suggestion,
                "escalation_target": result.escalation_target,
            },
        ))

    async def _on_task_failed(self, event: Event) -> None:
        """处理 task.failed 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        task_id = payload.get("task_id", "")
        error_message = payload.get("error_message", "")
        retry_count = payload.get("retry_count", 0)
        agent_id = payload.get("agent_id", "")

        reason_type = self._classify_reason(error_message)

        if self._should_auto_retry(reason_type, retry_count):
            await self._event_bus.publish(Event(
                event_type="interrupt.retry_requested",
                source="interrupt_handler",
                payload={
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "reason": error_message,
                    "reason_type": reason_type,
                    "retry_count": retry_count + 1,
                },
            ))
        else:
            decision_id = f"decision_{task_id}_{len(self._pending_decisions)}"
            self._pending_decisions[decision_id] = {
                "agent_id": agent_id,
                "task_id": task_id,
                "reason": error_message,
            }
            await self._event_bus.publish(Event(
                event_type="interrupt.user_decision_needed",
                source="interrupt_handler",
                payload={
                    "decision_id": decision_id,
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "error": error_message,
                    "options": ["continue", "cancel"],
                },
            ))

    async def _on_user_decision(self, event: Event) -> None:
        """处理 user.decision 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        decision_id = payload.get("decision_id", "")
        choice = payload.get("choice", "")

        if decision_id not in self._pending_decisions:
            return

        decision = self._pending_decisions.pop(decision_id)

        if choice == "continue":
            await self._event_bus.publish(Event(
                event_type="interrupt.retry_requested",
                source="interrupt_handler",
                payload={
                    "task_id": decision["task_id"],
                    "agent_id": decision["agent_id"],
                    "reason": decision["reason"],
                },
            ))
        elif choice == "cancel":
            await self._event_bus.publish(Event(
                event_type="interrupt.cancelled",
                source="interrupt_handler",
                payload={
                    "task_id": decision["task_id"],
                    "agent_id": decision["agent_id"],
                    "reason": decision["reason"],
                },
            ))

    # ── 热更新 ──

    def _reload_keywords(self) -> None:
        """重新加载关键词（内置 + 外部覆盖）。"""
        self._keywords = {}
        for k, v in BUILTIN_KEYWORDS.items():
            self._keywords[k] = list(v)

        external = self._load_external_keywords()
        if external:
            for k, v in external.items():
                self._keywords[k] = v

        self._detect_keyword_conflicts()

    def _load_external_keywords(self) -> Dict[str, List[str]]:
        """加载外部关键词文件。"""
        path = Path(self.EXTERNAL_KEYWORDS_PATH)
        if not path.exists():
            return {}
        # YAML 格式的外部关键词文件（暂未实现解析）
        return {}

    def _detect_keyword_conflicts(self) -> None:
        """检测不同类型之间的关键词冲突。"""
        all_keywords = {}
        for reason_type, keywords in self._keywords.items():
            for kw in keywords:
                if kw in all_keywords:
                    print(f"[Warning] 关键词 '{kw}' 在 '{all_keywords[kw]}' 和 '{reason_type}' 中冲突")
                else:
                    all_keywords[kw] = reason_type

    async def _on_config_updated(self, event: Event) -> None:
        """处理 config.updated 事件。"""
        payload = event.payload if hasattr(event, 'payload') else event
        if payload.get("plugin_id") == "interrupt_handler":
            self._reload_keywords()

    async def _on_keywords_updated(self, event: Event) -> None:
        """处理 keywords_updated 事件。"""
        self._reload_keywords()

    # ── 健康检查 ──

    def health_check(self) -> dict:
        return {"status": "pass"}