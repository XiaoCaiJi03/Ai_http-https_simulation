<template>
  <div class="simulation-page">
    <div class="page-navbar">
      <div class="brand">
        <div class="logo-icon">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <div class="brand-text">
          <h1>HTTP/HTTPS 会话仿真实验室</h1>
        </div>
      </div>
      <div class="status-tags">
      </div>
    </div>

    <el-row :gutter="24" class="main-content">
      
      <!-- 左侧控制面板 -->
      <el-col :span="8" :xs="24" :md="9" :lg="7" class="col-left">
        <el-card shadow="never" class="control-panel glass-panel">
          <template #header>
            <div class="panel-header">
              <span class="title"><el-icon><Setting /></el-icon> 仿真参数配置</span>
              <div v-if="sessionActive" class="live-status-badge">
                <span class="pulse-dot" :class="{ warning: remainingSeconds <= 10, closed: remainingSeconds <= 0 }"></span>
                <span>LIVE</span>
                <span class="countdown-text">{{ remainingSeconds }}s</span>
              </div>
            </div>
          </template>
          <el-form label-position="top" size="default" class="simulation-form">
            
            <div class="form-section hover-effect">
            <div class="section-header">
                <span class="section-title">基础协议 & 模式侦测</span>
            </div>

            <el-row :gutter="12">
                <el-col :span="24">
                    <div class="protocol-switch-wrapper">
                        <span class="label">传输协议</span>
                        <el-radio-group 
                          v-model="form.isHttps" 
                          size="small"
                          @change="handleProtocolChange"
                          :disabled="sessionActive"
                          class="custom-radio-group"
                        >
                          <el-radio-button :label="false">HTTP</el-radio-button>
                          <el-radio-button :label="true">HTTPS</el-radio-button>
                        </el-radio-group>
                    </div>
                </el-col>
            </el-row>

            <el-row :gutter="12" style="margin-top: 15px;">
                <el-col :span="24">
                    <div class="protocol-switch-wrapper">
                        <span class="label">恶意报文检测</span>
                        <el-switch 
                          v-model="form.checkMalicious" 
                          size="small"
                          active-text="开启"
                          inactive-text="关闭"
                          style="margin-left: auto;"
                        />
                    </div>
                </el-col>
            </el-row>

              <!-- 智能模式显示 -->
              <div class="auto-detect-card" :class="detectedModeClass">
                <div class="card-icon">
                  <el-icon v-if="isKeepAlive"><Link /></el-icon>
                  <el-icon v-else><Close /></el-icon>
                </div>
                <div class="card-content">
                  <div class="detect-title">
                    连接模式: {{ isKeepAlive ? 'Keep-Alive (支持管线化)' : 'Short-Lived (短连接)' }}
                  </div>
                  <div class="detect-desc">{{ detectedModeDesc }}</div>
                </div>
              </div>

              <!-- Socket Monitor (修复样式) -->
              <el-collapse-transition>
                <div v-if="connectionState.id && sessionActive" class="socket-monitor">
                  <div class="monitor-body simple">
                  <div class="info-row">
                    <span class="label">Socket ID</span>
                    <span class="value mono-font">{{ connectionState.id }}</span>
                  </div>
                </div>
                </div>
              </el-collapse-transition>
            </div>

            <div class="form-section hover-effect">
              <div class="section-header-row">
                <div class="section-title">请求载荷 (Payload)</div>
                <el-dropdown trigger="click" @command="applyTemplate">
                  <el-button type="primary" link size="small" class="template-btn">
                    <el-icon><MagicStick /></el-icon> 加载模板 <el-icon class="el-icon--right"><arrow-down /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="http">HTTP/1.1 (Standard)</el-dropdown-item>
                      <el-dropdown-item command="https">HTTPS (Secure)</el-dropdown-item>
                      <el-dropdown-item command="close">HTTP/1.0 (Close)</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>

              <div class="code-editor-wrapper">
                <div class="editor-bar">
                  <span class="dot red"></span>
                  <span class="dot yellow"></span>
                  <span class="dot green"></span>
                  <span class="editor-lang">Request Message</span>
                </div>
                <el-input
                  v-model="httpRequestContent"
                  type="textarea"
                  :rows="10"
                  placeholder="在此输入 HTTP 请求..."
                  class="code-input dark-theme-input"
                  resize="none"
                />
              </div>
            </div>

            <div class="form-actions">
              <template v-if="!sessionActive">
                <el-button
                  type="primary"
                  @click="startSimulation"
                  :loading="loading"
                  class="action-btn main-btn shadow-btn"
                  round
                  size="large"
                >
                  <el-icon class="btn-icon"><VideoPlay /></el-icon> 开始仿真
                </el-button>
                <el-button
                  @click="clearForm"
                  class="action-btn reset-btn"
                  circle
                  plain
                  size="large"
                >
                  <el-icon><RefreshLeft /></el-icon>
                </el-button>
              </template>

              <template v-else>
                <el-button
                  type="danger"
                  @click="endSimulation(false)"
                  class="action-btn stop-btn shadow-btn"
                  round
                  size="large"
                >
                  <el-icon class="btn-icon"><SwitchButton /></el-icon> 结束
                </el-button>
                
                <el-button
                  type="success"
                  @click="sendRequest"
                  :loading="loading"
                  class="action-btn send-btn shadow-btn"
                  round
                  size="large"
                >
                  <el-icon class="btn-icon"><Position /></el-icon> 发送
                </el-button>
              </template>
            </div>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧结果面板 -->
      <el-col :span="16" :xs="24" :md="15" :lg="17" class="col-right">
        <el-card shadow="never" class="result-panel glass-panel">
          <el-tabs v-model="activeTab" class="custom-tabs">
            
            <!-- Tab 1: 交互概览 (支持堆叠) -->
            <el-tab-pane name="data-compare">
              <template #label>
                <div class="custom-tab-label">
                  <el-icon><DataLine /></el-icon> <span>交互概览</span>
                </div>
              </template>
              
              <div v-if="visibleResponses.length > 0 || sessionActive" class="result-content scrollable-area">
                <div class="summary-card" v-if="result">
                  <div class="summary-item">
                    <span class="s-label">Protocol</span>
                    <el-tag :type="form.isHttps ? 'success' : 'warning'" effect="dark" size="small" round>
                      {{ form.isHttps ? 'HTTPS' : 'HTTP' }}
                    </el-tag>
                  </div>
                  <div class="summary-divider"></div>
                  <div class="summary-item">
                    <span class="s-label">Mode</span>
                    <el-tag size="small" effect="plain" :type="isKeepAlive ? 'success' : 'info'" round>
                      {{ isKeepAlive ? 'Persistent' : 'Short-Lived' }}
                    </el-tag>
                  </div>
                  <div class="summary-divider"></div>
                  <div class="summary-item">
                    <span class="s-label">Session ID</span>
                    <span class="s-value mono">{{ result.sessionId || connectionState.id || '--' }}</span>
                  </div>
                </div>

                <div class="interaction-stream">
                  <!-- 循环展示所有历史交互 -->
                  <div v-for="(item, idx) in interactionHistory" :key="idx" class="history-block">
                    
                    <!-- 历史请求 -->
                    <div class="stream-node client-node">
                      <div class="node-avatar"><el-icon><UserFilled /></el-icon></div>
                      <div class="node-content">
                        <div class="node-header">Client Request</div>
                        <div class="code-block-viewer">
                          <pre>{{ item.request }}</pre>
                        </div>
                      </div>
                    </div>
                    
                    <div class="stream-line"></div>

                    <!-- 历史响应 -->
                    <div class="response-stream-container">
                      <div 
                        v-for="(res, rIdx) in item.responses" 
                        :key="rIdx" 
                        class="stream-node server-node slide-in-item"
                      > 
                        <div class="node-content">
                          <div class="node-header">
                            <span>Server Response</span>
                            <el-icon><Monitor /></el-icon>
                          </div>
                          <div class="code-block-viewer server-theme">
                            <pre>{{ res }}</pre>
                          </div>
                        </div>
                        <div class="node-avatar server-avatar"><el-icon><Platform /></el-icon></div>
                      </div>
                    </div>

                    <div class="history-divider" v-if="idx < interactionHistory.length - 1"></div>
                  </div>
                </div>
              </div>
              <el-empty v-else>
                <template #description>
                  <p style="color: #909399;">请点击 <span style="color: #409EFF">开始仿真</span></p>
                </template>
              </el-empty>
            </el-tab-pane>

             <!-- Tab 2: 报文详情 -->
            <el-tab-pane name="packet-detail">
              <template #label>
                <div class="custom-tab-label">
                  <el-icon><Document /></el-icon> <span>报文详情</span>
                </div>
              </template>
              <div class="result-content scrollable-area" v-if="result">
                 <div class="json-wrapper">
                    <JSONViewer :value="result" :expand-depth="2" boxed copyable theme="jv-light"/>
                 </div>
              </div>
              <el-empty v-else description="暂无报文数据" />
            </el-tab-pane>

            <!-- Tab 3: 全链路拓扑 (美化版) -->
            <el-tab-pane name="topology">
              <template #label>
                <div class="custom-tab-label">
                  <el-icon><Share /></el-icon> <span>全链路拓扑</span>
                </div>
              </template>
              <div class="topology-container scrollable-area">
                <div class="topology-grid-bg"></div> <!-- 背景网格 -->
                <div class="topology-header">
                  <div class="actor client">
                    <div class="actor-icon"><el-icon><UserFilled /></el-icon></div>
                    <span>Client</span>
                  </div>
                  <div class="actor server">
                    <div class="actor-icon"><el-icon><Platform /></el-icon></div>
                    <span>Server</span>
                  </div>
                </div>
                
                <div class="sequence-diagram">
                  <div class="vertical-line client-line"></div>
                  <div class="vertical-line server-line"></div>

                  <transition-group name="list">
                    <div v-for="(event, idx) in topologyEvents" :key="idx" class="seq-event" :class="event.type">
                      <div class="time-label">{{ event.time }}</div>
                      <div class="arrow-wrapper" :class="event.direction">
                        <div class="arrow-line" :class="{ 'dashed': event.isAck }"></div>
                        <div class="arrow-head"></div>
                        <div class="event-label-box">
                          <span class="protocol-badge" :class="event.protocol.toLowerCase()">{{ event.protocol }}</span>
                          <span class="msg-text">{{ event.message }}</span>
                          <span class="detail-text" v-if="event.detail && !event.payload">{{ event.detail }}</span>

                          <!-- 新增：HTTP 报文查看按钮 -->
                          <el-popover
                            v-if="event.type === 'http' && event.payload"
                            placement="bottom"
                            :width="500"
                            trigger="click"
                            popper-class="payload-popover"
                          >
                            <template #reference>
                              <el-button type="primary" link size="small" class="view-payload-btn">
                                <el-icon><View /></el-icon> 查看报文
                              </el-button>
                            </template>
                            <div class="payload-viewer">
                              <div class="payload-header" :class="event.direction === 'c2s' ? 'request' : 'response'">
                                <el-icon v-if="event.direction === 'c2s'"><Upload /></el-icon>
                                <el-icon v-else><Download /></el-icon>
                                {{ event.direction === 'c2s' ? '请求报文 (Request)' : '响应报文 (Response)' }}
                              </div>
                              <div class="payload-content-wrapper">
                                <pre class="payload-content">{{ event.payload }}</pre>
                              </div>
                              <div class="payload-footer">
                                <span class="payload-size">{{ getPayloadSize(event.payload) }} bytes</span>
                                <el-button type="primary" size="small" @click="copyPayload(event.payload)">
                                  <el-icon><DocumentCopy /></el-icon> 复制
                                </el-button>
                              </div>
                            </div>
                          </el-popover>
                        </div>
                      </div>
                    </div>
                  </transition-group>

                  <div v-if="!sessionActive && topologyEvents.length > 0" class="connection-closed-marker">
                    <span>Connection Closed</span>
                  </div>
                </div>
              </div>
            </el-tab-pane>

          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import JSONViewer from 'vue-json-viewer'
