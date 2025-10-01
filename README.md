# 压力音乐生成器

一个基于用户压力水平生成个性化音乐的 Web 应用，结合了正念冥想动画和 AI 音乐生成技术。

## 功能特点

- 🎵 **智能音乐生成**: 根据用户选择的压力水平（低/中/高）生成相应的音乐
- 🧘 **正念动画**: 类似 Apple Watch 的呼吸引导和粒子效果
- 🎨 **动态主题**: 根据压力水平自动调整界面颜色主题
- 📱 **响应式设计**: 支持桌面和移动设备
- ⚡ **实时状态**: 显示模型加载状态和生成进度

## 技术栈

- **后端**: Flask (Python)
- **前端**: HTML5 + CSS3 + JavaScript
- **AI 模型**: Facebook MusicGen
- **音频处理**: SciPy
- **机器学习**: Transformers (Hugging Face)

## 安装和运行

### 方法一：直接运行（推荐用于开发）

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 准备模型

确保您的MusicGen模型位于 `/Users/xibei/MusicGPT/model` 目录下。

#### 3. 运行应用

```bash
# 使用启动脚本（推荐）
python run.py

# 或直接运行
python app.py
```

#### 4. 访问应用

打开浏览器访问: http://localhost:5001

### 方法二：Docker部署（推荐用于生产）

#### 1. 准备模型

确保您的MusicGen模型位于 `/Users/xibei/MusicGPT/model` 目录下。

#### 2. 使用部署脚本

```bash
# 一键部署
./deploy.sh
```

#### 3. 手动Docker部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 4. 访问应用

打开浏览器访问: http://localhost:5001

## 项目结构

```
InteractiveWebPage/
├── app.py                 # Flask主应用
├── stress.py             # 压力水平处理模块
├── music.py              # 音乐生成模块（原始版本）
├── requirements.txt      # Python依赖
├── templates/
│   └── index.html        # 主页面模板
├── static/
│   ├── css/
│   │   └── style.css     # 样式文件
│   └── js/
│       └── app.js        # 前端逻辑
└── generated_audio/      # 生成的音频文件存储目录
```

## 使用说明

1. **选择压力水平**: 点击对应的压力水平选项（低/中/高）
2. **观看动画**: 享受正念冥想动画效果
3. **等待生成**: 系统会根据您的压力水平生成专属音乐
4. **播放音乐**: 音乐生成完成后可以直接播放
5. **重新生成**: 可以随时重新生成音乐

## 压力水平对应

- **低压力**: 个性化偏好音乐
- **中等压力**: 轻快音乐 (80-100 BPM, 大调)
- **高压力**: 舒缓音乐 (小提琴悲伤音乐)

## 注意事项

- 首次运行需要下载和加载 AI 模型，请耐心等待
- 生成的音频文件会保存在 `generated_audio` 目录
- 建议使用现代浏览器以获得最佳体验

## 开发说明

- 模型在后台异步加载，避免阻塞用户界面
- 支持并发请求，但建议避免同时生成多个音乐
- 音频文件使用 UUID 命名，避免冲突

## 故障排除

如果遇到问题：

1. 检查模型路径是否正确
2. 确保所有依赖已正确安装
3. 查看控制台错误信息
4. 检查端口 5001 是否被占用

## 许可证

本项目仅供学习和研究使用。
