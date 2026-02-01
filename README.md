# 多模态交互式个性化心理压力疗愈系统

基于 HRV（心率变异性）监测和 AI 音乐生成的个性化心理压力疗愈 Web 应用系统。

## 功能特点

- 🎵 **智能音乐生成**: 基于用户 HRV 值和音乐偏好生成个性化疗愈音乐
- 🎨 **多页面交互流程**: 完整的用户体验流程，从检测到音乐播放
- 🧘 **粒子动画效果**: 音乐播放时的动态粒子动画
- 📊 **实时 HRV 监测**: 支持通过 MAX30102/MAX30105 传感器实时监测 HRV
- 🎹- **支持 10 种音乐风格**: 流行 (Pop)、摇滚 (Rock)、古典 (Classic)、嘻哈 (Hip-Hop)、电子 (Electronic)、R&B、爵士 (Jazz)、乡村 (Country)、布鲁斯 (Blues)、雷鬼 (Reggae)。

### 响应式设计
- 支持桌面和移动设备，莫兰迪橙色主题，统一的“左侧交互+右侧光斑”视觉风格。

### 智能状态管理
- 自动检测 HRV 更新和模型加载状态，增加串口冲突智能提示。

## 系统流程

1. **初始页面**: 用户点击"开始"按钮，触发 HRV 监测和模型加载
2. **检测中页面**: 显示实时检测日志（浏览器控制台可见），等待有效心跳数据
3. **音乐偏好选择页面**: 用户从 10 种风格中选择偏好
4. **加载中页面**: 结合压力等级和用户偏好生成个性化音乐
5. **音乐播放页面**: 沉浸式 CD 播放界面与动态光效

## 技术栈

- **后端**: Flask (Python)
- **前端**: HTML5 + CSS3 (Glassmorphism, CSS Grid) + JavaScript (原生)
- **AI 模型**: Facebook MusicGen (通过 Hugging Face Transformers)
- **音频处理**: SciPy
- **硬件支持**: MAX30102/MAX30105 心率传感器 + Arduino

## 安装和运行

### 前置要求

- Python 3.9+
- MusicGen 模型文件（放置在 `/Users/xibei/MusicGPT/model` 目录）
- 可选：Arduino Uno + MAX30102/MAX30105 传感器（用于 HRV 监测）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备模型

确保您的 MusicGen 模型位于 `/Users/xibei/MusicGPT/model` 目录下，包含以下文件：

- `config.json`
- `pytorch_model.bin`
- `preprocessor_config.json`

### 3. 运行应用

```bash
# 使用启动脚本（推荐）
python run.py

# 或直接运行
python app.py
```

### 4. 访问应用

打开浏览器访问: http://localhost:5001

## 项目结构

```
InteractiveWebPage/
├── app.py                 # Flask 主应用（包含 API 和模型加载）
├── stress.py             # 压力水平处理模块（HRV 到压力等级转换）
├── music.py              # 音乐生成模块（原始版本，独立使用）
├── hrv_reader.py         # HRV 串口读取器（从 Arduino 读取 IBI）
├── hrv_watcher.py        # HRV 文件监听器（自动触发音乐生成）
├── hrv_service.py        # HRV 常驻服务（低延迟音乐生成）
├── requirements.txt      # Python 依赖
├── templates/
│   └── index.html        # 主页面模板
├── static/
│   ├── css/
│   │   └── style.css     # 样式文件（莫兰迪橙色主题）
│   └── js/
│       └── app.js         # 前端逻辑（页面状态管理、API 调用）
├── generated_audio/      # 生成的音频文件存储目录
│   ├── latest_hrv.txt    # 最新 HRV 值（由 hrv_reader.py 写入）
│   └── stress_music_map.json  # 用户偏好持久化文件
├── hardware/
│   └── max30102_example/
│       └── max30102_example.ino  # Arduino 示例代码
└── tools/
    └── simulate_hrv.py   # HRV 模拟工具（用于测试）
```

## 核心功能说明

### HRV 监测与压力等级

系统根据 HRV (RMSSD) 值自动判断压力等级：

- **HRV ≥ 35 ms**: 低压力
- **20 ≤ HRV < 35 ms**: 中等压力
- **HRV < 20 ms**: 高压力

### 音乐偏好系统

用户可以选择 10 种音乐风格：

- **基础风格**: 流行 (pop)、摇滚 (rock)、古典 (classical)
- **新增风格**: 嘻哈 (hip hop)、电子 (electronic)、R&B、爵士 (jazz)、乡村 (country)、布鲁斯 (blues)、雷鬼 (reggae)

用户偏好会：

