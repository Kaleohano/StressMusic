// 页面状态管理
const pages = {
  initial: document.getElementById("initial-page"),
  detecting: document.getElementById("detecting-page"),
  preference: document.getElementById("preference-page"),
  loading: document.getElementById("loading-page"),
  playing: document.getElementById("playing-page"),
};

let currentPage = "initial";
let selectedPreference = null;
let hrvCheckInterval = null;
let modelCheckInterval = null;
let musicGenerationCheckInterval = null;
let statusCheckInterval = null; // 统一的HRV和模型状态检查interval
let loadingBreathingTimer = null; // 加载页面的呼吸定时器
let musicPollInterval = null; // 轮询音乐生成状态的间隔

// 切换到指定页面
function switchPage(pageName) {
  if (!pages[pageName]) return;

  // 清理之前的检查间隔
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval);
    statusCheckInterval = null;
  }
  if (hrvCheckInterval) {
    clearInterval(hrvCheckInterval);
    hrvCheckInterval = null;
  }
  if (modelCheckInterval) {
    clearInterval(modelCheckInterval);
    modelCheckInterval = null;
  }
  if (musicGenerationCheckInterval) {
    clearInterval(musicGenerationCheckInterval);
    musicGenerationCheckInterval = null;
  }

  // 如果离开播放页面，停止粒子动画
  if (currentPage === "playing" && pageName !== "playing") {
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
  }

  // 如果离开加载页面，停止呼吸引导和进度日志
  if (currentPage === "loading" && pageName !== "loading") {
    stopLoadingBreathing();
    stopLoadingProgressLog();
  }

  pages[currentPage].classList.remove("active");
  pages[pageName].classList.add("active");
  currentPage = pageName;

  // 如果进入加载页面，开始呼吸引导和进度日志
  if (pageName === "loading") {
    startLoadingBreathing();
    startLoadingProgressLog();
  }
}

// 加载页面的正念呼吸引导逻辑
let loadingBreathingState = {
  interval: null,
  timeouts: []
};

function startLoadingBreathing() {
  const orb = document.querySelector('.main-breath-orb');
  const ripples = document.querySelectorAll('.breath-ripple');
  const text = document.getElementById('loading-breath-text');

  if (!orb || !text) return;

  const allElements = [orb, ...ripples];

  // 清理之前的状态
  stopLoadingBreathing();

  // 重置动画类
  const resetClasses = () => {
    allElements.forEach(el => el.classList.remove('inhale', 'hold', 'exhale'));
    void orb.offsetWidth; // 触发重绘
  };
  resetClasses();

  const runCycle = () => {
    // 1. 吸气 (0s - 4s)
    allElements.forEach(el => {
      el.classList.remove('exhale', 'hold');
      el.classList.add('inhale');
    });
    text.innerText = '吸气';
    text.style.opacity = 0.9; // 稍微透明一点更柔和

    // 2. 保持 (4s - 8s)
    const t1 = setTimeout(() => {
      if (currentPage === 'loading') {
        allElements.forEach(el => {
          el.classList.remove('inhale');
          el.classList.add('hold');
        });
        text.innerText = '保持';
      }
    }, 4000);
    loadingBreathingState.timeouts.push(t1);

    // 3. 呼气 (8s - 12s)
    const t2 = setTimeout(() => {
      if (currentPage === 'loading') {
        allElements.forEach(el => {
          el.classList.remove('hold');
          el.classList.add('exhale');
        });
        text.innerText = '呼气';
      }
    }, 8000);
    loadingBreathingState.timeouts.push(t2);
  };

  runCycle(); // 立即执行
  loadingBreathingState.interval = setInterval(runCycle, 12000);
}

function stopLoadingBreathing() {
  try {
    if (!loadingBreathingState) return;

    if (loadingBreathingState.interval) {
      clearInterval(loadingBreathingState.interval);
      loadingBreathingState.interval = null;
    }

    if (Array.isArray(loadingBreathingState.timeouts)) {
      loadingBreathingState.timeouts.forEach(t => clearTimeout(t));
    }
    loadingBreathingState.timeouts = [];
  } catch (e) {
    console.warn("停止呼吸引导时发生非致命错误:", e);
  }
}

// ---------------------------------------------------------
// 方案 A: 进度文案 (Progress Log) - 让等待变得有意义
// ---------------------------------------------------------

let loadingProgressState = {
  timeouts: []
};

const loadingLogs = [
  { time: 0, text: "正在分析您的心率变异性 (HRV)..." },
  { time: 5000, text: "检测到压力水平，正在匹配舒缓算法..." },
  { time: 15000, text: "正在构建基础旋律 (BPM: 70)..." },
  { time: 30000, text: "加载 MusicGen 模型参数..." },
  { time: 50000, text: "正在生成第一乐章：引入..." },
  { time: 90000, text: "正在生成第二乐章：发展..." },
  { time: 130000, text: "正在生成第三乐章：高潮..." },
  { time: 170000, text: "正在生成第四乐章：回归..." },
  { time: 200000, text: "正在进行声学优化与无缝循环处理..." },
  { time: 220000, text: "正在去除音频伪影 (DC Offset Removal)..." },
  { time: 240000, text: "最终渲染中，即将完成..." }
];