import 'vue-json-viewer/style.css'
import request from '@/utils/request'
import {
  Setting, VideoPlay, RefreshLeft, DataLine, Document,
  Connection, Cpu, SwitchButton, Position,
  UserFilled, Platform, Monitor, Link, Close, MagicStick,
  Share, DataAnalysis, View
} from '@element-plus/icons-vue'

// --- 状态定义 ---
const loading = ref(false)
const sessionActive = ref(false)
const result = ref(null)
const activeTab = ref('data-compare')

// 历史交互记录 (Req 1: 堆叠显示)
// 结构: { request: string, responses: string[] }
const interactionHistory = ref([])
const visibleResponses = ref([]) // 仅用于 Tab 1 判定显示

const connectionState = reactive({
  id: null,
  used: 0, max: 100, percent: 0
})

const timeoutSeconds = ref(60)
const remainingSeconds = ref(60)
let countdownTimer = null
let pendingTimeouts = []

const templates = {
  http: `GET /index.html HTTP/1.1
Host: www.baidu.com
User-Agent: Simulation-Lab/1.0
Connection: keep-alive
Accept: */*

`,
  https: `POST /login.jsp HTTP/1.1
Host: www.testfire.net
Content-Type: application/json
Connection: keep-alive

{"username": "admin", "password": "123456"}`,
  close: `GET /api/data HTTP/1.0
Host: www.example.com
Connection: close

`
}

