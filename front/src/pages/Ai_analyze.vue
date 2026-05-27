<template>
  <div class="analysis-page">
    <!-- 顶部导航栏 (保持风格一致) -->
    <div class="page-navbar">
      <div class="brand">
        <div class="logo-icon ai-theme">
          <el-icon><Cpu /></el-icon>
        </div>
        <div class="brand-text">
          <h1>智能协议分析中心</h1>
        </div>
      </div>
    </div>

    <el-row :gutter="24" class="main-content">

      <!-- 左侧：AI 分析对话区 -->
      <el-col :span="10" :xs="24" class="col-left">
        <el-card shadow="never" class="chat-panel glass-panel">
          <template #header>
            <div class="panel-header">
              <span class="title"><el-icon><ChatDotRound /></el-icon> 分析报告 (AI Agent)</span>
              <el-tag v-if="analyzing" type="success" size="small" effect="dark" class="status-tag">
                <span class="pulse-dot"></span> Generating...
              </el-tag>
            </div>
          </template>

          <div class="chat-container" ref="chatContainer">
            <!-- 欢迎/空状态 -->
            <div v-if="!messages.length" class="empty-state">
              <el-icon class="empty-icon"><MagicStick /></el-icon>
              <p>点击“开始深度分析”以生成报告</p>
            </div>

            <!-- 消息列表 -->
            <div v-for="(msg, index) in messages" :key="index" class="message-wrapper" :class="msg.role">
              <div class="avatar">
                <el-icon v-if="msg.role === 'ai'"><Cpu /></el-icon>
                <el-icon v-else><UserFilled /></el-icon>
              </div>
              <div class="message-bubble">
                <div class="sender-name">{{ msg.role === 'ai' ? 'Protocol Analyst AI' : 'User' }}</div>
                <!-- 这里可以使用 v-html 配合 marked 库渲染 markdown，此处仅做样式模拟 -->
                <div class="bubble-content markdown-body" v-html="formatMessage(msg.content)"></div>
                <div class="cursor" v-if="msg.role === 'ai' && index === messages.length - 1 && analyzing"></div>
              </div>
            </div>
          </div>

          <!-- 底部操作区 -->
          <div class="chat-footer">
            <el-button
              type="primary"
              class="analyze-btn shadow-btn"
              :loading="analyzing"
              @click="startAnalysis"
              round
              block
            >
              <el-icon><VideoPlay /></el-icon>
              {{ analyzing ? '正在分析中...' : '生成分析报告' }}
            </el-button>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：报文上下文 (Request & Response) -->
      <el-col :span="14" :xs="24" class="col-right">
        <div class="context-container">

          <!-- 请求报文卡片 -->
          <div class="context-card glass-panel mb-4">
            <div class="editor-bar">
              <span class="dot red"></span>
              <span class="dot yellow"></span>
              <span class="dot green"></span>
              <span class="editor-lang">Request Packet</span>
            </div>
            <div class="code-viewer-wrapper">
              <el-input
                v-model="requestContent"
                type="textarea"
                readonly
                class="code-input dark-theme-input"
                resize="none"
              />
            </div>
          </div>

          <!-- 响应报文卡片 -->
          <div class="context-card glass-panel">
            <div class="editor-bar">
              <span class="dot red"></span>
              <span class="dot yellow"></span>
              <span class="dot green"></span>
              <span class="editor-lang">Response Packet</span>
            </div>
            <div class="code-viewer-wrapper">
              <el-input
                v-model="responseContent"
                type="textarea"
                readonly
                class="code-input dark-theme-input"
                resize="none"
              />
            </div>
          </div>

        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import {
  Cpu, UserFilled, MagicStick, VideoPlay, ChatDotRound
} from '@element-plus/icons-vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

// --- Props: 接收从父组件传来的报文 (保留作为备用) ---
const props = defineProps({
  initialRequest: { type: String, default: '' },
  initialResponse: { type: String, default: '' }
})

// --- 核心状态 ---
// 初始化时优先使用 Props，没有则使用空字符串
const requestContent = ref(props.initialRequest || '')
const responseContent = ref(props.initialResponse || '')

// --- Chat Logic ---
const analyzing = ref(false)
const messages = ref([])
const chatContainer = ref(null)

