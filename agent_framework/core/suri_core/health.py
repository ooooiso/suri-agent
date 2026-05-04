"""启动自检模块 — Pre-boot Healthcheck。

执行 7 类检查，确保系统启动前所有条件满足。
返回三级判定：通过 / 警告 / 致命。
"""

import json
import os
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class HealthCheckItem:
    """单条检查结果。"""
    name: str                          # 检查项名称
    status: str                        # passed | warning | failed
    message: str                       # 详细描述
    severity: str = "warning"          # warning | fatal
    
    def is_passed(self) -> bool:
        return self.status == "passed"
    
    def is_fatal(self) -> bool:
        return self.severity == "fatal" and self.status == "failed"


@dataclass
class HealthReport:
    """健康检查报告。"""
    items: List[HealthCheckItem] = field(default_factory=list)
    
    def add(self, item: HealthCheckItem) -> None:
        self.items.append(item)
    
    @property
    def has_fatal(self) -> bool:
        return any(item.is_fatal() for item in self.items)
    
    @property
    def has_warning(self) -> bool:
        return any(item.status == "warning" for item in self.items)
    
    @property
    def all_passed(self) -> bool:
        return all(item.is_passed() for item in self.items)
    
    def summary(self) -> Dict[str, Any]:
        return {
            "total": len(self.items),
            "passed": sum(1 for i in self.items if i.is_passed()),
            "warning": sum(1 for i in self.items if i.status == "warning"),
            "failed": sum(1 for i in self.items if i.status == "failed"),
            "has_fatal": self.has_fatal,
            "has_warning": self.has_warning,
            "all_passed": self.all_passed,
        }
    
    def print_report(self) -> None:
        """打印可读的健康报告。"""
        lines = ["\n" + "=" * 50, "  Pre-boot Healthcheck Report", "=" * 50]
        for item in self.items:
            icon = {"passed": "✅", "warning": "⚠️", "failed": "❌"}.get(item.status, "❓")
            lines.append(f"  {icon} [{item.status.upper()}] {item.name}")
            lines.append(f"      {item.message}")
        lines.append("-" * 50)
        s = self.summary()
        lines.append(f"  总计: {s['total']} | ✅ {s['passed']} | ⚠️ {s['warning']} | ❌ {s['failed']}")
        if s['all_passed']:
            lines.append("  结论: ✅ 全部通过")
        elif s['has_fatal']:
            lines.append("  结论: ❌ 存在致命错误，阻止启动")
        else:
            lines.append("  结论: ⚠️ 存在警告，建议处理")
        lines.append("=" * 50 + "\n")
        print("\n".join(lines))


def check_environment() -> List[HealthCheckItem]:
    """1. 环境自检：Python 版本, OS, 磁盘空间"""
    items = []
    
    # Python 版本
    py_version = sys.version_info
    if py_version.major >= 3 and py_version.minor >= 8:
        items.append(HealthCheckItem(
            name="Python 版本",
            status="passed",
            message=f"Python {py_version.major}.{py_version.minor}.{py_version.micro} (要求 >= 3.8)"
        ))
    else:
        items.append(HealthCheckItem(
            name="Python 版本",
            status="failed",
            message=f"Python {py_version.major}.{py_version.minor}.{py_version.micro} (要求 >= 3.8)",
            severity="fatal"
        ))
    
    # 操作系统
    items.append(HealthCheckItem(
        name="操作系统",
        status="passed",
        message=f"{sys.platform}"
    ))
    
    # 磁盘空间 (~/.suri 目录所在分区)
    suri_dir = Path.home() / ".suri"
    try:
        suri_dir.mkdir(parents=True, exist_ok=True)
        stat = shutil.disk_usage(suri_dir)
        free_mb = stat.free // (1024 * 1024)
        if free_mb > 100:
            items.append(HealthCheckItem(
                name="磁盘空间",
                status="passed",
                message=f"剩余 {free_mb} MB"
            ))
        elif free_mb > 10:
            items.append(HealthCheckItem(
                name="磁盘空间",
                status="warning",
                message=f"剩余 {free_mb} MB，建议释放空间"
            ))
        else:
            items.append(HealthCheckItem(
                name="磁盘空间",
                status="failed",
                message=f"剩余 {free_mb} MB，磁盘空间不足",
                severity="fatal"
            ))
    except Exception as e:
        items.append(HealthCheckItem(
            name="磁盘空间",
            status="warning",
            message=f"无法检查磁盘空间: {e}"
        ))
    
    return items


