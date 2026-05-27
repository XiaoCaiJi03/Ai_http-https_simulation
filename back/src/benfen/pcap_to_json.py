import subprocess
import json
import os
from typing import Optional
import datetime


def find_latest_pcap_file(target_dir: str) -> Optional[str]:
    """
    扫描指定目录，找到最新的pcap/pcapng文件（按修改时间排序）
    :param target_dir: 要扫描的目录路径
    :return: 最新pcap文件的完整路径，无符合条件文件则返回None
    """
    # 校验目录是否存在
    if not os.path.isdir(target_dir):
        print(f"错误：指定的目录不存在 → {target_dir}")
        return None

    # 筛选目录下所有.pcap/.pcapng文件
    pcap_files = []
    for file_name in os.listdir(target_dir):
        # 支持.pcap和.pcapng两种格式
        if file_name.lower().endswith(('.pcap', '.pcapng')):
            file_path = os.path.join(target_dir, file_name)
            # 仅处理文件（排除目录）
            if os.path.isfile(file_path):
                # 获取文件修改时间（时间戳，单位秒）
                file_mtime = os.path.getmtime(file_path)
                pcap_files.append((file_path, file_mtime))

    # 无符合条件的文件
    if not pcap_files:
        print(f"提示：目录 {target_dir} 下未找到.pcap/.pcapng文件")
        return None

    # 按修改时间降序排序，取第一个（最新）
    pcap_files.sort(key=lambda x: x[1], reverse=True)
    latest_file_path, latest_mtime = pcap_files[0]
    latest_time = datetime.datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")
    print(f"找到最新的pcap文件：")
    print(f"  文件路径：{latest_file_path}")
    print(f"  最后修改时间：{latest_time}")

    return latest_file_path


def check_tshark_available(tshark_path: str) -> bool:
    """校验tshark是否可用"""
    try:
        result = subprocess.run(
            [tshark_path, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"✅ tshark可用，版本信息：{result.stdout[:50].strip()}")
            return True
        else:
            print(f"❌ tshark执行失败：{result.stderr}")
            return False
    except FileNotFoundError:
        print(f"❌ 未找到tshark程序，请检查路径是否正确 → {tshark_path}")
        return False
    except Exception as e:
        print(f"❌ 校验tshark失败：{str(e)}")
        return False


def tshark_export_pcap_to_json(pcap_file_path: str, output_dir: str, tshark_path) -> tuple[bool, Optional[str]]:
    """
    调用tshark将pcap文件导出为JSON（拆分每个报文为单独文件）
    :param pcap_file_path: 待处理的pcap文件路径
    :param output_dir: JSON输出根目录
    :param tshark_path: tshark程序路径
    :return: （执行结果bool，生成的JSON子目录名Optional[str]）→ 成功返回(True, 目录名)，失败返回(False, None)
    """
    # 校验tshark是否可用
    if not check_tshark_available(tshark_path):
        return (False, None)

    # 确保输出根目录存在
    os.makedirs(output_dir, exist_ok=True)

    # ========== 原有逻辑：临时文件路径 ==========
    temp_json_path = os.path.join(output_dir, "temp_all_packets.json")

    # 构造tshark命令
    cmd = [
        tshark_path,
        "-r", pcap_file_path,
        "-T", "json",  # 输出JSON格式
        "-n",  # 禁用地址解析（加速解析）
        "-l"  # 行缓冲输出（避免大文件卡顿）
    ]

    # 执行tshark命令（原有逻辑完整保留）
    try:
        print(f"\n开始调用tshark解析文件：{pcap_file_path}")
        with open(temp_json_path, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                timeout=300  # 超时时间（5分钟）
            )
        print(f"✅ tshark解析完成，临时总JSON文件：{temp_json_path}")
    except subprocess.TimeoutExpired:
        print(f"❌ 错误：tshark执行超时（超过5分钟），请检查pcap文件大小")
        return (False, None)
    except subprocess.CalledProcessError as e:
        print(f"❌ 错误：tshark执行失败（返回码：{e.returncode}）")
        print(f"tshark错误详情：{e.stderr}")
        return (False, None)
    except PermissionError:
        print(f"❌ 错误：无权限写入临时文件 → {temp_json_path}，请检查输出目录权限")
        return (False, None)
    except Exception as e:
        print(f"❌ 错误：导出JSON时发生异常 → {str(e)}")
        return (False, None)

    # ========== 原有逻辑：拆分JSON文件 ==========
    try:
        # 读取总JSON，拆分每个报文为单独的JSON文件
        with open(temp_json_path, "r", encoding="utf-8") as f:
            packets = json.load(f)  # 总JSON是一个包含所有报文的数组

        # 按pcap文件名创建子目录（避免多个文件冲突）
        pcap_basename = os.path.splitext(os.path.basename(pcap_file_path))[0]
        final_output_dir = os.path.join(output_dir, pcap_basename)

        # 补充：创建最终的JSON子目录（避免目录不存在导致写入失败，不影响原有功能）
        os.makedirs(final_output_dir, exist_ok=True)

        # 写入每个报文的JSON文件（原有逻辑完整保留）
        for idx, packet in enumerate(packets):
            json_file_name = f"packet_{idx}.json"
            json_file_path = os.path.join(final_output_dir, json_file_name)

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(packet, f, ensure_ascii=False, indent=2)

            print(f"✅ 已生成报文{idx}的JSON文件：{json_file_path}")

        # 删除临时总JSON文件（原有逻辑完整保留）
        os.remove(temp_json_path)
        print(f"✅ 已清理临时文件：{temp_json_path}")
        print(f"\n📁 所有JSON文件存储目录：{final_output_dir}")

        # 关键修复：执行成功返回（True, 子目录名），保留原有功能的同时满足解包需求
        return (True, pcap_basename)

    except json.JSONDecodeError:
        print(f"❌ 错误：tshark生成的临时文件不是合法JSON → {temp_json_path}")
        return (False, None)
    except Exception as e:
        print(f"❌ 错误：拆分JSON文件失败 → {str(e)}")
        return (False, None)


# 调用示例（原有逻辑完整保留，兼容新返回值）
if __name__ == "__main__":
    # 配置项（根据你的实际路径修改）
    PCAP_SCAN_DIR = r"back\data\generated_http"
    JSON_OUTPUT_DIR = r"back\data\pcap_to_json"
    tshark_path = r"E:\Program Files\Wireshark\tshark.exe"

    # 1. 找最新的pcap文件
    latest_pcap = find_latest_pcap_file(PCAP_SCAN_DIR)
    if not latest_pcap:
        exit(1)

    # 2. 自动导出为JSON（兼容新返回值，不影响原有调用逻辑）
    success, _ = tshark_export_pcap_to_json(latest_pcap, JSON_OUTPUT_DIR, tshark_path)
    if success:
        print("\n🎉 全自动化流程完成：最新pcap已成功导出为JSON文件")
    else:
        print("\n❌ 全自动化流程失败")
        exit(1)