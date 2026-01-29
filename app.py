from flask import Flask, render_template, request, jsonify, send_file
import os
import uuid
from datetime import datetime, timedelta
import threading
import time
import shutil

# 导入我们现有的模块
from stress import get_stress_music_prompt, STRESS_MUSIC_MAP
import json
import re
import scipy
import torch
import numpy as np
import scipy.signal
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import subprocess
import sys

app = Flask(__name__)

# 全局变量存储模型（避免重复加载）
model = None
processor = None
model_loaded = False

# 测量进程状态（在内存中跟踪）
measurement_state = {
    'running': False,
    'finished': False,
    'error': None,
    'output': ''
}
measurement_proc = None
watcher_proc = None

def load_model():
    """在后台加载模型"""
    global model, processor, model_loaded
    try:
        print("🎵 开始加载音乐生成模型...")
        
        # 检查模型路径是否存在
        model_path = "/Users/xibei/MusicGPT/model"
        if not os.path.exists(model_path):
            print(f"❌ 模型路径不存在: {model_path}")
            print("💡 请确保模型文件已正确下载并放置到指定路径")
            model_loaded = False
            return
        
        # 检查必要的模型文件
        required_files = ["config.json", "pytorch_model.bin", "preprocessor_config.json"]
        missing_files = []
        for file in required_files:
            file_path = os.path.join(model_path, file)
            if not os.path.exists(file_path):
                missing_files.append(file)
                print(f"❌ 缺少模型文件: {file}")
        
        if missing_files:
            print(f"💡 缺少以下模型文件: {', '.join(missing_files)}")
            print("💡 请下载完整的模型文件")
            model_loaded = False
            return
        
        print("📦 正在加载处理器和模型...")
        # 强制使用 CPU 以修复 MPS 产生的"大风吹"噪声问题
        # 虽然 MPS 理论上更快，但在当前 PyTorch/MusicGen 组合下输出可能是纯噪声
        device = "cpu"
        print(f"🖥️  强制使用设备: {device} (为了保证音质绝对稳定，放弃 GPU 加速)")
        
        # 这里的旧代码已注释，因为 MPS 确实不可用
        # if torch.cuda.is_available(): ...
            
        processor = AutoProcessor.from_pretrained(model_path)
        model = MusicgenForConditionalGeneration.from_pretrained(model_path).to(device)
        
        # 验证模型加载是否成功
        if processor is None or model is None:
            raise Exception("模型或处理器加载失败")
        
        model_loaded = True
        print("✅ 模型加载完成！")
        print(f"📊 模型信息: {model.config}")
        
    except FileNotFoundError as e:
        print(f"❌ 模型文件错误: {e}")
        model_loaded = False
    except ImportError as e:
        print(f"❌ 依赖库错误: {e}")
        print("💡 请确保已安装 transformers 和 torch 库")
        model_loaded = False
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        print("💡 可能的原因：模型文件损坏、内存不足、CUDA错误等")
        model_loaded = False

# 在应用启动时开始加载模型
threading.Thread(target=load_model, daemon=True).start()

# 创建音频文件存储目录
AUDIO_DIR = "generated_audio"
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)

# 文件管理配置
MAX_AUDIO_FILES = 50  # 最大音频文件数量
CLEANUP_INTERVAL = 3600  # 清理间隔（秒）
AUDIO_RETENTION_HOURS = 24  # 音频文件保留时间（小时）

