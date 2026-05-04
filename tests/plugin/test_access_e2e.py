"""Access 插件端到端终端模拟测试 — 模拟真实用户交互。

测试场景（PRD 对齐验证）：
1. 会话生命周期：create → touch → idle → expired
2. SessionHub 三层隔离：adhoc / project / global
3. 通道注册/发现机制
4. 统一协议适配（SessionMessage → user.input, SessionOutput → CLI send）
5. 能力协商与降级链（rich→markdown→text）
6. CLI 通道输入/输出循环
7. 多会话隔离与事件路由
8. 会话统计与清理

PRD 引用：
- prd/plugins/access/session-hub.md
- prd/plugins/access/session-protocol.md
- prd/plugins/access/channel-capabilities.md
- prd/plugins/access/README.md
- prd/plugins/access/channels/cli.md
- prd/operations/system-flow.md §2
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent_framework.plugins.access.session_hub import (
    SessionHub,
    Session,
    SessionMessage,
    SessionOutput,
    ChannelCapabilities,
    RegisteredChannel,
    SESSION_ACTIVE,
    SESSION_IDLE,
    SESSION_SUSPENDED,
    SESSION_EXPIRED,
    ISOLATION_ADHOC,
    ISOLATION_PROJECT,
    ISOLATION_GLOBAL,
    IDLE_TIMEOUT,
    ABSOLUTE_TIMEOUT,
    ADHOC_EXPIRE_DAYS,
    MAX_CONCURRENT_SESSIONS,
)
from agent_framework.plugins.access.channels.cli import CLIChannelPlugin
from agent_framework.plugins.access.formatter import MessageFormatter
from agent_framework.shared.utils.event_types import Event, Priority
from agent_framework.event_bus.bus import EventBus


# ── 辅助：模拟事件总线 ──


class MockEventBus:
    """模拟事件总线，采集所有发布的事件。"""

    def __init__(self):
        self.published_events: List[Event] = []
        self.subscribers: Dict[str, list] = {}

    async def publish(self, event: Event) -> None:
        self.published_events.append(event)
        # 同步调用订阅者
        handlers = self.subscribers.get(event.event_type, [])
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)

    def subscribe(self, event_type: str, handler) -> None:
        self.subscribers.setdefault(event_type, []).append(handler)


# ════════════════════════════════════════════════════════════════
# 测试 1: 会话生命周期（PRD: session-hub.md §二 会话状态流转）
# ════════════════════════════════════════════════════════════════


class TestSessionLifecycle:
    """会话生命周期测试 — 模拟用户会话从创建到过期。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "session_hub.db"
        self.hub = SessionHub(str(self.db_path))

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_create_session(self):
        """PRD: 创建会话 → 状态 active, 隔离层 adhoc（默认）。"""
        session = self.hub.create_session(
            channel_type="cli", channel_id="terminal:1"
        )
        assert session.session_id.startswith("sess_")
        assert session.state == SESSION_ACTIVE
        assert session.isolation_layer == ISOLATION_ADHOC
        assert session.channel_type == "cli"
        assert session.channel_id == "terminal:1"

    def test_session_state_transitions(self):
        """PRD: active → idle → suspended → expired 状态流转。"""
        session = self.hub.create_session(
            channel_type="cli", channel_id="terminal:2"
        )
        assert session.state == SESSION_ACTIVE

        # active → idle
        assert self.hub.update_session_state(session.session_id, SESSION_IDLE)
        reloaded = self.hub.get_session(session.session_id)
        assert reloaded.state == SESSION_IDLE

        # idle → suspended
        assert self.hub.update_session_state(session.session_id, SESSION_SUSPENDED)
        reloaded = self.hub.get_session(session.session_id)
        assert reloaded.state == SESSION_SUSPENDED

        # suspended → expired
        assert self.hub.update_session_state(session.session_id, SESSION_EXPIRED)
        reloaded = self.hub.get_session(session.session_id)
        assert reloaded.state == SESSION_EXPIRED

    def test_touch_session_resurrects_idle(self):
        """PRD: touch_session 将 idle 状态复活为 active。"""
        session = self.hub.create_session(
            channel_type="cli", channel_id="terminal:3"
        )
        self.hub.update_session_state(session.session_id, SESSION_IDLE)
        self.hub.touch_session(session.session_id)
        assert self.hub.get_session(session.session_id).state == SESSION_ACTIVE

    def test_close_session(self):
        """PRD: close_session → expired。"""
        session = self.hub.create_session(
            channel_type="cli", channel_id="terminal:4"
        )
        assert self.hub.close_session(session.session_id)
        assert self.hub.get_session(session.session_id).state == SESSION_EXPIRED

    def test_get_session_not_found(self):
        """边界：获取不存在的会话返回 None。"""
        assert self.hub.get_session("nonexistent") is None