const httpRequestContent = ref(templates.http)
const form = reactive({ isHttps: false, checkMalicious: false })

const isKeepAlive = computed(() => {
  const content = httpRequestContent.value || ''
  const hasClose = content.match(/Connection:\s*close/gi) !== null
  if (hasClose) return false
  return true
})

const detectedModeClass = computed(() => isKeepAlive.value ? 'keep-alive' : 'short-lived')
const detectedModeDesc = computed(() => {
  if (isKeepAlive.value) return 'TCP 连接保持激活，支持多次请求复用及管线化。'
  return '请求完成后 TCP 连接立即关闭 (Short-Lived)。'
})

// --- 拓扑图逻辑 ---
const topologyEvents = ref([])
const hasHandshaked = ref(false)

const getTimeStr = () => {
  const now = new Date()
  return `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}.${now.getMilliseconds().toString().slice(0,2)}`
}

// 修改：增加 payload 参数用于存储报文内容
const addTopologyEvent = (type, direction, message, detail = '', protocol = '', payload = null) => {
  const isAck = message.includes('ACK') && !message.includes('FIN') && !message.includes('SYN')
  topologyEvents.value.push({
    type, // tcp, tls, http
    direction, // c2s, s2c
    message,
    detail,
    protocol,
    time: getTimeStr(),
    isAck,
    payload // 新增：存储报文内容
  })
  nextTick(() => {
    const container = document.querySelector('.topology-container')
    if (container) container.scrollTop = container.scrollHeight
  })
}

// 新增：获取报文大小
const getPayloadSize = (payload) => {
  if (!payload) return 0
  return new Blob([payload]).size
}

// 新增：复制报文到剪贴板
const copyPayload = async (payload) => {
  try {
    await navigator.clipboard.writeText(payload)
    ElMessage.success('报文已复制到剪贴板')
  } catch (err) {
    ElMessage.error('复制失败')
  }
}

// --- 操作逻辑 ---

const applyTemplate = (command) => {
  if (templates[command]) {
    httpRequestContent.value = templates[command]
    form.isHttps = command === 'https'
    ElMessage.success('模板已加载')
  }
}

