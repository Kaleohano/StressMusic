// 全局变量
let selectedStressLevel = null;
let currentAudioFileId = null;
let isPlaying = false;
let isGenerating = false; // 防止重复生成
let generationStartTime = null; // 生成开始时间

// DOM元素
const stressOptions = document.getElementById("stressOptions");
const musicGeneration = document.getElementById("musicGeneration");
const musicPlayer = document.getElementById("musicPlayer");
const audioPlayer = document.getElementById("audioPlayer");
const playPauseBtn = document.getElementById("playPauseBtn");
const regenerateBtn = document.getElementById("regenerateBtn");
const statusText = document.getElementById("statusText");
const modelStatus = document.getElementById("modelStatus");
const breathingCircle = document.getElementById("breathingCircle");
const particles = document.getElementById("particles");

// 初始化应用
document.addEventListener("DOMContentLoaded", function () {
  initializeApp();
  createParticles();
  checkModelStatus();
});

// 初始化应用
async function initializeApp() {
  try {
    // 加载压力水平选项
    const response = await fetch("/api/stress-levels");
    const stressLevels = await response.json();
    createStressOptions(stressLevels);
  } catch (error) {
    console.error("初始化失败:", error);
    showError("初始化失败，请刷新页面重试");
  }
}

// 创建压力水平选项
function createStressOptions(levels) {
  stressOptions.innerHTML = "";

  levels.forEach((level) => {
    const option = document.createElement("div");
    option.className = "stress-option";
    option.textContent = getStressLevelText(level);
    option.dataset.level = level;

    option.addEventListener("click", () => selectStressLevel(level, option));
    stressOptions.appendChild(option);
  });
}

// 获取压力水平显示文本
function getStressLevelText(level) {
  const levelTexts = {
    低: "😌 低压力 - 个性化音乐",
    中: "😐 中等压力 - 轻快音乐",
    高: "😰 高压力 - 舒缓音乐",
  };
  return levelTexts[level] || level;
}

// 选择压力水平
function selectStressLevel(level, element) {
  // 移除其他选项的选中状态
  document.querySelectorAll(".stress-option").forEach((opt) => {
    opt.classList.remove("selected");
  });

  // 选中当前选项
  element.classList.add("selected");
  selectedStressLevel = level;

  // 根据压力水平调整动画颜色
  updateAnimationForStressLevel(level);

  // 开始生成音乐
  generateMusic();
}

// 根据压力水平更新动画
function updateAnimationForStressLevel(level) {
  const circle = breathingCircle.querySelector(".breathing-circle");
  const body = document.body;

  // 移除之前的颜色类
  body.classList.remove("stress-low", "stress-medium", "stress-high");

  // 添加对应的颜色类
  switch (level) {
    case "低":
      body.classList.add("stress-low");
      break;
    case "中":
      body.classList.add("stress-medium");
      break;
    case "高":
      body.classList.add("stress-high");
      break;
  }
}

// 生成音乐
async function generateMusic() {
  if (!selectedStressLevel) return;
  
  // 防止重复生成
  if (isGenerating) {
    showError("正在生成音乐中，请稍候...", 'duplicate_request');
    return;
  }

  try {
    isGenerating = true;
    generationStartTime = Date.now();
    
    // 显示生成界面
    musicGeneration.style.display = "block";
    musicPlayer.style.display = "none";
    statusText.textContent = "正在生成音乐...";
    
    // 更新状态文本
    updateGenerationStatus();

    // 发送生成请求
    const response = await fetch("/api/generate-music", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        stress_level: selectedStressLevel,
      }),
    });

    const result = await response.json();

    if (result.success) {
      currentAudioFileId = result.file_id;
      isGenerating = false; // 重置生成状态
      showMusicPlayer();
    } else {
      // 根据错误类型显示不同的提示
      const errorType = result.error_type || 'unknown';
      let errorMessage = result.error || "生成音乐失败";
      
      switch (errorType) {
        case 'model_loading':
          errorMessage = "模型正在加载中，请稍后再试...";
          break;
        case 'model_error':
          errorMessage = "模型加载失败，请检查模型文件";
          break;
        case 'invalid_stress_level':
          errorMessage = `无效的压力水平，请选择: ${result.valid_levels?.join(', ') || '低/中/高'}`;
          break;
        case 'generation_error':
          errorMessage = "音频生成失败，请重试";
          break;
        case 'file_error':
          errorMessage = "文件操作失败，请检查存储空间";
          break;
        default:
          errorMessage = result.error || "生成音乐失败";
      }
      
      throw new Error(errorMessage);
    }
  } catch (error) {
    console.error("生成音乐失败:", error);
    
    // 根据错误类型决定是否隐藏生成界面
    if (error.message.includes('模型正在加载') || error.message.includes('模型加载失败')) {
      // 模型相关错误，保持生成界面显示
      statusText.textContent = error.message;
    } else {
      // 其他错误，隐藏生成界面
      musicGeneration.style.display = "none";
    }
    
    isGenerating = false; // 重置生成状态
    showError(error.message, 'music_generation');
  }
}

