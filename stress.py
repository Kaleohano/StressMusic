
# 压力水平与音乐关键词对应关系
import os
import json
from typing import Optional

# 基础关键词（不包含用户偏好）
# 基础的压力-音乐映射表（MusicGen 风格优化版）
_BASE_STRESS_MUSIC_MAP = {
    # 压力低：欢快、活力
    "低": ["upbeat pop rock", "energetic", "catchy melody", "positive vibes", "bright atmosphere", "major scale"],
    # 压力中：平静、流畅
    "中": ["smooth jazz", "lo-fi hip hop", "relaxing flow", "chill", "soft textures", "moderate tempo"],
    # 压力高：疗愈、冥想
    "高": [
        "soft piano", "acoustic guitar", "cello", "soothing instrumental", "relaxing melody", "arpeggio", "clear melody", "warm tone"
    ]
}

# 持久化文件路径（会写入用户选择的偏好关键词）
_MAP_STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'generated_audio', 'stress_music_map.json')


def _load_persistent_map():
    """如果持久化文件存在则加载，否则使用内存中的默认值。"""
    try:
        if os.path.exists(_MAP_STORAGE_PATH):
            with open(_MAP_STORAGE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 保证包含三个级别
                for k in ["低", "中", "高"]:
                    if k not in data:
                        data[k] = _BASE_STRESS_MUSIC_MAP.get(k, [])
                return data
    except Exception:
        pass
    return _BASE_STRESS_MUSIC_MAP.copy()


def _save_persistent_map(mapping: dict):
    try:
        os.makedirs(os.path.dirname(_MAP_STORAGE_PATH), exist_ok=True)
        with open(_MAP_STORAGE_PATH, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception:
        # 写入失败不应中断主流程
        pass


# 用户音乐偏好选择列表
VALID_PREFERENCES = [
    'pop', 'rock', 'classical', 'hip hop', 'electronic',
    'r&b', 'jazz', 'country', 'blues', 'reggae'
]


# 用户音乐偏好选择（运行时变量，不修改文件）
# 可选值: 见 VALID_PREFERENCES, None（未选择）
USER_MUSIC_PREFERENCE = None


def _build_stress_music_map(base_map=None, user_preference=None):
    """根据基础映射和用户偏好构建完整的 STRESS_MUSIC_MAP。
    
    如果 user_preference 不为 None，会将其添加到每个压力等级的关键词列表开头。
    """
    if base_map is None:
        base_map = _BASE_STRESS_MUSIC_MAP.copy()
    else:
        base_map = base_map.copy()
    
    result = {}
    for level, keywords in base_map.items():
        # 复制关键词列表
        level_keywords = keywords.copy()
        
        # 如果用户有偏好，将其添加到开头（先移除旧的偏好关键词）
        if user_preference is not None:
            # 移除旧的偏好关键词
            level_keywords = [kw for kw in level_keywords if kw not in VALID_PREFERENCES]
            # 将用户偏好添加到开头
            level_keywords.insert(0, user_preference)
        
        result[level] = level_keywords
    
    return result


# 在模块加载时尝试用持久化数据覆盖默认映射
# 注意：_load_persistent_map() 会尝试从持久化文件中恢复 USER_MUSIC_PREFERENCE
_persistent_map = _load_persistent_map()

# 构建最终的 STRESS_MUSIC_MAP（包含用户偏好）
# 如果持久化文件存在，使用持久化数据；否则使用基础映射
if _persistent_map != _BASE_STRESS_MUSIC_MAP:
    STRESS_MUSIC_MAP = _persistent_map
    # 从持久化数据中恢复用户偏好
    first_keywords = []
    for level in ["低", "中", "高"]:
        if level in _persistent_map and len(_persistent_map[level]) > 0:
            first_keyword = _persistent_map[level][0]
            if first_keyword in VALID_PREFERENCES:
                first_keywords.append(first_keyword)
    if len(first_keywords) == 3 and len(set(first_keywords)) == 1:
        USER_MUSIC_PREFERENCE = first_keywords[0]
        print(f"✅ 已从持久化文件恢复用户音乐偏好: {USER_MUSIC_PREFERENCE}")
else:
    # 使用基础映射构建（此时 USER_MUSIC_PREFERENCE 为 None）
    STRESS_MUSIC_MAP = _build_stress_music_map()

# 用户输入压力水平
def hrv_to_stress_level(hrv_ms: float) -> str:
    """
    根据 HRV(RMSSD) 的毫秒值返回压力等级：
    - HRV >= 35 ms: 低压力（'低'）
    - 20 <= HRV < 35 ms: 中压力（'中'）
    - HRV < 20 ms: 高压力（'高'）

    注意：如果输入为 None 或非正数，会返回默认的 '高'。
    """
    try:
        if hrv_ms is None:
            return "高"
        h = float(hrv_ms)
    except Exception:
        return "高"

    if h >= 35.0:
        return "低"
    if 20.0 <= h < 35.0:
        return "中"
    return "高"


def get_user_stress_level(hrv_ms: Optional[float] = None) -> str:
    """返回压力等级：

    优先规则：
    - 如果显式传入 `hrv_ms`，基于 HRV 计算等级。
    - 否则尝试从 `generated_audio/latest_hrv.txt` 读取最近的 HRV 值并计算等级。
    - 若仍无法获取，则返回默认的 '高'（不会打印交互式错误）。
    """
    if hrv_ms is not None:
        return hrv_to_stress_level(hrv_ms)

    # 尝试从文件读取最近的 HRV 值
    latest_path = os.path.join(os.path.dirname(__file__), 'generated_audio', 'latest_hrv.txt')
    try:
        if os.path.exists(latest_path):
            with open(latest_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return hrv_to_stress_level(float(content))
    except Exception:
        pass

    # 回退到默认，不再要求手动输入
    return '高'

def get_user_bpm() -> int:
    """读取最近的脉搏 BPM"""
    path = os.path.join(os.path.dirname(__file__), 'generated_audio', 'latest_bpm.txt')
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return int(float(f.read().strip()))
    except:
        pass
    return 75  # 默认值


# 根据压力水平和关键词生成音乐模型输入文本
def get_stress_music_prompt(hrv_ms: Optional[float] = None) -> str:
    """根据 HRV（可选）返回用于音乐生成的关键词文本。

    用法：
        - `get_stress_music_prompt(hrv_ms=25.3)` 会基于 HRV 自动选择压力等级并返回关键词。
        - 不传 `hrv_ms` 时尝试读取 `latest_hrv.txt` 来判断等级。
        - 如果设置了 USER_MUSIC_PREFERENCE，会自动添加到关键词列表的开头。
        - 会读取 user BPM 并动态调整生成音乐的速度（BPM）。
    """
    stress_level = get_user_stress_level(hrv_ms)
    # 获取当前压力等级的关键词（已经包含了 USER_MUSIC_PREFERENCE，如果设置了的话）
    # 注意：必须 copy，否则会修改全局变量
    music_keywords = STRESS_MUSIC_MAP.get(stress_level, STRESS_MUSIC_MAP['高']).copy()
    
    # --- 动态 BPM 策略 ---
    user_bpm = get_user_bpm()
    target_bpm = user_bpm
    
    if stress_level == '高':
        # 高压力（如 90）：目标提升到 75，避免 60bpm 导致的呆板长音
        target_bpm = max(75, user_bpm - 15)
    elif stress_level == '中':
        # 中压力：稍微慢一点
        target_bpm = max(60, user_bpm - 5)
    else: 
        # 低压力：同频共振，保持活力
        target_bpm = user_bpm

    # 移除原有的硬编码 BPM 范围 (如 "80-100 BPM")
    music_keywords = [k for k in music_keywords if "BPM" not in k]
    
    # 将 BPM 转换为语义描述，这更利于 MusicGen 生成高质量音乐
    if target_bpm < 70:
        tempo_desc = "slow tempo"
    elif target_bpm < 110:
        tempo_desc = "moderate tempo"
    else:
        tempo_desc = "fast tempo"

    # 插入动态 BPM 和描述
    
    # --- 关键修复：恢复丢失的智能偏好适配逻辑 ---
    if USER_MUSIC_PREFERENCE:
        pref = USER_MUSIC_PREFERENCE.lower()
        
        # 1. 高压力修饰：Pop -> Soft Pop Ballad
        if stress_level == '高' and len(music_keywords) > 0 and music_keywords[0] == USER_MUSIC_PREFERENCE:
             music_keywords[0] = f"soft {music_keywords[0]} ballad, acoustic version"
        
        # 2. 低压力修饰：防止特定风格 + Pop Rock 的冲突
        # 扩充保护名单：Blues, R&B, Soul, Country, Folk 等都不应该和 Pop Rock 混搭
        protected_genres = ['classical', 'jazz', 'piano', 'orchestral', 'blues', 'r&b', 'soul', 'country', 'folk', 'acoustic']
        
        if stress_level == '低' and any(g in pref for g in protected_genres):
            # 动态替换 STRESS_LEVEL_LOW 的默认 Pop Rock 描述
            # 这里的 trick 是直接重构列表，抛弃默认的 upbeat pop rock
            music_keywords = [USER_MUSIC_PREFERENCE, "energetic", "virtuoso", "upbeat rhythm", "positive vibes", "bright atmosphere", "major scale"]
        # 2. 低压力修饰... (Existing code)
        
        # 3. 中压力修饰 (新增)：防止 Reggae + Smooth Jazz 的"撞钟"惨剧
        # Reggae, Funk, Latin, Hip Hop 等强节奏风格不应强行转 Jazz
        rhythmic_genres = ['reggae', 'funk', 'latin', 'hip hop', 'disco', 'house', 'soul']
        if stress_level == '中' and any(g in pref for g in rhythmic_genres):
             # 保持原风格，但加上"Chill", "Laid back" 等中性放松词，而不是 Jazz
             music_keywords = [USER_MUSIC_PREFERENCE, "chill groove", "laid back", "melodic", "soft textures", "moderate tempo", "instrumental"]
             
    # ---------------------------------------------
    seen = set()
    deduped_keywords = []
    
    # 先处理 BPM 字符串
    bpm_str = f"{tempo_desc}, bpm: {target_bpm}"
    
    # 遍历现有关键词并去重
    for k in music_keywords:
        k_clean = k.strip()
        k_lower = k_clean.lower()
        # 过滤掉重复的 tempo 描述，因为我们最后会统一加 bpm_str
        if k_clean and k_lower not in seen and "tempo" not in k_lower and "bpm" not in k_lower:
            seen.add(k_lower)
            deduped_keywords.append(k_clean)
            
    # 将 BPM 描述插入到合适位置 (紧跟风格之后)
    # 如果有用户偏好且在第一位，插在第二位；否则插在第一位
    insert_pos = 0
    if USER_MUSIC_PREFERENCE and len(deduped_keywords) > 0 and USER_MUSIC_PREFERENCE in deduped_keywords[0]:
        insert_pos = 1
        
    deduped_keywords.insert(insert_pos, bpm_str)
    
    # 优化 Prompt 尾部 (添加高质量标签和去人声，防止恐怖原本)
    extras = ["high fidelity", "4k audio", "stereo", "instrumental", "no vocals"]
    for e in extras:
        if e not in seen:
            deduped_keywords.append(e)
    
    return ", ".join(deduped_keywords)


def set_user_music_preference(preference_keyword: str) -> bool:
    """设置用户音乐偏好（运行时变量，不修改文件）。
    
    参数:
        preference_keyword: 偏好关键词，应为 VALID_PREFERENCES 中的值
    
    返回:
        bool: 设置是否成功
    """
    global USER_MUSIC_PREFERENCE, STRESS_MUSIC_MAP
    if preference_keyword in VALID_PREFERENCES:
        USER_MUSIC_PREFERENCE = preference_keyword
        # 重新构建 STRESS_MUSIC_MAP，包含新的用户偏好
        STRESS_MUSIC_MAP = _build_stress_music_map(_BASE_STRESS_MUSIC_MAP, USER_MUSIC_PREFERENCE)
        # 同时更新持久化文件，以便下次启动时也能加载偏好
        _save_persistent_map(STRESS_MUSIC_MAP)
        return True
    return False


def apply_user_music_preference(preference_keyword: str, hrv_ms: Optional[float] = None) -> str:
    """将用户选择的偏好关键词追加到对应压力等级的关键词列表并触发持久化。

    返回用于生成的 prompt 文本（逗号分隔）。
    如果没有传入 `hrv_ms`，会尝试读取 `latest_hrv.txt` 来判定当前压力等级。
    
    注意：此函数已更新为使用 USER_MUSIC_PREFERENCE 变量。
    """
    # 设置用户偏好
    set_user_music_preference(preference_keyword)
    # 返回更新后的 prompt
    return get_stress_music_prompt(hrv_ms)


def apply_user_preference_and_generate(preference_keyword: str, hrv_ms: Optional[float] = None) -> None:
    """便捷函数：应用偏好并触发音乐生成（会调用 `music.generate_music`）。"""
    prompt = apply_user_music_preference(preference_keyword, hrv_ms)
    # 延迟导入以避免循环依赖或模型在未需要时加载
    try:
        from music import generate_music
        generate_music(input_text=prompt)
    except Exception:
        # 如果无法触发生成（例如模块问题），静默失败，已更新持久化映射
        pass