def cleanup_old_files():
    """清理旧的音频文件"""
    try:
        if not os.path.exists(AUDIO_DIR):
            return
        
        current_time = datetime.now()
        files = os.listdir(AUDIO_DIR)
        
        # 按修改时间排序，删除最旧的文件
        audio_files = []
        for file in files:
            if file.endswith('.wav'):
                file_path = os.path.join(AUDIO_DIR, file)
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                audio_files.append((file_path, mtime))
        
        # 按修改时间排序
        audio_files.sort(key=lambda x: x[1])
        
        # 删除超过保留时间的文件
        for file_path, mtime in audio_files:
            if current_time - mtime > timedelta(hours=AUDIO_RETENTION_HOURS):
                try:
                    os.remove(file_path)
                    print(f"已删除过期文件: {file_path}")
                except Exception as e:
                    print(f"删除文件失败 {file_path}: {e}")
        
        # 如果文件数量仍然超过限制，删除最旧的文件
        remaining_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith('.wav')]
        if len(remaining_files) > MAX_AUDIO_FILES:
            excess_count = len(remaining_files) - MAX_AUDIO_FILES
            for i in range(excess_count):
                try:
                    os.remove(os.path.join(AUDIO_DIR, remaining_files[i]))
                    print(f"已删除超量文件: {remaining_files[i]}")
                except Exception as e:
                    print(f"删除文件失败 {remaining_files[i]}: {e}")
                    
    except Exception as e:
        print(f"清理文件时出错: {e}")

def start_cleanup_scheduler():
    """启动定期清理任务"""
    def cleanup_loop():
        while True:
            time.sleep(CLEANUP_INTERVAL)
            cleanup_old_files()
    
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    print("文件清理任务已启动")


def _run_measurement_in_thread(cmd, state_dict):
    """在后台线程内执行测量命令并更新状态字典。
    
    使用 subprocess 执行 hrv_reader.py，并实时捕获输出。
    """
    global measurement_proc
    try:
        # 启动子进程，行缓冲
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        measurement_proc = process
        
        state_dict.update({'running': True, 'finished': False, 'error': None, 'output': '正在启动传感器...'})
        
        # 持续读取输出
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.strip()
                if line:
                    state_dict['output'] = line
                    # 可选：打印到后台控制台
                    print(f"[HRV] {line}")
        
        process.wait()
        ret = process.returncode
        
        state_dict['running'] = False
        state_dict['finished'] = True
        if ret != 0:
            err = f"进程异常退出 (code {ret})"
            state_dict['error'] = err
            state_dict['output'] = err
        else:
            state_dict['output'] = "测量已结束"
            
    except Exception as e:
        state_dict['error'] = str(e)
        state_dict['running'] = False
        state_dict['finished'] = True
        print(f"启动 HRV 测量失败: {e}")
    finally:
        measurement_proc = None


def _persist_stress_map(stress_map):
    """将给定的 STRESS_MUSIC_MAP 写回到 stress.py（备份原文件）。"""
    stress_path = os.path.join(os.path.dirname(__file__), 'stress.py')
    try:
        # 读取原文件内容
        with open(stress_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 构建新的 STRESS_MUSIC_MAP 文本（保持可读的 Python 字面量格式）
        entries = []
        for key, lst in stress_map.items():
            vals = ', '.join([f'"{s}"' for s in lst])
            entries.append(f'    "{key}": [{vals}]')
        new_map_text = 'STRESS_MUSIC_MAP = {\n' + ',\n'.join(entries) + '\n}\n'

        # 使用正则替换原 MAP 块（非贪婪），若不存在则在文件顶部插入
        pattern = r"(?m)^STRESS_MUSIC_MAP\s*=\s*\{[\s\S]*?\}"
        new_content, n = re.subn(pattern, new_map_text.rstrip('\n'), content, count=1)
        if n == 0:
            # 未找到现有定义，将新定义插入文件开头并保留原注释/导入
            new_content = new_map_text + '\n' + content

        # 备份并以原子方式写入新文件：先写到临时文件，再重命名替换
        backup_path = stress_path + '.bak'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)

        tmp_path = stress_path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        # 原子替换
        os.replace(tmp_path, stress_path)
        return True, None
    except Exception as e:
        return False, str(e)