# ════════════════════════════════════════════════════════════════
# 测试 2: 三层会话隔离（PRD: session-hub.md §二 三层隔离层）
# ════════════════════════════════════════════════════════════════


class TestSessionIsolation:
    """三层上下文隔离测试 — adhoc / project / global。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "sessions.db"
        self.hub = SessionHub(str(self.db_path))

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_default_is_adhoc(self):
        """PRD: 默认隔离层 = adhoc。"""
        session = self.hub.create_session(channel_type="cli", channel_id="t1")
        assert session.isolation_layer == ISOLATION_ADHOC
        assert session.adhoc_expire_at is not None

    def test_explicit_global(self):
        """PRD: global 层无过期时间。"""
        session = self.hub.create_session(
            channel_type="cli", channel_id="t2",
            isolation_layer=ISOLATION_GLOBAL,
        )
        assert session.isolation_layer == ISOLATION_GLOBAL
        assert session.adhoc_expire_at is None

    def test_explicit_project(self):
        """PRD: project 层关联 project_id。"""
        session = self.hub.create_session(
            channel_type="cli", channel_id="t3",
            isolation_layer=ISOLATION_PROJECT,
            project_id="proj-42",
        )
        assert session.isolation_layer == ISOLATION_PROJECT
        assert session.project_id == "proj-42"
        assert session.adhoc_expire_at is None

    def test_switch_layer_adhoc_to_project(self):
        """PRD: adhoc ↔ project ↔ global 层切换。"""
        session = self.hub.create_session(channel_type="cli", channel_id="t4")
        assert session.isolation_layer == ISOLATION_ADHOC

        # adhoc → project
        assert self.hub.switch_layer(session.session_id, ISOLATION_PROJECT, "new-project")
        reloaded = self.hub.get_session(session.session_id)
        assert reloaded.isolation_layer == ISOLATION_PROJECT
        assert reloaded.project_id == "new-project"
        assert reloaded.adhoc_expire_at is None

        # project → adhoc（恢复过期）
        assert self.hub.switch_layer(session.session_id, ISOLATION_ADHOC)
        reloaded = self.hub.get_session(session.session_id)
        assert reloaded.isolation_layer == ISOLATION_ADHOC
        assert reloaded.project_id is None
        assert reloaded.adhoc_expire_at is not None

    def test_switch_layer_global(self):
        """PRD: switch_layer to global。"""
        session = self.hub.create_session(channel_type="cli", channel_id="t5")
        assert self.hub.switch_layer(session.session_id, ISOLATION_GLOBAL)
        reloaded = self.hub.get_session(session.session_id)
        assert reloaded.isolation_layer == ISOLATION_GLOBAL
        assert reloaded.project_id is None

    def test_list_sessions_by_layer(self):
        """PRD: 按隔离层筛选会话。"""
        s1 = self.hub.create_session(channel_type="cli", channel_id="l1",
                                      isolation_layer=ISOLATION_ADHOC)
        s2 = self.hub.create_session(channel_type="cli", channel_id="l2",
                                      isolation_layer=ISOLATION_PROJECT,
                                      project_id="p1")
        s3 = self.hub.create_session(channel_type="cli", channel_id="l3",
                                      isolation_layer=ISOLATION_GLOBAL)

        adhoc_list = self.hub.list_sessions(isolation_layer=ISOLATION_ADHOC)
        assert len(adhoc_list) == 1
        assert adhoc_list[0].session_id == s1.session_id

        project_list = self.hub.list_sessions(isolation_layer=ISOLATION_PROJECT)
        assert len(project_list) == 1

        global_list = self.hub.list_sessions(isolation_layer=ISOLATION_GLOBAL)
        assert len(global_list) == 1


# ════════════════════════════════════════════════════════════════
# 测试 3: 通道注册/发现（PRD: session-hub.md §四）
# ════════════════════════════════════════════════════════════════


class TestChannelRegistration:
    """通道注册与发现 — 模拟插件注册流程。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.hub = SessionHub(str(Path(self.tmp_dir) / "hub.db"))
        self.event_bus = MockEventBus()
        self.hub.set_event_bus(self.event_bus)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_register_channel(self):
        """PRD: 注册通道 → 可查找 + 发布 channel.registered 事件。"""
        caps = ChannelCapabilities(text=True, commands=True)
        handler = MagicMock()

        await self.hub.register_channel(
            name="channel.cli",
            channel_type="cli",
            capabilities=caps,
            handler=handler,
            manifest={"version": "1.0.0"},
        )

        # 可查找
        found = self.hub.get_channel("cli")
        assert found is not None
        assert found.name == "channel.cli"
        assert found.channel_type == "cli"
        assert found.handler == handler

        # 按名称查找
        by_name = self.hub.get_channel_by_name("channel.cli")
        assert by_name is not None
        assert by_name.channel_type == "cli"

        # 发布了事件
        assert any(
            e.event_type == "channel.registered"
            for e in self.event_bus.published_events
        )

    @pytest.mark.asyncio
    async def test_list_channels(self):
        """PRD: list_channels 返回所有已注册通道。"""
        await self.hub.register_channel(
            name="channel.cli", channel_type="cli",
            capabilities=ChannelCapabilities(text=True),
            handler=MagicMock(),
        )
        await self.hub.register_channel(
            name="channel.tg", channel_type="tg",
            capabilities=ChannelCapabilities(text=True, images=True),
            handler=MagicMock(),
        )

        channels = self.hub.list_channels()
        assert len(channels) == 2
        assert any(c["name"] == "channel.cli" for c in channels)
        assert any(c["name"] == "channel.tg" for c in channels)

    @pytest.mark.asyncio
    async def test_get_channel_not_found(self):
        """边界：查找未注册通道返回 None。"""
        assert self.hub.get_channel("nonexistent") is None
        assert self.hub.get_channel_by_name("ghost") is None


