<template>
  <div class="lab-page-container">
    
    <!-- ========== 顶部导航 ========== -->
    <div class="page-navbar">
      <div class="brand">
        <div class="logo-icon lab-theme">
          <el-icon><Connection /></el-icon>
        </div>
        <div class="brand-text">
          <h1>HTTP 协议性能实验室</h1>
          <span class="subtitle">Go 高并发压测引擎</span>
        </div>
      </div>
      <div class="status-badge" :class="testPhaseClass">
        <span class="dot"></span>
        <span class="status-text">{{ statusLabel }}</span>
      </div>
    </div>

    <div class="main-content">
      
      <!-- ========== 阶段进度条 ========== -->
      <div class="phase-bar">
        <div 
          v-for="(phase, idx) in phases" 
          :key="phase.key"
          class="phase-step"
          :class="{ active: activePhase === idx, done: activePhase > idx }"
        >
          <div class="phase-circle">
            <el-icon v-if="activePhase > idx"><Check /></el-icon>
            <span v-else>{{ idx + 1 }}</span>
          </div>
          <div class="phase-label">{{ phase.label }}</div>
          <div v-if="idx < phases.length - 1" class="phase-line" :class="{ filled: activePhase > idx }"></div>
        </div>
      </div>

      <!-- ========== 统计卡片行 ========== -->
      <div class="stats-row">
        <div class="stat-card" :class="{ 'is-active': isRunning }">
          <div class="stat-icon-wrapper" :class="isRunning ? 'bg-blue-soft pulse-glow' : 'bg-blue-soft'">
            <el-icon class="text-blue"><Cpu /></el-icon>
          </div>
          <div class="stat-info">
            <span class="label">并发连接</span>
            <div class="value-group">
              <span class="value">{{ params.concurrency }}</span>
              <span class="unit">conn</span>
            </div>
          </div>
          <div class="stat-trend" v-if="results.speed > 0">
            <span class="trend-up">↑</span>
          </div>
        </div>
        
        <div class="stat-card" :class="{ 'is-active': isRunning }">
          <div class="stat-icon-wrapper" :class="isRunning ? 'bg-purple-soft pulse-glow' : 'bg-purple-soft'">
            <el-icon class="text-purple"><Timer /></el-icon>
          </div>
          <div class="stat-info">
            <span class="label">运行时长</span>
            <div class="value-group">
              <span class="value">{{ timerDisplay }}</span>
              <span class="unit">sec</span>
            </div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrapper" :class="results.speed > 0 ? 'bg-green-soft pulse-glow' : 'bg-gray-soft'">
            <el-icon :class="results.speed > 0 ? 'text-green' : 'text-gray'"><Odometer /></el-icon>
          </div>
          <div class="stat-info">
            <span class="label">页面吞吐量</span>
            <div class="value-group">
              <span class="value">{{ animatedSpeed }}</span>
              <span class="unit">pg/min</span>
            </div>
          </div>
          <div class="stat-trend" v-if="results.speed > 0">
            <span class="trend-up">↑</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrapper" :class="results.successRate === 100 ? 'bg-emerald-soft' : results.successRate >= 80 ? 'bg-amber-soft' : 'bg-red-soft'">
            <el-icon :class="results.successRate === 100 ? 'text-emerald' : results.successRate >= 80 ? 'text-amber' : 'text-red'"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <span class="label">请求成功率</span>
            <div class="value-group">
              <span class="value" :class="{'text-success': results.successRate === 100, 'text-warning': results.successRate < 100 && results.successRate >= 80, 'text-danger': results.successRate < 80}">{{ results.successRate }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ========== 主栅格布局 ========== -->
      <div class="grid-layout">
        <div class="left-column">
          
          <!-- ===== 压测参数卡片 ===== -->
          <el-card shadow="hover" class="control-card panel-card glass-effect">
            <template #header>
              <div class="card-header">
                <span class="header-title"><el-icon class="mr-2"><Setting /></el-icon> 压测参数配置</span>
              </div>
            </template>
            
            <div class="form-container">
              <div class="form-item">
                <div class="form-label">
                  <span class="label-text">并发连接数</span>
                  <el-tag size="small" effect="dark" :type="isRunning ? 'info' : 'primary'" round>{{ params.concurrency }}</el-tag>
                </div>
                <el-slider 
                  v-model="params.concurrency" 
                  :min="10" :max="5000" :step="10" 
                  :disabled="isRunning"
                  show-input :show-input-controls="false"
                  size="default"
                />
                <div class="slider-marks">
                  <span>10</span><span>1k</span><span>2k</span><span>3k</span><span>4k</span><span>5k</span>
                </div>
              </div>

              <div class="form-item">
                <div class="form-label">
                  <span class="label-text">测试持续时间</span>
                  <el-tag size="small" effect="dark" :type="isRunning ? 'info' : 'warning'" round>{{ params.duration }}s</el-tag>
                </div>
                <el-slider 
                  v-model="params.duration" 
                  :min="5" :max="200" :step="5" 
                  :disabled="isRunning"
                  show-input :show-input-controls="false"
                  size="default"
                />
                <div class="slider-marks">
                  <span>5s</span><span>50s</span><span>100s</span><span>150s</span><span>200s</span>
                </div>
              </div>

              <div class="action-area">
                <el-button 
                  type="primary" 
                  size="large" 
                  class="start-btn" 
                  :loading="isRunning"
                  :icon="isRunning ? undefined : Aim"
                  @click="startSimulation"
                >
                  {{ isRunning ? '压测引擎运行中...' : '开始性能压测' }}
                </el-button>
              </div>
            </div>
          </el-card>

          <!-- ===== 实时速率仪表盘 ===== -->
          <el-card shadow="hover" class="gauge-card panel-card glass-effect">
            <template #header>
              <div class="card-header">
                <span class="header-title"><el-icon class="mr-2"><TrendCharts /></el-icon> 实时速率仪表盘</span>
                <el-tag v-if="results.speed > 0" size="small" type="success" effect="dark">{{ results.speed }} pg/min</el-tag>
              </div>
            </template>
            <div class="gauge-wrapper">
              <div ref="gaugeRef" class="gauge-chart"></div>
            </div>
          </el-card>

        </div>

        <!-- ========== 右侧列 ========== -->
        <div class="right-column">

          <!-- ===== 连接活动可视化 ===== -->
          <el-card shadow="hover" class="activity-card panel-card glass-effect">
            <template #header>
              <div class="card-header">
                <span class="header-title"><el-icon class="mr-2"><Connection /></el-icon> 连接活动</span>
                <div class="header-tags">
                  <el-tag v-if="isRunning" size="small" type="warning" effect="dark" class="blink-tag">
                    ● {{ activeConnDots }} 活跃连接
                  </el-tag>
                  <el-tag v-if="results.totalRequests > 0" size="small" type="info" effect="plain">
                    总计 {{ results.totalRequests }} 请求
                  </el-tag>
                </div>
              </div>
            </template>
            <div class="activity-visual">
              <!-- 连接动画区域 -->
              <div class="conn-animation-area">
                <div class="server-node">
                  <div class="node-icon server">
                    <el-icon><Monitor /></el-icon>
                  </div>
                  <span class="node-label">目标服务器</span>
                  <span class="node-addr">{{ targetHost }}</span>
                </div>
                <div class="conn-flow">
                  <div 
                    v-for="dot in visibleDots" 
                    :key="dot.id"
                    class="conn-dot"
                    :style="{ 
                      left: dot.x + '%', 
                      top: dot.y + '%',
                      animationDelay: dot.delay + 's',
                      opacity: dot.opacity,
                      background: dot.success ? 'var(--success)' : 'var(--danger)'
                    }"
                  ></div>
                  <div class="flow-line"></div>
                </div>
                <div class="client-node">
                  <div class="node-icon client">
                    <el-icon><Cpu /></el-icon>
                  </div>
                  <span class="node-label">压测引擎</span>
                  <span class="node-addr">Go Bench ×{{ params.concurrency }}</span>
                </div>
              </div>
              <!-- 迷你统计 -->
              <div class="mini-stats">
                <div class="mini-stat-item">
                  <span class="mini-label">成功</span>
                  <span class="mini-value text-success">{{ animatedSuccess }}</span>
                </div>
                <div class="mini-stat-item">
                  <span class="mini-label">失败</span>
                  <span class="mini-value" :class="results.failedCount > 0 ? 'text-danger' : 'text-muted'">{{ results.failedCount }}</span>
                </div>
                <div class="mini-stat-item">
                  <span class="mini-label">吞吐率</span>
                  <span class="mini-value text-primary">{{ animatedSpeed }} <small>pg/min</small></span>
                </div>
                <div class="mini-stat-item">
                  <span class="mini-label">传输</span>
                  <span class="mini-value">{{ formatBytes(animatedBytes) }}/s</span>
                </div>
              </div>
            </div>
          </el-card>

          <!-- ===== 结果分析 ===== -->
          <el-card shadow="hover" class="result-card panel-card glass-effect">
            <template #header>
              <div class="card-header">
                <span class="header-title"><el-icon class="mr-2"><DataAnalysis /></el-icon> 结果分析</span>
                <el-button v-if="results.speed > 0" text type="primary" size="small" @click="exportResult">
                  <el-icon><Download /></el-icon> 导出
                </el-button>
              </div>
            </template>
            
            <div class="result-grid">
              <div class="result-metric">
                <div class="metric-header">
                  <span>数据吞吐量</span>
                  <span class="metric-value">{{ results.bytes }} <small>Bytes/sec</small></span>
                </div>
                <el-progress 
                  :percentage="Math.min((results.bytes / 5000) * 100, 100)" 
                  :format="() => ''" 
                  :color="bytesGradient"
                  striped 
                  :striped-flow="isRunning"
                  :stroke-width="18"
                  class="custom-progress"
                />
              </div>
              
              <div class="result-metric">
                <div class="metric-header">
                  <span>请求成功率</span>
                  <span class="metric-value">
                    <span class="text-success">{{ animatedSuccess }} OK</span>
                    <span class="divider">/</span>
                    <span class="text-danger">{{ results.failedCount }} Fail</span>
                  </span>
                </div>
                <el-progress 
                  :percentage="results.successRate" 
                  :status="results.successRate === 100 ? 'success' : results.successRate >= 80 ? 'warning' : 'exception'"
                  :stroke-width="18"
                  class="custom-progress"
                  :format="(p) => p + '%'"
                />
              </div>
            </div>
            
            <!-- ECharts 结果对比图 -->
            <div class="chart-wrapper">
              <div ref="chartRef" class="result-chart"></div>
            </div>
          </el-card>

          <!-- ===== 控制台日志 ===== -->
          <el-card shadow="hover" class="log-card">
            <template #header>
              <div class="card-header">
                <span class="header-title"><el-icon class="mr-2"><Memo /></el-icon> 控制台输出日志</span>
                <div class="header-actions">
                  <el-tooltip content="滚动到底部" placement="top">
                    <el-button text size="small" @click="scrollLogToBottom" :disabled="logs.length === 0">
                      <el-icon><Bottom /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-button text size="small" @click="clearLogs" :disabled="logs.length === 0">清空日志</el-button>
                </div>
              </div>
            </template>
            
            <div class="terminal-window" ref="logContainer">
              <div v-if="logs.length === 0" class="empty-log">
                <el-icon class="mb-3" size="40"><Monitor /></el-icon>
                <div class="empty-title">等待指令输入...</div>
                <div class="empty-hint">配置上方参数后点击「开始性能压测」</div>
              </div>
              <div v-for="(log, index) in logs" :key="index" class="log-line" :class="log.type">
                <span class="log-time">{{ log.time }}</span>
                <span class="log-arrow">▸</span>
                <span class="log-content">{{ log.text }}</span>
              </div>
              <div v-if="isRunning" class="log-line typing-cursor">
                <span class="log-time">{{ getCurrentTime() }}</span>
                <span class="log-arrow">▸</span>
                <span class="blink">_</span>
              </div>
            </div>
          </el-card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { 
  Connection, Cpu, Timer, Odometer, Setting, Memo, TrendCharts, 
  Aim, Check, CircleCheck, Monitor, DataAnalysis, Download, Bottom
} from '@element-plus/icons-vue'
import request from '@/utils/request'
import * as echarts from 'echarts'