const handleProtocolChange = (val) => {
  applyTemplate(val ? 'https' : 'http')
}

const resetCountdown = (timeout = 60) => {
  if (countdownTimer) clearInterval(countdownTimer)
  timeoutSeconds.value = timeout
  remainingSeconds.value = timeout
  countdownTimer = setInterval(() => {
    if (remainingSeconds.value <= 0) {
      endSimulation(true)
      return
    }
    remainingSeconds.value -= 1
  }, 1000)
}

const clearCountdown = () => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

const clearForm = () => {
  httpRequestContent.value = templates.http
  result.value = null
  visibleResponses.value = []
  interactionHistory.value = [] // 清空历史
  topologyEvents.value = []
  hasHandshaked.value = false
  clearCountdown()
  ElMessage.info('已重置')
}

const startSimulation = async () => {
  if (!httpRequestContent.value.trim()) {
    ElMessage.warning('请求报文不能为空')
    return
  }

  // 不要在这里设置 sessionActive 为 true，而是在确认连接成功后设置
  interactionHistory.value = [] // 新会话开始时清空历史
  topologyEvents.value = []
  hasHandshaked.value = false

  await sendRequest()
}

// 结束仿真 (Req 3: 修复多余 ACK)
const endSimulation = (auto = false) => {
  if (sessionActive.value) {
    // 只有在连接还是 Keep-Alive 状态下（即未被服务端关闭）手动结束时，才画断开图
    // 模拟客户端主动断开：Client FIN -> Server ACK -> Server FIN -> Client ACK
    addTopologyEvent('tcp', 'c2s', 'FIN, ACK', 'Client Close', 'TCP')
    const t1 = setTimeout(() => {
        addTopologyEvent('tcp', 's2c', 'ACK', '', 'TCP')
        const t2 = setTimeout(() => {
             addTopologyEvent('tcp', 's2c', 'FIN, ACK', '', 'TCP')
             const t3 = setTimeout(() => {
                 addTopologyEvent('tcp', 'c2s', 'ACK', 'Connection Closed', 'TCP')
             }, 100)
             pendingTimeouts.push(t3)
        }, 100)
        pendingTimeouts.push(t2)
    }, 100)
    pendingTimeouts.push(t1)
  }

  sessionActive.value = false
  connectionState.id = null
  clearCountdown()
  remainingSeconds.value = 60
  if (auto) ElMessage.warning('连接超时或自动断开')
  else ElMessage.info('会话已结束')
}

const sendRequest = async () => {
  if (!httpRequestContent.value.trim()) return

  loading.value = true

  // 保存当前请求内容，用于后续添加到拓扑图
  const currentRequestContent = httpRequestContent.value

  // 1. 握手逻辑 (保持不变)
  if (!hasHandshaked.value) {
    addTopologyEvent('tcp', 'c2s', 'SYN', 'Seq=0', 'TCP')
    addTopologyEvent('tcp', 's2c', 'SYN, ACK', 'Seq=0 Ack=1', 'TCP')
    addTopologyEvent('tcp', 'c2s', 'ACK', 'Seq=1 Ack=1', 'TCP')

    if (form.isHttps) {
      addTopologyEvent('tls', 'c2s', 'Client Hello', 'TLS 1.3', 'TLS')
      addTopologyEvent('tls', 's2c', 'Server Hello', 'Cert, Key', 'TLS')
      addTopologyEvent('tls', 'c2s', 'Finished', 'Encrypted', 'TLS')
      addTopologyEvent('tls', 's2c', 'Finished', 'Encrypted', 'TLS')
    }
    hasHandshaked.value = true
  }

  // 2. 发送数据拓扑 - 修改：添加请求报文内容
  const protocolLabel = form.isHttps ? 'HTTPS' : 'HTTP'
  const reqCount = httpRequestContent.value.split('HTTP/1.1').length - 1 || 1
  if (reqCount > 1) {
    addTopologyEvent('http', 'c2s', `Pipeline Req (${reqCount})`, 'Batch Send', protocolLabel, currentRequestContent)
  } else {
    addTopologyEvent('http', 'c2s', 'Application Data', 'Request Payload', protocolLabel, currentRequestContent)
  }

  try {
    // 构造请求参数
    const params = {
      is_https: form.isHttps,
      full_http_request: httpRequestContent.value,
      connection_id: connectionState.id,
      check_malicious: form.checkMalicious
    }

    const res = await request.post('/api/run_simulation', params)

    const data = res.data

    // --- 分支 A: 需要用户确认 (恶意报文) ---
    if (data.need_confirm) {
      // 显示确认对话框
      ElMessageBox.confirm(
        `检测结果：${data.malicious_check_result['预测结果']}\n置信度：${data.malicious_check_result['置信度']}\n\n是否继续发送该请求？`,
        '恶意请求检测',
        {
          confirmButtonText: '继续发送',
          cancelButtonText: '取消发送',
          type: 'warning'
        }
      ).then(async () => {
        // 用户点击了确认按钮
        const confirmParams = { ...params, continue_sending: true }
        try {
          const confirmRes = await request.post('/api/run_simulation', confirmParams)
          const confirmData = confirmRes.data
          saveToLocalStorage(httpRequestContent.value, confirmData)
          result.value = confirmData
          handleSimulationSuccess(confirmData, protocolLabel)
        } catch (err) {
          ElMessage.error('发送请求失败，请稍后重试')
        }
      }).catch(() => {
        // 用户点击了取消按钮或关闭了对话框
        ElMessage.info('已取消发送恶意请求')
      })
    } else {
      // --- 分支 B: 正常发送成功 ---
      saveToLocalStorage(httpRequestContent.value, data)
      result.value = data
      handleSimulationSuccess(data, protocolLabel)
    }
  } catch (err) {
    ElMessage.error('网络错误：' + err.message)
    endSimulation()
  } finally {
    loading.value = false
  }
}

