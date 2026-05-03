"""code_tool 插件 — 代码操作工具入口（迭代 1：只读）。"""

from pathlib import Path
from typing import Any, Dict

from shared.interfaces.plugin import PluginInterface, RuleProvider, TaskTemplate, TemplateStep
from shared.utils.event_types import Event, Priority

from plugins.code_tool.reader import read_file
from plugins.code_tool.explorer import list_dir
from plugins.code_tool.search import grep
from plugins.code_tool.stats import stat_project
from plugins.code_tool.writer import write_file, append_file, create_file


class CodeToolPlugin(PluginInterface, RuleProvider):
    """代码工具插件（迭代 1 增强版：只读 + 写入）。

    支持的操作：
    - read_file: 读取文件内容
    - list_dir: 列出目录内容
    - grep: 在文件中搜索文本
    - stat_project: 统计项目信息
    - write_file: 写入文件
    - append_file: 追加文件
    - create_file: 创建新文件
    """

    def __init__(self):
        self._event_bus = None
        self._project_root: Path = None

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._project_root = Path(__file__).parent.parent.parent

    async def start(self) -> None:
        # 注册任务模板到 task_planner
        if self._event_bus:
            templates = self.get_task_templates()
            await self._event_bus.publish(Event(
                event_type="task_planner.register_rules",
                source="code_tool",
                payload={
                    "plugin_id": "code_tool",
                    "templates": [
                        {
                            "template_id": t.template_id,
                            "name": t.name,
                            "keywords": t.keywords,
                            "steps": [s.__dict__ for s in t.steps],
                            "default_role": t.default_role,
                            "priority": t.priority,
                            "description": t.description,
                        }
                        for t in templates
                    ],
                }
            ))

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    def get_task_templates(self) -> list:
        """实现 RuleProvider 接口，返回任务模板列表。"""
        return [
            TaskTemplate(
                template_id="code_tool.write_file",
                name="文件写入",
                keywords=["写入", "创建文件", "write", "create", "生成代码", "新建文件"],
                steps=[
                    TemplateStep("分析文件结构", "suri"),
                    TemplateStep("生成代码内容", "suri"),
                    TemplateStep("写入文件", "suri"),
                    TemplateStep("运行测试验证", "suri"),
                ],
                default_role="suri",
                priority=10,
                description="创建或写入文件内容"
            ),
            TaskTemplate(
                template_id="code_tool.read_file",
                name="文件读取",
                keywords=["读取", "查看文件", "read", "open", "查看代码"],
                steps=[
                    TemplateStep("定位文件路径", "suri"),
                    TemplateStep("读取文件内容", "suri"),
                    TemplateStep("分析内容", "suri"),
                ],
                default_role="suri",
                priority=5,
                description="读取并分析文件内容"
            ),
            TaskTemplate(
                template_id="code_tool.search_code",
                name="代码搜索",
                keywords=["搜索", "查找", "grep", "search", "find", "查询"],
                steps=[
                    TemplateStep("确定搜索模式", "suri"),
                    TemplateStep("执行搜索", "suri"),
                    TemplateStep("整理结果", "suri"),
                ],
                default_role="suri",
                priority=5,
                description="在代码库中搜索文本"
            ),
        ]

    def register_events(self) -> None:
        self._event_bus.subscribe("tool.call", self._on_tool_call)

    async def _on_tool_call(self, event: Event) -> None:
        """处理 tool.call 事件。"""
        tool_name = event.payload.get("tool_name", "")
        params = event.payload.get("params", {})
        result = None

        if tool_name == "code_tool.read_file":
            result = read_file(
                self._project_root,
                params.get("path", ""),
                int(params.get("offset", 0)),
                int(params.get("limit", 100)),
            )
        elif tool_name == "code_tool.list_dir":
            result = list_dir(self._project_root, params.get("path", "."))
        elif tool_name == "code_tool.grep":
            result = grep(
                self._project_root,
                params.get("pattern", ""),
                params.get("path", "."),
                params.get("glob", "*"),
            )
        elif tool_name == "code_tool.stat_project":
            result = stat_project(self._project_root, params.get("path", "."))
        elif tool_name == "code_tool.write_file":
            result = write_file(
                self._project_root,
                params.get("path", ""),
                params.get("content", ""),
            )
        elif tool_name == "code_tool.append_file":
            result = append_file(
                self._project_root,
                params.get("path", ""),
                params.get("content", ""),
            )
        elif tool_name == "code_tool.create_file":
            result = create_file(
                self._project_root,
                params.get("path", ""),
                params.get("content", ""),
            )
        else:
            return

        await self._event_bus.publish(Event(
            event_type="tool.result",
            source="code_tool",
            target=event.source,
            payload={
                "tool_name": tool_name,
                "result": result,
                "request_id": event.payload.get("request_id"),
            },
            priority=Priority.NORMAL,
        ))
