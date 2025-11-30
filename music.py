import os
import scipy
from stress import get_stress_music_prompt
import time
from transformers import AutoProcessor, MusicgenForConditionalGeneration

print("Start downloading model...")

# 加载处理器和模型（路径按用户本地模型存放位置）
processor = AutoProcessor.from_pretrained("/Users/xibei/MusicGPT/model")
print("Processor loaded")
model = MusicgenForConditionalGeneration.from_pretrained("/Users/xibei/MusicGPT/model")
print("Model loaded")


def generate_music(input_text: str = None, output_path: str = "generated_audio/musicgen_out.wav"):
    """基于给定的 `input_text`（prompt）生成音乐并写入 `output_path`。

    如果 `input_text` 为 None，会尝试基于最近的 HRV 调用 `get_stress_music_prompt` 获取 prompt。
    """
    # 如果没有提供 prompt，则基于最近 HRV 读取生成
    if input_text is None:
        latest_hrv_path = os.path.join(os.path.dirname(__file__), 'generated_audio', 'latest_hrv.txt')
        hrv_val = None
        if os.path.exists(latest_hrv_path):
            try:
                with open(latest_hrv_path, 'r', encoding='utf-8') as f:
                    hrv_val = float(f.read().strip())
                    print(f"Detected latest HRV from file: {hrv_val} ms")
            except Exception as e:
                print("无法读取 latest_hrv.txt，回退至默认压力等级：", e)
        input_text = get_stress_music_prompt(hrv_val)

    print("input_text:", input_text)

    inputs = processor(
        text=[input_text],
        padding=True,
        return_tensors="pt"
    )

    start = time.time()
    # 启用采样以避免每次都生成完全相同的输出
    audio_values = model.generate(
        **inputs,
        max_new_tokens=500,
        do_sample=True,
        temperature=1.2,
        top_k=250,
        top_p=0.9
    )
    print(time.time() - start)  # Log time taken in generation

    sampling_rate = model.config.audio_encoder.sampling_rate
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    scipy.io.wavfile.write(output_path, rate=sampling_rate, data=audio_values[0, 0].numpy())
    print(f"音乐已保存到: {output_path}")


# 模型加载完成后，如果HRV文件存在，自动触发一次音乐生成
# 这样可以确保即使HRV不再更新，模型加载完成后也能生成音乐
# 注意：如果通过 --no-auto 参数调用，则不会自动触发（用于被watcher调用时）
if __name__ == '__main__':
    import sys
    # 检查是否有 --no-auto 参数（用于被watcher调用时避免重复触发）
    auto_trigger = '--no-auto' not in sys.argv
    
    if auto_trigger:
        latest_hrv_path = os.path.join(os.path.dirname(__file__), 'generated_audio', 'latest_hrv.txt')
        if os.path.exists(latest_hrv_path):
            try:
                # 检查文件是否最近更新过
                file_mtime = os.path.getmtime(latest_hrv_path)
                time_since_update = time.time() - file_mtime
                # 如果文件存在（无论多久前更新），都触发一次生成
                # 这样即使HRV不再更新，模型加载完成后也能基于最新的HRV值生成音乐
                print(f"检测到HRV文件存在（{time_since_update:.1f}秒前更新），自动触发音乐生成...")
                generate_music()
                print("自动音乐生成完成")
            except Exception as e:
                print(f"自动触发音乐生成时出错: {e}")
        else:
            print("未检测到HRV文件，跳过自动生成。请先运行HRV测量程序。")
    else:
        # 被watcher调用，显式调用generate_music
        print("被watcher调用，开始生成音乐...")
        generate_music()
        print("音乐生成完成")