// =======================================================
// 【辅助函数】：用于将数据存入 LocalStorage
//  请将此函数放在 script setup 的任意位置（sendRequest 外部）
// =======================================================
const saveToLocalStorage = (reqStr, dataObj) => {
  try {
    // 1. 保存请求报文
    localStorage.setItem('auto_sync_request', reqStr)

    // 2. 保存响应报文 (处理数组或字符串)
    let respText = ''
    if (Array.isArray(dataObj.responses) && dataObj.responses.length > 0) {
      respText = dataObj.responses.join('\n\n')
    } else {
      respText = dataObj.httpResponseContent || ''
    }
    localStorage.setItem('auto_sync_response', respText)
  } catch (e) {
    console.error('Failed to sync data to localStorage', e)
  }
}

// 处理仿真成功的逻辑
const handleSimulationSuccess = (data, protocolLabel) => {
  // 设置会话为活跃状态，显示 LIVE 60s
  sessionActive.value = true

  // 更新连接状态
  connectionState.id = data.sessionId
  if (data.keepAliveInfo) {
    connectionState.used = data.keepAliveInfo.used
    connectionState.max = data.keepAliveInfo.max
    // 计算资源使用百分比
    connectionState.percent = Math.floor((data.keepAliveInfo.used / data.keepAliveInfo.max) * 100)
    resetCountdown(data.keepAliveInfo.timeout)
  }

  // 兼容单响应和管线化多响应
  const serverResponses = data.responses || [data.httpResponseContent]

  // 拓扑响应 - 修改：添加响应报文内容
  serverResponses.forEach((resp, idx) => {
    const tid = setTimeout(() => {
      addTopologyEvent('http', 's2c', 'Application Data', `Response #${idx+1}`, protocolLabel, resp)
    }, idx * 250)
    pendingTimeouts.push(tid)
  })

  // 交互视图：堆叠历史 (Req 1)
  // 将本次请求和响应打包推入历史记录
  const currentInteraction = {
    request: httpRequestContent.value,
    responses: []
  }
  interactionHistory.value.push(currentInteraction)

  // 模拟逐条接收响应
  serverResponses.forEach((resContent, index) => {
    const tid = setTimeout(() => {
      currentInteraction.responses.push(resContent)
      // 保持 visibleResponses 用于简单的空状态判断
      visibleResponses.value.push(resContent)
    }, index * 300)
    pendingTimeouts.push(tid)
  })

  // 处理连接关闭 (Connection Status from Backend)
  if (data.connectionStatus === 'closed') {
    const delay = serverResponses.length * 300 + 400

    // 判断是否是客户端请求头导致的关闭 (Connection: close)
    // 如果是，走客户端主动关闭流程 (Req 3)
    if (!isKeepAlive.value) {
        const t1 = setTimeout(() => {
            addTopologyEvent('tcp', 'c2s', 'FIN, ACK', 'Client Initiated', 'TCP')
            const t2 = setTimeout(() => {
                addTopologyEvent('tcp', 's2c', 'ACK', '', 'TCP')
                const t3 = setTimeout(() => {
                    addTopologyEvent('tcp', 's2c', 'FIN, ACK', 'Server Close', 'TCP')
                    const t4 = setTimeout(() => {
                        addTopologyEvent('tcp', 'c2s', 'ACK', 'Connection Closed', 'TCP')
                    }, 100)
                    pendingTimeouts.push(t4)
                }, 100)
                pendingTimeouts.push(t3)
            }, 100)
            pendingTimeouts.push(t2)
        }, delay)
        pendingTimeouts.push(t1)
    } else {
        // 服务端主动关闭（如超时或次数耗尽）: Server FIN -> Client ACK -> Client FIN -> Server ACK
        const t1 = setTimeout(() => {
          addTopologyEvent('tcp', 's2c', 'FIN, ACK', 'Server Initiated', 'TCP')
          const t2 = setTimeout(() => {
              addTopologyEvent('tcp', 'c2s', 'ACK', '', 'TCP')
              const t3 = setTimeout(() => {
                  addTopologyEvent('tcp', 'c2s', 'FIN, ACK', '', 'TCP')
                  const t4 = setTimeout(() => {
                      addTopologyEvent('tcp', 's2c', 'ACK', 'Connection Closed', 'TCP')
                  }, 100)
                  pendingTimeouts.push(t4)
              }, 100)
              pendingTimeouts.push(t3)
          }, 100)
          pendingTimeouts.push(t2)
        }, delay)
        pendingTimeouts.push(t1)
    }

    sessionActive.value = false
    connectionState.id = null
    clearCountdown()

    if (!isKeepAlive.value) {
      ElMessage.success('请求完成，连接正常关闭')
    } else {
      ElMessage.warning('服务端主动关闭了连接')
    }
  }
}