def check_roles(roles_dir: Path) -> List[HealthCheckItem]:
    """2. 角色自检：核心角色 suri 存在"""
    items = []
    
    suri_dir = roles_dir / "suri"
    suri_soul = suri_dir / "soul.md"
    suri_meta = suri_dir / "meta.json"
    
    if suri_dir.exists() and suri_soul.exists() and suri_meta.exists():
        items.append(HealthCheckItem(
            name="核心角色 suri",
            status="passed",
            message="suri Soul 和 meta 文件均存在"
        ))
    else:
        items.append(HealthCheckItem(
            name="核心角色 suri",
            status="failed",
            message="suri 角色不完整，将自动创建",
            severity="fatal"
        ))
    
    # 列出所有角色
    try:
        roles = []
        for item in roles_dir.iterdir():
            if item.is_dir() and (item / "meta.json").exists():
                roles.append(item.name)
        if len(roles) > 0:
            items.append(HealthCheckItem(
                name="角色列表",
                status="passed",
                message=f"已注册 {len(roles)} 个角色: {', '.join(roles)}"
            ))
    except Exception as e:
        items.append(HealthCheckItem(
            name="角色列表",
            status="warning",
            message=f"无法扫描角色: {e}"
        ))
    
    return items


def check_project(project_root: Path) -> List[HealthCheckItem]:
    """3. 项目自检：关键目录和文件"""
    items = []
    checks = {
        "agent_framework": "框架核心",
        "prd": "PRD 文档",
        "roles": "角色定义",
        "tests": "测试",
        "main.py": "入口文件",
        "requirements.txt": "依赖清单",
    }
    
    for path, desc in checks.items():
        if (project_root / path).exists():
            items.append(HealthCheckItem(
                name=f"项目目录: {path}",
                status="passed",
                message=f"{desc} 存在"
            ))
        else:
            items.append(HealthCheckItem(
                name=f"项目目录: {path}",
                status="warning",
                message=f"{desc} 不存在"
            ))
    
    return items


def check_plugins(plugins_dir: Path) -> List[HealthCheckItem]:
    """4. 插件自检：manifest.json 扫描"""
    items = []
    
    if not plugins_dir.exists():
        items.append(HealthCheckItem(
            name="插件目录",
            status="failed",
            message="插件目录不存在",
            severity="fatal"
        ))
        return items
    
    try:
        manifests = list(plugins_dir.rglob("manifest.json"))
        plugin_names = []
        missing_plugins = []
        
        # 期望的关键插件
        expected = [
            "config_service", "log_service", "security_service",
            "llm_gateway", "role_manager",
            "task_planner", "task_scheduler", "interrupt_handler",
            "code_tool",
        ]
        
        found_expected = []
        for m in manifests:
            try:
                with open(m, "r", encoding="utf-8") as f:
                    data = json.load(f)
                pid = data.get("id", m.parent.name)
                plugin_names.append(pid)
                if pid in expected:
                    found_expected.append(pid)
            except Exception:
                plugin_names.append(f"{m.parent.name} (load error)")
        
        # 检查缺失的关键插件
        for exp in expected:
            if exp not in found_expected:
                missing_plugins.append(exp)
        
        items.append(HealthCheckItem(
            name="插件扫描",
            status="passed",
            message=f"发现 {len(manifests)} 个插件: {', '.join(plugin_names[:10])}{'...' if len(plugin_names) > 10 else ''}"
        ))
        
        if missing_plugins:
            items.append(HealthCheckItem(
                name="关键插件缺失",
                status="warning",
                message=f"缺失 {missing_plugins}（可能尚未实现）"
            ))
    
    except Exception as e:
        items.append(HealthCheckItem(
            name="插件扫描",
            status="warning",
            message=f"扫描失败: {e}"
        ))
    
    return items


