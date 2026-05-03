"""interrupt_handler 插件 — 任务执行中断处理"""

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.interfaces.plugin import (
    PluginInterface, InterruptResult
)
from shared.utils.event_types import Event, Priority


class InterruptHandlerPlugin(PluginInterface):
    """中断处理插件。
    
    任务执行受阻时的系统级处理。分类受阻原因，生成用户决策建议，提供升级通道。
    只处理系统级中断，不处理业务逻辑错误。
    支持从外部 YAML 文件加载关键词和热更新。
    """
    
    # 外部关键词文件路径
    EXTERNAL_KEYWORDS_PATH = os.path.expanduser("~/.suri/data/configs/interrupt_keywords.yaml")
    
    def __init__(self):
        self.name = "interrupt_handler"
        self.event_bus = None
        self.config = {}
        self._retry_counts: Dict[str, int] = {}  # agent_id -> retry count
        self._pending_decisions: Dict[str, Dict] = {}  # decision_id -> decision info
        
        # 内置关键词映射（代码内 fallback）
        self._builtin_keywords = {
            "missing_tool": [
                "缺少工具", "没有接口", "不支持", "need tool",
                "missing", "not supported", "unavailable"
            ],
            "knowledge_gap": [
                "不会", "不了解", "不清楚", "unknown",
                "don't know", "not sure", "knowledge"
            ],
            "permission_denied": [
                "权限不足", "拒绝访问", "无权限", "forbidden",
                "denied", "access denied", "403"
            ],
            "dependency_failed": [
                "依赖失败", "上游错误", "调用失败", "unavailable",
                "dependency", "connection refused"
            ],
            "timeout": [
                "超时", "无响应", "hang", "timeout",
                "no response", "stuck"
            ],
            "resource_exhausted": [
                "内存不足", "OOM", "quota", "exhausted",
                "rate limit", "429", "too many requests"
            ],
        }
        self._keywords = dict(self._builtin_keywords)
    
    def _load_external_keywords(self) -> Dict[str, List[str]]:
        """从外部 YAML 文件加载关键词"""
        keywords = {}
        try:
            if not os.path.exists(self.EXTERNAL_KEYWORDS_PATH):
                return keywords
            
            import yaml
            with open(self.EXTERNAL_KEYWORDS_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data or "keywords" not in data:
                return keywords
            
            for reason_type, kw_list in data["keywords"].items():
                if isinstance(kw_list, list):
                    keywords[reason_type] = kw_list
            
            return keywords
        except Exception as e:
            print(f"[interrupt_handler] 加载外部关键词失败: {e}")
            return keywords
    
    def _detect_keyword_conflicts(self) -> None:
        """检测关键词冲突并告警"""
        all_keywords = {}
        for reason_type, kw_list in self._keywords.items():
            for kw in kw_list:
                kw_lower = kw.lower()
                if kw_lower in all_keywords:
                    prev_type = all_keywords[kw_lower]
                    if prev_type != reason_type:
                        print(f"[interrupt_handler] ⚠️ 关键词冲突: '{kw}' 同时出现在 '{prev_type}' 和 '{reason_type}'")
                else:
                    all_keywords[kw_lower] = reason_type
    
    def _reload_keywords(self) -> None:
        """重新加载所有关键词（内置 + 外部），用于热更新"""
        # 从内置关键词开始
        self._keywords = dict(self._builtin_keywords)
        
        # 加载外部关键词（覆盖内置）
        external = self._load_external_keywords()
        for reason_type, kw_list in external.items():
            if reason_type in self._keywords:
                self._keywords[reason_type] = kw_list
            else:
                self._keywords[reason_type] = kw_list
        
        # 检测冲突
        self._detect_keyword_conflicts()
        
        total = sum(len(v) for v in self._keywords.values())
        print(f"[interrupt_handler] 关键词加载完成: {len(self._keywords)} 类型, {total} 个关键词")
    
    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        """初始化插件"""
        self.event_bus = event_bus
        self.config = config.get("interrupt_handler", {})
        
        # 从外部文件加载关键词
        self._reload_keywords()
    
    def register_events(self) -> None:
        """注册事件订阅"""
        self.event_bus.subscribe("agent.blocked", self._on_agent_blocked)
        self.event_bus.subscribe("task.failed", self._on_task_failed)
        self.event_bus.subscribe("task.timeout", self._on_task_timeout)
        self.event_bus.subscribe("user.decision", self._on_user_decision)
        # 热更新事件
        self.event_bus.subscribe("config.updated", self._on_config_updated)
        self.event_bus.subscribe("interrupt_handler.keywords_updated", self._on_keywords_updated)
    
    async def start(self) -> None:
        """启动插件"""
        pass
    
    async def pause(self) -> None:
        """暂停插件"""
        pass
    
    async def resume(self) -> None:
        """恢复插件"""
        pass
    
    async def stop(self) -> None:
        """停止插件"""
        self._retry_counts.clear()
        self._pending_decisions.clear()
    
    async def cleanup(self) -> None:
        """清理资源"""
        self._retry_counts.clear()
        self._pending_decisions.clear()
    
    # --- 事件处理 ---
    
    async def _on_agent_blocked(self, event: Event) -> None:
        """Agent 受阻"""
        agent_id = event.payload.get("agent_id", "")
        reason = event.payload.get("reason", "")
        block_type = event.payload.get("block_type", "")
        
        result = await self.handle(agent_id, reason)
        
        # 发布中断处理结果
        await self.event_bus.publish(Event(
            event_type="interrupt.handled",
            source=self.name,
            payload={
                "agent_id": agent_id,
                "action": result.action,
                "reason": result.reason,
            }
        ))
        
        # 根据结果执行对应操作
        if result.action == "retry":
            await self._handle_retry(agent_id, result)
        elif result.action == "escalate":
            await self._handle_escalation(agent_id, result)
        elif result.action == "cancel":
            await self._handle_cancel(agent_id, result)
        elif result.action == "wait":
            await self._handle_user_decision(agent_id, result)
    
    async def _on_task_failed(self, event: Event) -> None:
        """任务失败"""
        task_id = event.payload.get("task_id", "")
        error_message = event.payload.get("error_message", "")
        retry_count = event.payload.get("retry_count", 0)
        agent_id = event.payload.get("agent_id", "")
        
        # 分类失败原因
        reason_type = self._classify_reason(error_message)
        
        # 检查是否需要自动重试
        if self._should_auto_retry(reason_type, retry_count):
            await self.event_bus.publish(Event(
                event_type="interrupt.retry_requested",
                source=self.name,
                payload={
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "retry_number": retry_count + 1,
                }
            ))
        else:
            # 需要用户决策
            await self._request_user_decision(
                agent_id=agent_id,
                task_id=task_id,
                reason=error_message,
                reason_type=reason_type,
            )
    
    async def _on_task_timeout(self, event: Event) -> None:
        """任务超时"""
        task_id = event.payload.get("task_id", "")
        timeout_seconds = event.payload.get("timeout_seconds", 300)
        agent_id = event.payload.get("agent_id", "")
        
        reason_type = "timeout"
        retry_count = self._retry_counts.get(agent_id, 0)
        
        if self._should_auto_retry(reason_type, retry_count):
            self._retry_counts[agent_id] = retry_count + 1
            await self.event_bus.publish(Event(
                event_type="interrupt.retry_requested",
                source=self.name,
                payload={
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "retry_number": retry_count + 1,
                }
            ))
        else:
            await self._request_user_decision(
                agent_id=agent_id,
                task_id=task_id,
                reason=f"任务执行超时（{timeout_seconds}秒）",
                reason_type=reason_type,
            )
    
    async def _on_user_decision(self, event: Event) -> None:
        """用户决策回复"""
        decision_id = event.payload.get("decision_id", "")
        choice = event.payload.get("choice", "")
        custom_instruction = event.payload.get("custom_instruction", "")
        
        decision = self._pending_decisions.get(decision_id)
        if not decision:
            return
        
        agent_id = decision.get("agent_id")
        
        if choice == "continue":
            # 继续执行
            await self.event_bus.publish(Event(
                event_type="interrupt.retry_requested",
                source=self.name,
                payload={
                    "task_id": decision.get("task_id"),
                    "agent_id": agent_id,
                    "retry_number": 1,
                }
            ))
        elif choice == "cancel":
            # 取消任务
            await self.event_bus.publish(Event(
                event_type="interrupt.cancelled",
                source=self.name,
                payload={
                    "agent_id": agent_id,
                    "cancelled_by": "user",
                    "reason": decision.get("reason", ""),
                }
            ))
        elif choice == "custom" and custom_instruction:
            # 自定义指令
            await self.event_bus.publish(Event(
                event_type="interrupt.custom_instruction",
                source=self.name,
                payload={
                    "agent_id": agent_id,
                    "instruction": custom_instruction,
                }
            ))
        
        # 清理决策记录
        self._pending_decisions.pop(decision_id, None)
    
    # --- 热更新事件处理 ---
    
    async def _on_config_updated(self, event: Event) -> None:
        """处理配置变更事件（热更新）"""
        plugin_id = event.payload.get("plugin_id")
        if plugin_id and plugin_id != self.name:
            return
        
        print(f"[interrupt_handler] 收到配置变更事件，重新加载关键词...")
        self._reload_keywords()
    
    async def _on_keywords_updated(self, event: Event) -> None:
        """处理关键词更新事件（热更新）"""
        print(f"[interrupt_handler] 收到关键词更新事件，重新加载关键词...")
        self._reload_keywords()
    
    # --- 核心处理逻辑 ---
    
    async def handle(self, agent_id: str,
                     block_reason: str) -> InterruptResult:
        """处理中断"""
        reason_type = self._classify_reason(block_reason)
        
        # 根据类型分发
        handlers = {
            "missing_tool": self._handle_missing_tool,
            "knowledge_gap": self._handle_knowledge_gap,
            "permission_denied": self._handle_permission_denied,
            "dependency_failed": self._handle_dependency_failed,
            "timeout": self._handle_timeout,
            "resource_exhausted": self._handle_resource_exhausted,
        }
        
        handler = handlers.get(reason_type, self._handle_unknown)
        return await handler(agent_id, block_reason)
    
    def _classify_reason(self, block_reason: str) -> str:
        """分类受阻原因"""
        reason_lower = block_reason.lower()
        
        for reason_type, keywords in self._keywords.items():
            for keyword in keywords:
                if keyword.lower() in reason_lower:
                    return reason_type
        
        return "unknown"
    
    async def _handle_missing_tool(self, agent_id: str,
                                   reason: str) -> InterruptResult:
        """处理缺少工具"""
        return InterruptResult(
            handled=True,
            action="escalate",
            suggestion="当前缺少必要的工具或接口。建议：1. 安装相关插件 2. 使用替代方案 3. 升级系统",
            reason="missing_tool",
            escalation_target="suri",
        )
    
    async def _handle_knowledge_gap(self, agent_id: str,
                                    reason: str) -> InterruptResult:
        """处理知识不足"""
        return InterruptResult(
            handled=True,
            action="escalate",
            suggestion="当前角色知识不足以完成任务。建议：1. 补充角色知识 2. 切换其他角色 3. 简化任务",
            reason="knowledge_gap",
            escalation_target="suri",
        )
    
    async def _handle_permission_denied(self, agent_id: str,
                                        reason: str) -> InterruptResult:
        """处理权限不足"""
        return InterruptResult(
            handled=True,
            action="escalate",
            suggestion="权限不足，无法执行操作。建议：1. 申请权限 2. 使用其他方式 3. 联系管理员",
            reason="permission_denied",
            escalation_target="suri",
        )
    
    async def _handle_dependency_failed(self, agent_id: str,
                                        reason: str) -> InterruptResult:
        """处理依赖失败"""
        retry_count = self._retry_counts.get(agent_id, 0)
        
        if self._should_auto_retry("dependency_failed", retry_count):
            self._retry_counts[agent_id] = retry_count + 1
            return InterruptResult(
                handled=True,
                action="retry",
                suggestion=f"依赖服务失败，正在进行第 {retry_count + 1} 次重试",
                reason="dependency_failed",
            )
        else:
            return InterruptResult(
                handled=True,
                action="wait",
                suggestion="依赖服务多次失败，请确认服务状态后选择：继续重试 / 取消任务",
                reason="dependency_failed",
            )
    
    async def _handle_timeout(self, agent_id: str,
                              reason: str) -> InterruptResult:
        """处理超时"""
        retry_count = self._retry_counts.get(agent_id, 0)
        
        if self._should_auto_retry("timeout", retry_count):
            self._retry_counts[agent_id] = retry_count + 1
            return InterruptResult(
                handled=True,
                action="retry",
                suggestion=f"操作超时，正在进行第 {retry_count + 1} 次重试",
                reason="timeout",
            )
        else:
            return InterruptResult(
                handled=True,
                action="wait",
                suggestion="操作多次超时，请选择：继续重试 / 取消任务",
                reason="timeout",
            )
    
    async def _handle_resource_exhausted(self, agent_id: str,
                                         reason: str) -> InterruptResult:
        """处理资源耗尽"""
        return InterruptResult(
            handled=True,
            action="wait",
            suggestion="系统资源不足。建议：1. 等待资源释放 2. 关闭其他任务 3. 升级系统配置",
            reason="resource_exhausted",
        )
    
    async def _handle_unknown(self, agent_id: str,
                              reason: str) -> InterruptResult:
        """处理未知类型"""
        return InterruptResult(
            handled=True,
            action="escalate",
            suggestion=f"遇到未知问题：{reason[:100]}。建议：1. 查看详细日志 2. 联系技术支持",
            reason="unknown",
            escalation_target="suri",
        )
    
    def _should_auto_retry(self, reason_type: str,
                           retry_count: int) -> bool:
        """判断是否应该自动重试"""
        if not self.config.get("enable_auto_retry", True):
            return False
        
        auto_retry_types = self.config.get("auto_retry_types",
                                           ["dependency_failed", "timeout"])
        max_retries = self.config.get("max_auto_retries", 2)
        
        return reason_type in auto_retry_types and retry_count < max_retries
    
    async def _handle_retry(self, agent_id: str,
                            result: InterruptResult) -> None:
        """处理重试"""
        await self.event_bus.publish(Event(
            event_type="interrupt.retry_requested",
            source=self.name,
            payload={
                "agent_id": agent_id,
                "retry_number": self._retry_counts.get(agent_id, 1),
            }
        ))
    
    async def _handle_escalation(self, agent_id: str,
                                 result: InterruptResult) -> None:
        """处理升级"""
        await self.event_bus.publish(Event(
            event_type="interrupt.escalated",
            source=self.name,
            payload={
                "agent_id": agent_id,
                "escalation_target": result.escalation_target or "suri",
                "reason": result.reason,
                "context": {"suggestion": result.suggestion},
            }
        ))
    
    async def _handle_cancel(self, agent_id: str,
                             result: InterruptResult) -> None:
        """处理取消"""
        await self.event_bus.publish(Event(
            event_type="interrupt.cancelled",
            source=self.name,
            payload={
                "agent_id": agent_id,
                "cancelled_by": "system",
                "reason": result.reason,
            }
        ))
    
    async def _handle_user_decision(self, agent_id: str,
                                    result: InterruptResult) -> None:
        """请求用户决策"""
        decision_id = f"decision_{uuid.uuid4().hex[:8]}"
        
        self._pending_decisions[decision_id] = {
            "agent_id": agent_id,
            "reason": result.reason,
            "suggestion": result.suggestion,
        }
        
        await self.event_bus.publish(Event(
            event_type="interrupt.user_decision_needed",
            source=self.name,
            payload={
                "decision_id": decision_id,
                "agent_id": agent_id,
                "question": result.suggestion,
                "options": ["continue", "cancel"],
                "timeout": self.config.get("decision_timeout", 600),
            }
        ))
    
    async def _request_user_decision(self, agent_id: str, task_id: str,
                                     reason: str,
                                     reason_type: str) -> None:
        """请求用户决策（简化版）"""
        decision_id = f"decision_{uuid.uuid4().hex[:8]}"
        
        self._pending_decisions[decision_id] = {
            "agent_id": agent_id,
            "task_id": task_id,
            "reason": reason,
            "reason_type": reason_type,
        }
        
        await self.event_bus.publish(Event(
            event_type="interrupt.user_decision_needed",
            source=self.name,
            payload={
                "decision_id": decision_id,
                "agent_id": agent_id,
                "question": f"【任务受阻】{reason[:200]}",
                "options": ["continue", "cancel"],
                "timeout": self.config.get("decision_timeout", 600),
            }
        ))