onUnmounted(() => {
  clearCountdown()
  pendingTimeouts.forEach(id => clearTimeout(id))
  pendingTimeouts = []
})
</script>

<style scoped>
/* 基础样式保持不变 */
.simulation-page {
  background: linear-gradient(135deg, #f0f5fa 0%, #e6eef5 100%);
  min-height: 100vh;
  font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  height: 100vh;
  overflow: hidden;
  display: flex; flex-direction: column;
}

.page-navbar {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  padding: 0 40px;
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid rgba(0,0,0,0.05);
  height: 70px; flex-shrink: 0;
}
.brand { display: flex; align-items: center; gap: 15px; }
.logo-icon {
  width: 40px; height: 40px; background: linear-gradient(135deg, #409EFF, #005cbf);
  border-radius: 10px; display: flex; align-items: center; justify-content: center;
  color: white; font-size: 20px;
}
.brand-text h1 { margin: 0; font-size: 18px; color: #1a1a1a; }
.subtitle { font-size: 11px; color: #909399; display: block;}
.glass-tag { backdrop-filter: blur(4px); margin-left: 8px; font-weight: 500;}

.main-content { padding: 20px 40px; flex: 1; margin: 0 !important; overflow: hidden; height: calc(100vh - 70px); }
.col-left, .col-right { height: 100%; display: flex; flex-direction: column; }
.glass-panel {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
  height: 100%; display: flex; flex-direction: column; overflow: hidden;
}

/* --- 左侧面板优化 (仿真参数配置) --- */

.form-section {
  margin-bottom: 20px;
  padding: 10px;
  border-radius: 8px;
  transition: background 0.3s ease;
}
.form-section.hover-effect:hover {
  background: rgba(0,0,0,0.02);
}

.section-header { margin-bottom: 12px; }
.section-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-title { font-size: 13px; font-weight: 700; color: #606266; text-transform: uppercase; letter-spacing: 0.5px; }

.protocol-switch-wrapper {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; padding: 8px 12px; border-radius: 8px; border: 1px solid #e4e7ed;
}
.protocol-switch-wrapper .label { font-size: 13px; color: #303133; font-weight: 600; }

/* 智能模式显示卡片 */
.auto-detect-card {
  margin-top: 15px;
  padding: 16px;
  background: #f8f9fa;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.auto-detect-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
  flex-shrink: 0;
}

.auto-detect-card.keep-alive .card-icon {
  background: linear-gradient(135deg, #409EFF, #66b1ff);
}

.auto-detect-card.short-lived .card-icon {
  background: linear-gradient(135deg, #F56C6C, #f78989);
}

.card-content {
  flex: 1;
}

.detect-title {
  font-size: 14px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 4px;
}

.detect-desc {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}

/* Socket Monitor 修复 (Req 4) */
.socket-monitor {
  margin-top: 15px; background: #ffffff; border-radius: 10px; padding: 15px; color: #333;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  border: 1px solid #e0e0e0;
  word-break: break-all;
  overflow-wrap: break-word;
}
.monitor-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; border-bottom: 1px solid #e0e0e0; padding-bottom: 8px;
}
.monitor-title-group { display: flex; align-items: center; gap: 8px; font-weight: 700; color: #409EFF; font-size: 13px; }
.monitor-body { font-size: 12px; }
/* 简化的socket monitor样式，只显示Socket ID */
.monitor-body.simple {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  padding: 0;
  width: 100%;
}
.info-row { display: flex; justify-content: flex-start; align-items: center; margin-bottom: 0; gap: 10px; width: 100%; flex-wrap: wrap; }
.info-row.vertical { flex-direction: column; align-items: stretch; gap: 6px; }
.label { color: #606266; font-weight: 600; font-size: 13px; }
.value.mono-font { font-family: monospace; color: #67C23A; font-size: 14px; font-weight: bold; background: #f0f9eb; padding: 4px 8px; border-radius: 4px; border: 1px solid #e1f3d8; flex: 1; overflow-wrap: break-word; word-break: break-all; }
.progress-label { display: flex; justify-content: space-between; color: #a0a0a0; font-size: 11px; margin-bottom: 4px; }
.divider { height: 1px; background: #e0e0e0; margin: 8px 0; }

/* 代码编辑器样式优化 */
.code-editor-wrapper {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}
.editor-bar {
  background: #f5f7fa;
  padding: 8px 12px;
  border-bottom: 1px solid #dcdfe6;
  display: flex; align-items: center; gap: 6px;
}
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dot.red { background: #ff5f56; border: 1px solid #e0443e; }
.dot.yellow { background: #ffbd2e; border: 1px solid #dea123; }
.dot.green { background: #27c93f; border: 1px solid #1aab29; }
.editor-lang { margin-left: auto; font-size: 10px; color: #909399; font-weight: 600; }

.code-input.dark-theme-input :deep(.el-textarea__inner) {
  background: #ffffff; color: #303133; border: none;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px; line-height: 1.6; padding: 12px;
  box-shadow: none;
}
.code-input.dark-theme-input :deep(.el-textarea__inner):focus {
  background: #faffff;
}

.form-actions {
  margin-top: 20px; display: flex; justify-content: center; gap: 15px; padding-bottom: 10px;
}
.action-btn { font-weight: 600; letter-spacing: 0.5px; transition: all 0.3s; }
.shadow-btn { box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3); }
.stop-btn.shadow-btn { box-shadow: 0 4px 12px rgba(245, 108, 108, 0.3); }
.send-btn.shadow-btn { box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3); }
.btn-icon { margin-right: 4px; }

/* --- 右侧面板优化 (交互概览) --- */

/* 总结卡片表格样式 */
.summary-card {
  display: table;
  width: 100%;
  border-collapse: collapse;
  background: #f8f9fa;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: hidden;
}

.summary-item {
  display: table-row;
  border-bottom: 1px solid #e4e7ed;
  transition: background-color 0.2s ease;
}

.summary-item:last-child {
  border-bottom: none;
}

.summary-item:hover {
  background-color: #ecf5ff;
}

.summary-divider {
  display: none;
}

.s-label {
  display: table-cell;
  padding: 12px 16px;
  font-weight: 700;
  color: #303133;
  background-color: #f0f2f5;
  width: 120px;
  text-align: left;
  font-size: 13px;
}

.summary-item > span:not(.s-label),
.summary-item > .el-tag {
  display: table-cell;
  padding: 12px 16px;
  color: #606266;
  font-size: 13px;
  vertical-align: middle;
}

.summary-item .s-value.mono {
  font-family: monospace;
  color: #67C23A;
  font-weight: 600;
}

/* 交互流堆叠样式 (Req 1) */
.history-block { margin-bottom: 30px; }
.history-divider { height: 2px; background: #f0f2f5; margin: 20px 0; border-top: 1px dashed #dcdfe6; }

.stream-node { display: flex; gap: 12px; margin-bottom: 20px; align-items: flex-start; }
.node-avatar {
  width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
  color: white; font-size: 18px; flex-shrink: 0; box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
.client-node .node-avatar { background: linear-gradient(135deg, #409EFF, #337ecc); }
.server-node .server-avatar { background: linear-gradient(135deg, #67C23A, #529b2e); order: 2; }

.server-node { justify-content: flex-end; }
.server-node .node-content { order: 1; margin-left: auto; text-align: right; }

.node-content { max-width: 85%; flex: 1; }
.node-header { font-size: 11px; color: #909399; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; font-weight: 600; }
.server-node .node-header { justify-content: flex-end; }

.code-block-viewer {
  background: #ffffff; border: 1px solid #ebeef5; border-radius: 8px; padding: 12px;
  font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; line-height: 1.6; overflow-x: auto;
  box-shadow: 0 2px 8px rgba(0,0,0,0.03);
  text-align: left;
}
.code-block-viewer.server-theme {
  background: #282c34; color: #abb2bf; border: 1px solid #282c34;
}

.slide-in-item {
  animation: slideIn 0.4s ease-out forwards;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 拓扑图美化 (Req 2) */
.topology-container {
  background: #fff; padding: 20px; border-radius: 8px; min-height: 100%;
  display: flex; flex-direction: column; position: relative; overflow-x: hidden;
}
.topology-grid-bg {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background-image: linear-gradient(#f5f7fa 1px, transparent 1px), linear-gradient(90deg, #f5f7fa 1px, transparent 1px);
  background-size: 20px 20px; z-index: 0; pointer-events: none;
}
.topology-header {
  display: flex; justify-content: space-between; padding: 0 15%; margin-bottom: 30px;
  position: sticky; top: 0; background: rgba(255,255,255,0.95); z-index: 10; padding-bottom: 10px; border-bottom: 1px solid #eee;
}
.actor { display: flex; flex-direction: column; align-items: center; font-weight: 700; color: #303133; font-size: 14px; gap: 8px; }
.actor-icon {
  width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 20px; color: #fff; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
}
.actor.client .actor-icon { background: linear-gradient(135deg, #409EFF, #337ecc); }
.actor.server .actor-icon { background: linear-gradient(135deg, #67C23A, #529b2e); }

.sequence-diagram { position: relative; flex: 1; padding: 0 15%; min-height: 300px; z-index: 1; }
.vertical-line {
  position: absolute; top: 0; bottom: 0; width: 2px; background: #e4e7ed;
  border-left: 2px dashed #ccc;
}
.client-line { left: 18%; }
.server-line { right: 18%; }

.seq-event {
  margin-bottom: 25px; position: relative; height: 36px;
  display: flex; align-items: center; justify-content: center;
}
.time-label {
  position: absolute; left: -60px; font-size: 10px; color: #c0c4cc; font-family: monospace;
}
.arrow-wrapper {
  position: relative; width: 64%; height: 2px; display: flex; align-items: center; justify-content: center;
}
.arrow-line { width: 100%; height: 2px; background: #909399; position: relative; }
.arrow-line.dashed { background: transparent; border-bottom: 2px dashed #909399; height: 0; }

.c2s .arrow-line { background: #409EFF; }
.c2s .arrow-line.dashed { border-bottom-color: #409EFF; }
.s2c .arrow-line { background: #67C23A; }
.s2c .arrow-line.dashed { border-bottom-color: #67C23A; }

.arrow-head {
  position: absolute; width: 0; height: 0; border-top: 6px solid transparent; border-bottom: 6px solid transparent; top: -5px;
}
.c2s .arrow-head { right: -2px; border-left: 8px solid #409EFF; }
.s2c .arrow-head { left: -2px; border-right: 8px solid #67C23A; }

.event-label-box {
  position: absolute; top: -22px; background: #fff; padding: 3px 10px;
  font-size: 11px; color: #606266; border: 1px solid #ebeef5; border-radius: 12px;
  display: flex; gap: 6px; align-items: center; white-space: nowrap;
  box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}
.protocol-badge { padding: 0 6px; border-radius: 4px; font-weight: 700; font-size: 9px; color: #fff; }
.protocol-badge.tcp { background: #909399; }
.protocol-badge.tls { background: #E6A23C; }
.protocol-badge.http { background: #409EFF; }
.protocol-badge.https { background: #67C23A; }

.msg-text { font-weight: 600; color: #303133; }
.detail-text { color: #909399; font-size: 10px; }

/* TLS 特殊样式 */
.seq-event.tls .arrow-line { background: #E6A23C; }
.seq-event.tls .c2s .arrow-head { border-left-color: #E6A23C; }
.seq-event.tls .s2c .arrow-head { border-right-color: #E6A23C; }

.connection-closed-marker {
  text-align: center; margin-top: 40px; padding: 15px; border-top: 2px solid #F56C6C;
  color: #F56C6C; font-weight: 700; font-size: 13px; letter-spacing: 1px; text-transform: uppercase;
  background: linear-gradient(to bottom, rgba(245, 108, 108, 0.05), transparent);
}

/* 列表过渡动画 */
.list-enter-active, .list-leave-active { transition: all 0.5s ease; }
.list-enter-from, .list-leave-to { opacity: 0; transform: translateY(20px); }

/* Panel Header */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* LIVE状态样式 */
.live-status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: rgba(103, 194, 58, 0.1);
  border: 1px solid #67C23A;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  color: #67C23A;
  animation: fadeIn 0.3s ease;
}

/* 呼吸灯效果 */
.pulse-dot {
  width: 8px;
  height: 8px;
  background: #67C23A;
  border-radius: 50%;
  animation: pulse 1.5s infinite ease-in-out;
  box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.4);
}

.pulse-dot.warning {
  background: #E6A23C;
  box-shadow: 0 0 0 0 rgba(230, 162, 60, 0.4);
}

.pulse-dot.closed {
  background: #F56C6C;
  animation: none;
  box-shadow: none;
}

.countdown-text {
  font-family: monospace;
  font-weight: 600;
}

/* 呼吸灯动画 */
@keyframes pulse {
  0% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.7);
  }
  70% {
    transform: scale(1.2);
    box-shadow: 0 0 0 10px rgba(103, 194, 58, 0);
  }
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(103, 194, 58, 0);
  }
}

/* 警告状态呼吸灯 */
.pulse-dot.warning {
  animation: pulse-warning 1.5s infinite ease-in-out;
}

@keyframes pulse-warning {
  0% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(230, 162, 60, 0.7);
  }
  70% {
    transform: scale(1.2);
    box-shadow: 0 0 0 10px rgba(230, 162, 60, 0);
  }
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(230, 162, 60, 0);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 自定义通知样式 */
.custom-notification-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-container {
  height: 4px;
  background-color: #f0f0f0;
  border-radius: 2px;
  overflow: hidden;
  margin-top: 8px;
  margin-bottom: 4px;
}

.progress-bar {
  height: 100%;
  background-color: #e6a23c;
  width: 0%;
  transition: width 0.3s ease;
}

.time-remaining {
  font-size: 12px;
  color: #606266;
  text-align: right;
}

/* ========== 新增：查看报文按钮样式 ========== */
.view-payload-btn {
  padding: 2px 8px !important;
  font-size: 11px !important;
  border-radius: 10px;
  background: rgba(64, 158, 255, 0.1);
  transition: all 0.2s ease;
}

.view-payload-btn:hover {
  background: rgba(64, 158, 255, 0.2);
  transform: scale(1.05);
}

/* ========== 新增：报文查看器弹出框样式 ========== */
.payload-viewer {
  max-height: 400px;
  display: flex;
  flex-direction: column;
}

.payload-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-weight: 700;
  font-size: 13px;
  border-radius: 8px 8px 0 0;
  margin: -12px -12px 12px -12px;
}

.payload-header.request {
  background: linear-gradient(135deg, #409EFF, #337ecc);
  color: #fff;
}

.payload-header.response {
  background: linear-gradient(135deg, #67C23A, #529b2e);
  color: #fff;
}

.payload-content-wrapper {
  flex: 1;
  overflow: auto;
  max-height: 280px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
}

.payload-content {
  margin: 0;
  padding: 12px;
  font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  color: #303133;
}

.payload-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
}

.payload-size {
  font-size: 11px;
  color: #909399;
  font-family: monospace;
}
</style>

<style>
/* 全局样式：Popover 弹出框优化 */
.payload-popover {
  border-radius: 12px !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12) !important;
}

.payload-popover .el-popover__title {
  display: none;
}
</style>