// =======================================================
// 【核心修改】：页面加载时自动读取 LocalStorage
// =======================================================
onMounted(() => {
  // 1. 尝试从 LocalStorage 读取 SimulationPage 存入的数据
  const syncedReq = localStorage.getItem('auto_sync_request')
  const syncedRes = localStorage.getItem('auto_sync_response')

  // 2. 如果存在同步数据，覆盖当前的默认值
  if (syncedReq) {
    requestContent.value = syncedReq
  }

  if (syncedRes) {
    responseContent.value = syncedRes
  }
})

// --- 格式化与交互逻辑 ---

const formatMessage = (text) => {
  if (!text) return ''
  // 先转义 HTML 特殊字符，防止 XSS
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
  // 再应用 Markdown 格式化
  html = html
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
    .replace(/`(.*?)`/g, '<code class="inline-code">$1</code>')
    .replace(/### (.*?)<br>/g, '<h3>$1</h3>')
    .replace(/&gt; (.*?)<br>/g, '<blockquote class="ai-quote">$1</blockquote>')
  return html
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

const typeWriterEffect = async (fullText) => {
  const currentMsgIndex = messages.value.length - 1
  let currentText = ''
  const chars = fullText.split('')

  for (let i = 0; i < chars.length; i++) {
    currentText += chars[i]
    messages.value[currentMsgIndex].content = currentText
    scrollToBottom()
    await new Promise(r => setTimeout(r, Math.random() * 20 + 10))
  }
}

const startAnalysis = async () => {
  if (analyzing.value) return

  analyzing.value = true
  messages.value = [] // 清空旧消息

  // 1. 发送用户指令
  messages.value.push({
    role: 'user',
    content: '请分析右侧的 HTTP 请求与响应报文，重点关注安全字段。'
  })

  await new Promise(r => setTimeout(r, 600))

  // 2. 初始化 AI 回复占位
  messages.value.push({
    role: 'ai',
    content: ''
  })

  try {
    // 3. 调用真实后端 API
    // 确保这里的参数名 request_msg 和 response_msgs 与后端接收的一致
    const res = await request.post('/api/analyze_interaction', {
      request_msg: requestContent.value,
      response_msgs: responseContent.value
    }, { timeout: 60000 })

    // request.js 拦截器已处理 code !== 200 的情况
    await typeWriterEffect(res.data.analysis)

  } catch (e) {
    // 4. 如果网络请求失败 (例如 404 接口没找到，或者后端没启动)
    // 【修改点】：不再显示 Mock 数据，而是显示真实错误，方便调试
    console.error("API Error:", e)
    let errorMsg = "请求失败"
    if (e.response && e.response.status === 404) {
      errorMsg = "错误 404: 后端 app.py 中未找到 /api/analyze_interaction 接口"
    } else {
      errorMsg = "网络错误: " + e.message
    }
    messages.value[1].content = "⚠️ " + errorMsg
  } finally {
    analyzing.value = false
  }
}
</script>

<style scoped>
/* 全局布局与背景 (复用之前风格) */
.analysis-page {
  background: linear-gradient(135deg, #f0f5fa 0%, #e6eef5 100%);
  height: 100vh;
  display: flex; flex-direction: column;
  overflow: hidden;
  font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

.page-navbar {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  padding: 0 30px;
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid rgba(0,0,0,0.05);
  height: 60px; flex-shrink: 0;
}
.brand { display: flex; align-items: center; gap: 12px; }
.logo-icon {
  width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
  color: white; font-size: 20px;
}
.logo-icon.ai-theme { background: linear-gradient(135deg, #8e44ad, #9b59b6); /* 紫色系代表 AI */ }
.brand-text h1 { margin: 0; font-size: 16px; color: #1a1a1a; }
.subtitle { font-size: 10px; color: #909399; display: block; }

/* 布局网格 */
.main-content { padding: 20px; flex: 1; margin: 0 !important; height: calc(100vh - 60px); }
.col-left, .col-right { height: 100%; display: flex; flex-direction: column; }

/* 玻璃拟态面板通用 */
.glass-panel {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

/* --- 左侧聊天面板样式 --- */
.chat-panel {
  display: flex; flex-direction: column;
  height: 100%;
}
.chat-panel :deep(.el-card__header) { padding: 15px 20px; border-bottom: 1px solid #ebeef5; }
.chat-panel :deep(.el-card__body) { padding: 0; display: flex; flex-direction: column; flex: 1; overflow: hidden; }

.panel-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 700; color: #303133; font-size: 14px; display: flex; align-items: center; gap: 6px; }

.chat-container {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: #f9fafc;
  display: flex; flex-direction: column; gap: 20px;
}

.empty-state {
  height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #909399;
}
.empty-icon { font-size: 48px; margin-bottom: 10px; color: #dcdfe6; }

/* 消息气泡 */
.message-wrapper {
  display: flex; gap: 12px; max-width: 95%;
  animation: slideIn 0.3s ease;
}
.message-wrapper.user { align-self: flex-end; flex-direction: row-reverse; }

.avatar {
  width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff;
  flex-shrink: 0; font-size: 16px;
}
.message-wrapper.ai .avatar { background: linear-gradient(135deg, #8e44ad, #9b59b6); box-shadow: 0 3px 8px rgba(142, 68, 173, 0.3); }
.message-wrapper.user .avatar { background: linear-gradient(135deg, #409EFF, #66b1ff); }

.message-bubble {
  background: #fff; padding: 12px 16px; border-radius: 12px; border-top-left-radius: 2px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.03); border: 1px solid #eee;
  font-size: 13px; line-height: 1.6; color: #303133; position: relative;
}
.message-wrapper.user .message-bubble {
  background: #409EFF; color: #fff; border: none; border-radius: 12px; border-top-right-radius: 2px;
}
.message-wrapper.user .sender-name { display: none; }

.sender-name { font-size: 10px; color: #909399; margin-bottom: 4px; font-weight: 600; }

/* Markdown 模拟样式 */
.bubble-content :deep(h3) { margin: 10px 0 6px 0; font-size: 14px; color: #303133; }
.bubble-content :deep(ul) { margin: 0; padding-left: 18px; }
.bubble-content :deep(li) { margin-bottom: 4px; }
.bubble-content :deep(.inline-code) {
  background: rgba(0,0,0,0.06); padding: 2px 4px; border-radius: 4px; font-family: monospace; color: #c7254e; font-size: 12px;
}
.bubble-content :deep(.ai-quote) {
  border-left: 3px solid #67C23A; background: #f0f9eb; padding: 8px; margin: 8px 0; border-radius: 0 4px 4px 0; color: #5e6d82;
}

/* 光标动画 */
.cursor {
  display: inline-block; width: 6px; height: 14px; background: #303133; margin-left: 4px; vertical-align: middle;
  animation: blink 1s infinite;
}

.chat-footer {
  padding: 15px 20px; background: #fff; border-top: 1px solid #ebeef5;
}
.analyze-btn { font-weight: 600; }
.shadow-btn { box-shadow: 0 4px 12px rgba(142, 68, 173, 0.2); border: none; background: linear-gradient(135deg, #8e44ad, #9b59b6); }
.shadow-btn:hover { background: linear-gradient(135deg, #9b59b6, #a569bd); opacity: 0.9; }

/* --- 右侧上下文面板样式 --- */
.context-container { height: 100%; display: flex; flex-direction: column; gap: 16px; }

.context-card {
  flex: 1; display: flex; flex-direction: column;
}
.mb-4 { margin-bottom: 0; /* Flex grow handles height */ }

.editor-bar {
  background: #f5f7fa; padding: 8px 12px; border-bottom: 1px solid #dcdfe6;
  display: flex; align-items: center; gap: 6px; flex-shrink: 0;
}
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dot.red { background: #ff5f56; border: 1px solid #e0443e; }
.dot.yellow { background: #ffbd2e; border: 1px solid #dea123; }
.dot.green { background: #27c93f; border: 1px solid #1aab29; }
.editor-lang { margin-left: 8px; font-size: 11px; color: #606266; font-weight: 600; }
.protocol-tag { margin-left: auto; font-family: monospace; font-weight: 700; }

.code-viewer-wrapper { flex: 1; overflow: hidden; position: relative; }
.code-input { height: 100%; }
.code-input :deep(.el-textarea__inner) {
  height: 100% !important; border: none; border-radius: 0; padding: 12px;
  background: #282c34; color: #abb2bf; font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px; line-height: 1.5; resize: none; box-shadow: none;
}
.code-input :deep(.el-textarea__inner):focus { box-shadow: none; }

/* 动画 */
@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
@keyframes pulse {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.5); opacity: 0.5; }
  100% { transform: scale(1); opacity: 1; }
}
.pulse-dot { display: inline-block; width: 6px; height: 6px; background: #fff; border-radius: 50%; animation: pulse 1s infinite; margin-right: 4px; }
</style>