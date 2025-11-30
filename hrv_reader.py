"""
hrv_reader.py

说明：监听串口中 Arduino 输出的 IBI（ms）消息，计算 RMSSD（以 ms 为单位）并输出当前 HRV 值与对应压力等级。

使用：
  pip install pyserial
  python hrv_reader.py --port /dev/tty.usbmodemXXXX --baud 115200

Arduino 端（示例）应输出形如：
  IBI:640
  IBI:650
  ...（每次检测到心跳时输出）

脚本会维护一个滑动窗口（默认 30 个 IBI），并持续计算 RMSSD。
"""

import argparse
import math
import re
import time
import json
import urllib.request
import urllib.error
from collections import deque
import statistics
import os  # 添加os模块导入

try:
    import serial
except Exception:
    print("请先安装 pyserial：pip install pyserial")
    raise

from stress import hrv_to_stress_level, get_stress_music_prompt

IBI_RE = re.compile(r"IBI\s*:\s*(\d+(?:\.\d+)?)")
BPM_RE = re.compile(r"BPM\s*=\s*(\d+(?:\.\d+)?)")


def rmssd_from_ibi_list(ibi_list):
    """计算 RMSSD（以毫秒为单位）。ibi_list 是按时间顺序的相邻 IBI（ms）数组。

    为了避免历史或孤立异常点放大 RMSSD，
    - 先进行极值过滤与 MAD 去噪（见 `clean_ibi_list`），
    - 然后仅使用最近的 `last_n` 个 IBI 计算 RMSSD（默认 8）。
    """
    if len(ibi_list) < 2:
        return None

    # 使用更严格的清洗策略以去除孤立异常点，防止单点放大 RMSSD
    cleaned, removed = clean_ibi_list(ibi_list, min_ibi=350.0, max_ibi=1500.0, mad_multiplier=1.5)
    if len(cleaned) < 2:
        return None

    # 仅对最近的几个样本计算 RMSSD，减小历史数据影响
    last_n = 8
    tail = cleaned[-last_n:]
    if len(tail) < 2:
        return None

    # 对最近样本先做一个简单的中值平滑（窗口 3），以抑制孤立脉冲
    smoothed = []
    for i in range(len(tail)):
        lo = max(0, i - 1)
        hi = min(len(tail), i + 2)
        smoothed.append(statistics.median(tail[lo:hi]))

    diffs_sq = []
    for i in range(1, len(smoothed)):
        diff = smoothed[i] - smoothed[i - 1]
        diffs_sq.append(diff * diff)

    if not diffs_sq:
        return None

    mean_sq = sum(diffs_sq) / len(diffs_sq)
    return math.sqrt(mean_sq)