1. 实时更新到 `USER_MUSIC_PREFERENCE` 变量（运行时，不修改文件）
2. 保存到 `generated_audio/stress_music_map.json`（持久化）
3. 应用到所有压力等级的关键词列表开头

### 音乐生成流程

1. 系统读取 `latest_hrv.txt` 获取最新 HRV 值
2. 根据 HRV 值确定压力等级
3. 结合用户选择的音乐偏好生成提示词
4. 使用 MusicGen 模型生成个性化音乐
5. 保存为 WAV 文件并返回给前端播放

## 使用说明

### Web 界面使用

1. **启动应用**: 运行 `python app.py` 或 `python run.py`
2. **访问页面**: 在浏览器中打开 http://localhost:5001
3. **开始检测**: 点击"开始"按钮
4. **等待就绪**: 系统会自动检测 HRV 更新和模型加载状态
5. **选择偏好**: 在偏好选择页面选择音乐风格
6. **生成音乐**: 系统根据 HRV 和偏好生成音乐
7. **播放音乐**: 享受个性化疗愈音乐和粒子动画

### 硬件 HRV 监测（可选）

#### 硬件连接

- **Arduino Uno** + **MAX30102/MAX30105** 传感器
- 接线：
  - `VCC` -> `5V` 或 `3.3V`
  - `GND` -> `GND`
  - `SDA` -> `A4`
  - `SCL` -> `A5`

#### Arduino 代码

1. 安装 `SparkFun MAX3010x` 库
2. 上传 `hardware/max30102_example/max30102_example.ino` 到 Arduino
3. 代码会通过串口输出 `IBI:<value>` 格式的数据

#### 启动 HRV 监测

```bash
# 查找串口设备（macOS）
ls /dev/tty.*

# 启动 HRV 读取器
python hrv_reader.py --port /dev/tty.usbmodemXXXX --baud 115200 --window 30
```

参数说明：

- `--port`: 串口设备路径
- `--baud`: 波特率（默认 115200）
- `--window`: 滑动窗口大小（默认 30，用于计算 RMSSD）

#### 自动触发音乐生成

```bash
# 方式1: 使用文件监听器（推荐用于开发）
python hrv_watcher.py --poll 2 --debounce 10

# 方式2: 使用常驻服务（推荐用于生产，低延迟）
python hrv_service.py --host 127.0.0.1 --port 5002
```

### 测试模式（无硬件）

如果没有硬件设备，可以使用模拟工具：

```bash
# 模拟 HRV 值（用于测试）
python tools/simulate_hrv.py
```

或在 Web 界面中使用 `/api/simulate-hrv` API（仅开发环境）。

## API 接口

### 模型状态

- `GET /api/model-status`: 获取模型加载状态
  - 返回: `{loaded: bool, loading: bool, status: string, message: string}`

### HRV 监测

- `POST /api/start-measurement`: 启动 HRV 监测进程
  - 请求体: `{port: string, baud: int, window: int}`
- `GET /api/latest-hrv`: 获取最新 HRV 值
  - 返回: `{exists: bool, hrv: float, mtime: float}`

### 音乐偏好

- `POST /api/confirm-preference`: 确认用户音乐偏好
  - 请求体: `{preference: string}` (可选值: "流行", "摇滚", "古典")
  - 返回: `{success: bool, preference: string}`

### 音乐生成

- `POST /api/generate-music`: 生成音乐
  - 返回: `{success: bool, file_id: string, message: string}`
- `GET /api/audio/<file_id>`: 获取生成的音频文件

## 配置说明

### 模型路径

默认模型路径: `/Users/xibei/MusicGPT/model`

如需修改，请编辑 `app.py` 中的 `model_path` 变量。

### 串口配置

默认串口配置：

- 端口: `/dev/tty.usbmodem2017_2_251` (macOS)
- 波特率: 115200
- 窗口大小: 30

可在前端代码或 API 调用中自定义。

### 文件存储

- 音频文件: `generated_audio/` 目录
- 最大文件数: 50（可在 `app.py` 中配置）
- 保留时间: 24 小时（可在 `app.py` 中配置）

## 注意事项

- ⚠️ **首次运行**: 模型加载可能需要几分钟时间，请耐心等待
- ⚠️ **内存要求**: MusicGen 模型较大，建议至少 8GB RAM
- ⚠️ **GPU 支持**: 如有 GPU，可显著加速模型加载和音乐生成
- ⚠️ **文件权限**: 确保 `generated_audio/` 目录有写入权限
- ⚠️ **浏览器兼容**: 建议使用 Chrome、Firefox 或 Safari 最新版本