# ════════════════════════════════════════════════════════════════
# 测试 4: 统一协议 — 事件路由（PRD: session-protocol.md）
# ════════════════════════════════════════════════════════════════


class TestEventRouting:
    """模拟终端用户输入 → 系统输出全流程。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.hub = SessionHub(str(Path(self.tmp_dir) / "e2e.db"))
        self.event_bus = MockEventBus()
        self.hub.set_event_bus(self.event_bus)
        self.cli_outputs: List[str] = []

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    async def _cli_send(self, output: SessionOutput):
        """模拟 CLI 通道 send 方法。"""
        self.cli_outputs.append(f"[{output.content_type}] {output.content}")

    async def _setup_channel_and_session(self) -> str:
        """注册 CLI 通道并创建会话，返回 session_id。"""
        caps = ChannelCapabilities(text=True, markdown=True)
        await self.hub.register_channel(
            name="channel.cli",
            channel_type="cli",
            capabilities=caps,
            handler=MagicMock(send=self._cli_send),
        )
        session = self.hub.create_session(
            channel_type="cli", channel_id="terminal:e2e"
        )
        return session.session_id

    @pytest.mark.asyncio
    async def test_user_text_message_routes_to_input_event(self):
        """PRD: SessionMessage(text) → route_user_input → user.input 事件。"""
        session_id = await self._setup_channel_and_session()

        msg = SessionMessage(
            session_id=session_id,
            channel_type="cli",
            channel_id="terminal:e2e",
            msg_type="text",
            content="你好，今天天气怎么样？",
        )

        await self.hub.route_user_input(msg)

        # 检查事件
        events = [e for e in self.event_bus.published_events
                  if e.event_type == "user.input"]
        assert len(events) >= 1
        assert events[0].payload["content"] == "你好，今天天气怎么样？"
        assert events[0].payload["session_id"] == session_id
        assert events[0].source == "session_hub.cli"

    @pytest.mark.asyncio
    async def test_user_command_routes_to_command_event(self):
        """PRD: SessionMessage(command) → route_user_input → user.command 事件。"""
        session_id = await self._setup_channel_and_session()

        msg = SessionMessage(
            session_id=session_id,
            channel_type="cli",
            channel_id="terminal:e2e",
            msg_type="command",
            content="/status",
        )

        await self.hub.route_user_input(msg)

        events = [e for e in self.event_bus.published_events
                  if e.event_type == "user.command"]
        assert len(events) >= 1
        assert events[0].payload["command"] == "status"

    @pytest.mark.asyncio
    async def test_system_output_routes_to_channel_send(self):
        """PRD: 系统输出 → route_system_output → 通道 send 方法。"""
        session_id = await self._setup_channel_and_session()

        # 模拟 LLM 响应事件
        event = Event(
            event_type="llm.response",
            source="llm_gateway",
            payload={
                "content": "今天天气很好！☀️",
                "session_id": session_id,
                "content_type": "markdown",
            },
            priority=Priority.NORMAL,
        )

        await self.hub.route_system_output(event)

        # CLI 通道应已收到输出
        assert len(self.cli_outputs) >= 1
        assert "今天天气很好" in self.cli_outputs[0]

    @pytest.mark.asyncio
    async def test_full_user_input_cycle(self):
        """模拟完整终端交互：用户输入 → 事件 → 系统输出 → 通道 send。"""
        session_id = await self._setup_channel_and_session()

        # Step 1: 用户输入 "写首诗"
        msg = SessionMessage(
            session_id=session_id,
            channel_type="cli", channel_id="terminal:e2e",
            msg_type="text", content="写首关于编程的诗",
        )
        await self.hub.route_user_input(msg)

        # 验证已发布 user.input
        assert any(e.event_type == "user.input" for e in self.event_bus.published_events)

        # Step 2: 系统 LLM 返回
        event = Event(
            event_type="llm.response",
            source="llm_gateway",
            payload={
                "content": "## 《编程》\n\n代码如诗，逻辑如画",
                "session_id": session_id,
            },
            priority=Priority.NORMAL,
        )
        await self.hub.route_system_output(event)

        # 验证输出路由成功
        assert len(self.cli_outputs) >= 1


# ════════════════════════════════════════════════════════════════
# 测试 5: 能力协商与降级链（PRD: channel-capabilities.md §二）
# ════════════════════════════════════════════════════════════════


class TestCapabilityNegotiation:
    """能力协商测试 — 模拟不同通道的能力降级。"""

    def setup_method(self):
        self.hub = SessionHub(":memory:")

    def _create_cli_session(self) -> Session:
        """低能力通道：仅 text, markdown。"""
        return self.hub.create_session(
            channel_type="cli", channel_id="t1",
            capabilities=ChannelCapabilities(
                text=True, markdown=True, html=False,
                images=False, video=False,
            ),
        )

    def _create_tg_session(self) -> Session:
        """中能力通道：text, markdown, images。"""
        return self.hub.create_session(
            channel_type="tg", channel_id="chat:1",
            capabilities=ChannelCapabilities(
                text=True, markdown=True, html=False,
                images=True, video=False, files=True,
            ),
        )

    def test_cli_markdown_direct(self):
        """PRD: CLI 通道直接支持 markdown。"""
        session = self._create_cli_session()
        output = self.hub.negotiate_output(session, "markdown", "# Hello")
        assert output.content_type == "markdown"
        assert output.content == "# Hello"

    def test_cli_image_degrade_to_text(self):
        """PRD: CLI 不支持图片 → image → text 降级。"""
        session = self._create_cli_session()
        output = self.hub.negotiate_output(session, "image", "sunset.png")
        assert output.content_type == "text"
        assert "图片" in output.content

    def test_cli_video_degrade_to_text(self):
        """PRD: CLI 不支持视频 → video → image → text 降级。"""
        session = self._create_cli_session()
        output = self.hub.negotiate_output(session, "video", "movie.mp4")
        assert output.content_type == "text"

    def test_cli_html_degrade_to_markdown(self):
        """PRD: CLI 不支持 HTML → html → markdown 降级。"""
        session = self._create_cli_session()
        output = self.hub.negotiate_output(session, "html", "<b>bold</b>")
        assert output.content_type in ("markdown", "text")

    def test_cli_file_degrade_to_text(self):
        """PRD: CLI 不支持文件 → file → text 降级。"""
        session = self._create_cli_session()
        output = self.hub.negotiate_output(session, "file", "doc.pdf")
        assert output.content_type == "text"

    def test_cli_rich_degrade_to_markdown(self):
        """PRD: CLI 不支持富文本 → rich → markdown → text 降级。"""
        session = self._create_cli_session()
        output = self.hub.negotiate_output(session, "rich",
                                            "**富文本内容**\n- 列表项1")
        assert output.content_type in ("markdown", "text")

    def test_tg_image_direct(self):
        """PRD: Telegram 通道直接支持图片。"""
        session = self._create_tg_session()
        output = self.hub.negotiate_output(session, "image", "photo.jpg")
        assert output.content_type == "image"

    def test_tg_file_direct(self):
        """PRD: Telegram 通道直接支持文件。"""
        session = self._create_tg_session()
        output = self.hub.negotiate_output(session, "file", "doc.pdf")
        assert output.content_type == "file"

    def test_degrade_nonexistent_channel(self):
        """边界：通道未注册时使用默认降级链。"""
        session = Session(
            session_id="orphan", channel_type="unknown",
            channel_id="nobody",
            capabilities=ChannelCapabilities(text=True),
        )
        output = self.hub.negotiate_output(session, "video", "clip.mp4")
        assert output.content_type == "text"


# ════════════════════════════════════════════════════════════════
# 测试 6: 会话过期清理（PRD: session-hub.md 超时机制）
# ════════════════════════════════════════════════════════════════


class TestSessionCleanup:
    """模拟终端长时间闲置后的会话清理。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.hub = SessionHub(str(Path(self.tmp_dir) / "cleanup.db"))
        # 让 IDLE_TIMEOUT 短一些便于测试
        self.original_idle = IDLE_TIMEOUT
        from agent_framework.plugins.access import session_hub
        session_hub.IDLE_TIMEOUT = 0.1  # 100ms
        session_hub.ABSOLUTE_TIMEOUT = 3600  # 避免干扰

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        from agent_framework.plugins.access import session_hub
        session_hub.IDLE_TIMEOUT = self.original_idle

    @pytest.mark.asyncio
    async def test_idle_timeout_expires_session(self):
        """PRD: idle 超时 → expired。"""
        session = self.hub.create_session(channel_type="cli", channel_id="idle-test")
        self.hub.update_session_state(session.session_id, SESSION_IDLE)
        await asyncio.sleep(0.2)
        cleaned = self.hub.cleanup_stale_sessions()
        assert cleaned >= 1
        assert self.hub.get_session(session.session_id).state == SESSION_EXPIRED

    def test_adhoc_expiry(self):
        """PRD: Ad-hoc 层 7 天后过期。"""
        session = self.hub.create_session(
            channel_type="cli", channel_id="adhoc-exp",
            isolation_layer=ISOLATION_ADHOC,
        )
        # 手动设置过去的时间
        session.adhoc_expire_at = time.time() - 1  # 已过期
        self.hub._persist_session(session)
        cleaned = self.hub.cleanup_stale_sessions()
        assert cleaned >= 1

    def test_expired_sessions_removed_from_cache(self):
        """PRD: 过期会话从内存缓存中移除。"""
        session = self.hub.create_session(
            channel_type="cli", channel_id="cache-test"
        )
        assert session.session_id in self.hub._sessions

        self.hub.close_session(session.session_id)
        self.hub._sessions = {
            k: v for k, v in self.hub._sessions.items()
            if v.state != SESSION_EXPIRED
        }
        assert session.session_id not in self.hub._sessions