def check_database(db_path: Path) -> List[HealthCheckItem]:
    """5. 数据库自检：SQLite 可读写 + schema 版本"""
    items = []
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 检查可读写
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result:
            items.append(HealthCheckItem(
                name="SQLite 连接",
                status="passed",
                message="数据库连接正常，读写可用"
            ))
        
        # 检查 schema 版本
        try:
            cursor.execute("SELECT version FROM _schema_version ORDER BY version DESC LIMIT 1")
            version = cursor.fetchone()
            if version:
                items.append(HealthCheckItem(
                    name="数据库 Schema",
                    status="passed",
                    message=f"Schema 版本: {version[0]}"
                ))
            else:
                items.append(HealthCheckItem(
                    name="数据库 Schema",
                    status="warning",
                    message="Schema 版本表为空，需要迁移"
                ))
        except sqlite3.OperationalError:
            items.append(HealthCheckItem(
                name="数据库 Schema",
                status="warning",
                message="Schema 版本表不存在，需要初始化迁移"
            ))
        
        conn.close()
        
    except sqlite3.Error as e:
        items.append(HealthCheckItem(
            name="数据库",
            status="failed",
            message=f"数据库异常: {e}",
            severity="fatal"
        ))
    
    return items


def check_config(config_path: Path) -> List[HealthCheckItem]:
    """6. 配置自检：config.json 存在性 + LLM Key"""
    items = []
    
    if config_path.exists():
        items.append(HealthCheckItem(
            name="配置文件",
            status="passed",
            message=f"{config_path} 存在"
        ))
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # 检查 LLM 配置
            llm_cfg = config.get("llm_gateway", {})
            if llm_cfg.get("default_provider") and llm_cfg.get("providers"):
                has_key = False
                providers = llm_cfg.get("providers", {})
                for name, provider in providers.items():
                    if provider.get("api_key"):
                        has_key = True
                        break
                
                # 检查环境变量
                if not has_key:
                    for name in ["deepseek", "kimi", "chatglm", "tongyi", "wenxin"]:
                        if os.environ.get(f"SURI_{name.upper()}_API_KEY"):
                            has_key = True
                            break
                
                if has_key:
                    items.append(HealthCheckItem(
                        name="LLM 配置",
                        status="passed",
                        message="已配置 API Key"
                    ))
                else:
                    items.append(HealthCheckItem(
                        name="LLM 配置",
                        status="warning",
                        message="未配置 API Key，可使用 /setkey 或 /reconfig 配置",
                        severity="fatal"
                    ))
            else:
                items.append(HealthCheckItem(
                    name="LLM 配置",
                    status="warning",
                    message="LLM 配置不完整",
                    severity="fatal"
                ))
            
        except json.JSONDecodeError:
            items.append(HealthCheckItem(
                name="配置文件",
                status="failed",
                message="config.json 格式错误",
                severity="fatal"
            ))
    else:
        items.append(HealthCheckItem(
            name="配置文件",
            status="warning",
            message="config.json 不存在，将运行配置向导"
        ))
    
    return items