// ==================== 阶段状态 ====================
const phases = [
  { key: 'idle', label: '参数配置' },
  { key: 'running', label: '压测执行中' },
  { key: 'parsing', label: '结果分析' },
  { key: 'done', label: '完成' },
]
const activePhase = ref(0)

const statusLabel = computed(() => {
  if (isRunning.value) return '压测引擎运行中'
  if (results.value.speed > 0) return '测试完成'
  return '就绪 ✓'
})

const testPhaseClass = computed(() => {
  if (isRunning.value) return 'running'
  if (results.value.speed > 0) return 'done'
  return ''
})

// ==================== 状态定义 ====================
const isRunning = ref(false)
const params = ref({
  concurrency: 600,
  duration: 10
})

const logs = ref([])
const logContainer = ref(null)
const chartRef = ref(null)
const gaugeRef = ref(null)
let chartInstance = null
let gaugeInstance = null

// 计时器
const timerValue = ref(0)
const timerIntervalId = ref(null)
const timerDisplay = computed(() => timerValue.value.toFixed(2))

// 结果数据
const results = ref({
  speed: 0,
  bytes: 0,
  successRate: 100,
  successCount: 0,
  failedCount: 0,
  totalRequests: 0,
})

// 动画数值 (从 0 递增到最终值)
const animatedSpeed = ref(0)
const animatedSuccess = ref(0)
const animatedBytes = ref(0)
let animFrameIds = new Set()