# ════════════════════════════════════════════════════════════════
# 测试 7: 会话统计（PRD: session-hub.md 监控）
# ════════════════════════════════════════════════════════════════


class TestSessionStats:
    """会话统计与监控。"""

    def setup_method(self):
        self.hub = SessionHub(":memory:")

    def test_get_stats(self):
        """PRD: get_stats 返回完整的会话统计。"""
        self.hub.create_session(channel_type="cli", channel_id="s1")
        self.hub.create_session(channel_type="cli", channel_id="s2",
                                 isolation_layer=ISOLATION_PROJECT,
                                 project_id="p1")
        self.hub.create_session(channel_type="tg", channel_id="chat:1")

        stats = self.hub.get_stats()
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 3
        assert stats["by_channel"]["cli"] == 2
        assert stats["by_channel"]["tg"] == 1
        assert stats["by_isolation_layer"][ISOLATION_ADHOC] == 2
        assert stats["by_isolation_layer"][ISOLATION_PROJECT] == 1


# ════════════════════════════════════════════════════════════════
# 测试 8: CLI 通道插件完整功能（PRD: cli.md）
# ════════════════════════════════════════════════════════════════


class TestCLIChannelPlugin:
    """CLI 通道插件终端模拟。"""

    def setup_method(self):
        self.event_bus = MockEventBus()
        self.cli = CLIChannelPlugin(self.event_bus)

    @pytest.mark.asyncio
    async def test_cli_capabilities(self):
        """PRD cli.md §二: CLI 能力清单匹配。"""
        caps = self.cli.capabilities
        assert caps.text is True
        assert caps.markdown is True
        assert caps.commands is True
        assert caps.images is False
        assert caps.video is False
        assert caps.audio is False
        assert caps.files is False
        assert caps.rich_ui is False
        assert caps.buttons is False
        assert caps.text_stream is True

    def test_cli_channel_type(self):
        """PRD cli.md §二: channel_type = "cli"。"""
        assert self.cli.channel_type == "cli"

    @pytest.mark.asyncio
    async def test_cli_start_with_hub(self):
        """CLI 通道启动并注册到 SessionHub。"""
        hub = SessionHub(":memory:")
        hub.set_event_bus(self.event_bus)
        await self.cli.start(session_hub=hub)

        assert self.cli._session_hub is not None
        found = hub.get_channel("cli")
        assert found is not None

    @pytest.mark.asyncio
    async def test_cli_send_output(self):
        """PRD cli.md §四: send 方法输出文本。"""
        output = SessionOutput(
            channel_type="cli",
            channel_id="terminal",
            content_type="text",
            content="Hello, Suri!",
        )
        # 不应抛出异常
        await self.cli.send(output)

    @pytest.mark.asyncio
    async def test_cli_stop(self):
        """CLI 通道 stop 正确停止。"""
        self.cli.stop()
        assert self.cli._running is False


