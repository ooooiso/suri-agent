"""
中间件层

职责：
- 请求认证（简单 Token 或 IP 白名单）
- 请求/响应日志
- 异常捕获与 JSON-RPC 错误格式化
- CORS 支持（如果 TUI 前端通过 Web 加载）
"""

import json
import traceback
from typing import Dict, Any, Callable, Optional
from functools import wraps


class JSONRPCError:
    """JSON-RPC 2.0 标准错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000


def format_error(error_code: int, message: str, data: Any = None) -> Dict[str, Any]:
    """格式化 JSON-RPC 错误响应"""
    error = {"code": error_code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "error": error, "id": None}


def format_response(result: Any, request_id: Any) -> Dict[str, Any]:
    """格式化 JSON-RPC 成功响应"""
    return {"jsonrpc": "2.0", "result": result, "id": request_id}


class MiddlewareManager:
    """
    中间件管理器
    
    支持前置中间件（请求处理前）和后置中间件（响应返回前）。
    """
    
    def __init__(self):
        self.before_hooks: list[Callable] = []
        self.after_hooks: list[Callable] = []
    
    def before(self, fn: Callable):
        """注册前置中间件"""
        self.before_hooks.append(fn)
        return fn
    
    def after(self, fn: Callable):
        """注册后置中间件"""
        self.after_hooks.append(fn)
        return fn
    
    async def run_before(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """执行前置中间件，返回非 None 则直接作为响应"""
        for hook in self.before_hooks:
            result = await hook(request) if hasattr(hook, '__code__') and 'await' in hook.__code__.co_code else hook(request)
            if result is not None:
                return result
        return None
    
    async def run_after(self, request: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """执行后置中间件"""
        for hook in self.after_hooks:
            if hasattr(hook, '__code__') and 'await' in hook.__code__.co_code:
                response = await hook(request, response) or response
            else:
                response = hook(request, response) or response
        return response


# ---- 内置中间件 ----

def auth_middleware(required_token: Optional[str] = None):
    """
    简单 Token 认证中间件
    
    请求头或 params 中需包含 token。
    """
    def check_auth(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not required_token:
            return None
        
        # 从 params 中获取 token
        params = request.get("params", {})
        token = params.get("_token") or request.get("_token")
        
        if token != required_token:
            return format_error(
                JSONRPCError.INVALID_REQUEST,
                "认证失败：无效的访问令牌"
            )
        return None
    return check_auth


def logging_middleware(logger=None):
    """请求日志中间件"""
    def log_request(request: Dict[str, Any]) -> None:
        method = request.get("method", "unknown")
        req_id = request.get("id", "notification")
        if logger:
            logger.info(f"[UI] RPC {method} id={req_id}")
        else:
            print(f"[ui_gateway] {method} id={req_id}")
    return log_request


def exception_middleware():
    """异常捕获包装器"""
    def wrap_exception(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                if hasattr(fn, '__code__') and 'await' in fn.__code__.co_code:
                    return await fn(*args, **kwargs)
                return fn(*args, **kwargs)
            except Exception as e:
                traceback_str = traceback.format_exc()
                print(f"[ui_gateway] 异常: {e}\n{traceback_str}")
                return format_error(
                    JSONRPCError.INTERNAL_ERROR,
                    str(e),
                    {"traceback": traceback_str}
                )
        return wrapper
    return wrap_exception
