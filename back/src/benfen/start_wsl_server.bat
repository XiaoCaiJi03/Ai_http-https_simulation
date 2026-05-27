@echo off
echo 启动WSL服务...
:: 2>&1 把错误输出合并到标准输出，确保Python能捕获所有日志
wsl.exe -e bash -c "cd /home/ubuntu/webserver-main && ./server 12568" 2>&1
echo WSL服务已停止