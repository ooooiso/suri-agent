#!/bin/bash
# Suri 平台启动脚本

set -e

echo "========================================"
echo "  Suri 智能体平台启动器"
echo "========================================"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 需要 Python 3"
    exit 1
fi

# 显示菜单
echo "请选择启动模式:"
echo "  1) 启动主程序 (suri-agent)"
echo "  2) 启动 TUI 后端 (JSON-RPC)"
echo "  3) 启动终端客户端 (命令行交互)"
echo "  4) 启动全部"
echo ""
read -p "输入选项 [1-4]: " choice

case $choice in
    1)
        echo ""
        echo ">>> 启动 suri-agent 主程序..."
        PYTHONPATH="$PROJECT_ROOT/suri-agent:$PYTHONPATH" python3 -m suri_agent.main
        ;;
    2)
        echo ""
        echo ">>> 启动 TUI JSON-RPC 后端..."
        PYTHONPATH="$PROJECT_ROOT/suri-agent:$PYTHONPATH" python3 -m suri_agent.access.tui.server --port 8080
        ;;
    3)
        echo ""
        echo ">>> 启动终端客户端..."
        PYTHONPATH="$PROJECT_ROOT/suri-agent:$PYTHONPATH" python3 "$PROJECT_ROOT/suri-agent/access/tui/cli.py"
        ;;
    4)
        echo ""
        echo ">>> 启动 TUI 后端 (后台)..."
        PYTHONPATH="$PROJECT_ROOT/suri-agent:$PYTHONPATH" python3 -m suri_agent.access.tui.server --port 8080 &
        TUI_PID=$!
        echo "TUI PID: $TUI_PID"
        sleep 2
        echo ""
        echo ">>> 启动终端客户端..."
        PYTHONPATH="$PROJECT_ROOT/suri-agent:$PYTHONPATH" python3 "$PROJECT_ROOT/suri-agent/access/tui/cli.py"
        kill $TUI_PID 2>/dev/null
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac
