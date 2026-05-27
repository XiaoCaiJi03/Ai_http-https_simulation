@echo off
chcp 65001 >nul
echo 启动WSL服务...
:: 实时输出服务启动日志（确保Python能捕获）
wsl.exe -e bash -c "cd /home/ubuntu/webserver-main && ./server 12568"
echo WSL服务已停止