// 连接动画
const visibleDots = ref([])
const activeConnDots = ref(0)
let dotIntervalId = null
let dotIdCounter = 0

// 目标服务器地址
const targetHost = computed(() => window.location.host)

// 进度条渐变色
const bytesGradient = [
  { color: '#3b82f6', percentage: 30 },
  { color: '#8b5cf6', percentage: 60 },
  { color: '#10b981', percentage: 100 },
]

// ==================== 工具函数 ====================

function getCurrentTime() {
  const now = new Date()
  return `[${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}]`
}

function addLog(text, type = 'info') {
  let styledText = text
  let logType = 'info'
  
  if (text.includes('[✅]') || text.includes('✅')) {
    styledText = text.replace(/\[✅\]/g, '').replace(/✅/g, '').trim()
    logType = 'success'
  } else if (text.includes('[❌]') || text.includes('❌')) {
    styledText = text.replace(/\[❌\]/g, '').replace(/❌/g, '').trim()
    logType = 'error'
  } else if (text.includes('[INFO]') || text.includes('INFO')) {
    styledText = text.replace(/\[INFO\]/g, '').replace(/INFO:/g, '').trim()
    logType = 'info'
  } else if (text.includes('Speed=') || text.includes('pages/min')) {
    logType = 'highlight'
  }

  logs.value.push({
    time: getCurrentTime(),
    text: styledText || text,
    type: logType,
  })

  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

function clearLogs() {
  logs.value = []
}

function scrollLogToBottom() {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

// 格式化字节数
function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let val = bytes
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024
    i++
  }
  return val.toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

// 动画计数器 (从 0 逐步增长到目标值)
function animateCounter(targetRef, targetVal, duration = 800) {
  const start = targetRef.value
  const diff = targetVal - start
  if (diff === 0) return
  const startTime = performance.now()
  
  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1)
    // easeOutQuart
    const eased = 1 - Math.pow(1 - progress, 3)
    targetRef.value = Math.round(start + diff * eased)
    if (progress < 1) {
      const id = requestAnimationFrame(step)
      animFrameIds.add(id)
    }
  }
  const id = requestAnimationFrame(step)
  animFrameIds.add(id)
}