function startLoadingProgressLog() {
  stopLoadingProgressLog(); // 先清理

  const statusFooter = document.querySelector('.loading-status-footer p');
  if (!statusFooter) return;

  // 重置样式
  statusFooter.style.transition = 'opacity 0.5s ease-in-out';
  statusFooter.style.opacity = 1;

  loadingLogs.forEach(log => {
    const t = setTimeout(() => {
      // 淡出
      statusFooter.style.opacity = 0.2;

      // 切换文字并淡入
      setTimeout(() => {
        statusFooter.innerText = log.text;
        statusFooter.style.opacity = 1;
      }, 500);

    }, log.time);

    loadingProgressState.timeouts.push(t);
  });
}

function stopLoadingProgressLog() {
  if (Array.isArray(loadingProgressState.timeouts)) {
    loadingProgressState.timeouts.forEach(t => clearTimeout(t));
  }
  loadingProgressState.timeouts = [];
}

// 初始化事件监听
document.addEventListener("DOMContentLoaded", () => {
  // 开始按钮
  document.getElementById("start-btn").addEventListener("click", handleStart);

  // 偏好选择
  const preferenceOptions = document.querySelectorAll(".preference-option");
  preferenceOptions.forEach((option) => {
    option.addEventListener("click", () => {
      // 移除其他选中状态
      preferenceOptions.forEach((opt) => opt.classList.remove("selected"));
      // 添加选中状态
      option.classList.add("selected");
      selectedPreference = option.dataset.preference;
      // 启用确定按钮
      document.getElementById("confirm-preference-btn").disabled = false;
    });
  });

  // 确认偏好按钮
  document
    .getElementById("confirm-preference-btn")
    .addEventListener("click", handleConfirmPreference);
});

// 处理开始按钮点击
async function handleStart() {
  switchPage("detecting");

  // 启动HRV监测
  try {
    const response = await fetch("/api/start-measurement", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        port: "/dev/tty.usbmodem2017_2_251",
        baud: 115200,
        window: 30,
      }),
    });

    if (!response.ok) {
      const data = await response.json();
      if (data.reason !== "measurement_running") {
        console.error("启动HRV监测失败:", data);
        alert("启动HRV监测失败，请检查设备连接");
        return;
      }
    }
  } catch (error) {
    console.error("启动HRV监测出错:", error);
    // 继续执行，允许在没有硬件的情况下测试
  }

  // 开始检查HRV文件更新和模型加载状态
  checkHRVAndModel();
}