## 故障排除

### 模型加载失败

1. 检查模型路径是否正确
2. 确认模型文件完整（config.json, pytorch_model.bin, preprocessor_config.json）
3. 检查内存是否充足
4. 查看控制台错误信息

### HRV 检测不到

1. 检查串口设备是否正确连接
2. 确认 Arduino 代码已正确上传
3. **关键**: 检查串口是否被其他程序占用（如 Arduino IDE 串口监视器），请务必关闭它们
4. 尝试拔掉 USB 线重新插入
5. 查看浏览器控制台（F12）获取实时传感器日志

### 音乐生成失败

1. 确认模型已加载完成（检查 `/api/model-status`）
2. 检查 `latest_hrv.txt` 文件是否存在且包含有效数值
3. 查看后端日志了解详细错误信息
4. 确认有足够的磁盘空间

### 页面无法访问

1. 检查端口 5001 是否被占用
2. 确认防火墙设置
3. 尝试使用 `http://127.0.0.1:5001` 而不是 `localhost`

## 开发说明

### 代码结构

- **前端状态管理**: `static/js/app.js` 中的页面状态机
- **后端 API**: `app.py` 中的 Flask 路由
- **压力等级处理**: `stress.py` 中的 HRV 到压力等级转换
- **用户偏好**: 使用运行时变量 `USER_MUSIC_PREFERENCE`，不修改源文件

### 扩展开发

- 添加新的音乐风格：修改 `app.py` 中的 `update_and_persist_preference` 函数
- 自定义压力等级：修改 `stress.py` 中的 `hrv_to_stress_level` 函数
- 调整音乐参数：修改 `stress.py` 中的 `_BASE_STRESS_MUSIC_MAP`

## 许可证

本项目仅供学习和研究使用。

## 更新日志

### v2.3 (2026-02-01)

- ✨ **传感器稳定性大幅提升**:
  - 动态过滤策略：初期响应速度从 10秒+ 缩短至 3秒。
  - 实时心跳反馈：后端控制台增加 `❤️` 可视化心跳包，告别“假死”焦虑。
  - 更智能的异常值剔除算法，减少因手指微动导致的数据断流。
- 🐛 **修复**:
  - 修复了 `/api/latest-hrv` 接口未读取 BPM 数据导致前端始终显示默认值 (72 BPM) 的 Bug。
  - 现在疗愈报告能展示真实且精确的 Before/After 心率变化。

### v2.2 (2026-01-29)

- ✨ **音质革命性提升**: 引入 `DC Offset Removal` (去除低频拼接噪音) 和 `Instrumental Safeguard` (防止人声伪影)。
- ✨ **性能压榨**: 启用 `torch.inference_mode()`，推理速度提升 ~10%。
- ✨ **疗愈级等待体验**: 
  - **正念呼吸引导**: 加载页新增 4-7-8 呼吸法视觉引导。
  - **透明化进度日志**: 实时展示 AI 生成的幕后步骤，缓解等待焦虑。
- ✨ **智能疗愈报告**: 
  - 全新的 session 闭环，生成 Before/After 对比报告。
  - 可视化心率波动曲线 (SVG)。
  - **生理指标修正**: 明确 BPM 下降 (↓) 和 HRV 上升 (↑) 为正向疗愈指标 (绿色高亮)。
- 🐛 **修复**: 解决了高压力下生成的音乐可能不连贯的问题。

### v2.1 (2026-01-18)

- ✨ **扩展音乐偏好**: 新增 7 种音乐风格（嘻哈、电子、R&B、爵士、乡村、布鲁斯、雷鬼），共支持 10 种风格。
- ✨ **UI 视觉升级**: 全新的左侧玻璃面板 + 右侧梦幻光斑（Glowing Orbs）统一设计语言。
- ✨ **HRV 算法优化**: 放宽异常值检测标准，提升传感器在手指微动时的稳定性。
- ✨ **实时反馈**: 增加前端控制台实时打印传感器原始日志的功能，便于调试。
- 🐛 **智能报错**: 增加串口占用检测，自动提示关闭其他占用程序。

### v2.0

- ✨ 完整的交互式页面流程
- ✨ 用户音乐偏好选择系统
- ✨ 基于 HRV 的自动压力等级判断
- ✨ 粒子动画效果
- ✨ 智能状态检测（HRV + 模型加载）
- 🐛 修复模型加载状态检测问题
- 🐛 修复文件修改导致应用重启的问题

### v1.0

- 基础音乐生成功能
- HRV 监测支持
- 硬件集成

---

如有问题或建议，欢迎提交 Issue 或 Pull Request。