def update_and_persist_preference(pref):
    """将偏好（中文或英文）映射为关键词，更新 USER_MUSIC_PREFERENCE 变量并持久化到JSON文件（不修改stress.py）。
    返回 (success, message_or_pref_word)
    """
    from stress import set_user_music_preference
    
    mapping = {
        '流行': 'pop', '摇滚': 'rock', '古典': 'classical',
        'pop': 'pop', 'rock': 'rock', 'classical': 'classical',
        '嘻哈': 'hip hop', '电子': 'electronic', 'R&B': 'r&b',
        '爵士': 'jazz', '乡村': 'country', '布鲁斯': 'blues', '雷鬼': 'reggae'
    }
    pref_word = mapping.get(pref, None)
    if pref_word is None:
        return False, f'不支持的偏好: {pref}'

    # 使用新的函数设置用户偏好（这会更新 USER_MUSIC_PREFERENCE 变量并持久化到JSON文件）
    success = set_user_music_preference(pref_word)
    if success:
        return True, pref_word
    else:
        return False, f'设置偏好失败: {pref_word}'

# 启动文件清理任务
start_cleanup_scheduler()

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/stress-levels')
def get_stress_levels():
    """获取可用的压力水平选项"""
    return jsonify(list(STRESS_MUSIC_MAP.keys()))

@app.route('/api/model-status')
def model_status():
    """检查模型加载状态"""
    # 检查模型是否正在加载中（通过检查线程是否还在运行）
    # 如果 model_loaded 为 False 且 model 和 processor 都为 None，说明还在加载中
    is_loading = not model_loaded and (model is None or processor is None)
    
    status_info = {
        'loaded': model_loaded,
        'loading': is_loading,
        'status': 'ready' if model_loaded else ('loading' if is_loading else 'not_started'),
        'message': '模型已就绪' if model_loaded else ('模型正在加载中，请稍候...' if is_loading else '模型尚未开始加载')
    }
    
    # 如果模型加载失败，提供更多信息
    if not model_loaded and not is_loading:
        status_info['error'] = True
        status_info['suggestion'] = '建议检查模型文件路径或重新启动应用'
    
    return jsonify(status_info)

# 全局变量控制生成状态
music_generation_status = {
    'status': 'idle', # idle, processing, completed, failed
    'file_id': None,
    'error': None
}

# 启用 MPS 后备模式，以防部分算子在 GPU 上不支持
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
# 解除 MPS 显存限制 (允许使用更多系统内存)，避免 OOM
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

import uuid
from datetime import datetime, timedelta
import threading
import time
import shutil
import gc  # 引入垃圾回收

# ... (imports) ...

