import subprocess
import sys
import re
import time
import os
import socket
import psutil

# ==================== 配置项（核对！）====================
WEBBENCH_DIR = "/home/ubuntu/webserver-main/webbench-1.5"    
BAT_PATH = r"F:\CodeRepository\combie_1\back\src\start_server.bat"  # 你的bat路径
SERVER_PORT = "12568"                       
# ==========================================================

def force_release_port():
    """启动前：强制释放WSL中占用12568端口的所有进程（核心！）"""
    print("\n[0/6] 检查并释放12568端口...")
    try:
        # 暴力杀死WSL中所有占用12568端口的进程（不管进程名）
        release_cmd = f"lsof -i:{SERVER_PORT} | grep -v PID | awk '{{print $2}}' | xargs -r kill -9 2>/dev/null; " \
                      f"ps aux | grep server | grep -v grep | awk '{{print $2}}' | xargs -r kill -9 2>/dev/null"
        subprocess.run(
            ["wsl", "-e", "bash", "-c", release_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        print(f"[✅] 12568端口已强制释放（即使被占用也已清理）")
    except Exception as e:
        print(f"[⚠️] 释放端口时出现提示：{e}（不影响，继续执行）")

def check_bat_exists():
    """校验bat文件"""
    global BAT_PATH
    BAT_PATH = BAT_PATH.replace("\\", "/")
    if not os.path.exists(BAT_PATH):
        print(f"❌ 未找到bat：{BAT_PATH}")
        return False
    if " " in BAT_PATH:
        BAT_PATH = f'"{BAT_PATH}"'
    return True

def start_service_via_bat():
    """启动bat"""
    print("\n[1/6] 启动bat窗口...")
    try:
        subprocess.run(['cmd', '/c', 'start', '"WebServer"', 'cmd', '/k', BAT_PATH], creationflags=0x00000010)
        time.sleep(5)
        print("[✅] bat窗口已弹出，服务启动中...")
        return True
    except Exception as e:
        print(f"❌ 启动bat失败：{e}")
        return False

def get_wsl_real_ip():
    """获取WSL IP"""
    print("\n[2/6] 获取WSL真实IP...")
    try:
        result = subprocess.run(
            ["wsl", "-e", "bash", "-c", "ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        wsl_ip = result.stdout.strip()
        if re.match(r'^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$', wsl_ip):
            print(f"[✅] WSL IP：{wsl_ip}")
            return wsl_ip
    except Exception:
        pass
    print("[⚠️] 用127.0.0.1兜底")
    return "127.0.0.1"

def check_server_connect(ip, port):
    """检测连通性"""
    print(f"\n[3/6] 检测 {ip}:{port}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((ip, int(port)))
        s.close()
        print(f"[✅] {ip}:{port} 连通成功")
        return True
    except ConnectionRefusedError:
        print(f"[❌] {ip}:{port} 拒绝连接（请检查服务启动命令）")
        return False
    except Exception as e:
        print(f"[❌] 检测失败：{e}")
        return False

def kill_wsl_server_process():
    """暴力杀死WSL中所有server进程（彻底释放端口）"""
    print("\n[5/6] 强制杀死WSL中的server进程...")
    try:
        subprocess.run(['wsl', '-e', 'bash', '-c', f'lsof -ti:{SERVER_PORT} | xargs -r kill -9'], capture_output=True)
        subprocess.run(['wsl', '-e', 'bash', '-c', 'pkill -9 server'], capture_output=True)
        time.sleep(2)
        print("[✅] WSL中server进程已全部杀死，端口释放")
    except Exception as e:
        print(f"[⚠️] 杀进程提示：{e}（已尽力释放）")

def kill_bat_window_force():
    """暴力关闭bat对应的cmd窗口（不管标题，精准杀）"""
    print("\n[6/6] 强制关闭bat窗口...")
    bat_filename = os.path.basename(BAT_PATH)  # 获取bat文件名（如start_server.bat）
    killed = False
    # 遍历所有cmd进程，找到关联bat的进程并杀死
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'cmd.exe':
                cmdline = str(proc.info['cmdline']).lower()
                if bat_filename.lower() in cmdline:
                    proc.kill()
                    killed = True
                    print(f"[✅] 找到bat进程（PID={proc.info['pid']}），已杀死")
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # 兜底：杀所有标题含WebServer的cmd窗口
    if not killed:
        os.system('taskkill /FI "WINDOWTITLE eq WebServer" /F 2>nul')
        os.system('taskkill /FI "IMAGENAME eq cmd.exe" /FI "WINDOWTITLE eq WebServer" /F 2>nul')
        print("[✅] 兜底关闭bat窗口")

def main():
    print("===== 全自动压测（彻底释放端口版）=====")
    # 第一步：启动前先释放端口（核心！避免端口被占）
    force_release_port()

    # 校验bat
    if not check_bat_exists():
        return

    # 启动bat
    if not start_service_via_bat():
        return

    # 获取IP
    target_ip = get_wsl_real_ip()

    # 检测连通性
    check_server_connect(target_ip, SERVER_PORT)

    # 输入参数
    try:
        print("\n[4/6] 输入压测参数（回车默认1000/30）")
        concur = input("并发数：").strip() or "1000"
        test_time = input("测试秒数：").strip() or "30"
    except Exception:
        concur, test_time = "1000", "30"

    # 执行压测
    target_url = f"http://{target_ip}:{SERVER_PORT}/index.html"
    wsl_cmd = f"cd {WEBBENCH_DIR} && sudo ./webbench -c{concur} -t{test_time} {target_url}"
    print(f"\n执行压测命令：{wsl_cmd}")
    print("------------------------ 压测结果 ------------------------")
    try:
        subprocess.run(
            ["wsl", "-e", "bash", "-c", wsl_cmd],
            stdout=sys.stdout,
            stderr=sys.stderr,
            encoding="utf-8",
            errors="ignore"
        )
    except Exception as e:
        print(f"❌ 压测出错：{e}")
    finally:
        # 压测结束：先杀WSL服务（释放端口）→ 再关bat窗口
        kill_wsl_server_process()
        kill_bat_window_force()
        print("\n✅ 全部清理完成！端口已释放，下次可直接运行")

if __name__ == "__main__":
    # 自动安装psutil
    try:
        import psutil
    except ImportError:
        print("[⚠️] 安装psutil...")
        subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"], check=True)
        import psutil

    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 用户中断，强制清理资源...")
        kill_wsl_server_process()
        kill_bat_window_force()