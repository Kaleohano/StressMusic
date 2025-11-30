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
        processor = AutoProcessor.from_pretrained(model_path)
        model = MusicgenForConditionalGeneration.from_pretrained(model_path)
        
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
    """在后台线程内执行测量命令并更新状态字典。"""
    global measurement_proc
    try:
        state_dict.update({'running': True, 'finished': False, 'error': None, 'output': ''})
        # 使用 Popen 启动进程，但不等待完成（因为 hrv_reader.py 是持续运行的）
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        measurement_proc = proc
        print(f"已启动HRV测量进程: {' '.join(cmd)}")
        
        # 不等待进程完成，因为 hrv_reader.py 是持续运行的
        # 只检查进程是否成功启动
        time.sleep(2)  # 等待2秒检查进程状态
        if proc.poll() is not None:
            # 进程已经退出，说明启动失败
            stdout, stderr = proc.communicate()
            out = ''
            if stdout:
                out += stdout
            if stderr:
                out += '\n' + stderr
            state_dict['output'] = out
            state_dict['finished'] = True
            state_dict['running'] = False
            state_dict['error'] = f"进程启动失败: {out}"
            print(f"HRV测量进程启动失败: {out}")
        else:
            # 进程正在运行
            state_dict['output'] = "HRV测量进程已启动"
            print("HRV测量进程正在运行...")
            
    except Exception as e:
        state_dict['error'] = str(e)
        state_dict['running'] = False
        state_dict['finished'] = True
        print(f"启动HRV测量失败: {e}")
    finally:
        # 注意：这里不设置 measurement_proc = None，因为进程可能还在运行
        pass


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
        'pop': 'pop', 'rock': 'rock', 'classical': 'classical'
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

@app.route('/api/generate-music', methods=['POST'])
def generate_music():
    """生成音乐API"""
    try:
        # 检查请求数据
        if not request.is_json:
            return jsonify({
                'error': '请求必须是JSON格式',
                'error_type': 'invalid_request'
            }), 400
        
        data = request.get_json()
        if data is None:
            return jsonify({
                'error': '请求数据为空',
                'error_type': 'invalid_request'
            }), 400
        
        # 检查模型状态
        if not model_loaded:
            return jsonify({
                'error': '模型还在加载中，请稍后再试',
                'error_type': 'model_loading',
                'suggestion': '建议等待1-3分钟让模型完全加载'
            }), 503
        
        if model is None or processor is None:
            return jsonify({
                'error': '模型未正确加载，请检查模型文件',
                'error_type': 'model_error',
                'suggestion': '请检查模型文件是否存在且完整'
            }), 500
        
        # 生成唯一的文件名
        file_id = str(uuid.uuid4())
        output_file = os.path.join(AUDIO_DIR, f"{file_id}.wav")
        
        # 使用基于HRV和用户偏好的提示词
        from stress import get_stress_music_prompt
        input_text = get_stress_music_prompt()
        print(f"🎵 开始生成音乐，提示词: {input_text}")
        
        # 生成音乐
        try:
            inputs = processor(
                text=[input_text],
                padding=True,
                return_tensors="pt"
            )
            
            audio_values = model.generate(
                **inputs,
                max_new_tokens=500,
                do_sample=True,
                temperature=1.2,
                top_k=250,
                top_p=0.9
            )
            
            # 保存音频文件
            sampling_rate = model.config.audio_encoder.sampling_rate
            audio_data = audio_values[0, 0].numpy()
            
            if len(audio_data) == 0:
                raise ValueError("生成的音频数据为空")
            
            scipy.io.wavfile.write(output_file, rate=sampling_rate, data=audio_data)
            
            # 验证文件是否成功创建
            if not os.path.exists(output_file):
                raise FileNotFoundError("音频文件保存失败")
            
            file_size = os.path.getsize(output_file)
            if file_size == 0:
                raise ValueError("生成的音频文件为空")
            
            print(f"✅ 音乐生成完成: {file_id}, 文件大小: {file_size} bytes")
            
            return jsonify({
                'success': True,
                'file_id': file_id,
                'message': '音乐生成完成！',
                'file_size': file_size
            })
            
        except Exception as e:
            # 清理可能创建的空文件
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
            raise e
        
    except ValueError as e:
        return jsonify({
            'error': f'音频生成失败: {str(e)}',
            'error_type': 'generation_error',
            'suggestion': '请重试或检查模型配置'
        }), 500
    except FileNotFoundError as e:
        return jsonify({
            'error': f'文件操作失败: {str(e)}',
            'error_type': 'file_error',
            'suggestion': '请检查存储空间和文件权限'
        }), 500
    except Exception as e:
        return jsonify({
            'error': f'生成音乐时出错: {str(e)}',
            'error_type': 'unknown_error',
            'suggestion': '请稍后重试或联系技术支持'
        }), 500

# 删除重复的generate_music路由定义（第408行开始）
# 保留上面第296行开始的改进版本

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