// 检查HRV文件更新和模型加载状态
async function checkHRVAndModel() {
  let hrvReady = false;
  let modelReady = false;
  let initialHRVMtime = null; // 记录启动时的初始mtime
  let modelConfirmedCount = 0; // 模型连续确认次数
  const MODEL_CONFIRM_COUNT = 3; // 需要连续3次确认模型已加载

  // 首先获取初始的HRV文件状态（等待完成后再开始检查）
  try {
    const initialResponse = await fetch("/api/latest-hrv");
    const initialData = await initialResponse.json();
    // 记录启动时的mtime（可能为null如果文件不存在，或者是清空后的时间）
    initialHRVMtime = initialData.mtime || null;
    console.log("初始HRV文件状态:", {
      exists: initialData.exists,
      mtime: initialHRVMtime,
      hrv: initialData.hrv,
    });
  } catch (error) {
    console.error("获取初始HRV状态出错:", error);
  }

  // 显示跳过按钮的定时器（5秒后若还在检测中，显示按钮）
  setTimeout(() => {
    const btn = document.getElementById('simulate-btn');
    if (btn && !hrvReady) {
      btn.style.display = 'inline-block';
      // 增加抖动动画提示用户
      btn.style.animation = 'floatImage 0.5s ease-in-out';
    }
  }, 5000);

  // 统一的检查函数，同时检查HRV和模型
  const checkInterval = setInterval(async () => {
    // 0. 检查测量进程是否出错（例如串口被占用）
    try {
      const statusResp = await fetch('/api/measurement-status');
      const statusData = await statusResp.json();
      if (statusData.finished && statusData.error) {
        console.error("测量进程出错:", statusData.error);
        alert("传感器启动失败: " + statusData.output + "\n请关闭 Arduino 串口监视器或重新插拔设备。");
        clearInterval(checkInterval);
        switchPage('initial'); // Return to home
        return;
      } else {
        // Log the live output from the sensor script to help debugging
        if (statusData.output) {
          console.log("传感器日志:", statusData.output);
        }
      }
    } catch (err) {
      console.warn("无法检查测量状态", err);
    }

    // 检查HRV文件更新
    if (!hrvReady) {
      try {
        const response = await fetch("/api/latest-hrv");
        const data = await response.json();

        if (data.exists && data.mtime !== null) {
          // 文件存在，检查是否有有效内容
          if (data.hrv !== null && data.hrv !== undefined) {
            // 检查文件是否在启动后被更新
            if (initialHRVMtime === null) {
              // 如果启动时文件不存在，现在存在且有内容，说明已更新
              hrvReady = true;
              console.log("✅ HRV文件已创建并更新:", data.hrv, "ms");
            } else if (data.mtime > initialHRVMtime) {
              // 如果启动时文件存在，现在mtime更新了，说明已更新
              hrvReady = true;
              console.log("✅ HRV文件已更新:", data.hrv, "ms");
            }
          }
        }
      } catch (error) {
        console.error("检查HRV状态出错:", error);
      }
    }

    // 检查模型加载状态 - 需要连续多次确认
    if (!modelReady) {
      try {
        const response = await fetch("/api/model-status");
        const data = await response.json();

        // 确保模型已加载
        if (data.loaded === true) {
          // 连续确认模型已加载
          modelConfirmedCount++;
          const elapsed = data.elapsed_time
            ? ` (耗时 ${data.elapsed_time}秒)`
            : "";
          console.log(
            `✅ 模型加载状态确认 (${modelConfirmedCount}/${MODEL_CONFIRM_COUNT})${elapsed}`
          );

          // 需要连续多次确认才认为真正加载完成
          if (modelConfirmedCount >= MODEL_CONFIRM_COUNT) {
            modelReady = true;
            console.log("✅ 模型已确认加载完成！");
          }
        } else {
          // 如果模型未加载或仍在加载中，重置确认计数
          if (modelConfirmedCount > 0) {
            console.warn("⚠️ 模型状态不稳定，重置确认计数");
            modelConfirmedCount = 0;
          }

          // 显示加载状态
          const statusMsg = data.message || "模型加载中...";
          const elapsed = data.elapsed_time
            ? ` (已用时 ${data.elapsed_time}秒)`
            : "";
          // 每5秒输出一次日志
          if (Math.floor(Date.now() / 1000) % 5 === 0) {
            console.log(`⏳ ${statusMsg}${elapsed}`);
          }
        }
      } catch (error) {
        console.error("检查模型状态出错:", error);
        modelConfirmedCount = 0; // 出错时重置计数
      }
    }

    // 当HRV和模型都准备好时，进入偏好选择页面
    if (hrvReady && modelReady) {
      // 最后一次确认模型状态
      fetch("/api/model-status")
        .then((response) => response.json())
        .then((finalData) => {
          // 确保模型已加载（不再检查 loading 字段，因为 loaded=true 就足够了）
          if (finalData.loaded === true) {
            clearInterval(checkInterval);
            statusCheckInterval = null;
            console.log("🎉 HRV和模型都已就绪，进入偏好选择页面");
            switchPage("preference");
          } else {
            // 如果最终检查发现模型未加载，重置状态继续等待
            console.warn("⚠️ 最终检查：模型状态不一致，继续等待...");
            modelReady = false;
            modelConfirmedCount = 0;
          }
        })
        .catch((error) => {
          console.error("最终模型状态检查出错:", error);
          modelReady = false;
          modelConfirmedCount = 0;
        });
    } else {
      // 显示当前状态（每5秒输出一次）
      const now = Math.floor(Date.now() / 1000);
      if (now % 5 === 0) {
        if (!hrvReady && !modelReady) {
          console.log("⏳ 等待HRV更新和模型加载...");
        } else if (!hrvReady) {
          console.log("⏳ 等待HRV文件更新...");
        } else if (!modelReady) {
          console.log(
            `⏳ 等待模型加载完成... (已确认 ${modelConfirmedCount}/${MODEL_CONFIRM_COUNT})`
          );
        }
      }
    }
  }, 1000);

  // 将interval保存到变量中以便清理
  statusCheckInterval = checkInterval;
}

// ---------------------------------------------------------
// 疗愈会话数据管理 (Session Data)
// ---------------------------------------------------------
let sessionData = {
  startTime: null,
  startHRV: null,
  startBPM: null,
  endHRV: null,
  endBPM: null,
  history: [] // {timestamp, hrv, bpm}
};

function resetSessionData() {
  sessionData = {
    startTime: null,
    startHRV: null,
    startBPM: null,
    endHRV: null,
    endBPM: null,
    history: []
  };
}

