import os

class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    AUDIO_DIR = os.environ.get('AUDIO_DIR') or 'generated_audio'
    MAX_AUDIO_FILES = int(os.environ.get('MAX_AUDIO_FILES', 50))
    CLEANUP_INTERVAL = int(os.environ.get('CLEANUP_INTERVAL', 3600))
    AUDIO_RETENTION_HOURS = int(os.environ.get('AUDIO_RETENTION_HOURS', 24))
    
    # 模型配置
    MODEL_PATH = os.environ.get('MODEL_PATH') or '/Users/xibei/MusicGPT/model'
    
    # 生成配置
    MAX_NEW_TOKENS = int(os.environ.get('MAX_NEW_TOKENS', 500))
    TEMPERATURE = float(os.environ.get('TEMPERATURE', 1.2))
    TOP_K = int(os.environ.get('TOP_K', 250))
    TOP_P = float(os.environ.get('TOP_P', 0.9))

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    FLASK_ENV = 'production'

# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
