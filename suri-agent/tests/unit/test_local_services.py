#!/usr/bin/env python3
"""
本地服务测试（无 API 调用）
覆盖：日志服务、安全服务、文件系统服务
"""
import sys, os, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from infrastructure.logger import LoggerService
from infrastructure.security import SecurityService
from infrastructure.filesystem import FileService
from infrastructure.config import ConfigService

# ====== 颜色 ======
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; RST = '\033[0m'

def ok(id, msg): print(f"  {G}✓{RST} [{id}] {msg}")
def fail(id, msg): print(f"  {R}✗{RST} [{id}] {msg}")

def main():
    passed = failed = 0
    project_root = Path(__file__).parent.parent.parent.parent.resolve()
    
    # ========== Logger 测试 ==========
    print("\n" + "="*50)
    print("日志服务测试")
    print("="*50)
    
    try:
        logger = LoggerService(project_root)
        # L01: 分类目录自动创建
        for cat in ["runtime", "error", "schedule", "role", "system"]:
            p = project_root / "logs" / cat
            if p.exists(): ok("L01", f"{cat} 目录存在")
            else: fail("L01", f"{cat} 目录缺失"); failed += 1; continue
            passed += 1
        
        # L02: 写入日志
        logger.info("test_module", "测试日志消息")
        logs = logger.get_today_logs("runtime")
        if logs["runtime"].exists():
            content = logs["runtime"].read_text()
            if "测试日志消息" in content:
                ok("L02", "日志写入并读取成功")
                passed += 1
            else:
                fail("L02", "日志内容未找到"); failed += 1
        else:
            fail("L02", "日志文件未创建"); failed += 1
        
        # L03: 错误日志双写
        logger.error("test_module", "测试错误")
        err_logs = logger.get_today_logs("error")
        if err_logs["error"].exists():
            content = err_logs["error"].read_text()
            if "测试错误" in content:
                ok("L03", "错误日志写入成功")
                passed += 1
            else:
                fail("L03", "错误日志内容未找到"); failed += 1
        else:
            fail("L03", "错误日志文件未创建"); failed += 1
        
        # L04: 业务快捷方法
        logger.log_startup(5)
        logger.log_task_created("T001", "user", "测试任务")
        logger.log_task_dispatched("T001", "suri", "suri-dev")
        ok("L04", "业务快捷方法执行无异常"); passed += 1
        
    except Exception as e:
        fail("Logger", f"异常: {e}"); failed += 4
    
    # ========== Security 测试 ==========
    print("\n" + "="*50)
    print("安全服务测试")
    print("="*50)
    
    try:
        config = ConfigService(project_root)
        config.load_all()
        security = SecurityService(project_root, config)
        
        # S05: 权限检查 - suri-dev 操作代码文件
        allowed, reason = security.check_permission("suri-dev", "suri-agent/core/context.py")
        if allowed:
            ok("S05", f"suri-dev 有权操作代码文件: {reason}"); passed += 1
        else:
            fail("S05", f"suri-dev 无权操作代码文件: {reason}"); failed += 1
        
        # S06: 权限检查 - 无权角色
        allowed, reason = security.check_permission("random-role", "suri-agent/core/context.py")
        if not allowed:
            ok("S06", f"无权角色正确拒绝: {reason}"); passed += 1
        else:
            fail("S06", f"无权角色不应通过: {reason}"); failed += 1
        
        # S07: 审批令牌 - 空令牌
        valid, reason = security.validate_approval_token("", "test.py")
        if not valid and "缺少审批令牌" in reason:
            ok("S07", "空令牌正确拒绝"); passed += 1
        else:
            fail("S07", f"空令牌处理异常: {reason}"); failed += 1
        
        # S08: 豁免路径检查
        exempt = security._is_exempt("resources/cache/test.txt")
        if exempt:
            ok("S08", "缓存路径正确豁免"); passed += 1
        else:
            fail("S08", "缓存路径应豁免"); failed += 1
        
        # S09: 综合检查 - 非监控路径无需审批
        allowed, reason = security.pre_file_change_check("suri-dev", "suri-agent/core/context.py")
        if allowed and "非监控路径" in reason:
            ok("S09", f"非监控路径免审批: {reason}"); passed += 1
        else:
            fail("S09", f"非监控路径检查异常: {reason}"); failed += 1
        
        # S10a: Soul 文件权限 - hr 有权修改（用 check_permission，不测试审批令牌）
        allowed, reason = security.check_permission("suri_hr", "group/central/suri/suri.md")
        if allowed:
            ok("S10a", f"Soul 文件 hr 有权修改: {reason}"); passed += 1
        else:
            fail("S10a", f"Soul 文件 hr 应能修改: {allowed} {reason}"); failed += 1
        
        # S10b: Soul 文件权限 - 非 admin 角色无权修改
        allowed, reason = security.check_permission("suri_dev", "group/central/suri/suri.md")
        if not allowed:
            ok("S10b", f"Soul 文件非 admin 无权修改: {reason}"); passed += 1
        else:
            fail("S10b", f"Soul 文件非 admin 应被拒绝: {allowed} {reason}"); failed += 1
        
    except Exception as e:
        fail("Security", f"异常: {e}"); failed += 6
    
    # ========== FileService 测试 ==========
    print("\n" + "="*50)
    print("文件系统服务测试")
    print("="*50)
    
    try:
        file_svc = FileService(project_root, security)
        
        # F11: 读取存在的文件
        try:
            content = file_svc.read_file("config.yaml")
            if "suri" in content:
                ok("F11", "读取 config.yaml 成功"); passed += 1
            else:
                fail("F11", "config.yaml 内容异常"); failed += 1
        except Exception as e:
            fail("F11", f"读取失败: {e}"); failed += 1
        
        # F12: 读取不存在的文件
        try:
            file_svc.read_file("nonexistent_file_12345.txt")
            fail("F12", "应抛出 FileNotFoundError"); failed += 1
        except FileNotFoundError:
            ok("F12", "不存在的文件正确抛出异常"); passed += 1
        
        # F13: 列出目录
        items = file_svc.list_directory("suri-agent/core")
        if any("context.py" in i for i in items):
            ok("F13", "列出目录成功"); passed += 1
        else:
            fail("F13", "目录列表异常"); failed += 1
        
        # F14: 写文件（非监控路径，无需审批）
        test_dir = project_root / "resources" / "temp" / "test_fs"
        if test_dir.exists():
            shutil.rmtree(test_dir)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        result = file_svc.write_file(
            "resources/temp/test_fs/test_write.txt",
            "hello test",
            operator="suri-dev"
        )
        if result["success"]:
            ok("F14", f"写文件成功: {result['reason']}"); passed += 1
        else:
            fail("F14", f"写文件失败: {result['reason']}"); failed += 1
        
        # F15: 删除文件
        result = file_svc.delete_file(
            "resources/temp/test_fs/test_write.txt",
            operator="suri-dev"
        )
        if result["success"]:
            ok("F15", f"删除文件成功: {result['reason']}"); passed += 1
        else:
            fail("F15", f"删除文件失败: {result['reason']}"); failed += 1
        
        # F16: 创建目录
        result = file_svc.mkdir(
            "resources/temp/test_fs/subdir",
            operator="suri-dev"
        )
        if result["success"]:
            ok("F16", f"创建目录成功: {result['reason']}"); passed += 1
        else:
            fail("F16", f"创建目录失败: {result['reason']}"); failed += 1
        
        # 清理
        if test_dir.exists():
            shutil.rmtree(test_dir)
        
    except Exception as e:
        fail("FileService", f"异常: {e}"); failed += 6
    
    # ========== 汇总 ==========
    print("\n" + "="*50)
    print(f"本地服务测试完成: {G}{passed} 通过{RST}, {R}{failed} 失败{RST}")
    print("="*50)
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