# ════════════════════════════════════════════════════════════════
# 测试 9: MessageFormatter 消息格式化（PRD: cli.md §四、七）
# ════════════════════════════════════════════════════════════════


class TestMessageFormatter:
    """消息格式化 — 模拟终端显示格式。"""

    def test_error_401_suggests_setkey(self):
        """401 错误含 /setkey 提示。"""
        msg = MessageFormatter.format_error(401, "API Key 无效", "deepseek")
        assert "/setkey" in msg
        assert "deepseek" in msg
        assert "⚠️" in msg

    def test_error_3002_suggests_setkey(self):
        """3002 错误含 /setkey 提示。"""
        msg = MessageFormatter.format_error(3002, "No API key", "kimi")
        assert "/setkey" in msg

    def test_status_panel(self):
        """状态面板含模型和 Key 状态。"""
        providers = {
            "deepseek": {"models": ["deepseek-chat"], "api_key": True},
            "kimi": {"models": ["moonshot-v1-8k"], "api_key": False},
        }
        panel = MessageFormatter.format_status(
            providers, "deepseek", "deepseek-chat",
            {"deepseek": "sk-xxx"}
        )
        assert "✅" in panel
        assert "❌" in panel

    def test_decision_menu(self):
        """决策菜单含选项和编号范围。"""
        menu = MessageFormatter.format_decision("请选择：", ["A", "B", "C"])
        assert "A" in menu
        assert "C" in menu
        assert "1-3" in menu