def clean_ibi_list(ibi_list, min_ibi=300.0, max_ibi=2000.0, mad_multiplier=3.0):
    """清洗 IBI 列表：去掉超出 [min_ibi, max_ibi] 的值，基于 MAD 去除孤立异常点。
    返回 (cleaned_list, removed_count)
    """
    if not ibi_list:
        return [], 0
    filtered = [x for x in ibi_list if min_ibi <= x <= max_ibi]
    removed = len(ibi_list) - len(filtered)
    if len(filtered) < 2:
        return filtered, removed

    sorted_vals = sorted(filtered)
    mid = sorted_vals[len(sorted_vals) // 2]
    abs_devs = [abs(x - mid) for x in filtered]
    mad = sorted(abs_devs)[len(abs_devs) // 2]
    if mad > 0:
        allowed = mad_multiplier * mad
        cleaned = [x for x in filtered if abs(x - mid) <= allowed]
        removed_more = len(filtered) - len(cleaned)
        return cleaned, removed + removed_more
    return filtered, removed


def run(port, baudrate, window_size, service_url=None, final=False, compact=False):
    ser = serial.Serial(port, baudrate, timeout=1)
    print(f"已打开串口 {port} @ {baudrate}")

    ibi_window = deque(maxlen=window_size)
    # 使用绝对路径，确保无论从哪个目录启动都能正确写入文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    latest_hrv_file = os.path.join(script_dir, 'generated_audio', 'latest_hrv.txt')
    
    # 确保目录存在
    os.makedirs(os.path.dirname(latest_hrv_file), exist_ok=True)

    try:
        # EMA 平滑参数和最小样本数（适度放宽，配合更严格的清洗）
        ema_hrv = None
        ema_alpha = 0.25
        min_count_for_hrv = 6

        while True:
            line = ser.readline().decode(errors='ignore').strip()
            if not line:
                continue

            m = IBI_RE.search(line)
            ibi_val = None
            if m:
                ibi_val = float(m.group(1))
            else:
                # 尝试解析 BPM（Arduino 示例打印形式为: IR=..., BPM=78.74, ...）
                m2 = BPM_RE.search(line)
                if m2:
                    bpm = float(m2.group(1))
                    if bpm > 0:
                        ibi_val = 60000.0 / bpm

            if ibi_val is not None:
                ibi_window.append(ibi_val)
                now = time.strftime('%Y-%m-%d %H:%M:%S')

                cleaned, removed = clean_ibi_list(list(ibi_window))
                if len(cleaned) < min_count_for_hrv:
                    if not final and not compact:
                        print(f"接收到 IBI={ibi_val:.2f} ms；等待更多数据以计算 HRV... (window {len(ibi_window)})")
                    continue

                raw_hrv = rmssd_from_ibi_list(cleaned)
                if raw_hrv is None:
                    print(f"清洗后样本不足或计算失败（removed {removed}）")
                    continue

                # EMA 平滑以稳定输出
                if ema_hrv is None:
                    ema_hrv = raw_hrv
                else:
                    ema_hrv = ema_alpha * raw_hrv + (1 - ema_alpha) * ema_hrv

                stress_level = hrv_to_stress_level(ema_hrv)
                prompt = get_stress_music_prompt(ema_hrv)

                # 将最新 HRV 写入文件，供其他程序（如 music.py）读取
                try:
                    with open(latest_hrv_file, 'w') as f:
                        f.write(f"{ema_hrv:.4f}")
                    print(f"已写入 HRV 值到文件: {ema_hrv:.4f}")  # 添加调试日志
                except Exception as e:
                    print(f"写入 latest_hrv.txt 失败：{e}，文件路径：{latest_hrv_file}")

                # 如果提供了常驻服务地址，则 POST HRV 到服务以降低延迟
                if service_url:
                    payload = json.dumps({"hrv": float(ema_hrv)}).encode('utf-8')
                    req = urllib.request.Request(service_url, data=payload, headers={
                        'Content-Type': 'application/json'
                    })
                    try:
                        with urllib.request.urlopen(req, timeout=2) as resp:
                            resp_body = resp.read().decode('utf-8')
                            print(f"已向服务发送 HRV, 响应: {resp.status} {resp_body}")
                    except urllib.error.URLError as e:
                        print("向 HRV 服务发送失败：", e)

                # 如果只需一次最终 HRV（--final），打印并退出；如果要求简洁输出（--compact），或默认模式，均只输出单个 HRV（EMA 值）
                if final:
                    print(f"FINAL_HRV={ema_hrv:.2f} ms, 压力等级={stress_level}")
                    return
                elif compact:
                    # 仅输出一行简洁的 HRV 信息，便于脚本消费或重定向
                    print(f"HRV={ema_hrv:.2f} ms, 压力等级={stress_level}")
                else:
                    # 默认也只打印 EMA HRV，避免在一行内出现 raw/EMA 两个 HRV 数值导致混淆
                    print(f"[{now}] HRV={ema_hrv:.2f} ms, 压力等级={stress_level} -> {prompt}")
                    
            else:
                # 非 IBI 行：仅在非 final 且非 compact 模式打印（便于调试）
                if not final and not compact:
                    print(f"串口: {line}")

    except KeyboardInterrupt:
        print("已停止监听。")
    finally:
        ser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='串口 HRV 读取器（基于 IBI）')
    parser.add_argument('--port', required=True, help='串口设备，例如 /dev/tty.usbmodemXXXX 或 COM3')
    parser.add_argument('--baud', type=int, default=115200, help='波特率，默认 115200')
    parser.add_argument('--window', type=int, default=30, help='用于 RMSSD 的 IBI 滑动窗口大小，默认 30')
    parser.add_argument('--service-url', type=str, default=None, help='可选：常驻服务 URL，例如 http://localhost:5002/hrv，若提供则会 POST HRV 到服务')
    parser.add_argument('--final', action='store_true', help='只输出一个最终 HRV 后退出（抑制中间日志）')
    parser.add_argument('--compact', action='store_true', help='简洁输出：每次只打印一行 HRV（格式: HRV=xx ms, 压力等级=...）')
    args = parser.parse_args()

    run(args.port, args.baud, args.window, service_url=args.service_url, final=args.final, compact=args.compact)