def generate_music_task(input_text):
    global music_generation_status
    print(f"🧵 后台线程启动，开始生成音乐，提示词: {input_text}")
    try:
        # 确保模型已加载
        if model is None or processor is None:
            raise Exception("模型未正确加载")

        # 每轮生成前主动清理内存
        gc.collect()
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            torch.mps.empty_cache()

        # 获取当前配置的设备
        original_device = model.device
        
        # 使用 inference_mode 极限压榨 CPU 性能
        with torch.inference_mode():
            try:
                print(f"🚀 尝试在 {original_device} 上生成...")
                inputs = processor(
                    text=[input_text],
                    return_tensors="pt"
                ).to(original_device)
                
                audio_values = model.generate(
                    **inputs,
                    max_new_tokens=1250,
                    do_sample=True,
                    guidance_scale=3.0,
                    temperature=0.8,
                    top_p=0.9
                )
            except RuntimeError as e:
                print(f"⚠️ 硬件加速生成失败 ({e})")
                print("🔄 正在自动回退到 CPU 重试...")
                
                model.to('cpu')
                inputs = processor(text=[input_text], return_tensors="pt").to('cpu')
                audio_values = model.generate(
                    **inputs,
                    max_new_tokens=1250,
                    do_sample=True,
                    guidance_scale=3.0,
                    temperature=0.8,
                    top_p=0.9
                )
                if original_device.type != 'cpu':
                    try: model.to(original_device)
                    except: pass

        # 保存音频文件
        file_id = str(uuid.uuid4())
        output_file = os.path.join(AUDIO_DIR, f"{file_id}.wav")
        
        sampling_rate = model.config.audio_encoder.sampling_rate
        # 必须先移回 CPU
        audio_data = audio_values[0, 0].cpu().numpy()
        
        # --- 优化：去除直流偏移 (DC Offset)，防止拼接时的"噗"声 ---
        if len(audio_data) > 0:
            audio_data = audio_data - np.mean(audio_data)
        
        if len(audio_data) == 0:
            raise ValueError("生成的音频数据为空")

        # --- 策略：DSP 变奏循环 (A-B-A-B 结构) ---
        target_duration = 300  # 5 分钟
        current_duration = len(audio_data) / sampling_rate
        
        if current_duration > 0 and current_duration < target_duration:
            print(f"🔄 正在应用 Overlap-Add 无缝重叠拼接策略 (Duration: {current_duration:.2f}s)...")
            
            # 1. 准备素材: A (原版) 和 B (变奏)
            # 制作 B 段 (变奏)：施加柔和的低通滤波器
            try:
                b, a = scipy.signal.butter(4, 1200 / (sampling_rate / 2), 'low')
                audio_data_lowpass = scipy.signal.lfilter(b, a, audio_data)
                if np.isnan(audio_data_lowpass).any(): audio_data_lowpass = audio_data.copy() 
            except:
                audio_data_lowpass = audio_data.copy()

            # 2. 定义重叠参数
            overlap_sec = 3.0 # 3秒重叠
            overlap_len = int(sampling_rate * overlap_sec)
            
            # --- 关键修复：防止音频过导致 Overlap 崩溃 ---
            # 遇到"叮一声"就是因为音频还没 overlap 长，导致切片索引错乱
            min_required_len = int(sampling_rate * 5.0) # 至少要有5秒才能做漂亮的 fade
            if len(audio_data) < min_required_len:
                print(f"⚠️ 生成音频过短 ({len(audio_data)/sampling_rate:.2f}s)，正在强制补齐...")
                # 简单重复几次直到足够长，保证后续算法不崩
                if len(audio_data) > 0:
                    repeat_times = int(np.ceil(min_required_len / len(audio_data)))
                    audio_data = np.tile(audio_data, repeat_times)
                    # 同时也补齐 B 段
                    audio_data_lowpass = np.tile(audio_data_lowpass, repeat_times)
            
            # 如果还是不够长（极小概率），缩小 Overlap
            if len(audio_data) < 2 * overlap_len:
                overlap_len = len(audio_data) // 3
            # ---------------------------------------------
            
            # 3. 预计算淡入淡出曲线 (用于重叠区)
            # 使用 sqrt(t) 曲线，保证功率恒定 (Constant Power Crossfade)
            t = np.linspace(0, 1, overlap_len)
            fade_in = np.sqrt(t)
            fade_out = np.sqrt(1 - t)
            
            # 4. 开始拼接
            # 计算总共需要多少段
            # 每一段贡献的有效新长度是 (Length - Overlap)
            segment_len = len(audio_data)
            hop_len = segment_len - overlap_len
            if hop_len <= 0: hop_len = segment_len // 2 # 防御性编码

            target_samples = int(target_duration * sampling_rate)
            num_segments = int(np.ceil(target_samples / hop_len)) + 2
            
            # 初始化大数组
            # 预估一个足够长的长度，最后再截断
            estimated_len = hop_len * num_segments + segment_len
            combined_audio = np.zeros(estimated_len, dtype=np.float32)
            
            print(f"🧩 正在拼接 {num_segments} 个片段，重叠长度: {overlap_len} 采样点")

            for i in range(num_segments):
                # 选择素材: A-B-A-B
                part = audio_data if i % 2 == 0 else audio_data_lowpass
                
                # 获取当前段在总数组中的位置
                # 第 i 段的起始位置由 hop_len 决定
                start = i * hop_len
                
                # 复制一份当前片段
                this_segment = part.copy()
                
                # 如果这不是第一段，开头要 Fade In (为了和上一段的 Tail 融合)
                if i > 0:
                     this_segment[:overlap_len] *= fade_in
                
                # 如果这不是最后一段，结尾要 Fade Out (为了和下一段的 Head 融合)
                if i < num_segments - 1:
                     this_segment[-overlap_len:] *= fade_out
                     
                # 叠加到主数组 (Overlap-Add)
                write_len = min(segment_len, len(combined_audio) - start)
                if write_len > 0:
                    combined_audio[start : start + write_len] += this_segment[:write_len]
            
            # 截取有效长度并赋值
            final_valid_len = min(len(combined_audio), target_samples)
            # 找到最后一个非零点的附近，或者直接用 target_samples
            audio_data = combined_audio[:final_valid_len]

        # 4. 最终检查与保存
        # 检查 NaN / Inf
        if np.isnan(audio_data).any() or np.isinf(audio_data).any():
            print("❌ 检测到 NaN 或 Inf 数值！替换为 0...")
            audio_data = np.nan_to_num(audio_data)
            
        print(f"🔍 音频数据检查: Min={audio_data.min()}, Max={audio_data.max()}")
        
        # 归一化
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val
            
        # 最终转换为 Int16 (标准 WAV)
        audio_data_int16 = (audio_data * 32767).clip(-32768, 32767).astype(np.int16)
        scipy.io.wavfile.write(output_file, rate=sampling_rate, data=audio_data_int16)
        
        # 验证文件
        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            raise FileNotFoundError("音频文件保存失败")
        
        print(f"✅ 后台生成完成: {file_id}, 大小: {os.path.getsize(output_file)}")
        music_generation_status = {
            'status': 'completed',
            'file_id': file_id,
            'error': None
        }
        
    except Exception as e:
        print(f"❌ 后台生成出错: {e}")
        music_generation_status = {
            'status': 'failed',
            'file_id': None,
            'error': str(e)
        }

