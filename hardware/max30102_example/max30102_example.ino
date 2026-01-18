#include "MAX30105.h"
#include <Wire.h>
#include <heartRate.h>

MAX30105 particleSensor;

const byte RATE_SIZE = 4;
byte rates[RATE_SIZE];
byte rateSpot = 0;
long lastBeat = 0;
float beatsPerMinute;
int beatAvg;

unsigned long lastDataTime = 0;
const unsigned long TIMEOUT = 10000; // 10秒无数据时重启

void setup() {
  Serial.begin(115200);
  Serial.println("MAX30102心率监测器启动中...");

  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("传感器初始化失败！检查连接。");
    while (1) {
      delay(1000);
    }
  }

  // 重新配置传感器，使用更保守的设置
  particleSensor.setup();

  // 降低LED亮度，防止饱和
  particleSensor.setPulseAmplitudeRed(0x16); // 降低亮度
  particleSensor.setPulseAmplitudeGreen(0);  // 关闭绿光

  Serial.println("传感器就绪。请轻轻将手指放在传感器上...");
  Serial.println("提示：手指不要用力按压，保持稳定接触");

  lastDataTime = millis();
}

void loop() {
  long irValue = particleSensor.getIR();
  unsigned long currentTime = millis();

  // 检查数据超时
  if (currentTime - lastDataTime > TIMEOUT) {
    Serial.println("检测到数据超时，重新启动传感器...");
    restartSensor();
    lastDataTime = currentTime;
    return;
  }

  // 检查传感器是否饱和
  if (irValue >= 262000) {
    Serial.println("警告：传感器饱和，请调整手指位置");
    delay(100);
    return;
  }

  // 检查手指是否放置
  if (irValue < 50000) {
    Serial.println("请将手指轻轻放在传感器上...");
    delay(500);
    return;
  }

  // 正常的心率检测
  bool beatDetected = checkForBeat(irValue);

  if (beatDetected) {
    long delta = millis() - lastBeat;
    lastBeat = millis();

    beatsPerMinute = 60 / (delta / 1000.0);

    if (beatsPerMinute > 30 && beatsPerMinute < 200) { // 更宽松的心率范围
      rates[rateSpot++] = beatsPerMinute;
      rateSpot %= RATE_SIZE;

      beatAvg = 0;
      for (byte x = 0; x < RATE_SIZE; x++) {
        beatAvg += rates[x];
      }
      beatAvg /= RATE_SIZE;

      // 输出数据
      Serial.print("IR=");
      Serial.print(irValue);
      Serial.print(", BPM=");
      Serial.print(beatsPerMinute);
      Serial.print(", 平均BPM=");
      Serial.print(beatAvg);
      Serial.println();

      lastDataTime = currentTime;
    }
  }

  delay(10); // 简短延迟
}

void restartSensor() {
  Serial.println("重新启动传感器...");

  // 重置传感器
  particleSensor.shutDown();
  delay(100);
  particleSensor.wakeUp();

  // 重新配置（使用更低的设置）
  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x12); // 更低的亮度
  particleSensor.setPulseAmplitudeGreen(0);

  Serial.println("传感器重新启动完成");
}