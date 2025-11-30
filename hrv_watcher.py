"""
hrv_watcher.py

说明：简单的基于轮询的文件监听器。监视 `generated_audio/latest_hrv.txt` 的修改时间或内容变化，
当检测到新 HRV 值时调用 `music.py`（在子进程中）触发音乐生成。

用法示例：
  python hrv_watcher.py --poll 2 --debounce 10

参数：
  --poll: 轮询间隔（秒），默认 2s
  --debounce: 防抖间隔（秒），检测到变化后在该时间内不再重复触发，默认 10s
  --once: 检测到一次变化后退出

注意：该脚本通过运行 `python music.py` 来触发生成。如果你想用其它命令或虚拟环境，请调整 `MUSIC_CMD`。
"""

import argparse
import os
import time
import subprocess


def read_float_from_file(path):
    try:
        with open(path, 'r') as f:
            s = f.read().strip()
            return float(s)
    except Exception:
        return None


def main(poll_interval, debounce_seconds, once):
    base_dir = os.path.dirname(__file__)
    latest_hrv_path = os.path.join(base_dir, 'generated_audio', 'latest_hrv.txt')

    # 可定制的音乐生成命令（可替换为虚拟环境内的 python 可执行路径）
    MUSIC_CMD = ['python', os.path.join(base_dir, 'music.py')]

    last_mtime = None
    last_value = None
    last_trigger = 0

    print(f"监听文件: {latest_hrv_path}")
    try:
        while True:
            if os.path.exists(latest_hrv_path):
                mtime = os.path.getmtime(latest_hrv_path)
                if last_mtime is None:
                    last_mtime = mtime
                    last_value = read_float_from_file(latest_hrv_path)
                # 文件修改时间变化视为新数据
                if mtime != last_mtime:
                    cur_time = time.time()
                    if cur_time - last_trigger < debounce_seconds:
                        print("检测到更新，但在防抖周期内，跳过触发")
                        last_mtime = mtime
                        last_value = read_float_from_file(latest_hrv_path)
                    else:
                        # 记录触发前的值，用于日志
                        old_value = last_value
                        last_mtime = mtime
                        new_val = read_float_from_file(latest_hrv_path)
                        print(f"检测到 HRV 更新: {old_value} -> {new_val} (mtime {mtime})")
                        last_value = new_val
                        last_trigger = cur_time
                        print("触发音乐生成（调用 music.py）...")
                        try:
                            # 使用 subprocess 启动音乐生成功能；注意这可能比较耗时
                            # 在生成期间，subprocess.run 会阻塞，不会继续检查HRV
                            # 传递 --no-auto 参数，避免自动触发逻辑（因为watcher已经检测到更新）
                            subprocess.run(MUSIC_CMD + ['--no-auto'], check=True)
                            print("音乐生成完成")
                            # 生成完成后，重新读取文件的最新修改时间，避免在生成期间
                            # 如果有新的HRV更新，立即再次触发
                            if os.path.exists(latest_hrv_path):
                                # 更新 last_mtime 为当前文件的最新修改时间
                                # 这样即使生成期间HRV更新了，也不会立即再次触发
                                last_mtime = os.path.getmtime(latest_hrv_path)
                                last_value = read_float_from_file(latest_hrv_path)
                                # 更新 last_trigger 为当前时间，确保防抖机制生效
                                last_trigger = time.time()
                        except subprocess.CalledProcessError as e:
                            print("调用 music.py 失败:", e)
                            # 即使失败，也更新 mtime 和 trigger，避免重复触发失败的任务
                            if os.path.exists(latest_hrv_path):
                                last_mtime = os.path.getmtime(latest_hrv_path)
                                last_value = read_float_from_file(latest_hrv_path)
                                last_trigger = time.time()
                        if once:
                            print("--once 指定，已完成一次触发后退出")
                            return
            else:
                # 文件还不存在，等待
                pass
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("已停止监听（KeyboardInterrupt）")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='监听 latest_hrv.txt 并在更新时触发 music.py')
    parser.add_argument('--poll', type=float, default=2.0, help='轮询间隔（秒），默认 2s')
    parser.add_argument('--debounce', type=float, default=10.0, help='防抖（秒），默认 10s')
    parser.add_argument('--once', action='store_true', help='检测到一次后退出')
    args = parser.parse_args()

    main(args.poll, args.debounce, args.once)
