#!/bin/bash

# 压力音乐生成器部署脚本

echo "🎵 压力音乐生成器部署脚本"
echo "================================"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 检查模型文件是否存在
MODEL_PATH="/Users/xibei/MusicGPT/model"
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ 模型文件不存在: $MODEL_PATH"
    echo "请确保MusicGen模型已下载到指定路径"
    exit 1
fi

echo "✅ 环境检查通过"

# 创建必要的目录
mkdir -p generated_audio
echo "✅ 创建目录结构"

# 构建Docker镜像
echo "🔨 构建Docker镜像..."
docker-compose build

if [ $? -eq 0 ]; then
    echo "✅ Docker镜像构建成功"
else
    echo "❌ Docker镜像构建失败"
    exit 1
fi

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

if [ $? -eq 0 ]; then
    echo "✅ 服务启动成功"
    echo ""
    echo "📱 应用访问地址: http://localhost:5001"
    echo "📊 健康检查: http://localhost:5001/api/model-status"
    echo ""
    echo "🛠️  管理命令:"
    echo "  查看日志: docker-compose logs -f"
    echo "  停止服务: docker-compose down"
    echo "  重启服务: docker-compose restart"
else
    echo "❌ 服务启动失败"
    exit 1
fi
