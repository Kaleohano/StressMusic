from flask import Flask, render_template, request, jsonify, send_file
import os
import uuid
from datetime import datetime, timedelta
import threading
import time
import shutil

# 导入我们现有的模块
from stress import get_stress_music_prompt, STRESS_MUSIC_MAP
import scipy
from transformers import AutoProcessor, MusicgenForConditionalGeneration

app = Flask(__name__)

# 全局变量存储模型（避免重复加载）
model = None
processor = None
model_loaded = False

def load_model():
    """在后台加载模型"""
    global model, processor, model_loaded
    try:
        print("开始加载模型...")
        
        # 检查模型路径是否存在
        model_path = "/Users/xibei/MusicGPT/model"
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型路径不存在: {model_path}")
        
        # 检查必要的模型文件
        required_files = ["config.json", "pytorch_model.bin"]
        for file in required_files:
            if not os.path.exists(os.path.join(model_path, file)):
                raise FileNotFoundError(f"缺少模型文件: {file}")
        
        processor = AutoProcessor.from_pretrained(model_path)
        model = MusicgenForConditionalGeneration.from_pretrained(model_path)
        model_loaded = True
        print("模型加载完成！")
        
    except FileNotFoundError as e:
        print(f"模型文件错误: {e}")
        model_loaded = False
    except ImportError as e:
        print(f"依赖库错误: {e}")
        model_loaded = False
    except Exception as e:
        print(f"模型加载失败: {e}")
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

@app.route('/api/generate-music', methods=['POST'])
def generate_music():
    """生成音乐API"""
    try:
        # 检查请求数据
        if not request.is_json:
            return jsonify({'error': '请求必须是JSON格式'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
        
        stress_level = data.get('stress_level', '高')
        
        # 检查模型状态
        if not model_loaded:
            return jsonify({
                'error': '模型还在加载中，请稍后再试',
                'error_type': 'model_loading'
            }), 503
        
        if model is None or processor is None:
            return jsonify({
                'error': '模型未正确加载，请检查模型文件',
                'error_type': 'model_error'
            }), 500
        
        # 验证压力水平
        if stress_level not in STRESS_MUSIC_MAP:
            return jsonify({
                'error': f'无效的压力水平: {stress_level}',
                'error_type': 'invalid_stress_level',
                'valid_levels': list(STRESS_MUSIC_MAP.keys())
            }), 400
        
        # 检查存储空间
        if not os.path.exists(AUDIO_DIR):
            os.makedirs(AUDIO_DIR)
        
        # 生成唯一的文件名
        file_id = str(uuid.uuid4())
        output_file = os.path.join(AUDIO_DIR, f"{file_id}.wav")
        
        # 获取音乐提示词
        music_keywords = STRESS_MUSIC_MAP[stress_level]
        input_text = f"音乐关键词：{'、'.join(music_keywords)}"
        
        print(f"开始生成音乐，压力水平: {stress_level}")
        
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
                temperature=1.2,
                top_k=250,
                top_p=0.9
            )
            
            # 保存音频文件
            sampling_rate = model.config.audio_encoder.sampling_rate
            audio_data = audio_values[0, 0].numpy()
            
            # 检查音频数据
            if len(audio_data) == 0:
                raise ValueError("生成的音频数据为空")
            
            scipy.io.wavfile.write(output_file, rate=sampling_rate, data=audio_data)
            
            # 验证文件是否成功创建
            if not os.path.exists(output_file):
                raise FileNotFoundError("音频文件保存失败")
            
            file_size = os.path.getsize(output_file)
            if file_size == 0:
                raise ValueError("生成的音频文件为空")
            
            print(f"音乐生成完成: {file_id}, 文件大小: {file_size} bytes")
            
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
            'error_type': 'generation_error'
        }), 500
    except FileNotFoundError as e:
        return jsonify({
            'error': f'文件操作失败: {str(e)}',
            'error_type': 'file_error'
        }), 500
    except Exception as e:
        return jsonify({
            'error': f'生成音乐时出错: {str(e)}',
            'error_type': 'unknown_error'
        }), 500

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

@app.route('/api/model-status')
def model_status():
    """检查模型加载状态"""
    return jsonify({
        'loaded': model_loaded,
        'status': 'ready' if model_loaded else 'loading'
    })

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