// 连接点动画 (压测运行时产生流动粒子)
function startDotAnimation() {
  let count = 0
  dotIntervalId = setInterval(() => {
    if (!isRunning.value) return
    count = Math.min(count + 2, 30)
    activeConnDots.value = count
    
    // 添加新的流动点
    const newDots = []
    for (let i = 0; i < 3; i++) {
      dotIdCounter++
      newDots.push({
        id: dotIdCounter,
        x: 10 + Math.random() * 20,
        y: 30 + Math.random() * 40,
        delay: Math.random() * 0.8,
        opacity: 0.5 + Math.random() * 0.5,
        success: Math.random() > 0.05,
      })
    }
    visibleDots.value = [...visibleDots.value, ...newDots].slice(-40)
  }, 200)
}

function stopDotAnimation() {
  if (dotIntervalId) {
    clearInterval(dotIntervalId)
    dotIntervalId = null
  }
  activeConnDots.value = 0
  visibleDots.value = []
}

// ==================== 解析结果 ====================
function parseBackendResult(resultText) {
  try {
    const speedMatch = resultText.match(/Speed=(\d+)\s+pages\/min/)
    const bytesMatch = resultText.match(/(\d+)\s+bytes\/sec/)
    const successMatch = resultText.match(/Requests:\s+(\d+)\s+succeeded/i) || resultText.match(/Requests:\s+(\d+)\s+succeed/i) || resultText.match(/Requests:\s+(\d+)\s+susceed/i)
    const failedMatch = resultText.match(/(\d+)\s+failed/)

    const speed = speedMatch ? parseInt(speedMatch[1]) : 0
    const bytes = bytesMatch ? parseInt(bytesMatch[1]) : 0
    const success = successMatch ? parseInt(successMatch[1]) : 0
    const failed = failedMatch ? parseInt(failedMatch[1]) : 0
    
    const total = success + failed
    const rate = total === 0 ? 0 : Math.round((success / total) * 100)

    return { speed, bytes, success, failed, rate }
  } catch (e) {
    console.error("Parse error", e)
    return null
  }
}

// ==================== ECharts 初始化 ====================

function initCharts() {
  // 结果对比柱状图
  if (chartRef.value && !chartInstance) {
    chartInstance = echarts.init(chartRef.value)
    updateResultChart()
  }
  // 速率仪表盘
  if (gaugeRef.value && !gaugeInstance) {
    gaugeInstance = echarts.init(gaugeRef.value)
    updateGaugeChart(0)
  }
}

function updateResultChart() {
  if (!chartInstance) return
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: '#334155',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    grid: {
      left: 60,
      right: 20,
      top: 20,
      bottom: 30,
    },
    xAxis: {
      type: 'category',
      data: ['页面吞吐量', '数据吞吐量', '成功请求', '失败请求'],
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#64748b', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: [
          { 
            value: results.value.speed,
            itemStyle: { 
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#3b82f6' },
                { offset: 1, color: '#1d4ed8' }
              ]),
              borderRadius: [4, 4, 0, 0],
            }
          },
          { 
            value: results.value.bytes,
            itemStyle: { 
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#10b981' },
                { offset: 1, color: '#059669' }
              ]),
              borderRadius: [4, 4, 0, 0],
            }
          },
          { 
            value: results.value.successCount,
            itemStyle: { 
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#8b5cf6' },
                { offset: 1, color: '#7c3aed' }
              ]),
              borderRadius: [4, 4, 0, 0],
            }
          },
          { 
            value: results.value.failedCount,
            itemStyle: { 
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#ef4444' },
                { offset: 1, color: '#dc2626' }
              ]),
              borderRadius: [4, 4, 0, 0],
            }
          },
        ],
        barWidth: '50%',
        animationDuration: 1000,
        animationEasing: 'cubicOut',
        label: {
          show: true,
          position: 'top',
          color: '#475569',
          fontSize: 11,
          fontWeight: 600,
          formatter: (p) => p.value > 0 ? p.value : '',
        }
      }
    ]
  }
  chartInstance.setOption(option, true)
}