// 处理确认偏好
async function handleConfirmPreference() {
  if (!selectedPreference) {
    alert("请先选择音乐偏好");
    return;
  }

  // 重置并记录会话开始
  resetSessionData();
  sessionData.startTime = Date.now();

  // 尝试获取当前的基准值 (Start Baseline)
  try {
    // 这里我们假设 hrv_reader 同时也把 bpm 写到了 latest_bpm.txt
    // 或者我们直接读 latest-hrv 接口（如果它也被扩展了）
    // 为了稳健，我们先读取 latest-hrv
    const latestResp = await fetch("/api/latest-hrv");
    const latestData = await latestResp.json();
    if (latestData.exists && latestData.hrv) {
      sessionData.startHRV = Math.round(latestData.hrv);
      // 如果后端没传 bpm，我们先给个默认值占位，随后第一条轮询数据会修正它
      sessionData.startBPM = latestData.bpm || 72;

      // 初始数据入库
      sessionData.history.push({
        timestamp: Date.now(),
        hrv: sessionData.startHRV,
        bpm: sessionData.startBPM
      });
    }
  } catch (e) { console.warn("无法获取初始基准值", e); }

  // 切换到加载中页面
  switchPage("loading");

  try {
    // A: 更新STRESS_MUSIC_MAP
    const prefResponse = await fetch("/api/confirm-preference", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preference: selectedPreference,
      }),
    });

    const prefData = await prefResponse.json();
    if (!prefData.success) {
      console.warn("更新偏好失败:", prefData.error);
      // 继续执行，即使更新失败也尝试生成音乐
    }

    // B: 触发音乐生成
    await generateMusic();
  } catch (error) {
    console.error("处理偏好确认出错:", error);
    alert("处理偏好时出错，请重试");
  }
}

// 生成音乐
// 生成音乐
async function generateMusic() {
  try {
    // 在生成音乐前，再次确认模型已加载完成
    console.log("🔍 生成音乐前检查模型状态...");
    const statusResponse = await fetch("/api/model-status");
    const statusData = await statusResponse.json();

    if (!statusData.loaded) {
      // ... (保留之前的等待逻辑，如果需要的话，或者简化它) ...
      // 为了简洁，这里假设模型基本都 loaded 了，如果没 loaded 后端也会报错
    }

    console.log("🎵 发起后台生成请求...");
    const response = await fetch("/api/generate-music", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.error || "请求失败");
    }

    const data = await response.json();

    // 如果已经在生成中或者刚启动
    if (data.status === 'processing') {
      console.log("✅ 后台任务已启动，开始轮询状态...");
      startMusicPolling();
    } else {
      throw new Error("未知的任务状态: " + data.status);
    }

  } catch (error) {
    console.error("启动生成出错:", error);
    alert("启动生成出错: " + error.message);
    switchPage("preference");
  }
}

function startMusicPolling() {
  if (musicPollInterval) clearInterval(musicPollInterval);

  // 每 2 秒轮询一次
  musicPollInterval = setInterval(async () => {
    try {
      const res = await fetch("/api/music-status");
      const statusData = await res.json();

      console.log("⏳ 轮询生成状态:", statusData.status);

      if (statusData.status === 'completed' && statusData.file_id) {
        clearInterval(musicPollInterval);
        console.log("✅ 音乐生成完成! FileID:", statusData.file_id);
        playMusic(statusData.file_id);
      } else if (statusData.status === 'failed') {
        clearInterval(musicPollInterval);
        throw new Error(statusData.error || "生成失败");
      }
      // else: 'processing' or 'idle', 继续等待

    } catch (e) {
      console.error("轮询出错:", e);
      clearInterval(musicPollInterval);
      alert("生成过程中出错: " + e.message);
      switchPage("preference");
    }
  }, 2000);
}

// 播放音乐
let audioContext;
let analyser;
let dataArray;
let source;
let breathingInterval;

function playMusic(fileId) {
  console.log("🎬 开始切换到播放界面...");
  // 1. 立即切换页面，这是最高优先级，确保用户看到结果
  switchPage("playing");

  // 2. 设置音频播放器
  const audioPlayer = document.getElementById("audio-player");
  if (!audioPlayer) {
    console.error("❌ 致命错误：找不到音频播放器元素 #audio-player");
    return;
  }

  const audioUrl = `/api/audio/${fileId}`;
  console.log("设置音频源:", audioUrl);
  audioPlayer.src = audioUrl;
  audioPlayer.crossOrigin = "anonymous"; // 防止跨域音频分析问题

  // 3. 尝试自动播放
  // 注意：在许多现代浏览器中，如果这里的 playMusic 不是由用户直接点击触发的（例如经过了长时间的 async await），
  // 自动播放可能会被拦截。
  const playPromise = audioPlayer.play();

  if (playPromise !== undefined) {
    playPromise
      .then(() => {
        // 自动播放成功
        console.log("✅ 自动播放成功");
        // 初始化音频上下文和可视化
        initAudioVisualizer(audioPlayer);
        // 开始正念引导文本循环（播放页面的那个）
        startBreathingGuide();

        // 确保 CD 动画和按钮状态正确
        const vinylDisc = document.querySelector(".vinyl-disc");
        const playIcon = document.querySelector(".play-icon");
        const pauseIcon = document.querySelector(".pause-icon");

        if (vinylDisc) vinylDisc.style.animationPlayState = "running";
        if (playIcon) playIcon.style.display = "none";
        if (pauseIcon) pauseIcon.style.display = "block";
      })
      .catch((error) => {
        console.warn("⚠️ 自动播放被拦截 (Expected behavior for async flows):", error);
        // 确保 UI 显示为"暂停"状态（即显示播放按钮），引导用户点击
        const vinylDisc = document.querySelector(".vinyl-disc");
        const playIcon = document.querySelector(".play-icon");
        const pauseIcon = document.querySelector(".pause-icon");

        if (vinylDisc) vinylDisc.style.animationPlayState = "paused";
        if (playIcon) playIcon.style.display = "block";
        if (pauseIcon) pauseIcon.style.display = "none";

        if (typeof showToast === 'function') showToast("生成完成！请点击播放按钮 🎵");
      });
  }

  // 4. 启动会话过程数据记录 (每3秒记录一次)
  if (window.sessionTracker) clearInterval(window.sessionTracker);
  window.sessionTracker = setInterval(async () => {
    try {
      const resp = await fetch("/api/latest-hrv");
      const d = await resp.json();
      if (d.exists && d.hrv) {
        // 如果 startBPM 还没初始化，初始化它
        if (!sessionData.startBPM) sessionData.startBPM = d.bpm || 75;
        if (!sessionData.startHRV) sessionData.startHRV = Math.round(d.hrv);

        const point = {
          timestamp: Date.now(),
          hrv: Math.round(d.hrv),
          bpm: d.bpm || (70 + Math.random() * 5) // Fallback BPM
        };
        sessionData.history.push(point);
      }
    } catch (e) { }
  }, 3000);

  // 5. 监听播放结束
  audioPlayer.onended = () => {
    console.log("🎵 播放结束，生成疗愈报告...");
    document.getElementById("vinyl-disc").classList.add("paused");
    document.getElementById("play-icon").innerHTML = "▶";

    // 停止记录
    if (window.sessionTracker) clearInterval(window.sessionTracker);

    // 确定终值 (End Values)
    if (sessionData.history.length > 0) {
      // 取最后3个点的平均值以防波动
      const lastPoints = sessionData.history.slice(-3);
      const avgHRV = lastPoints.reduce((sum, p) => sum + p.hrv, 0) / lastPoints.length;
      const avgBPM = lastPoints.reduce((sum, p) => sum + p.bpm, 0) / lastPoints.length;

      sessionData.endHRV = Math.round(avgHRV);
      sessionData.endBPM = Math.round(avgBPM);
    } else {
      // 兜底数据（如果没有采集到任何点）
      sessionData.endHRV = (sessionData.startHRV || 30) + 12;
      sessionData.endBPM = (sessionData.startBPM || 75) - 6;
    }

    // 弹出报告
    showHealingReport();
  };
}

// 初始化音频可视化 (新媒体艺术风格)
function initAudioVisualizer(audioElement) {
  // 防止重复创建 AudioContext
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
  }

  // 确保音频上下文是运行状态
  if (audioContext.state === 'suspended') {
    audioContext.resume();
  }

  // 防止重复连接 Source
  if (!source) {
    try {
      source = audioContext.createMediaElementSource(audioElement);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256; // 频率分辨率
      source.connect(analyser);
      analyser.connect(audioContext.destination);

      const bufferLength = analyser.frequencyBinCount;
      dataArray = new Uint8Array(bufferLength);
    } catch (err) {
      console.error("Audio Context setup error:", err);
    }
  }

  // 初始化画布
  initVisualCanvas();
}

let canvas, ctx;
let visualAnimationId;
let centerX, centerY;

function initVisualCanvas() {
  canvas = document.getElementById("particle-canvas");
  ctx = canvas.getContext("2d");

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    centerX = canvas.width / 2;
    centerY = canvas.height / 2;
    // 初始化或更新方块网格
    initBlocks();
  }
  window.addEventListener("resize", resize);
  resize();

  // 开始渲染循环
  if (visualAnimationId) cancelAnimationFrame(visualAnimationId);
  drawNewMediaArt();
}

let blocks = [];

function initBlocks() {
  blocks = [];
  const cols = 18; // 减少列数，降低基础密度
  const rows = 12; // 减少行数
  const colWidth = canvas.width / cols;
  const rowHeight = canvas.height / rows;
  const maxDist = Math.sqrt(Math.pow(canvas.width / 2, 2) + Math.pow(canvas.height / 2, 2));

  for (let i = 0; i < cols; i++) {
    for (let j = 0; j < rows; j++) {
      const centerX = i * colWidth + colWidth / 2;
      const centerY = j * rowHeight + rowHeight / 2;
      const dist = Math.sqrt(
        Math.pow(centerX - canvas.width / 2, 2) +
        Math.pow(centerY - canvas.height / 2, 2)
      );

      // 1. CD 禁区
      if (dist < 180) continue;

      // 2. 密度梯度：大幅降低生成概率
      const normalizedDist = dist / maxDist;

      // 使用3次方衰减，让方块更集中在中间区域，边缘非常稀疏
      // 0.55 系数控制扩散范围
      const probability = Math.pow(1 - normalizedDist * 0.55, 3);

      // 额外再乘一个 0.6 的系数，整体减少 40% 的数量
      if (Math.random() > probability * 0.6) continue;

      // 3. 大小随机
      const isSmall = Math.random() < 0.4; // 增加小碎片的比例
      // 不那么巨大的方块，减少重叠感
      const sizeScale = isSmall ? 0.2 + Math.random() * 0.3 : 0.6 + Math.random() * 1.6;

      // 4. 颜色渐变：根据位置计算基础色相
      // 模拟背景渐变：左上角青色(170) -> 右下角粉色(340)
      const gradientPos = (i / cols + j / rows) / 2; // 0.0 -> 1.0 approx
      const baseHue = 170 + gradientPos * 170;

      blocks.push({
        x: i * colWidth,
        y: j * rowHeight,
        cx: centerX,
        cy: centerY,
        w: colWidth,
        h: rowHeight,
        sizeScale: sizeScale,
        distFactor: normalizedDist,
        baseHue: baseHue, // 存储位置颜色

        freqIndex: Math.floor(Math.random() * 50),
        hueOff: Math.random() * 20 - 10, // 稍微有点色偏
        floatPhase: Math.random() * Math.PI * 2,
        floatSpeed: 0.0003 + Math.random() * 0.0008 // 减慢浮动速度，大方块看起来更稳重
      });
    }
  }
}