@app.route('/api/generate-music', methods=['POST'])
def generate_music():
    global music_generation_status
    
    # 检查是否正在运行
    if music_generation_status['status'] == 'processing':
         return jsonify({
             'status': 'processing', 
             'message': '任务正在进行中'
         }), 200 # 幂等返回 200

    # 重置状态
    music_generation_status = {'status': 'processing', 'file_id': None, 'error': None}
    
    try:
        # 模型加载检查
        if not model_loaded:
             return jsonify({'error': '模型正在加载中'}), 503

        # 生成 Prompt
        from stress import get_stress_music_prompt
        input_text = get_stress_music_prompt()
        
        # 启动后台线程
        thread = threading.Thread(target=generate_music_task, args=(input_text,))
        thread.start()
        
        return jsonify({
            'success': True,
            'status': 'processing', 
            'message': '音乐生成任务已在后台启动'
        })
        
    except Exception as e:
        music_generation_status['status'] = 'failed'
        return jsonify({'error': str(e)}), 500

@app.route('/api/music-status', methods=['GET'])
def get_music_status():
    return jsonify(music_generation_status)

@app.route('/api/audio/<file_id>')
def get_audio(file_id):
    """获取生成的音频文件"""
    try:
        file_path = os.path.join(AUDIO_DIR, f"{file_id}.wav")
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=False)
        else:
            return jsonify({'error': '音频文件不存在'}), 404
    except Exception as e:
        return jsonify({'error': f'获取音频文件时出错: {str(e)}'}), 500

# 删除重复的 /api/model-status 路由定义
# 保留上面第275行开始的改进版本