function updateGaugeChart(value) {
  if (!gaugeInstance) return
  const maxVal = Math.max(value * 1.5, 50000)
  const option = {
    series: [
      {
        type: 'gauge',
        center: ['50%', '55%'],
        radius: '90%',
        startAngle: 220,
        endAngle: -40,
        min: 0,
        max: maxVal,
        splitNumber: 5,
        progress: {
          show: true,
          width: 12,
          roundCap: true,
          itemStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 1, y2: 0,
              colorStops: [
                { offset: 0, color: '#3b82f6' },
                { offset: 0.5, color: '#8b5cf6' },
                { offset: 1, color: '#10b981' },
              ]
            }
          }
        },
        pointer: {
          show: value > 0,
          length: '60%',
          width: 4,
          itemStyle: { color: '#1e293b' }
        },
        axisLine: {
          lineStyle: {
            width: 12,
            color: [[1, '#e2e8f0']]
          }
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: {
          offsetCenter: [0, '40%'],
          fontSize: 24,
          fontWeight: 700,
          color: '#0f172a',
          formatter: value > 0 ? `{value} pg/min` : '等待测试...',
        },
        title: {
          offsetCenter: [0, '65%'],
          fontSize: 12,
          color: '#94a3b8',
        },
        data: [{ value: value, name: '页面吞吐量' }]
      }
    ]
  }
  gaugeInstance.setOption(option, true)
}

function resizeCharts() {
  chartInstance?.resize()
  gaugeInstance?.resize()
}

// ==================== 生命周期 ====================
onMounted(() => {
  nextTick(() => initCharts())
  window.addEventListener('resize', resizeCharts)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCharts)
  chartInstance?.dispose()
  gaugeInstance?.dispose()
  animFrameIds.forEach(id => cancelAnimationFrame(id))
  animFrameIds.clear()
  if (timerIntervalId.value) clearInterval(timerIntervalId.value)
  if (dotIntervalId) clearInterval(dotIntervalId)
})