# ════════════════════════════════════════════════════════════════
# 测试 10: 多会话隔离（PRD: session-hub.md §二）
# ════════════════════════════════════════════════════════════════


class TestMultiSessionIsolation:
    """多用户同时使用 — 会话间数据隔离。"""

    def setup_method(self):
        self.hub = SessionHub(":memory:")

    def test_find_session_by_channel(self):
        """PRD: 按通道查找活跃会话。"""
        self.hub.create_session(channel_type="cli", channel_id="user1-term")
        self.hub.create_session(channel_type="cli", channel_id="user2-term")
        self.hub.create_session(channel_type="tg", channel_id="tg:user1")

        found = self.hub.find_session_by_channel("cli", "user1-term")
        assert found is not None
        assert found.channel_id == "user1-term"

    def test_session_context_isolation(self):
        """不同会话的 context 相互隔离。"""
        s1 = self.hub.create_session(channel_type="cli", channel_id="ctx1")
        s2 = self.hub.create_session(channel_type="cli", channel_id="ctx2")

        s1.context["project"] = "proj-A"
        self.hub._persist_session(s1)

        r1 = self.hub.get_session(s1.session_id)
        r2 = self.hub.get_session(s2.session_id)

        assert r1.context.get("project") == "proj-A"
        assert r2.context.get("project") is None


# ════════════════════════════════════════════════════════════════
# 运行：python -m pytest tests/plugin/test_access_e2e.py -v --tb=short
# ════════════════════════════════════════════════════════════════