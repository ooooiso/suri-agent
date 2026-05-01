"""
Suri 服务基类

所有微服务的公共基类，定义：
- 生命周期管理（启动、运行、停止）
- 优雅重启协议（SIGUSR1 信号处理）
- 健康检查接口
- gRPC 服务器封装
- NATS 连接管理

关联文档: suri-agent/README.md
"""

import signal
import sys
from abc import ABC, abstractmethod
from enum import Enum


class ServiceState(Enum):
    """服务运行状态"""
    INIT = "init"
    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"      # 停止接收新请求，处理完当前请求后退出
    STOPPING = "stopping"
    STOPPED = "stopped"


class SuriService(ABC):
    """
    所有 Suri 微服务的抽象基类
    
    子类需实现：
    - on_startup()      → 启动初始化
    - on_run()          → 主运行循环
    - on_shutdown()     → 优雅退出清理
    - on_persist_state() → 状态持久化（热升级前调用）
    - on_restore_state() → 状态恢复（热升级后调用）
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.state = ServiceState.INIT
        self.active_requests = 0
        self._setup_signals()
    
    def _setup_signals(self):
        """注册 Unix 信号处理器"""
        signal.signal(signal.SIGTERM, self._on_sigterm)
        signal.signal(signal.SIGINT, self._on_sigterm)
        signal.signal(signal.SIGUSR1, self._on_sigusr1)  # 优雅重启信号
    
    def _on_sigterm(self, signum, frame):
        """收到停止信号"""
        self.state = ServiceState.STOPPING
        self.on_shutdown()
        sys.exit(0)
    
    def _on_sigusr1(self, signum, frame):
        """收到热升级信号（由 supervisor 发送）"""
        self.state = ServiceState.DRAINING
        # TODO: 等待当前请求完成
        self.on_persist_state()
        self.on_shutdown()
        sys.exit(0)
    
    def start(self):
        """启动服务"""
        self.state = ServiceState.STARTING
        self.on_startup()
        self.state = ServiceState.RUNNING
        self.on_run()
    
    # ---------- 子类需实现 ----------
    
    @abstractmethod
    def on_startup(self):
        """启动初始化：加载配置、连接数据库、注册到服务发现"""
        pass
    
    @abstractmethod
    def on_run(self):
        """主运行循环：启动 gRPC 服务器 / 消息消费者"""
        pass
    
    @abstractmethod
    def on_shutdown(self):
        """优雅退出：关闭连接、释放资源"""
        pass
    
    @abstractmethod
    def on_persist_state(self):
        """热升级前：将内存状态写入持久化存储"""
        pass
    
    @abstractmethod
    def on_restore_state(self):
        """热升级后：从持久化存储恢复状态"""
        pass
    
    @abstractmethod
    def health_check(self) -> dict:
        """健康检查：返回 {status: "healthy|unhealthy", details: {...}}"""
        pass