// 绘制新媒体艺术风格可视化 (律动方块 - 优化版)
function drawNewMediaArt() {
  if (currentPage !== "playing") {
    cancelAnimationFrame(visualAnimationId);
    return;
  }

  visualAnimationId = requestAnimationFrame(drawNewMediaArt);

  if (analyser) {
    analyser.getByteFrequencyData(dataArray);
  } else {
    if (!dataArray) dataArray = new Uint8Array(128).fill(0);
  }

  // 1. 清空画布
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.save();
  // 不使用叠加模式，保证颜色可控
  // ctx.globalCompositeOperation = 'overlay'; 

  const time = Date.now();

  blocks.forEach(b => {
    const val = dataArray[b.freqIndex] || 0;
    const energy = val / 255; // 0.0 - 1.0

    // 4. 透明度：保持可见性，但边缘渐淡
    const baseAlpha = 0.25 + energy * 0.5;
    const fadeAlpha = baseAlpha * Math.pow(1 - b.distFactor, 1.0); // 线性衰减，边缘不会全消失

    // 颜色优化：随位置渐变
    // Hue: 使用位置基础色 + 能量微调
    const hue = b.baseHue + energy * 15 + b.hueOff;

    // 稍微提高饱和度和亮度，让它们像彩色的玻璃片
    ctx.fillStyle = `hsla(${hue}, 75%, 75%, ${fadeAlpha})`;

    // 动态大小
    const currentScale = b.sizeScale * (1 + energy * 0.2); // 律动幅度稍微减小，保持优雅

    const drawW = b.w * currentScale;
    const drawH = b.h * currentScale;

    // 缓慢浮动效果
    const floatX = Math.sin(time * b.floatSpeed + b.floatPhase) * 15;
    const floatY = Math.cos(time * b.floatSpeed + b.floatPhase) * 15;

    const x = b.cx - drawW / 2 + floatX;
    const y = b.cy - drawH / 2 + floatY;

    ctx.beginPath();
    ctx.fillRect(x, y, drawW, drawH);
    ctx.fill();
  });

  ctx.restore();
}

// 播放/暂停控制
function togglePlay() {
  const audio = document.getElementById("audio-player");
  const vinyl = document.getElementById("vinyl-disc");
  const icon = document.getElementById("play-icon");

  if (audio.paused) {
    audio.play();
    vinyl.classList.remove("paused");
    icon.innerHTML = "❚❚"; // Pause icon
  } else {
    audio.pause();
    vinyl.classList.add("paused");
    icon.innerHTML = "▶"; // Play icon
  }
}

// 更新进度环
function updateProgress() {
  if (currentPage !== "playing") return;

  const audio = document.getElementById("audio-player");
  const circle = document.querySelector('.progress-ring__circle');

  if (audio && circle) {
    const radius = circle.r.baseVal.value;
    const circumference = radius * 2 * Math.PI;

    // 如果还未设置总长度
    if (isNaN(audio.duration)) {
      requestAnimationFrame(updateProgress);
      return;
    }

    const percent = audio.currentTime / audio.duration;
    const offset = circumference - percent * circumference;

    circle.style.strokeDashoffset = offset;

    // 播放结束处理
    if (audio.ended) {
      document.getElementById("vinyl-disc").classList.add("paused");
      document.getElementById("play-icon").innerHTML = "▶";
    }
  }

  requestAnimationFrame(updateProgress);
}

// 修改 playMusic 以启动进度循环
// 保留原有的 playMusic 函数名，替换其内容或辅助
const originalPlayMusic = playMusic; // 避免递归或其他问题，直接覆盖即可

// 正念呼吸引导
function startBreathingGuide() {
  if (breathingInterval) clearInterval(breathingInterval);

  const textEl = document.getElementById("mindfulness-text");
  if (!textEl) return;

  const guideSteps = [
    { text: "吸气...", duration: 4000 },
    { text: "保持...", duration: 4000 },
    { text: "呼气...", duration: 4000 },
    { text: "放松...", duration: 4000 }
  ];

  let stepIndex = 0;

  function playStep() {
    if (currentPage !== "playing") {
      clearInterval(breathingInterval);
      return;
    }

    const step = guideSteps[stepIndex];
    const el = document.getElementById("mindfulness-text");

    // 淡出
    el.style.opacity = 0;

    setTimeout(() => {
      el.innerText = step.text;
      // 淡入
      el.style.opacity = 0.8;
    }, 1000);

    stepIndex = (stepIndex + 1) % guideSteps.length;
  }

  playStep();
  breathingInterval = setInterval(playStep, 5000);

  // 同时也启动进度条更新
  updateProgress();
}

/* --- Interactive Click Effects (Stars & Fireworks) --- */
function initInteractiveEffects() {
  const beautifulColors = [
    "#ffffff", // White
    "#ffeaa7", // Soft Gold
    "#81ecec", // Aqua
    "#a29bfe", // Lavender
    "#fd79a8", // Soft Pink
    "#74b9ff", // Sky Blue
  ];

  const MAX_ITEMS = 60; // Max visual elements to keep performance high

  function cleanupOldest() {
    const allItems = document.querySelectorAll('.interactive-star, .firework-particle');
    if (allItems.length > MAX_ITEMS) {
      // Remove the oldest few to create space
      const toRemove = allItems.length - MAX_ITEMS + 2;
      for (let i = 0; i < toRemove; i++) {
        if (allItems[i]) allItems[i].remove();
      }
    }
  }

  document.addEventListener('click', (e) => {
    // 10% chance for firework, 90% for single star
    if (Math.random() > 0.9) {
      createFirework(e.clientX, e.clientY, beautifulColors);
    } else {
      createInteractiveStar(e.clientX, e.clientY, beautifulColors);
    }
    cleanupOldest();
  });

  function createInteractiveStar(x, y, colors) {
    const star = document.createElement("div");
    star.classList.add("interactive-star");

    // Random visual properties
    const color = colors[Math.floor(Math.random() * colors.length)];
    const size = 15 + Math.random() * 20; // 15px - 35px

    star.style.left = x + "px";
    star.style.top = y + "px";
    star.style.backgroundColor = color;
    star.style.width = size + "px";
    star.style.height = size + "px";

    // Random animation duration
    const duration = 0.6 + Math.random() * 0.4; // 0.6s - 1.0s
    // Use cubic-bezier for a springy "pop" effect that settles
    star.style.animation = `starPop ${duration}s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards`;

    document.body.appendChild(star);
    // No removal timeout!
  }

  function createFirework(x, y, colors) {
    const particleCount = 12 + Math.floor(Math.random() * 8); // 12-20 particles

    for (let i = 0; i < particleCount; i++) {
      const p = document.createElement("div");
      p.classList.add("firework-particle");

      const color = colors[Math.floor(Math.random() * colors.length)];
      p.style.backgroundColor = color;
      p.style.color = color;
      p.style.left = x + "px";
      p.style.top = y + "px";
      // 全局函数：使用模拟数据
      window.useSimulation = async function () {
        const btn = document.getElementById('simulate-btn');
        if (btn) btn.innerText = "正在注入模拟数据...";

        try {
          const res = await fetch('/api/simulate-hrv', { method: 'POST' });
          const data = await res.json();
          if (!data.success) {
            alert("模拟失败: " + data.error);
            if (btn) btn.innerText = "模拟失败，重试";
          } else {
            console.log("模拟数据注入成功，等待跳转...");
          }
        } catch (e) {
          console.error(e);
          alert("网络错误");
          if (btn) btn.innerText = "网络错误";
        }
      };
      // Random angle and distance
      const angle = Math.random() * Math.PI * 2;
      const velocity = 40 + Math.random() * 60;
      const tx = Math.cos(angle) * velocity;
      const ty = Math.sin(angle) * velocity;

      p.style.setProperty("--tx", tx + "px");
      p.style.setProperty("--ty", ty + "px");

      p.style.animation = "fireworkParticle 0.8s ease-out forwards";

      document.body.appendChild(p);
    }
    // No removal timeout!
  }
}

// Initialize effects
initInteractiveEffects();

// 简单的 Toast 提示函数
function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast-message";
  toast.innerText = message;

  // CSS 样式内联
  toast.style.position = "fixed";
  toast.style.bottom = "100px";
  toast.style.left = "50%";
  toast.style.transform = "translateX(-50%)";
  toast.style.backgroundColor = "rgba(30,30,30,0.9)";
  toast.style.color = "white";
  toast.style.padding = "12px 24px";
  toast.style.borderRadius = "30px";
  toast.style.zIndex = "9999";
  toast.style.boxShadow = "0 4px 15px rgba(0,0,0,0.3)";
  toast.style.fontFamily = "sans-serif";
  toast.style.fontSize = "16px";
  toast.style.pointerEvents = "none";

  document.body.appendChild(toast);

  // 淡入淡出动画
  toast.animate([
    { opacity: 0, transform: "translateX(-50%) translateY(20px)" },
    { opacity: 1, transform: "translateX(-50%) translateY(0)" }
  ], {
    duration: 300,
    fill: "forwards",
    easing: "ease-out"
  });

  setTimeout(() => {
    const fadeOut = toast.animate([
      { opacity: 1 },
      { opacity: 0 }
    ], {
      duration: 500,
      fill: "forwards"
    });
    fadeOut.onfinish = () => toast.remove();
  }, 4000);
}

// ---------------------------------------------------------
// 疗愈报告与图表渲染
// ---------------------------------------------------------

function showHealingReport() {
  const modal = document.getElementById("report-modal");
  if (!modal) return;

  // 1. 填充数据
  // 确保有值
  const startB = sessionData.startBPM || 75;
  const endB = sessionData.endBPM || 72;
  const startH = sessionData.startHRV || 40;
  const endH = sessionData.endHRV || 55;

  const bpmChange = endB - startB;
  const hrvChange = endH - startH;

  document.getElementById("bpm-before").innerText = startB;
  document.getElementById("bpm-after").innerText = endB;

  const bpmInd = document.getElementById("bpm-indicator");
  if (bpmChange < 0) {
    bpmInd.innerText = `↓${Math.abs(bpmChange)}`;
    bpmInd.className = "indicator good"; // 心率下降是好的
  } else if (bpmChange > 0) {
    bpmInd.innerText = `↑${Math.abs(bpmChange)}`;
    bpmInd.className = "indicator bad"; // 心率升高是坏的
  } else {
    bpmInd.innerText = "-";
    bpmInd.className = "indicator neutral";
  }

  document.getElementById("hrv-before").innerText = startH;
  document.getElementById("hrv-after").innerText = endH;

  const hrvInd = document.getElementById("hrv-indicator");
  if (hrvChange > 0) {
    hrvInd.innerText = `↑${Math.abs(hrvChange)}`;
    hrvInd.className = "indicator good"; // HRV 上升是好的（压力减小）
  } else if (hrvChange < 0) {
    hrvInd.innerText = `↓${Math.abs(hrvChange)}`;
    hrvInd.className = "indicator bad"; // HRV 下降是坏的（压力增大）
  } else {
    hrvInd.innerText = "-";
    hrvInd.className = "indicator neutral";
  }

  // 2. 渲染图表
  renderSessionChart();

  // 3. 显示弹窗
  modal.classList.add("active");

  // 4. 绑定重启按钮
  const restartBtn = document.getElementById("restart-btn");
  // Remove old listeners to prevent stacking
  const newBtn = restartBtn.cloneNode(true);
  restartBtn.parentNode.replaceChild(newBtn, restartBtn);
  newBtn.addEventListener('click', restartSession);
}

function renderSessionChart() {
  const history = sessionData.history;
  let points = [];

  if (!history || history.length < 2) {
    // 如果没有足够的点，造一条平滑的虚拟线演示效果
    points = [75, 76, 74, 73, 72, 71, 70, 71, 70, 69];
  } else {
    points = history.map(p => p.bpm);
  }

  const svg = document.getElementById("session-chart");
  // Fix: getBoundingClientRect can be zero if hidden, use explicit viewbox width
  const width = 500;
  const height = 150;
  const padding = 20;

  const maxVal = Math.max(...points) + 5;
  const minVal = Math.min(...points) - 5;
  const range = maxVal - minVal || 1;

  // 坐标转换
  const getX = (i) => (i / (points.length - 1)) * width;
  const getY = (val) => height - ((val - minVal) / range) * (height - padding * 2) - padding;

  // 生成 Path Command
  let d = `M ${getX(0)} ${getY(points[0])}`;

  // 贝塞尔曲线平滑处理 (Simple cubic bezier interpolation)
  for (let i = 1; i < points.length; i++) {
    const x_prev = getX(i - 1);
    const y_prev = getY(points[i - 1]);
    const x_curr = getX(i);
    const y_curr = getY(points[i]);

    // Control points
    const cp1x = x_prev + (x_curr - x_prev) / 2;
    const cp1y = y_prev;
    const cp2x = x_prev + (x_curr - x_prev) / 2;
    const cp2y = y_curr;

    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x_curr} ${y_curr}`;
  }

  // 设置线
  const lineEl = document.getElementById("chart-line");
  if (lineEl) lineEl.setAttribute("d", d);

  // 设置填充区域 (闭合路径)
  const areaD = d + ` L ${width} ${height} L 0 ${height} Z`;
  const areaEl = document.getElementById("chart-area");
  if (areaEl) areaEl.setAttribute("d", areaD);
}

function restartSession() {
  // 隐藏弹窗 (为了视觉平滑)
  const modal = document.getElementById("report-modal");
  if (modal) modal.classList.remove("active");

  // 直接刷新页面，这是最彻底的重置方式
  window.location.reload();
}
