"""
日志服务

关联文档: suri-agent/infrastructure/infrastructure.md

职责：
- 统一管理 suri 平台的分类运行日志
- 按模块分类存储于 logs/ 下各子目录
- 按天轮转日志文件
- 输出中文日志，包含时间戳、级别、模块、消息

日志分类：
- logs/runtime/   — 程序运行日志（用户交互、模型调用、命令）
- logs/error/     — 错误日志（异常、崩溃、API 失败）
- logs/schedule/  — 调度日志（任务创建、角色间调度）
- logs/role/      — 角色通信日志（角色间消息）
- logs/system/    — 系统日志（启动、关闭、代码变更、重载）
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


def _load_categories(project_root: Path) -> Dict[str, str]:
    """从 logs/categories.yaml 加载日志分类配置"""
    yaml_path = project_root / "logs" / "categories.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                cats = {}
                for key, val in data.get("categories", {}).items():
                    if isinstance(val, dict):
                        cats[key] = val.get("label", key)
                    else:
                        cats[key] = val
                return cats
        except Exception:
            pass
    # 回退到默认
    return {
        "runtime": "程序运行",
        "error": "错误",
        "schedule": "调度",
        "role": "角色通信",
        "system": "系统",
        "statistics": "统计",
        "tool_calls": "工具调用",
    }


class LoggerService:
    """日志服务"""
    
    LOG_BASE = "logs"
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.log_base = project_root / self.LOG_BASE
        self.CATEGORIES = _load_categories(project_root)
        self._ensure_dirs()
        self._current_date: Optional[str] = None
        
    def _ensure_dirs(self) -> None:
        """确保所有分类日志目录存在"""
        for cat in self.CATEGORIES:
            (self.log_base / cat).mkdir(parents=True, exist_ok=True)
        
    def _get_log_file(self, category: str) -> Path:
        """获取当前日期的分类日志文件路径"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_base / category / f"suri-{today}.log"
    
    def _write(self, category: str, level: str, module: str, message: str) -> None:
        """写入指定分类的日志"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now}] [{level}] [{module}] {message}\n"
        
        log_file = self._get_log_file(category)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            print(f"[日志写入失败] {e}", file=sys.stderr)
        
        # 日志只写入文件，不打印到控制台（避免干扰终端对话）
        # 如需调试，可直接查看 logs/ 目录下的分类日志文件
    
    # ========== 分类日志方法 ==========
    
    def runtime(self, level: str, module: str, message: str) -> None:
        """程序运行日志"""
        self._write("runtime", level, module, message)
    
    def error_log(self, level: str, module: str, message: str) -> None:
        """错误日志"""
        self._write("error", level, module, message)
    
    def schedule(self, level: str, module: str, message: str) -> None:
        """调度日志"""
        self._write("schedule", level, module, message)
    
    def role(self, level: str, module: str, message: str) -> None:
        """角色通信日志"""
        self._write("role", level, module, message)
    
    def system(self, level: str, module: str, message: str) -> None:
        """系统日志"""
        self._write("system", level, module, message)
    
    # ========== 业务事件快捷方法（自动选择分类） ==========
    
    def info(self, module: str, message: str) -> None:
        """通用信息（写入 runtime）"""
        self.runtime("信息", module, message)
    
    def warn(self, module: str, message: str) -> None:
        """通用警告（同时写入 runtime 和 error）"""
        self.runtime("警告", module, message)
        self.error_log("警告", module, message)
    
    def error(self, module: str, message: str) -> None:
        """通用错误（同时写入 runtime 和 error）"""
        self.runtime("错误", module, message)
        self.error_log("错误", module, message)
    
    def debug(self, module: str, message: str) -> None:
        """调试信息（仅写入 runtime 文件）"""
        self._write("runtime", "调试", module, message)
    
    def log_startup(self, roles_count: int) -> None:
        """记录程序启动"""
        self.system("信息", "系统", f"suri 平台启动，已加载 {roles_count} 个角色")
    
    def log_shutdown(self) -> None:
        """记录程序关闭"""
        self.system("信息", "系统", "suri 平台关闭")
    
    def log_user_input(self, user_id: str, content: str) -> None:
        """记录用户输入"""
        preview = content[:60] + "..." if len(content) > 60 else content
        self.runtime("信息", "用户交互", f"用户 {user_id} 输入: {preview}")
    
    def log_task_created(self, task_id: str, user_id: str, content: str) -> None:
        """记录任务创建"""
        preview = content[:50] + "..." if len(content) > 50 else content
        self.schedule("信息", "任务调度", f"任务 {task_id} 已创建 | 用户: {user_id} | 内容: {preview}")
    
    def log_task_dispatched(self, task_id: str, from_role: str, to_role: str, dept: str = "") -> None:
        """记录任务调度（角色间分发）"""
        dept_info = f" | 部门: {dept}" if dept else ""
        self.schedule("信息", "任务调度", f"任务 {task_id} 从 [{from_role}] 调度至 [{to_role}]{dept_info}")
    
    def log_model_call(self, model_name: str, model_id: str, status: str, detail: str = "") -> None:
        """记录模型调用"""
        detail_str = f" | {detail}" if detail else ""
        self.runtime("信息", "模型调用", f"模型 [{model_name}]({model_id}) 调用{status}{detail_str}")
    
    def log_model_call_error(self, model_name: str, error: str) -> None:
        """记录模型调用失败"""
        self.error_log("错误", "模型调用", f"模型 [{model_name}] 调用失败: {error}")
        self.runtime("错误", "模型调用", f"模型 [{model_name}] 调用失败: {error}")
    
    def log_command(self, user_id: str, command: str) -> None:
        """记录命令执行"""
        self.runtime("信息", "命令", f"用户 {user_id} 执行命令: {command}")
    
    def log_role_message(self, from_role: str, to_role: str, task_ref: str, msg_type: str = "消息") -> None:
        """记录角色间通信"""
        self.role("信息", "角色通信", f"[{from_role}] → [{to_role}] 发送{msg_type} | 任务关联: {task_ref}")
    
    def log_code_change_detected(self) -> None:
        """记录代码变更检测"""
        self.system("警告", "系统", "检测到核心代码已变更，建议执行 /reload 重新加载服务")
    
    def log_service_reload(self) -> None:
        """记录服务重载"""
        self.system("信息", "系统", "服务已重新加载，角色记忆保留")
    
    def log_config(self, event: str, detail: str = "") -> None:
        """记录配置相关事件"""
        detail_str = f" | {detail}" if detail else ""
        self.runtime("信息", "配置", f"{event}{detail_str}")
    
    def log_doc_sync(self, action: str, files: int = 0) -> None:
        """记录文档同步事件"""
        files_str = f"，涉及 {files} 个文件" if files else ""
        self.system("信息", "文档同步", f"{action}{files_str}")
    
    def log_learning(self, role_id: str, event: str, detail: str = "") -> None:
        """记录自学习事件"""
        detail_str = f" | {detail}" if detail else ""
        self.runtime("信息", "自学习", f"[{role_id}] {event}{detail_str}")
    
    def log_learning_error(self, role_id: str, error: str) -> None:
        """记录自学习错误"""
        self.error_log("错误", "自学习", f"[{role_id}] {error}")
        self.runtime("错误", "自学习", f"[{role_id}] {error}")
    
    def _write_json_log(self, category: str, data: Dict[str, Any]) -> None:
        """写入 JSON 结构化日志（便于统计角色解析）"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = self.log_base / category
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"suri-{today}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[JSON日志写入失败] {e}", file=sys.stderr)
    
    def log_token_usage(self, model_id: str, prompt_tokens: int, 
                        completion_tokens: int, total_tokens: int, 
                        task_hint: str = "", role_id: str = "") -> None:
        """记录 Token 消耗（文本日志 + JSON 结构化日志）"""
        hint_str = f" | 任务: {task_hint[:30]}" if task_hint else ""
        role_str = f" | 角色: {role_id}" if role_id else ""
        self.runtime(
            "信息", "Token消耗",
            f"模型: {model_id} | prompt={prompt_tokens} completion={completion_tokens} "
            f"total={total_tokens}{hint_str}{role_str}"
        )
        # 同时写入结构化 JSON 日志
        self._write_json_log("statistics", {
            "event": "token_usage",
            "timestamp": datetime.now().isoformat(),
            "model_id": model_id,
            "role_id": role_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "task_hint": task_hint
        })
    
    def log_file_created(self, role_id: str, filepath: str, 
                         file_type: str = "", size: int = 0) -> None:
        """记录文件创建事件"""
        self.runtime("信息", "文件创建", 
                     f"角色: {role_id} | 文件: {filepath} | 类型: {file_type} | 大小: {size}B")
        self._write_json_log("statistics", {
            "event": "file_created",
            "timestamp": datetime.now().isoformat(),
            "role_id": role_id,
            "filepath": filepath,
            "file_type": file_type,
            "size": size
        })
    
    def log_task_completed(self, task_id: str, role_id: str, 
                           status: str, duration_seconds: float = 0) -> None:
        """记录任务完成事件"""
        self.schedule("信息", "任务完成",
                      f"任务: {task_id} | 角色: {role_id} | 状态: {status} | 耗时: {duration_seconds:.1f}s")
        self._write_json_log("statistics", {
            "event": "task_completed",
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "role_id": role_id,
            "status": status,
            "duration_seconds": duration_seconds
        })
    
    def log_tool_call(self, caller_role: str, tool_id: str,
                       params: Dict[str, Any], success: bool) -> None:
        """记录工具调用（统一入口，替代 ToolService 独立写文件）"""
        self._write(
            "tool_calls", "信息", "工具调用",
            f"role={caller_role} tool={tool_id} params={str(params)[:200]} success={success}"
        )
    
    def get_today_logs(self, category: str = "") -> Dict[str, Path]:
        """获取今日所有分类日志文件路径"""
        today = datetime.now().strftime("%Y-%m-%d")
        if category and category in self.CATEGORIES:
            # statistics 使用 .jsonl 后缀
            suffix = "jsonl" if category == "statistics" else "log"
            return {category: self.log_base / category / f"suri-{today}.{suffix}"}
        result = {}
        for cat in self.CATEGORIES:
            suffix = "jsonl" if cat == "statistics" else "log"
            result[cat] = self.log_base / cat / f"suri-{today}.{suffix}"
        return result
