"""Suri Agent 共享常量。

所有硬编码路径、目录集合、安全规则集中在此文件，
各插件从此导入，避免重复定义。
"""

from typing import List, Tuple

# ============================================================
# 文件系统路径常量
# ============================================================

# 插件扫描目录
PLUGIN_SCAN_DIRS: List[str] = [
    "agent_framework/plugins/",
]

# 项目核心子目录（用于目录完整性检查）
REQUIRED_CORE_DIRS: List[str] = [
    "agent_framework/core/suri_core",
    "agent_framework/event_bus",
    "agent_framework/plugin_manager",
    "agent_framework/shared/interfaces",
    "agent_framework/shared/utils",
    "prd",
    "roles",
    "tests",
]

# 运行时数据目录（~/.suri/runtime/）
RUNTIME_DIR = ".suri/runtime"
RUNTIME_DB_NAME = "suri.db"

# 角色数据目录名
ROLES_DIR = "roles"
PLUGINS_DIR = "plugins"
PRD_DIR = "prd"
TESTS_DIR = "tests"
WORKS_DIR = "works"

# ============================================================
# 安全权限常量
# ============================================================

# 禁止写入的系统目录（这些目录写操作直接拒绝）
FORBIDDEN_WRITE_DIRS: List[str] = [
    "agent_framework/core/",
    "agent_framework/shared/interfaces/",
    "agent_framework/event_bus/",
    "agent_framework/plugin_manager/",
]

# 需要用户审批才能写入的目录
APPROVAL_REQUIRED_DIRS: List[str] = [
    "agent_framework/plugins/",
    "agent_framework/",
    "tests/",
    "roles/",
    "prd/",
]

# 安全可读目录（读操作无需审批）
SAFE_READ_DIRS: List[str] = [
    "agent_framework/",
    "roles/",
    "prd/",
    "tests/",
    "works/",
]

# 安全可写目录（写操作无需审批，通常为工作区）
SAFE_WRITE_DIRS: List[str] = [
    "works/",
]

# 代码扫描禁止的 API 列表
FORBIDDEN_APIS: List[str] = [
    "socket", "subprocess", "os.system", "os.popen",
    "os.exec", "os.spawn", "eval", "exec", "compile",
    "__import__", "ctypes", "imp",
]

# ============================================================
# 事件常量
# ============================================================

# 系统事件
EVENT_SYSTEM_STARTED = "system.started"
EVENT_SYSTEM_READY = "system.ready"
EVENT_SYSTEM_SHUTDOWN = "system.shutdown"
EVENT_SYSTEM_SHUTTING_DOWN = "system.shutting_down"
EVENT_SYSTEM_PLUGIN_LOADED = "system.plugin_loaded"
EVENT_SYSTEM_PLUGIN_UNLOADED = "system.plugin_unloaded"
EVENT_SYSTEM_CONFIG_CHANGED = "system.config_changed"

# 用户事件
EVENT_USER_INPUT = "user.input"
EVENT_USER_COMMAND = "user.command"
EVENT_USER_DECISION = "user.decision"

# 任务事件
EVENT_TASK_CREATED = "task.created"
EVENT_TASK_PLANNED = "task.planned"
EVENT_TASK_PLAN_UPDATED = "task.plan_updated"
EVENT_TASK_STARTED = "task.started"
EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_FAILED = "task.failed"
EVENT_TASK_TIMEOUT = "task.timeout"
EVENT_TASK_CANCELLED = "task.cancelled"
EVENT_TASK_STEP_ASSIGNED = "task.step_assigned"
EVENT_TASK_STEP_STARTED = "task.step_started"

# 工具事件
EVENT_TOOL_CALL = "tool.call"
EVENT_TOOL_RESULT = "tool.result"

# LLM 事件
EVENT_LLM_REQUEST = "llm.request"
EVENT_LLM_RESPONSE = "llm.response"
EVENT_LLM_ERROR = "llm.error"

# Agent 事件
EVENT_AGENT_CREATED = "agent.created"
EVENT_AGENT_STATUS_CHANGED = "agent.status_changed"
EVENT_AGENT_BLOCKED = "agent.blocked"
EVENT_AGENT_COMPLETED = "agent.completed"

# 角色事件
EVENT_ROLE_CONTEXT_READY = "role.context_ready"
EVENT_ROLE_CREATE_REQUESTED = "role.create_requested"
EVENT_ROLE_CREATED = "role.created"

# 插件事件
EVENT_PLUGIN_UPGRADE_PROPOSED = "plugin.upgrade_proposed"
EVENT_ERROR_PLUGIN = "error.plugin"
EVENT_ERROR_TOOL = "error.tool"
EVENT_ERROR_SECURITY = "error.security"

# 中断事件
EVENT_INTERRUPT_HANDLED = "interrupt.handled"
EVENT_INTERRUPT_ESCALATED = "interrupt.escalated"
EVENT_INTERRUPT_USER_DECISION_NEEDED = "interrupt.user_decision_needed"
EVENT_INTERRUPT_CANCELLED = "interrupt.cancelled"
EVENT_INTERRUPT_RETRY_REQUESTED = "interrupt.retry_requested"
EVENT_INTERRUPT_CUSTOM_INSTRUCTION = "interrupt.custom_instruction"

# ============================================================
# 拓扑排序优先级常量
# ============================================================

# 插件加载层级（数字越小越先加载）
PLUGIN_LAYER_CORE = 0      # SuriCorePlugin
PLUGIN_LAYER_BASIC = 1     # config_service, log_service, security_service
PLUGIN_LAYER_BUS = 2       # event_bus
PLUGIN_LAYER_STATE = 3     # role_manager, task_planner
PLUGIN_LAYER_CAPABILITY = 4  # code_tool, llm_gateway, agent_registry
PLUGIN_LAYER_EXTERNAL = 5  # access, interrupt_handler, task_scheduler

# ============================================================
# 文件写入常量
# ============================================================

# 文件备份后缀
BACKUP_SUFFIX = ".bak"

# 临时文件后缀（用于原子写入）
TEMP_SUFFIX = ".tmp"

# 最大文件大小（字节），超过此大小的文件写入需额外审批
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB