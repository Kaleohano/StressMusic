
# 压力水平与音乐关键词对应关系
import os
import json
from typing import Optional

# 基础关键词（不包含用户偏好）
_BASE_STRESS_MUSIC_MAP = {
    "低": ["animato", "80-100 BPM", "major scale"],
    "中": ["calm upbeat", "70-90 BPM", "major or modal", "moderate pitch"],
    "高": ["soothing", "60-75 BPM", "slow tempo", "soft instrumentation"]
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

# 根据压力水平和关键词生成音乐模型输入文本
def get_stress_music_prompt(hrv_ms: Optional[float] = None) -> str:
    """根据 HRV（可选）返回用于音乐生成的关键词文本。

    用法：
        - `get_stress_music_prompt(hrv_ms=25.3)` 会基于 HRV 自动选择压力等级并返回关键词。
        - 不传 `hrv_ms` 时尝试读取 `latest_hrv.txt` 来判断等级。
        - 如果设置了 USER_MUSIC_PREFERENCE，会自动添加到关键词列表的开头。
    """
    stress_level = get_user_stress_level(hrv_ms)
    # 获取当前压力等级的关键词（已经包含了 USER_MUSIC_PREFERENCE，如果设置了的话）
    music_keywords = STRESS_MUSIC_MAP.get(stress_level, STRESS_MUSIC_MAP['高'])
    
    # 返回英文的、逗号分隔的关键词，以便模型更好地理解提示词
    return ", ".join(music_keywords)


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


