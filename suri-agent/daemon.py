#!/usr/bin/env python3
"""
Suri 守护进程管理器

用法：
    python daemon.py start    # 启动后台服务
    python daemon.py stop     # 停止服务
    python daemon.py status   # 查看状态
    python daemon.py restart  # 重启服务

功能：
- 启动 JSON-RPC 服务端作为后台进程
- 记录 PID 到 suri-agent.pid
- 用户通过 cli.py 连接服务端进行交互
- 调试时可通过 daemon.py stop 随时关闭
"""

import os
import sys
import signal
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PID_FILE = PROJECT_ROOT / "logs" / "system" / ".suri.pid"
LOG_FILE = PROJECT_ROOT / "logs" / "system" / "suri-daemon.log"


def get_pid() -> int:
    """读取 PID 文件"""
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except ValueError:
            return 0
    return 0


def is_running(pid: int) -> bool:
    """检查进程是否在运行"""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start():
    """启动后台服务"""
    pid = get_pid()
    if pid and is_running(pid):
        print(f"[daemon] suri 已在运行 (PID: {pid})")
        return
    
    print("[daemon] 启动 suri 后台服务...")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "suri-agent")
    
    # 启动 server.py 作为后台进程
    with open(LOG_FILE, "w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "access.tui.server", "--port", "8080"],
            cwd=str(PROJECT_ROOT / "suri-agent"),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    
    PID_FILE.write_text(str(process.pid))
    time.sleep(1)
    
    if is_running(process.pid):
        print(f"[daemon] 启动成功 (PID: {process.pid})")
        print(f"[daemon] 日志: {LOG_FILE}")
        print(f"[daemon] 接入方式: cd ~/suri && ./suri")
    else:
        print("[daemon] 启动失败，请查看日志")
        PID_FILE.unlink(missing_ok=True)


def stop():
    """停止服务"""
    pid = get_pid()
    if not pid:
        print("[daemon] suri 未运行")
        return
    
    if not is_running(pid):
        print(f"[daemon] 进程已不存在 (PID: {pid})")
        PID_FILE.unlink(missing_ok=True)
        return
    
    print(f"[daemon] 停止 suri (PID: {pid})...")
    
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        
        if is_running(pid):
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
        
        PID_FILE.unlink(missing_ok=True)
        print("[daemon] 已停止")
    except OSError as e:
        print(f"[daemon] 停止失败: {e}")


def status():
    """查看状态"""
    pid = get_pid()
    if pid and is_running(pid):
        print(f"[daemon] suri 运行中 (PID: {pid})")
        print(f"[daemon] 日志: {LOG_FILE}")
    else:
        print("[daemon] suri 未运行")
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)


def restart():
    """重启服务"""
    stop()
    time.sleep(1)
    start()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python daemon.py [start|stop|status|restart]")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "status":
        status()
    elif cmd == "restart":
        restart()
    else:
        print(f"未知命令: {cmd}")
        print("用法: python daemon.py [start|stop|status|restart]")
        sys.exit(1)