class HealthCheck:
    """健康检查类（供测试和 CLI 使用）。

    支持路径注入，便于测试时隔离真实文件系统。
    """

    def __init__(self, project_root: Path, config_path: Optional[Path] = None,
                 db_path: Optional[Path] = None):
        self.project_root = project_root
        self.roles_dir = project_root / "roles"
        self.plugins_dir = project_root / "agent_framework" / "plugins"
        self.db_path = db_path or Path.home() / ".suri" / "suri.db"
        self.config_path = config_path or Path.home() / ".suri" / "config.json"

    def _map_status(self, status: str) -> str:
        """将 HealthCheckItem 的状态映射为简短状态。"""
        mapping = {
            "passed": "pass",
            "warning": "warn",
            "failed": "fail",
        }
        return mapping.get(status, status)

    def check_all(self) -> Dict[str, Any]:
        """执行所有检查，返回 {name: {status, detail}} 格式。"""
        results = {}
        for item in check_environment():
            results[item.name] = {"status": self._map_status(item.status), "detail": item.message}
        for item in check_roles(self.roles_dir):
            results[item.name] = {"status": self._map_status(item.status), "detail": item.message}
        for item in check_project(self.project_root):
            results[item.name] = {"status": self._map_status(item.status), "detail": item.message}
        for item in check_plugins(self.plugins_dir):
            results[item.name] = {"status": self._map_status(item.status), "detail": item.message}
        results["db"] = self._check_db()
        results["api_keys"] = self._check_api_keys()
        return results

    def all_pass(self) -> bool:
        """所有检查项均通过（或警告）。"""
        results = self.check_all()
        return all(r["status"] != "fail" for r in results.values())

    def fail_summary(self) -> List[str]:
        """返回失败项列表。"""
        results = self.check_all()
        return [f"{name}: {r['detail']}" for name, r in results.items() if r["status"] == "fail"]

    def _check_db(self) -> Dict[str, str]:
        """检查数据库。"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("SELECT 1")
            conn.close()
            return {"status": "pass", "detail": "数据库连接正常"}
        except Exception as e:
            return {"status": "fail", "detail": f"数据库异常: {e}"}

    def _check_roles(self) -> Dict[str, str]:
        """检查角色。"""
        if not self.roles_dir.exists():
            return {"status": "fail", "detail": f"角色目录 {self.roles_dir} 不存在"}
        suri_dir = self.roles_dir / "suri"
        if not suri_dir.exists() or not (suri_dir / "soul.md").exists():
            return {"status": "fail", "detail": "核心角色 suri 不完整"}
        return {"status": "pass", "detail": "角色正常"}

    def _check_plugins(self) -> Dict[str, str]:
        """检查插件。"""
        if not self.plugins_dir.exists():
            return {"status": "fail", "detail": f"插件目录 {self.plugins_dir} 不存在"}
        expected = ["access", "code_tool", "role_manager", "llm_gateway",
                     "task_planner", "task_scheduler", "security_service",
                     "config_service", "log_service", "agent_registry",
                     "interrupt_handler", "test_framework"]
        missing = [p for p in expected if not (self.plugins_dir / p).exists()]
        if missing:
            return {"status": "fail", "detail": f"缺失插件: {', '.join(missing)}"}
        return {"status": "pass", "detail": "所有关键插件均存在"}

    def _check_api_keys(self) -> Dict[str, str]:
        """检查 API Key。

        检查优先级：环境变量 > config.json > .env 文件。
        .env 文件不存在时返回 warn（启动向导会引导配置）。
        """
        # 检查环境变量是否已设置
        for name in ["deepseek", "kimi", "chatglm", "tongyi", "wenxin"]:
            if os.environ.get(f"SURI_{name.upper()}_API_KEY"):
                return {"status": "pass", "detail": "环境变量已配置 API Key"}

        # 检查 config.json 是否有 API Key
        if self.config_path.exists():
            try:
                config = json.loads(self.config_path.read_text())
                providers = config.get("llm_gateway", {}).get("providers", {})
                for pname, provider in providers.items():
                    if provider.get("api_key"):
                        return {"status": "pass", "detail": f"配置文件 {self.config_path} 已配置 API Key"}
            except Exception:
                pass

        # 检查 .env 文件
        env_path = self.project_root / ".env"
        if env_path.exists():
            return {"status": "pass", "detail": ".env 文件存在"}
        return {"status": "warn", "detail": ".env 文件不存在，可通过 /setkey 或 /reconfig 配置"}


def run_healthcheck(
    project_root: Path,
    roles_dir: Path,
    plugins_dir: Path,
    db_path: Path,
    config_path: Path
) -> HealthReport:
    """执行完整启动自检，返回健康报告。"""
    report = HealthReport()
    
    # 1. 环境自检
    for item in check_environment():
        report.add(item)
    
    # 2. 角色自检
    for item in check_roles(roles_dir):
        report.add(item)
    
    # 3. 项目自检
    for item in check_project(project_root):
        report.add(item)
    
    # 4. 插件自检
    for item in check_plugins(plugins_dir):
        report.add(item)
    
    # 5. 数据库自检
    for item in check_database(db_path):
        report.add(item)
    
    # 6. 配置自检
    for item in check_config(config_path):
        report.add(item)
    
    # 7. 汇总报告
    s = report.summary()
    report.add(HealthCheckItem(
        name="健康检查汇总",
        status="passed" if s['all_passed'] else ("warning" if not s['has_fatal'] else "failed"),
        message=f"通过 {s['passed']}/{s['total']}，警告 {s['warning']}，失败 {s['failed']}"
    ))
    
    return report