@app.route('/api/set-preference', methods=['POST'])
def set_preference():
    """设置用户音乐偏好（流行/摇滚/古典），更新运行时的 STRESS_MUSIC_MAP 并持久化到 stress.py。"""
    try:
        if not request.is_json:
            return jsonify({'error':'请求必须是JSON格式'}), 400
        data = request.get_json()
        pref = data.get('preference')
        if not pref:
            return jsonify({'error':'未提供 preference 字段'}), 400

        ok, msg = update_and_persist_preference(pref)
        if ok:
            return jsonify({'success': True, 'preference': msg})
        else:
            return jsonify({'success': False, 'error': msg}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/latest-hrv')
def latest_hrv():
    """返回 generated_audio/latest_hrv.txt 的值和修改时间（若存在）。"""
    try:
        latest_hrv_path = os.path.join(os.path.dirname(__file__), 'generated_audio', 'latest_hrv.txt')
        if not os.path.exists(latest_hrv_path):
            return jsonify({'exists': False, 'hrv': None, 'mtime': None})
        mtime = os.path.getmtime(latest_hrv_path)
        with open(latest_hrv_path, 'r', encoding='utf-8') as f:
            txt = f.read().strip()
        try:
            hrv = float(txt)
        except Exception:
            hrv = None
        return jsonify({'exists': True, 'hrv': hrv, 'mtime': mtime})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/confirm-preference', methods=['POST'])
def confirm_preference():
    """在前端确认偏好时：1) 更新并持久化 STRESS_MUSIC_MAP，2) 启动 hrv_watcher.py 进程。
    请求体: { 'preference': '流行' }
    """
    try:
        if not request.is_json:
            return jsonify({'error':'请求必须是JSON格式'}), 400
        data = request.get_json()
        pref = data.get('preference')
        if not pref:
            return jsonify({'error':'未提供 preference 字段'}), 400

        ok, msg = update_and_persist_preference(pref)
        # 如果持久化失败，仍然返回成功响应码 200，让前端决定是否继续生成音乐。
        # 前端有处理：若 success=false 则显示提示但继续生成。
        if not ok:
            return jsonify({'success': False, 'error': msg, 'preference': msg})

        # 不再自动启动 watcher；前端会在确认后触发生成
        return jsonify({'success': True, 'preference': msg})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/start-measurement', methods=['POST'])
def start_measurement():
    """启动 hrv_reader.py 测量进程。接收 JSON: { "port": "/dev/tty...", "baud": 115200, "window": 30 }
    如果已有测量在运行，则返回当前状态。"""
    try:
        global measurement_state
        if measurement_state.get('running'):
            return jsonify({'started': False, 'reason': 'measurement_running'}), 409

        data = request.get_json() or {}
        port = data.get('port', '/dev/tty.usbmodem2017_2_251')
        baud = int(data.get('baud', 115200))
        window = int(data.get('window', 30))

        # 基本校验（只允许以 /dev/ 开头的串口路径以防滥用）
        if not isinstance(port, str) or not port.startswith('/dev/'):
            return jsonify({'error': 'invalid port'}), 400

        # 检查 hrv_reader.py 是否存在
        script_path = os.path.join(os.path.dirname(__file__), 'hrv_reader.py')
        if not os.path.exists(script_path):
            return jsonify({'started': False, 'reason': 'hrv_reader_missing', 'error': f'找不到 {script_path}'}), 500

        # 不再在此处严格检查串口文件是否存在。
        # 在很多开发/测试环境下，设备文件不可用，但我们希望仍能启动测量线程让脚本自行报错或重试。
        # 如果需要更严格的校验，可以在前端或配置中启用。

        # 构建命令：使用当前 Python 解释器执行脚本
        cmd = [sys.executable, script_path, '--port', port, '--baud', str(baud), '--window', str(window)]

        # 清理旧状态并启动线程
        measurement_state = {'running': True, 'finished': False, 'error': None, 'output': ''}
        thread = threading.Thread(target=_run_measurement_in_thread, args=(cmd, measurement_state), daemon=True)
        try:
            thread.start()
        except Exception as e:
            measurement_state.update({'running': False, 'finished': True, 'error': str(e)})
            return jsonify({'started': False, 'reason': 'thread_start_failed', 'error': str(e)}), 500

        return jsonify({'started': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/measurement-status')
def measurement_status():
    """返回当前测量状态（running/finished/error 和输出片段）"""
    try:
        global measurement_proc
        
        # 检查进程是否仍在运行
        is_running = False
        if measurement_proc is not None:
            if measurement_proc.poll() is None:
                is_running = True
            else:
                # 进程已结束
                measurement_proc = None
        
        # 只返回必要字段，避免过大输出
        s = {
            'running': is_running or measurement_state.get('running', False),
            'finished': measurement_state.get('finished', False),
            'error': measurement_state.get('error'),
            'output_tail': (measurement_state.get('output') or '')[-1000:]
        }
        return jsonify(s)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/storage-status')
def storage_status():
    """获取存储状态"""
    try:
        if not os.path.exists(AUDIO_DIR):
            return jsonify({
                'total_files': 0,
                'total_size_mb': 0,
                'max_files': MAX_AUDIO_FILES,
                'retention_hours': AUDIO_RETENTION_HOURS
            })
        
        files = os.listdir(AUDIO_DIR)
        audio_files = [f for f in files if f.endswith('.wav')]
        
        total_size = 0
        for file in audio_files:
            file_path = os.path.join(AUDIO_DIR, file)
            total_size += os.path.getsize(file_path)
        
        return jsonify({
            'total_files': len(audio_files),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'max_files': MAX_AUDIO_FILES,
            'retention_hours': AUDIO_RETENTION_HOURS
        })
    except Exception as e:
        return jsonify({'error': f'获取存储状态失败: {str(e)}'}), 500

@app.route('/api/cleanup-files', methods=['POST'])
def cleanup_files():
    """手动清理文件"""
    try:
        cleanup_old_files()
        return jsonify({'success': True, 'message': '文件清理完成'})
    except Exception as e:
        return jsonify({'error': f'清理文件失败: {str(e)}'}), 500


@app.route('/api/simulate-hrv', methods=['POST'])
def simulate_hrv():
    """用于本地调试：写入 generated_audio/latest_hrv.txt 并返回新值。
    请求 JSON: { 'hrv': 32.5 }
    仅在开发环境下使用，生产应禁用此端点。
    """
    try:
        if not request.is_json:
            return jsonify({'error': '请求必须为 JSON'}), 400
        data = request.get_json()
        hrv = data.get('hrv')
        if hrv is None:
            return jsonify({'error': '未提供 hrv 字段'}), 400
        try:
            hrv_val = float(hrv)
        except Exception:
            return jsonify({'error': 'hrv 必须为数字'}), 400

        latest_hrv_path = os.path.join(os.path.dirname(__file__), 'generated_audio', 'latest_hrv.txt')
        os.makedirs(os.path.dirname(latest_hrv_path), exist_ok=True)
        with open(latest_hrv_path, 'w', encoding='utf-8') as f:
            f.write(f"{hrv_val:.4f}")

        return jsonify({'success': True, 'hrv': hrv_val})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-stress-map')
def get_stress_map():
    """只读：返回当前运行时的 STRESS_MUSIC_MAP，便于前端或测试脚本验证偏好已写入内存/文件。"""
    try:
        # 直接返回运行时内存中的映射
        return jsonify({'success': True, 'stress_map': STRESS_MUSIC_MAP})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # 清空 latest_hrv.txt 文件
    latest_hrv_path = os.path.join(os.path.dirname(__file__), 'generated_audio', 'latest_hrv.txt')
    try:
        os.makedirs(os.path.dirname(latest_hrv_path), exist_ok=True)
        # 清空文件内容（如果文件存在则清空，不存在则创建空文件）
        with open(latest_hrv_path, 'w', encoding='utf-8') as f:
            f.write('')
        print(f"✅ 已清空 latest_hrv.txt 文件")
    except Exception as e:
        print(f"⚠️  清空 latest_hrv.txt 文件时出错: {e}")
    
    app.run(debug=True, host='0.0.0.0', port=5001)