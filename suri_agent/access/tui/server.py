#!/usr/bin/env python3
"""
ui_gateway/server.py

JSON-RPC 2.0 HTTP 服务端

启动方式：
    python -m ui_gateway.server --port 8080

TUI 前端通过 HTTP POST 发送 JSON-RPC 请求：
    POST http://localhost:8080/rpc
    Content-Type: application/json

    {
        "jsonrpc": "2.0",
        "method": "suri.getRoles",
        "params": {},
        "id": 1
    }
"""

import json
import argparse
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

# 将项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from suri_agent.infrastructure.config import ConfigService
from suri_agent.infrastructure.memory import MemoryService
from suri_agent.infrastructure.security import SecurityService
from suri_agent.infrastructure.filesystem import FileService
from suri_agent.core.approval import ApprovalService
from suri_agent.core.task_dispatcher import TaskService

from suri_agent.access.tui.rpc_methods import RPCHandler
from suri_agent.access.tui.middleware import (
    MiddlewareManager,
    auth_middleware,
    logging_middleware,
    format_error,
    format_response,
    JSONRPCError,
)


class JSONRPCHandler(BaseHTTPRequestHandler):
    """
    HTTP 请求处理器
    
    只处理 POST /rpc 请求，其他路径返回 404。
    """
    
    # 类级别共享的 RPCHandler 实例
    rpc_handler: Optional[RPCHandler] = None
    middleware: Optional[MiddlewareManager] = None
    
    def log_message(self, format, *args):
        """覆盖默认日志，使用自定义格式"""
        print(f"[ui_gateway] {self.address_string()} - {format % args}")
    
    def _send_json(self, data: Dict[str, Any], status_code: int = 200) -> None:
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        """处理 POST 请求"""
        if self.path != '/rpc':
            self._send_json(
                format_error(JSONRPCError.METHOD_NOT_FOUND, "仅支持 POST /rpc"),
                404
            )
            return
        
        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_json(
                format_error(JSONRPCError.INVALID_REQUEST, "请求体为空"),
                400
            )
            return
        
        body = self.rfile.read(content_length).decode('utf-8')
        
        # 解析 JSON
        try:
            request = json.loads(body)
        except json.JSONDecodeError as e:
            self._send_json(
                format_error(JSONRPCError.PARSE_ERROR, f"JSON 解析失败: {e}"),
                400
            )
            return
        
        # 校验 JSON-RPC 格式
        if request.get("jsonrpc") != "2.0" or "method" not in request:
            self._send_json(
                format_error(JSONRPCError.INVALID_REQUEST, "无效的 JSON-RPC 请求"),
                400
            )
            return
        
        # 执行中间件前置钩子
        if self.middleware:
            intercept = None
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                intercept = loop.run_until_complete(self.middleware.run_before(request))
                loop.close()
            except Exception:
                pass
            
            if intercept:
                self._send_json(intercept, 200)
                return
        
        # 调用 RPC 方法
        response = self._dispatch(request)
        
        # 执行中间件后置钩子
        if self.middleware:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(self.middleware.run_after(request, response))
                loop.close()
            except Exception:
                pass
        
        self._send_json(response, 200)
    
    def _dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        分发 JSON-RPC 请求到对应方法
        """
        method_name = request.get("method", "")
        params = request.get("params", {}) or {}
        req_id = request.get("id")
        
        if not self.rpc_handler:
            return format_error(
                JSONRPCError.INTERNAL_ERROR,
                "RPC 处理器未初始化"
            )
        
        # 查找方法
        method = self.rpc_handler.get_method(method_name)
        if not method:
            return format_error(
                JSONRPCError.METHOD_NOT_FOUND,
                f"方法不存在: {method_name}",
                {"available_methods": self.rpc_handler.list_methods()}
            )
        
        # 调用方法
        try:
            if isinstance(params, list):
                result = method(*params)
            elif isinstance(params, dict):
                result = method(**params)
            else:
                result = method()
            
            # 如果是通知（无 id），不返回响应体
            if req_id is None:
                return {}
            
            return format_response(result, req_id)
            
        except TypeError as e:
            return format_error(
                JSONRPCError.INVALID_PARAMS,
                f"参数错误: {e}",
                {"method": method_name, "params": params}
            )
        except Exception as e:
            import traceback
            return format_error(
                JSONRPCError.INTERNAL_ERROR,
                str(e),
                {"traceback": traceback.format_exc()}
            )


class UIGatewayServer:
    """
    UI Gateway 服务端
    
    负责初始化所有依赖服务并启动 HTTP 服务器。
    """
    
    def __init__(self, project_root: Path, port: int = 8080, auth_token: Optional[str] = None):
        self.project_root = project_root
        self.port = port
        self.auth_token = auth_token
        
        # 核心服务（与 suri-agent 共享）
        self.config: Optional[ConfigService] = None
        self.memory: Optional[MemoryService] = None
        self.security: Optional[SecurityService] = None
        self.filesystem: Optional[FileService] = None
        self.approval: Optional[ApprovalService] = None
        self.task: Optional[TaskService] = None
        
        # RPC 处理器
        self.rpc_handler: Optional[RPCHandler] = None
        self.middleware = MiddlewareManager()
    
    def initialize(self) -> bool:
        """初始化所有服务"""
        print("[ui_gateway] 初始化服务...")
        
        self.config = ConfigService(self.project_root)
        self.config.load_all()
        
        self.memory = MemoryService(self.project_root, self.config)
        self.security = SecurityService(self.config)
        self.filesystem = FileService(self.project_root, self.security)
        self.approval = ApprovalService(self.config, self.memory, self.security)
        self.task = TaskService(self.config, self.memory, None, None, None)
        
        self.rpc_handler = RPCHandler(
            config=self.config,
            memory=self.memory,
            security=self.security,
            filesystem=self.filesystem,
            approval=self.approval,
            task=self.task,
            project_root=self.project_root,
        )
        
        # 注册中间件
        self.middleware.before(logging_middleware())
        if self.auth_token:
            self.middleware.before(auth_middleware(self.auth_token))
        
        print(f"[ui_gateway] 服务初始化完成，注册了 {len(self.rpc_handler.list_methods())} 个 RPC 方法")
        return True
    
    def start(self) -> None:
        """启动 HTTP 服务器"""
        JSONRPCHandler.rpc_handler = self.rpc_handler
        JSONRPCHandler.middleware = self.middleware
        
        server = HTTPServer(('0.0.0.0', self.port), JSONRPCHandler)
        print(f"[ui_gateway] 服务器已启动: http://0.0.0.0:{self.port}/rpc")
        print("[ui_gateway] 按 Ctrl+C 停止")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[ui_gateway] 正在关闭服务器...")
            server.shutdown()


def main():
    parser = argparse.ArgumentParser(description='Suri UI Gateway - JSON-RPC 后端服务')
    parser.add_argument('--port', type=int, default=8080, help='监听端口 (默认: 8080)')
    parser.add_argument('--token', type=str, default=None, help='访问令牌 (可选)')
    parser.add_argument('--root', type=str, default='.', help='项目根目录 (默认: 当前目录)')
    args = parser.parse_args()
    
    project_root = Path(args.root).resolve()
    if not (project_root / 'suri').exists():
        print(f"[ui_gateway] 警告: {project_root} 下未找到 manifest/ 目录")
    
    server = UIGatewayServer(
        project_root=project_root,
        port=args.port,
        auth_token=args.token
    )
    
    if server.initialize():
        server.start()
    else:
        print("[ui_gateway] 初始化失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
