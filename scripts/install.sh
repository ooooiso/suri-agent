#!/bin/bash
# Suri Agent 安装脚本
# 运行一次后，终端输入 suri 即可启动

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================"
echo "  Suri Agent 安装器"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 需要 Python 3"
    exit 1
fi

# 选择安装目录
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    INSTALL_DIR="/usr/local/bin"
elif [ -d "$HOME/.local/bin" ]; then
    INSTALL_DIR="$HOME/.local/bin"
else
    echo "创建 ~/.local/bin ..."
    mkdir -p "$HOME/.local/bin"
    INSTALL_DIR="$HOME/.local/bin"
fi

# 提示用户添加 PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "⚠️  ~/.local/bin 不在 PATH 中"
    echo "请执行以下命令（或添加到 ~/.zshrc）："
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

# 安装 suri
echo "安装 suri → $INSTALL_DIR ..."
TARGET="$INSTALL_DIR/suri"
if [ -L "$TARGET" ] || [ -f "$TARGET" ]; then
    rm -f "$TARGET"
fi
ln -s "$PROJECT_ROOT/suri" "$TARGET"

# 安装 suri-daemon
DAEMON_TARGET="$INSTALL_DIR/suri-daemon"
if [ -L "$DAEMON_TARGET" ] || [ -f "$DAEMON_TARGET" ]; then
    rm -f "$DAEMON_TARGET"
fi
ln -s "$PROJECT_ROOT/scripts/suri-daemon" "$DAEMON_TARGET"

echo ""
echo "✅ 安装完成！"
echo ""
echo "安装路径: $INSTALL_DIR"
echo ""
echo "常用命令："
echo "    suri              启动终端对话"
echo "    suri-daemon start  启动后台服务"
echo "    suri-daemon stop   停止后台服务"
echo "    suri-daemon status 查看状态"
echo ""

if [ "$INSTALL_DIR" = "$HOME/.local/bin" ]; then
    echo "如果命令找不到，请执行："
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi
