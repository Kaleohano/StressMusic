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

  pages[currentPage].classList.remove("active");
  pages[pageName].classList.add("active");
  currentPage = pageName;
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

  // 统一的检查函数，同时检查HRV和模型
  const checkInterval = setInterval(async () => {
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

// 处理确认偏好
async function handleConfirmPreference() {
  if (!selectedPreference) {
    alert("请先选择音乐偏好");
    return;
  }

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
async function generateMusic() {
  try {
    // 在生成音乐前，再次确认模型已加载完成
    console.log("🔍 生成音乐前检查模型状态...");
    const statusResponse = await fetch("/api/model-status");
    const statusData = await statusResponse.json();

    if (!statusData.loaded) {
      console.warn("⚠️ 模型尚未加载完成，等待中...");
      // 等待模型加载，最多等待120秒
      let waitCount = 0;
      const maxWait = 120;
      let modelLoaded = false;
      let modelConfirmedCount = 0;
      const MODEL_CONFIRM_COUNT = 3; // 需要连续3次确认

      while (!modelLoaded && waitCount < maxWait) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const checkResponse = await fetch("/api/model-status");
        const checkData = await checkResponse.json();

        if (checkData.loaded === true) {
          modelConfirmedCount++;
          console.log(
            `✅ 模型加载状态确认 (${modelConfirmedCount}/${MODEL_CONFIRM_COUNT})`
          );

          // 需要连续多次确认
          if (modelConfirmedCount >= MODEL_CONFIRM_COUNT) {
            modelLoaded = true;
            console.log("✅ 模型已确认加载完成，开始生成音乐");
            break;
          }
        } else {
          // 如果模型未加载，重置确认计数
          if (modelConfirmedCount > 0) {
            console.warn("⚠️ 模型状态不稳定，重置确认计数");
            modelConfirmedCount = 0;
          }
        }

        waitCount++;
        // 每5秒输出一次日志
        if (waitCount % 5 === 0) {
          console.log(
            `⏳ 等待模型加载... (${waitCount}/${maxWait}秒, 已确认 ${modelConfirmedCount}/${MODEL_CONFIRM_COUNT})`
          );
        }
      }

      if (!modelLoaded) {
        throw new Error(`模型加载超时（已等待${maxWait}秒），请刷新页面重试`);
      }
    }

    console.log("🎵 开始生成音乐...");
    const response = await fetch("/api/generate-music", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      const errorData = await response.json();
      const errorMsg = errorData.error || errorData.message || "音乐生成失败";
      const suggestion = errorData.suggestion || "";
      throw new Error(errorMsg + (suggestion ? "\n" + suggestion : ""));
    }

    const data = await response.json();

    if (data.success && data.file_id) {
      console.log("✅ 音乐生成成功，文件ID:", data.file_id);
      // 等待一小段时间确保文件已完全写入
      setTimeout(() => {
        playMusic(data.file_id);
      }, 500);
    } else {
      throw new Error("音乐生成失败: " + (data.message || "未知错误"));
    }
  } catch (error) {
    console.error("生成音乐出错:", error);
    alert("生成音乐时出错: " + error.message);
    // 返回加载中页面，让用户可以重试
    switchPage("loading");
  }
}

// 播放音乐
function playMusic(fileId) {
  // 切换到播放页面
  switchPage("playing");

  // 初始化粒子动画
  initParticleAnimation();

  // 设置音频播放器
  const audioPlayer = document.getElementById("audio-player");
  const audioUrl = `/api/audio/${fileId}`;
  audioPlayer.src = audioUrl;

  // 播放音频
  audioPlayer.play().catch((error) => {
    console.error("播放音频出错:", error);
    alert("播放音频时出错，请检查浏览器是否允许自动播放");
  });
}

// 粒子动画
let particleCanvas, particleCtx;
let particles = [];
let animationId = null;

function initParticleAnimation() {
  particleCanvas = document.getElementById("particle-canvas");
  particleCtx = particleCanvas.getContext("2d");

  // 设置画布大小
  function resizeCanvas() {
    particleCanvas.width = window.innerWidth;
    particleCanvas.height = window.innerHeight;
  }
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);

  // 创建粒子
  const particleCount = 100;
  particles = [];

  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: Math.random() * particleCanvas.width,
      y: Math.random() * particleCanvas.height,
      radius: Math.random() * 3 + 1,
      speedX: (Math.random() - 0.5) * 0.5,
      speedY: (Math.random() - 0.5) * 0.5,
      opacity: Math.random() * 0.5 + 0.2,
      color: `rgba(255, 255, 255, ${Math.random() * 0.5 + 0.2})`,
    });
  }

  // 开始动画
  animateParticles();
}

function animateParticles() {
  if (currentPage !== "playing") {
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
    return;
  }

  // 清空画布
  particleCtx.clearRect(0, 0, particleCanvas.width, particleCanvas.height);

  // 更新和绘制粒子
  particles.forEach((particle) => {
    // 更新位置
    particle.x += particle.speedX;
    particle.y += particle.speedY;

    // 边界检测
    if (particle.x < 0 || particle.x > particleCanvas.width) {
      particle.speedX = -particle.speedX;
    }
    if (particle.y < 0 || particle.y > particleCanvas.height) {
      particle.speedY = -particle.speedY;
    }

    // 绘制粒子
    particleCtx.beginPath();
    particleCtx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
    particleCtx.fillStyle = particle.color;
    particleCtx.fill();
  });

  // 绘制连接线
  particles.forEach((particle, i) => {
    particles.slice(i + 1).forEach((otherParticle) => {
      const dx = particle.x - otherParticle.x;
      const dy = particle.y - otherParticle.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance < 150) {
        particleCtx.beginPath();
        particleCtx.moveTo(particle.x, particle.y);
        particleCtx.lineTo(otherParticle.x, otherParticle.y);
        particleCtx.strokeStyle = `rgba(255, 255, 255, ${
          0.2 * (1 - distance / 150)
        })`;
        particleCtx.lineWidth = 0.5;
        particleCtx.stroke();
      }
    });
  });

  animationId = requestAnimationFrame(animateParticles);
}
