"""
Suri Config — 配置中心服务

职责：
1. 扫描 group/ 目录，索引所有 Soul 文件
2. 扫描 tools/ 目录，索引工具注册表
3. 别名解析（suri-dev → suri_dev）
4. 核心角色自动重建（Soul 缺失时生成默认模板）
5. 本地服务发现（轻量级注册表）

包含模块：
- config_service.py      → 配置扫描、Soul 解析
- service_registry.py    → 本地服务发现

关联文档: suri-agent/README.md
"""

from suri_agent.common.service_base import SuriService


class ConfigService(SuriService):
    """
    配置中心服务 — 极轻量，所有服务共享配置
    
    启动时扫描 group/ 和 tools/ 建立索引，
    运行时提供 Soul 查询、角色信息、工具注册表。
    """
    
    def __init__(self):
        super().__init__("suri-config")
    
    def on_startup(self):
        """扫描目录，建立索引"""
        pass
    
    def on_run(self):
        """启动 gRPC 服务器"""
        pass
    
    def on_shutdown(self):
        pass
    
    def on_persist_state(self):
        """配置服务无状态（索引可重建）"""
        pass
    
    def on_restore_state(self):
        """配置服务无状态"""
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
