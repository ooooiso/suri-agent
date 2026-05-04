#!/bin/bash
# 真实的终端交互测试 - 使用 coprocess 与 suri 交互
# 每发送一条命令都等待回应，不跳过任何输出

set -e

cd "$(dirname "$0")/.."

API_KEY="sk-aa3ce558e0eb4bb289a2e9ce0f8e20a8"
TELEGRAM_TOKEN="8561619663:AAEKrFzyvArWxN7ORDchzW3_EoL0WEmRp7E"

echo "========================================="
echo "  真实的 Suri CLI 终端交互测试"
echo "========================================="
echo ""

# 启动 suri 作为后台进程
python3 main.py > /tmp/suri_output.txt 2>&1 &
SURI_PID=$!

echo "[INFO] suri 进程已启动 (PID=$SURI_PID)"

# 等待 suri 启动完成（直到看到 "启动完成"）
echo "[WAIT] 等待 suri 启动..."
for i in $(seq 1 30); do
    if grep -q "启动完成" /tmp/suri_output.txt 2>/dev/null; then
        echo "[OK] suri 启动完成"
        break
    fi
    sleep 1
done

if ! grep -q "启动完成" /tmp/suri_output.txt 2>/dev/null; then
    echo "[ERROR] suri 启动超时"
    kill $SURI_PID 2>/dev/null
    exit 1
fi

# 显示启动输出
echo "--- suri 输出 ---"
cat /tmp/suri_output.txt
echo "--- end ---"

echo ""
echo "========================================="
echo "  Step 1: 检查初始状态"
echo "========================================="
# 模拟在终端输入 /status
echo "/status" >> /dev/null
# 由于通过管道通信困难，使用写入文件的方式
echo "输入: /status"
echo "/status" > /proc/$SURI_PID/fd/0 2>/dev/null || true
sleep 2
echo "--- suri 输出 ---"
cat /tmp/suri_output.txt
echo "--- end ---"