// ==================== 导出 ====================
function exportResult() {
  const data = {
    timestamp: new Date().toISOString(),
    params: { ...params.value },
    results: { ...results.value },
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `bench-result-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
  addLog('✅ 测试结果已导出为 JSON 文件', 'success')
}

// ==================== 核心业务逻辑 ====================

const startSimulation = async () => {
  if (isRunning.value) return
  
  // 初始化
  isRunning.value = true
  activePhase.value = 1
  timerValue.value = 0
  logs.value = []
  results.value = { speed: 0, bytes: 0, successRate: 100, successCount: 0, failedCount: 0, totalRequests: 0 }
  animatedSpeed.value = 0
  animatedSuccess.value = 0
  animatedBytes.value = 0

  // 启动连接动画
  startDotAnimation()

  const startTime = Date.now()
  timerIntervalId.value = setInterval(() => {
    timerValue.value = (Date.now() - startTime) / 1000
  }, 50)

  try {
    addLog('Go 压测引擎初始化...')
    addLog(`目标: http://${targetHost.value}/index.html`)
    addLog(`参数: 并发=${params.value.concurrency}, 时长=${params.value.duration}s`)
    addLog('正在启动 Go 压测引擎...')

    activePhase.value = 2

    const result = await request.post('/api/simulate', {
      concurrency: params.value.concurrency,
      duration: params.value.duration
    }, { timeout: 120000 })
    
    clearInterval(timerIntervalId.value)
    activePhase.value = 2

    addLog('后端响应成功 ✓')
    
    const fullOutput = result.data?.stats?.stdout || ''
    
    if (fullOutput) {
      addLog('──────── 压测引擎输出 ────────')
      const lines = fullOutput.split('\n')
      lines.forEach(line => {
        const trimmed = line.trim()
        if (trimmed) addLog(trimmed)
      })
    }

    addLog('──────── 分析报告 ────────')

    // 优先使用 API 返回的结构化数据
    const stats = result.data?.stats
    let parsed = null

    if (stats) {
      const speed = stats.throughput || 0
      const bytes = stats.bytesPerSec || 0
      const success = stats.requestCount || 0
      const failed = stats.failedCount || 0
      const total = success + failed
      const rate = total === 0 ? 0 : Math.round((success / total) * 100)

      if (speed > 0 || success > 0 || failed > 0) {
        parsed = { speed, bytes, success, failed, rate }
      }
    }

    // 结构化数据不可用时回退文本解析
    if (!parsed && fullOutput) {
      parsed = parseBackendResult(fullOutput)
    }

    if (parsed) {
      // 更新结果
      results.value.speed = parsed.speed
      results.value.bytes = parsed.bytes
      results.value.successCount = parsed.success
      results.value.failedCount = parsed.failed
      results.value.successRate = parsed.rate
        results.value.totalRequests = parsed.success + parsed.failed

      // 触发动画
      animateCounter(animatedSpeed, parsed.speed)
      animateCounter(animatedSuccess, parsed.success)
      animateCounter(animatedBytes, parsed.bytes)

      // 日志
      addLog(`吞吐量: ${parsed.speed} pages/min, ${parsed.bytes} bytes/sec`, 'highlight')
      addLog(`请求: ${parsed.success} 成功, ${parsed.failed} 失败`, parsed.failed === 0 ? 'success' : 'error')
      addLog(`成功率: ${parsed.rate}%`, parsed.rate === 100 ? 'success' : 'warning')

      // 更新图表
      updateResultChart()
      updateGaugeChart(parsed.speed)
    } else {
      addLog('⚠️ 无法解析压测结果，请检查输出格式', 'warning')
    }

    activePhase.value = 3
    addLog('✅ 压测完成！', 'success')

  } catch (e) {
    clearInterval(timerIntervalId.value)
    let errorMsg = e.message
    if (e.code === 'ECONNABORTED') {
      errorMsg = '请求超时 — 压测时间可能过长'
    }
    addLog(`❌ 压测失败: ${errorMsg}`, 'error')
    addLog(`运行时长: ${timerValue.value.toFixed(2)} 秒`)
  } finally {
    isRunning.value = false
    stopDotAnimation()
    if (!logs.value.some(l => l.text.includes('压测完成'))) {
      activePhase.value = 0
    }
  }
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ========== CSS 变量 ========== */
.lab-page-container {
  --primary: #3b82f6;
  --primary-dark: #2563eb;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --bg-main: #f0f4f8;
  --bg-card: #ffffff;
  --border-light: #e8edf2;
  --text-main: #0f172a;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  
  min-height: 100vh;
  background: linear-gradient(135deg, #f0f4f8 0%, #e8edf5 100%);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  color: var(--text-main);
  padding-bottom: 40px;
}

/* ========== 顶部导航 ========== */
.page-navbar {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  height: 72px;
  padding: 0 40px;
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  position: sticky; top: 0; z-index: 100;
  box-shadow: 0 1px 4px rgba(0,0,0,0.03);
}

.brand { display: flex; align-items: center; gap: 14px; }
.logo-icon {
  width: 42px; height: 42px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  color: white; font-size: 22px;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}
.logo-icon.lab-theme { background: linear-gradient(135deg, #2563eb, #3b82f6); }
.brand-text h1 { font-size: 20px; font-weight: 700; margin: 0; color: #0f172a; letter-spacing: -0.5px; }
.subtitle { font-size: 12px; color: var(--text-muted); font-weight: 500; margin-top: 2px; display: block; }

.status-badge {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 18px;
  background: #ffffff; 
  color: #10b981;
  border-radius: 99px; font-size: 13px; font-weight: 600;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  transition: all 0.3s ease;
}
.status-badge.running { 
  background: #eff6ff; color: #3b82f6; border-color: #bfdbfe; 
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
}
.status-badge.done { 
  background: #ecfdf5; color: #059669; border-color: #a7f3d0; 
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1);
}
.dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.running .dot { animation: pulse 1.5s infinite; }

/* ========== 阶段进度条 ========== */
.phase-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 28px;
  padding: 20px 40px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  border: 1px solid var(--border-light);
}
.phase-step {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
}
.phase-circle {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700;
  border: 2px solid #e2e8f0;
  color: #94a3b8;
  background: white;
  transition: all 0.4s ease;
  flex-shrink: 0;
}
.phase-step.active .phase-circle {
  border-color: #3b82f6;
  background: #3b82f6;
  color: white;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.15);
}
.phase-step.done .phase-circle {
  border-color: #10b981;
  background: #10b981;
  color: white;
}
.phase-label {
  font-size: 13px;
  font-weight: 500;
  color: #94a3b8;
  white-space: nowrap;
  transition: color 0.3s;
}
.phase-step.active .phase-label { color: #3b82f6; font-weight: 600; }
.phase-step.done .phase-label { color: #10b981; }
.phase-line {
  width: 80px; height: 2px;
  background: #e2e8f0;
  margin: 0 16px;
  border-radius: 1px;
  transition: background 0.4s;
}
.phase-line.filled { background: #10b981; }

/* ========== 统计卡片 ========== */
.stats-row {
  display: grid; 
  grid-template-columns: repeat(4, 1fr); 
  gap: 20px; 
  margin-bottom: 24px;
}
.stat-card {
  background: #fff; border-radius: 16px; padding: 20px 24px;
  border: 1px solid var(--border-light);
  display: flex; align-items: center; gap: 16px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  transition: all 0.3s ease;
  position: relative; overflow: hidden;
}
.stat-card::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, transparent);
  transition: background 0.5s;
}
.stat-card.is-active::after {
  background: linear-gradient(90deg, #3b82f6, #8b5cf6, #10b981);
  animation: shimmer 2s infinite linear;
}
.stat-card:hover { 
  transform: translateY(-2px); 
  box-shadow: 0 8px 20px rgba(0,0,0,0.06); 
}
.stat-icon-wrapper {
  width: 48px; height: 48px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
  transition: all 0.3s;
}
.pulse-glow { animation: pulseGlow 2s infinite; }
.bg-blue-soft { background: #eff6ff; }
.bg-purple-soft { background: #f3e8ff; }
.bg-green-soft { background: #ecfdf5; }
.bg-emerald-soft { background: #ecfdf5; }
.bg-amber-soft { background: #fffbeb; }
.bg-red-soft { background: #fef2f2; }
.bg-gray-soft { background: #f1f5f9; }
.text-blue { color: #3b82f6; }
.text-purple { color: #a855f7; }
.text-green { color: #10b981; }
.text-emerald { color: #059669; }
.text-amber { color: #d97706; }
.text-red { color: #dc2626; }
.text-gray { color: #94a3b8; }

.stat-info { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.stat-info .label { font-size: 12px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.value-group { display: flex; align-items: baseline; gap: 4px; }
.stat-info .value { 
  font-size: 26px; font-weight: 700; color: var(--text-main); 
  font-family: 'JetBrains Mono', monospace; letter-spacing: -0.5px; line-height: 1.2;
}
.stat-info .unit { font-size: 12px; color: var(--text-muted); font-weight: 500; }
.stat-trend {
  position: absolute; top: 16px; right: 16px;
}
.trend-up { color: #10b981; font-size: 18px; font-weight: bold; }

.text-success { color: var(--success) !important; }
.text-warning { color: var(--warning) !important; }
.text-danger { color: var(--danger) !important; }
.text-muted { color: var(--text-muted) !important; }
.text-primary { color: var(--primary) !important; }

/* ========== 主栅格布局 ========== */
.grid-layout {
  display: grid; 
  grid-template-columns: 400px 1fr; 
  gap: 24px;
  align-items: start;
}
.left-column, .right-column {
  display: flex; flex-direction: column; gap: 24px;
}

/* ========== 玻璃效果面板 ========== */
.panel-card {
  border: 1px solid var(--border-light);
  border-radius: 16px;
  background: var(--bg-card);
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}
.glass-effect {
  background: rgba(255,255,255,0.95);
  backdrop-filter: blur(10px);
}
:deep(.el-card__header) { 
  padding: 16px 24px; 
  border-bottom: 1px solid #f1f5f9; 
  background: #ffffff; 
}
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-title { 
  font-weight: 700; font-size: 14px; 
  display: flex; align-items: center; color: #1e293b;
}
.header-tags { display: flex; gap: 8px; align-items: center; }
.header-actions { display: flex; gap: 4px; }
.mr-2 { margin-right: 8px; }
.panel-card :deep(.el-card__body) { padding: 24px; }

/* ========== 表单区域 ========== */
.form-item { margin-bottom: 28px; }
.form-label { 
  display: flex; justify-content: space-between; align-items: center; 
  margin-bottom: 10px; 
}
.label-text { font-size: 14px; font-weight: 600; color: #334155; }

.slider-marks {
  display: flex; justify-content: space-between;
  font-size: 11px; color: #94a3b8; padding: 4px 2px 0;
}

.action-area { margin-top: 8px; }
.start-btn { 
  width: 100%; font-weight: 600; height: 50px; font-size: 16px;
  border-radius: 12px; 
  box-shadow: 0 4px 10px -2px rgba(59, 130, 246, 0.35);
  transition: all 0.2s;
  letter-spacing: 0.5px;
}
.start-btn:hover { 
  transform: translateY(-2px); 
  box-shadow: 0 10px 20px -4px rgba(59, 130, 246, 0.4); 
}
.start-btn:active { transform: translateY(0); }

/* ========== 仪表盘卡片 ========== */
.gauge-card :deep(.el-card__body) { padding: 12px 24px 24px; }
.gauge-wrapper {
  width: 100%;
  height: 200px;
}
.gauge-chart { width: 100%; height: 100%; }

/* ========== 连接活动可视化 ========== */
.activity-card :deep(.el-card__body) { padding: 16px 24px 20px; }
.blink-tag { animation: tagPulse 1.5s infinite; }
.activity-visual { display: flex; flex-direction: column; gap: 16px; }

.conn-animation-area {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 10px;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: 12px;
  position: relative;
  min-height: 90px;
  overflow: hidden;
}
.server-node, .client-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  z-index: 2;
  min-width: 80px;
}
.node-icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
  color: white;
}
.node-icon.server { background: linear-gradient(135deg, #3b82f6, #6366f1); box-shadow: 0 4px 12px rgba(59,130,246,0.3); }
.node-icon.client { background: linear-gradient(135deg, #10b981, #059669); box-shadow: 0 4px 12px rgba(16,185,129,0.3); }
.node-label { font-size: 11px; font-weight: 600; color: #94a3b8; }
.node-addr { font-size: 10px; color: #64748b; font-family: 'JetBrains Mono', monospace; }

.conn-flow {
  flex: 1;
  position: relative;
  height: 60px;
  margin: 0 20px;
}
.flow-line {
  position: absolute;
  top: 50%; left: 5%; right: 5%;
  height: 2px;
  background: linear-gradient(90deg, #10b981, #3b82f6, #10b981);
  transform: translateY(-50%);
  opacity: 0.3;
  border-radius: 1px;
}
.conn-dot {
  position: absolute;
  width: 6px; height: 6px;
  border-radius: 50%;
  animation: dotFlow 0.8s ease-out forwards;
}

.mini-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.mini-stat-item {
  text-align: center;
  padding: 10px 4px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
}
.mini-label { display: block; font-size: 11px; color: #94a3b8; margin-bottom: 4px; font-weight: 500; }
.mini-value { font-size: 16px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #0f172a; }
.mini-value small { font-size: 11px; font-weight: 500; color: #94a3b8; }

/* ========== 结果区域 ========== */
.result-grid { display: flex; flex-direction: column; gap: 20px; }
.result-metric { display: flex; flex-direction: column; gap: 8px; }
.metric-header { 
  display: flex; justify-content: space-between; 
  font-size: 13px; color: #64748b; font-weight: 500; 
}
.metric-value { font-family: 'JetBrains Mono'; font-weight: 600; color: #0f172a; font-size: 13px; }
.metric-value small { font-weight: 400; color: #94a3b8; font-size: 11px; }
.divider { margin: 0 6px; color: #cbd5e1; }

.chart-wrapper {
  height: 220px;
  width: 100%;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}
.result-chart { width: 100%; height: 100%; }

.custom-progress :deep(.el-progress-bar__outer) { 
  background-color: #f1f5f9; 
  border-radius: 20px;
}
.custom-progress :deep(.el-progress-bar__inner) { 
  border-radius: 20px;
  transition: width 1.5s ease;
}

/* ========== 日志卡片 ========== */
.log-card { 
  border-radius: 16px;
  border: 1px solid #1e293b;
  display: flex; flex-direction: column; 
  background: #0f172a;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}
.log-card :deep(.el-card__header) {
  background: #1e293b;
  border-bottom: 1px solid #334155;
}
.log-card :deep(.el-card__header .header-title) { color: #f8fafc; }
.log-card :deep(.el-card__body) { 
  flex: 1; padding: 0; 
  display: flex; flex-direction: column; 
  min-height: 0; 
  background: #0f172a;
}

/* 终端窗口 */
.terminal-window {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  max-height: 320px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.7;
  color: #e2e8f0; 
  scroll-behavior: smooth;
  scrollbar-width: thin;
}
.terminal-window::-webkit-scrollbar { width: 6px; }
.terminal-window::-webkit-scrollbar-track { background: #1e293b; }
.terminal-window::-webkit-scrollbar-thumb { 
  background: #475569; border-radius: 3px; 
}
.terminal-window::-webkit-scrollbar-thumb:hover { background: #64748b; }

.empty-log { 
  color: #475569; 
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 200px; gap: 8px;
}
.empty-title { font-family: 'Inter', sans-serif; font-size: 14px; font-weight: 500; color: #64748b; }
.empty-hint { font-family: 'Inter', sans-serif; font-size: 12px; color: #475569; }

.log-line { 
  display: flex; gap: 10px; padding: 1px 0; 
  opacity: 0.9;
}
.log-line:hover { opacity: 1; }
.log-line.success .log-content { color: #4ade80; }
.log-line.error .log-content { color: #f87171; }
.log-line.highlight .log-content { 
  color: #facc15; font-weight: 600; 
  background: rgba(250,204,21,0.08); padding: 1px 6px; border-radius: 3px;
}
.log-line.warning .log-content { color: #fbbf24; }

.log-time { color: #475569; user-select: none; min-width: 80px; font-size: 12px; flex-shrink: 0; }
.log-arrow { color: #334155; font-size: 11px; user-select: none; }
.log-content { word-break: break-all; white-space: pre-wrap; color: #cbd5e1; }

.typing-cursor .blink { 
  animation: blink 1s step-end infinite; 
  font-weight: bold; color: #3b82f6; 
}

/* ========== 动画关键帧 ========== */
@keyframes pulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}
@keyframes blink { 50% { opacity: 0; } }
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
@keyframes pulseGlow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.3); }
  50% { box-shadow: 0 0 0 8px rgba(59,130,246,0); }
}
@keyframes dotFlow {
  0% { transform: scale(1); opacity: 1; }
  100% { transform: translateX(100px) scale(0.3); opacity: 0; }
}
@keyframes tagPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* ========== 响应式 ========== */
@media (max-width: 1200px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .grid-layout { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .stats-row { grid-template-columns: 1fr; }
  .page-navbar { padding: 0 16px; }
  .main-content { padding: 0 12px; }
  .phase-bar { padding: 12px 16px; flex-wrap: wrap; gap: 8px; }
  .phase-line { width: 30px; }
  .mini-stats { grid-template-columns: repeat(2, 1fr); }
  .terminal-window { max-height: 240px; }
}
</style>
