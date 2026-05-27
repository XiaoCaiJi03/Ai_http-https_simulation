Set WshShell = CreateObject("WScript.Shell")
' 核心参数：
' 第二个参数 0 = 隐藏窗口；1 = 显示窗口
' 第三个参数 True = 等待脚本执行完成（确保日志完整）
WshShell.Run "cmd /c start_server.bat", 0, True
Set WshShell = Nothing