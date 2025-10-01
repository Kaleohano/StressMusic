
# 压力水平与音乐关键词对应关系
STRESS_MUSIC_MAP = {
    "低": ["个性化偏好"],
    "中": ["animato ", "80-100 BPM", "major scale", "moderate pitch"],
    #"高": ["Relaxed", "60-80 BPM", "Downtempo"]
    "高": ["violin sad music"],
    #低：个性化音乐
    #中：轻快，80-100 BPM，大调音乐，音调适中
    #高：舒缓，60-80 BPM，慢节奏
}

# 用户输入压力水平
def get_user_stress_level():
    #print("请输入压力水平（低/中/高）：")
    #level = input().strip()
    level = '高'
    if level not in STRESS_MUSIC_MAP:
        print("输入无效，默认使用'高'压力水平")
        level = "高"
    return level

# 根据压力水平和关键词生成音乐模型输入文本
def get_stress_music_prompt():
    stress_level = get_user_stress_level()
    music_keywords = STRESS_MUSIC_MAP[stress_level]
    return f"音乐关键词：{'、'.join(music_keywords)}"
