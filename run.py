#!/usr/bin/env python3
"""
压力音乐生成器启动脚本
"""

import os
import sys
import subprocess

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import flask
        import scipy
        import transformers
        import torch
        print("✅ 所有依赖已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def check_model():
    """检查模型是否存在"""
    model_path = "/Users/xibei/MusicGPT/model"
    if os.path.exists(model_path):
        print("✅ 模型文件存在")
        return True
    else:
        print(f"❌ 模型文件不存在: {model_path}")
        print("请确保MusicGen模型已下载到指定路径")
        return False

def main():
    """主函数"""
    print("🎵 压力音乐生成器启动中...")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查模型
    if not check_model():
        sys.exit(1)
    
    # 创建必要的目录
    os.makedirs("generated_audio", exist_ok=True)
    print("✅ 目录结构已准备")
    
    print("=" * 50)
    print("🚀 启动Web服务器...")
    print("📱 请在浏览器中访问: http://localhost:5001")
    print("⏹️  按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    # 启动Flask应用
    try:
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