// 更新生成状态文本
function updateGenerationStatus() {
  if (!isGenerating) return;
  
  const elapsed = Math.floor((Date.now() - generationStartTime) / 1000);
  let statusText = "正在生成音乐...";
  
  if (elapsed > 10) {
    statusText = `正在生成音乐... (${elapsed}秒)`;
  }
  if (elapsed > 30) {
    statusText = `正在生成音乐... (${elapsed}秒) 请耐心等待`;
  }
  if (elapsed > 60) {
    statusText = `正在生成音乐... (${elapsed}秒) 生成时间较长，请稍候`;
  }
  
  document.getElementById("statusText").textContent = statusText;
  
  // 继续更新状态
  setTimeout(updateGenerationStatus, 1000);
}

// 显示音乐播放器
function showMusicPlayer() {
  musicGeneration.style.display = "none";
  musicPlayer.style.display = "block";

  // 设置音频源
  audioPlayer.src = `/api/audio/${currentAudioFileId}`;

  // 重置播放按钮
  playPauseBtn.textContent = "播放";
  isPlaying = false;
}

// 播放/暂停音乐
playPauseBtn.addEventListener("click", function () {
  if (isPlaying) {
    audioPlayer.pause();
    playPauseBtn.textContent = "播放";
    isPlaying = false;
  } else {
    audioPlayer.play();
    playPauseBtn.textContent = "暂停";
    isPlaying = true;
  }
});

// 重新生成音乐
regenerateBtn.addEventListener("click", function () {
  if (selectedStressLevel) {
    generateMusic();
  }
});

// 检查模型状态
async function checkModelStatus() {
  try {
    const response = await fetch("/api/model-status");
    const status = await response.json();

    const indicator = modelStatus.querySelector(".status-indicator");
    const text = modelStatus.querySelector("#statusText");

    if (status.loaded) {
      indicator.className = "status-indicator ready";
      text.textContent = "模型已就绪";
    } else {
      indicator.className = "status-indicator loading";
      text.textContent = "模型加载中...";
      // 每5秒检查一次
      setTimeout(checkModelStatus, 5000);
    }
  } catch (error) {
    console.error("检查模型状态失败:", error);
    const indicator = modelStatus.querySelector(".status-indicator");
    const text = modelStatus.querySelector("#statusText");
    indicator.className = "status-indicator error";
    text.textContent = "模型加载失败";
  }
}

// 创建粒子效果
function createParticles() {
  setInterval(() => {
    if (particles.children.length < 20) {
      // 限制粒子数量
      const particle = document.createElement("div");
      particle.className = "particle";

      // 随机位置
      particle.style.left = Math.random() * 100 + "%";
      particle.style.animationDelay = Math.random() * 2 + "s";
      particle.style.animationDuration = Math.random() * 3 + 3 + "s";

      particles.appendChild(particle);

      // 动画结束后移除粒子
      setTimeout(() => {
        if (particle.parentNode) {
          particle.parentNode.removeChild(particle);
        }
      }, 6000);
    }
  }, 200);
}

// 显示错误信息
function showError(message, errorType = 'unknown') {
  // 创建错误提示元素
  const errorDiv = document.createElement('div');
  errorDiv.className = 'error-message';
  errorDiv.innerHTML = `
    <div class="error-content">
      <span class="error-icon">⚠️</span>
      <span class="error-text">${message}</span>
      <button class="error-close" onclick="this.parentElement.parentElement.remove()">×</button>
    </div>
  `;
  
  // 添加到页面顶部
  document.body.insertBefore(errorDiv, document.body.firstChild);
  
  // 自动移除（5秒后）
  setTimeout(() => {
    if (errorDiv.parentNode) {
      errorDiv.remove();
    }
  }, 5000);
  
  console.error(`错误类型: ${errorType}, 消息: ${message}`);
}

// 音频播放事件监听
audioPlayer.addEventListener("ended", function () {
  playPauseBtn.textContent = "播放";
  isPlaying = false;
});

audioPlayer.addEventListener("error", function () {
  showError("音频播放失败，请重新生成");
  playPauseBtn.textContent = "播放";
  isPlaying = false;
});
