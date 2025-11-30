"""
hrv_service.py

常驻服务：启动时加载 MusicGen 模型并暴露 HTTP 接口接受 HRV 值（POST /hrv）。
接收到 HRV 后立即在后台线程触发音乐生成（非阻塞），并将生成的音频保存到 `generated_audio/`。

用法示例：
  python hrv_service.py --host 0.0.0.0 --port 5002

接口：
  POST /hrv  JSON: {"hrv": 25.3}
    - 返回：{"status":"accepted","message":"started generation","job_id":"..."}
  GET /status
    - 返回基本运行状态

注意：该服务会在启动时加载模型，可能耗时较长（一次性开销），但之后生成延迟会低得多。
"""

import os
import time
import threading
import datetime
import json
from flask import Flask, request, jsonify

# 仅在运行环境可用时导入 heavy 依赖，便于本地编辑和错误提示
try:
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    import scipy.io.wavfile
    import torch
except Exception as e:
    # 在导入失败时，服务仍可启动，但会在尝试生成音乐时报错
    AutoProcessor = None
    MusicgenForConditionalGeneration = None
    scipy = None
    torch = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

from stress import get_stress_music_prompt

app = Flask(__name__)

MODEL_DIR = os.environ.get('MUSIC_MODEL_DIR', '/Users/xibei/MusicGPT/model')
GENERATED_DIR = os.path.join(os.path.dirname(__file__), 'generated_audio')
os.makedirs(GENERATED_DIR, exist_ok=True)
LATEST_HRV_FILE = os.path.join(GENERATED_DIR, 'latest_hrv.txt')

# 全局模型变量
processor = None
model = None


def load_model():
    global processor, model
    if AutoProcessor is None or MusicgenForConditionalGeneration is None:
        raise RuntimeError(f"模型依赖导入失败: {_IMPORT_ERROR}")
    print(f"加载模型，路径: {MODEL_DIR} ...")
    processor = AutoProcessor.from_pretrained(MODEL_DIR)
    model = MusicgenForConditionalGeneration.from_pretrained(MODEL_DIR)
    print("模型加载完成")


def generate_music_background(hrv_value, prompt_text=None):
    """在后台调用模型生成音乐并保存为 wav。"""
    try:
        if processor is None or model is None:
            print("模型未加载，无法生成音乐")
            return

        if prompt_text is None:
            prompt_text = get_stress_music_prompt(hrv_value)

        print(f"开始生成音乐：HRV={hrv_value}, prompt={prompt_text}")

        inputs = processor(
            text=[prompt_text],
            padding=True,
            return_tensors="pt"
        )

        # 生成参数可以根据需要调整
        audio_values = model.generate(
            **inputs,
            max_new_tokens=500,
            temperature=1.2,
            top_k=250,
            top_p=0.9
        )

        sampling_rate = model.config.audio_encoder.sampling_rate
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(GENERATED_DIR, f'generated_{ts}.wav')

        # audio_values 可能需要转换，保持与原 music.py 行为一致
        scipy.io.wavfile.write(out_path, rate=sampling_rate, data=audio_values[0, 0].numpy())
        print(f"音乐生成完成，保存到: {out_path}")

        # 更新 latest_hrv.txt
        try:
            with open(LATEST_HRV_FILE, 'w') as f:
                f.write(f"{hrv_value:.4f}")
        except Exception as e:
            print("更新 latest_hrv.txt 失败：", e)

    except Exception as e:
        print("生成过程中出现错误:", e)


@app.route('/status', methods=['GET'])
def status():
    ok = True
    msg = 'ok'
    if _IMPORT_ERROR is not None:
        ok = False
        msg = f"import error: {_IMPORT_ERROR}"
    return jsonify({'status': 'running' if ok else 'error', 'detail': msg})


@app.route('/hrv', methods=['POST'])
def receive_hrv():
    if not request.is_json:
        return jsonify({'error': 'expected application/json with key hrv'}), 400
    data = request.get_json()
    if 'hrv' not in data:
        return jsonify({'error': 'missing hrv field'}), 400
    try:
        hrv_val = float(data['hrv'])
    except Exception:
        return jsonify({'error': 'hrv must be a number'}), 400

    # 立即记录到文件（兼容旧流程）
    try:
        with open(LATEST_HRV_FILE, 'w') as f:
            f.write(f"{hrv_val:.4f}")
    except Exception as e:
        print("写入 latest_hrv.txt 失败：", e)

    # 非阻塞触发生成
    job_id = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    thread = threading.Thread(target=generate_music_background, args=(hrv_val, None), daemon=True)
    thread.start()

    return jsonify({'status': 'accepted', 'job_id': job_id}), 202


def main(host, port):
    # 尝试在主进程加载模型以减少首次生成延迟
    try:
        load_model()
    except Exception as e:
        print("模型加载失败：", e)
        print("服务仍将启动，但在请求生成时会报错。")
    # 启动 Flask
    app.run(host=host, port=port)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='常驻 HRV->Music 服务')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址，默认 127.0.0.1')
    parser.add_argument('--port', type=int, default=5002, help='监听端口，默认 5002')
    args = parser.parse_args()
    main(args.host, args.port)
