<template>
  <div class="topology-page">
    <!-- 1. 新的顶部导航栏 (增加磨砂玻璃效果) -->
    <div class="page-navbar">
      <div class="navbar-left">
        <div class="brand">
          <!-- 使用 DataLine 图标代表网络拓扑，配色蓝色系 -->
          <div class="logo-icon net-theme">
            <el-icon><DataLine /></el-icon>
          </div>
          <div class="brand-text">
            <h1>HTTP/HTTPS 协议拓扑深度分析</h1>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 内容包裹层 (用于保持原有的 padding 间距) -->
    <div class="content-wrapper">

    <!-- 控制面板 -->
    <el-card shadow="never" class="control-panel">
      <div class="control-group">
        <div class="control-item">
          <span class="label">协议版本：</span>
          <el-radio-group v-model="protocolVersion" @change="regenerateFlow" size="default">
            <el-radio-button label="HTTP/1.1">HTTP/1.1</el-radio-button>
            <el-radio-button label="HTTP/2">HTTP/2 (Multiplex)</el-radio-button>
            <el-radio-button label="HTTP/3">HTTP/3 (QUIC)</el-radio-button>
          </el-radio-group>
        </div>

        <div class="control-item">
          <span class="label">安全层：</span>
          <el-switch
            v-model="isHttps"
            active-text="HTTPS (TLS/SSL)"
            inactive-text="HTTP (Plain)"
            inline-prompt
            style="--el-switch-on-color: #7c3aed; --el-switch-off-color: #9ca3af"
            @change="regenerateFlow"
          />
        </div>

        <!-- TLS 版本选择 (仅在 HTTPS 且非 HTTP/3 时显示) -->
        <transition name="fade-slide">
          <div class="control-item" v-if="isHttps && protocolVersion !== 'HTTP/3'">
            <span class="label">TLS 版本：</span>
            <el-radio-group v-model="tlsVersion" @change="regenerateFlow" size="small">
              <el-radio-button label="SSLv3">SSL 3.0 (不安全)</el-radio-button>
              <el-radio-button label="TLS 1.2">TLS 1.2 (标准)</el-radio-button>
              <el-radio-button label="TLS 1.3">TLS 1.3 (极速)</el-radio-button>
            </el-radio-group>
          </div>
        </transition>

        <div class="control-item right-actions">
          <el-button type="primary" plain icon="Refresh" @click="regenerateFlow">重置演示</el-button>
          <el-button type="info" text icon="View" @click="viewRawData">查看原始定义</el-button>
        </div>
      </div>
      
      <!-- 安全风险分析摘要 -->
      <div class="protocol-summary">
        <el-alert
          :title="summaryTitle"
          :type="summaryType"
          :description="summaryDesc"
          show-icon
          :closable="false"
        >
          <template #default>
            <div class="security-note">
              <strong>安全分析：</strong> {{ securityAnalysis }}
            </div>
          </template>
        </el-alert>
      </div>
    </el-card>

    <!-- 拓扑主区域 -->
    <div class="topology-canvas">
      <!-- 背景网格 -->
      <div class="grid-bg"></div>

      <!-- 实体层：客户端 & 服务端 -->
      <div class="entities-layer">
        <!-- 客户端 -->
        <el-popover placement="right" :width="260" trigger="hover">
          <template #reference>
            <div class="entity client">
              <div class="entity-icon client-glow animated-pulse">
                <el-icon :size="40"><Monitor /></el-icon>
              </div>
              <div class="entity-info">
                <h3>客户端 (Client)</h3>
                <div class="ip-tag">192.168.1.105</div>
                <div class="port-tag">端口: {{ clientPort }}</div>
              </div>
              <div class="timeline-line"></div>
            </div>
          </template>
          <div class="entity-detail-card">
            <h4>客户端设备信息</h4>
            <p><strong>OS:</strong> Windows 11 Pro</p>
            <p><strong>Browser:</strong> Chrome 120.0.6099</p>
            <p><strong>Session:</strong> {{ hasSession ? 'Active (Cookie)' : 'None' }}</p>
          </div>
        </el-popover>

        <!-- 服务端 -->
        <el-popover placement="left" :width="260" trigger="hover">
          <template #reference>
            <div class="entity server">
              <div class="entity-icon server-glow animated-pulse">
                <el-icon :size="40"><DataLine /></el-icon>
              </div>
              <div class="entity-info">
                <h3>服务端 (Server)</h3>
                <div class="ip-tag">104.21.55.2</div>
                <div class="port-tag">端口: {{ isHttps ? 443 : 80 }}</div>
              </div>
              <div class="timeline-line"></div>
            </div>
          </template>
          <div class="entity-detail-card">
            <h4>源服务器信息</h4>
            <p><strong>Server:</strong> Nginx/1.24.0</p>
            <p><strong>Cert:</strong> {{ isHttps ? (tlsVersion === 'SSLv3' ? 'RSA 1024 (Weak)' : 'ECC P-256') : 'N/A' }}</p>
            <p><strong>Region:</strong> AWS US-East</p>
          </div>
        </el-popover>
      </div>

      <!-- 数据流层 -->
      <div class="flow-layer">
        <transition-group name="list-flow" tag="div">
          <div
            v-for="(packet, index) in flowData"
            :key="packet.id"
            class="packet-row-grid"
            :style="{ animationDelay: `${index * 0.05}s` }"
          >
            <!-- 左侧：客户端操作说明 -->
            <div class="side-action left-side">
              <div v-if="packet.cAction" class="action-note">
                <span class="note-text">{{ packet.cAction }}</span>
                <svg class="curved-arrow" viewBox="0 0 40 40">
                  <path d="M 30 0 Q 30 20 10 30" fill="none" stroke="#cbd5e1" stroke-width="2" marker-end="url(#arrowhead)" />
                </svg>
              </div>
              <div class="packet-meta left-meta">
                <span class="seq-num">#{{ index + 1 }}</span>
                <span class="time-delta">+{{ packet.delta }}ms</span>
              </div>
            </div>

            <!-- 中间：数据包箭头 -->
            <div class="packet-arrow-container">
              <el-popover
                placement="top"
                :width="340"
                trigger="hover"
                popper-class="packet-popper"
              >
                <template #reference>
                  <div class="arrow-body" :class="[packet.type, packet.direction]">
                    <!-- 标签 -->
                    <div class="packet-label">
                      <el-icon v-if="packet.encrypted" class="lock-icon"><Lock /></el-icon>
                      <span class="method">{{ packet.method }}</span>
                      <span class="info">{{ packet.info }}</span>
                    </div>
                    
                    <!-- 箭头线条 (根据类型展示不同动效) -->
                    <div class="line-graphic" :class="{ 'streamer-line': !packet.isData, 'particle-line': packet.isData }">
                      <!-- 仅数据包显示粒子 -->
                      <div v-if="packet.isData" class="moving-particle"></div>
                      <div class="arrow-head"></div>
                    </div>
                  </div>
                </template>

                <!-- 悬浮详情 -->
                <div class="packet-detail">
                  <div class="detail-header" :class="packet.type">
                    {{ packet.method }} - {{ packet.info }}
                  </div>
                  <div class="detail-grid">
                    <div class="d-item"><span>协议:</span> {{ packet.protocol }}</div>
                    <div class="d-item"><span>长度:</span> {{ packet.len }} bytes</div>
                    <div class="d-item" v-if="packet.seq"><span>Seq:</span> {{ packet.seq }}</div>
                    <div class="d-item" v-if="packet.ack"><span>Ack:</span> {{ packet.ack }}</div>
                    <div class="d-item full" v-if="packet.flags"><span>Flags:</span> {{ packet.flags }}</div>
                    <div class="d-item full highlight" v-if="packet.payload">
                      <span>Payload:</span> {{ packet.payload }}
                    </div>
                    <!-- Cookie 特别展示 -->
                    <div class="d-item full cookie-highlight" v-if="packet.cookieInfo">
                      <el-tag size="small" type="warning" effect="dark">Cookie</el-tag>
                      {{ packet.cookieInfo }}
                    </div>
                  </div>
                </div>
              </el-popover>
            </div>

            <!-- 右侧：服务端操作说明 -->
            <div class="side-action right-side">
              <div v-if="packet.sAction" class="action-note">
                <span class="note-text">{{ packet.sAction }}</span>
                 <svg class="curved-arrow mirror" viewBox="0 0 40 40">
                  <path d="M 10 0 Q 10 20 30 30" fill="none" stroke="#cbd5e1" stroke-width="2" marker-end="url(#arrowhead)" />
                </svg>
              </div>
            </div>

          </div>
        </transition-group>
      </div>

      <!-- 定义 SVG 箭头标记 -->
      <svg style="position: absolute; width: 0; height: 0; overflow: hidden;" aria-hidden="true">
        <defs>
          <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#cbd5e1" />
          </marker>
        </defs>
      </svg>

    </div>

  </div>

    <!-- 原始数据弹窗 -->
    <el-dialog v-model="jsonVisible" title="当前流原始结构 (JSON)" width="800px">
      <json-viewer :value="flowData" :expand-depth="2" copyable boxed sort></json-viewer>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { Monitor, DataLine, Lock, Refresh, View } from '@element-plus/icons-vue'
import JsonViewer from 'vue-json-viewer'
import 'vue-json-viewer/style.css'

// 状态
const protocolVersion = ref('HTTP/1.1')
const isHttps = ref(false)
const tlsVersion = ref('TLS 1.2') // SSLv3, TLS 1.2, TLS 1.3
const jsonVisible = ref(false)
const flowData = ref([])
const clientPort = ref(54321)
const hasSession = ref(false) // 模拟会话状态

// 摘要标题
const summaryTitle = computed(() => {
  let title = `${protocolVersion.value} `
  if (protocolVersion.value === 'HTTP/3') return 'HTTP/3 Over QUIC (Built-in TLS 1.3)'
  if (isHttps.value) return `${title} Over ${tlsVersion.value} (Secure)`
  return `${title} Over TCP (Insecure)`
})

const summaryType = computed(() => {
  if (!isHttps.value && protocolVersion.value !== 'HTTP/3') return 'error' // HTTP 不安全
  if (tlsVersion.value === 'SSLv3') return 'warning' // SSLv3 不推荐
  return 'success'
})

// 协议简介
const summaryDesc = computed(() => {
  if (protocolVersion.value === 'HTTP/3') return 'QUIC 协议基于 UDP，内置 TLS 1.3，实现 0-RTT/1-RTT 快速连接。'
  if (isHttps.value) return `使用 ${tlsVersion.value} 协议进行加密传输。`
  return '使用标准 TCP 传输，数据未加密。'
})

// 安全分析文案
const securityAnalysis = computed(() => {
  if (protocolVersion.value === 'HTTP/3') {
    return '✅ 极高安全性。QUIC 协议强制使用 TLS 1.3，且对握手包也进行了加密，有效防止中间人攻击和深度包检测(DPI)嗅探，支持前向保密(PFS)。'
  }
  if (!isHttps.value) {
    return '❌ 极度危险。所有数据（包括密码、Cookie）均以明文传输。在公共 Wi-Fi 下，攻击者可轻易通过嗅探工具截获您的会话 ID，导致账户被劫持。'
  }
  if (tlsVersion.value === 'SSLv3') {
    return '⚠️ 已废弃且不安全。SSL 3.0 存在 POODLE 等严重漏洞，无法提供现代加密保护。现代浏览器已完全禁用此协议。'
  }
  if (tlsVersion.value === 'TLS 1.2') {
    return '✅ 安全。当前行业标准。通过证书验证服务端身份，使用非对称加密交换密钥，再用对称加密传输数据。防止窃听和篡改。'
  }
  if (tlsVersion.value === 'TLS 1.3') {
    return '🚀 安全且高效。相比 1.2，它移除了不安全的加密算法，强制开启前向保密(PFS)，且握手仅需 1 个往返(1-RTT)，大幅降低延迟。'
  }
  return ''
})

// 核心：生成演示数据流
const regenerateFlow = async () => {
  flowData.value = []
  hasSession.value = false
  // 使用 nextTick 确保动画重置
  await nextTick()

  const flows = []
  let idCounter = 1
  let time = 0
  
  // 辅助函数
  const addPacket = (direction, type, method, info, details = {}, cAction = '', sAction = '') => {
    time += Math.floor(Math.random() * 10) + 5
    flows.push({
      id: idCounter++,
      direction: direction === 'c2s' ? 'c2s' : 's2c',
      type, // tcp, tls, http, quic
      method,
      info,
      delta: time,
      cAction, 
      sAction,
      isData: type === 'http' || (type === 'quic' && method === 'STREAM'), // 标记是否为数据传输包(用于粒子动画)
      encrypted: details.encrypted || false,
      protocol: details.protocol || 'TCP',
      len: details.len || 64,
      seq: details.seq,
      ack: details.ack,
      win: details.win || 65535,
      flags: details.flags,
      payload: details.payload,
      cookieInfo: details.cookieInfo
    })
  }

  // === 1. 连接建立 (TCP / QUIC) ===
  if (protocolVersion.value === 'HTTP/3') {
    // QUIC (UDP + TLS 1.3)
    addPacket('c2s', 'quic', 'QUIC', 'Initial (Client Hello)', 
      { protocol: 'UDP', len: 1280, encrypted: true, payload: 'TLS 1.3 ClientHello + KeyShare' },
      '生成 Client Hello', '解析初始包')
    
    addPacket('s2c', 'quic', 'QUIC', 'Handshake (Server Hello)', 
      { protocol: 'UDP', len: 1280, encrypted: true, payload: 'ServerHello + EncryptedExt + Cert + Verify' },
      '验证证书 & 密钥', '发送证书 & 密钥参数')
    
    addPacket('c2s', 'quic', 'QUIC', 'Handshake Done', 
      { protocol: 'UDP', len: 850, encrypted: true },
      '连接建立 (1-RTT)', '准备接收流数据')
  } else {
    // TCP 三次握手
    addPacket('c2s', 'tcp', 'SYN', 'Seq=0 Win=64240', 
      { flags: 'SYN', seq: 0, win: 64240 },
      '初始化 Socket (SYN_SENT)', '监听端口 80/443')
    
    addPacket('s2c', 'tcp', 'SYN, ACK', 'Seq=0 Ack=1 Win=29200', 
      { flags: 'SYN, ACK', seq: 0, ack: 1, win: 29200 },
      '处理 SYN 请求', '回复 SYN-ACK')
    
    addPacket('c2s', 'tcp', 'ACK', 'Seq=1 Ack=1 Win=64240', 
      { flags: 'ACK', seq: 1, ack: 1 },
      '连接已建立 (ESTABLISHED)', '更新 TCB 状态')
  }

  // === 2. TLS 握手 (根据版本不同) ===
  if (isHttps.value && protocolVersion.value !== 'HTTP/3') {
    if (tlsVersion.value === 'TLS 1.3') {
      // TLS 1.3 (高效 1-RTT)
      addPacket('c2s', 'tls', 'Client Hello', 'TLS 1.3 + Key Share', 
        { protocol: 'TLSv1.3', len: 512, payload: 'Cipher Suites, Random, KeyShare(X25519)' },
        '生成随机数 & 公钥', '协商加密套件')
      
      addPacket('s2c', 'tls', 'Server Hello', 'Change Cipher Spec', 
        { protocol: 'TLSv1.3', len: 1400, payload: 'ServerHello, EncryptedExtensions, Certificate, CertVerify, Finished' },
        '验证签名 & 完成握手', '发送证书 & 签名')
        
      // TLS 1.3 客户端发送 Finished 往往伴随第一条应用数据，这里简化展示
      addPacket('c2s', 'tls', 'Finished', 'Handshake Finished', 
        { protocol: 'TLSv1.3', len: 120, encrypted: true },
        '通道安全建立', '准备解密数据')

    } else if (tlsVersion.value === 'TLS 1.2') {
      // TLS 1.2 (标准 2-RTT)
      addPacket('c2s', 'tls', 'Client Hello', 'TLS 1.2', 
        { protocol: 'TLSv1.2', len: 256, payload: 'Random1, Cipher Suites' },
        '客户端发送 Hello', '协商加密算法')
      
      addPacket('s2c', 'tls', 'Server Hello', 'Certificate', 
        { protocol: 'TLSv1.2', len: 1024, payload: 'Random2, SessionID, Certificate Chain' },
        '验证服务端证书', '发送证书链')
        
      addPacket('s2c', 'tls', 'Server Key Exchange', 'Server Hello Done', 
        { protocol: 'TLSv1.2', len: 300, payload: 'EC Diffie-Hellman Params, Signature' },
        '获取密钥交换参数', '发送密钥参数')
      
      addPacket('c2s', 'tls', 'Client Key Exchange', 'Change Cipher Spec', 
        { protocol: 'TLSv1.2', len: 128, payload: 'Pre-Master Secret (Encrypted)' },
        '生成预主密钥', '计算会话密钥')
        
      addPacket('c2s', 'tls', 'Finished', 'Encrypted Handshake', 
        { protocol: 'TLSv1.2', len: 64, encrypted: true },
        '验证加密通道', '验证完整性')
        
      addPacket('s2c', 'tls', 'Finished', 'Encrypted Handshake', 
        { protocol: 'TLSv1.2', len: 64, encrypted: true },
        '握手完成', '通道就绪')

    } else {
      // SSLv3 / TLS 1.0 (旧版繁琐流程)
      addPacket('c2s', 'tls', 'Client Hello', 'SSL 3.0', 
        { protocol: 'SSLv3', len: 128, payload: 'Version 3.0, Random' },
        '尝试建立 SSL 连接', '检查协议版本')
      
      addPacket('s2c', 'tls', 'Server Hello', 'Certificate', 
        { protocol: 'SSLv3', len: 800, payload: 'Certificate (RSA)' },
        '解析 RSA 证书', '发送 RSA 证书')
      
      addPacket('s2c', 'tls', 'Server Hello Done', 'Wait for Client', 
        { protocol: 'SSLv3', len: 40 },
        '准备生成密钥', '握手阶段结束')
      
      addPacket('c2s', 'tls', 'Client Key Exchange', 'Pre-Master Secret', 
        { protocol: 'SSLv3', len: 256, payload: 'Encrypted with Server Public Key' },
        '加密传输预主密钥', 'RSA 解密获取密钥')
      
      addPacket('c2s', 'tls', 'Change Cipher Spec', 'Commit', 
        { protocol: 'SSLv3', len: 1 },
        '切换加密模式', '应用密钥')
        
      addPacket('c2s', 'tls', 'Finished', 'Hash Check', 
        { protocol: 'SSLv3', len: 64, encrypted: true },
        '发送握手哈希', '验证哈希')
        
      addPacket('s2c', 'tls', 'Change Cipher Spec', 'Commit', 
        { protocol: 'SSLv3', len: 1 },
        '切换加密模式', '应用密钥')
        
      addPacket('s2c', 'tls', 'Finished', 'Hash Check', 
        { protocol: 'SSLv3', len: 64, encrypted: true },
        '握手极其缓慢且危险', '通道建立(不安全)')
    }
  }

  // === 3. 应用数据 (HTTP) ===
  const isEncrypted = isHttps.value || protocolVersion.value === 'HTTP/3'
  
  // 3.1 第一次请求 (登录/获取页面)
  if (protocolVersion.value === 'HTTP/1.1') {
    addPacket('c2s', 'http', 'GET', '/login', 
      { protocol: 'HTTP/1.1', encrypted: isEncrypted, len: 450, payload: 'User-Agent: Chrome...' },
      '发送 HTTP 请求', '解析请求头')

    if (!isHttps.value) addPacket('s2c', 'tcp', 'ACK', 'Ack Segment', { seq: 1, ack: 451 }, '', '缓冲数据') 
    
    // 响应带 Set-Cookie
    addPacket('s2c', 'http', '200 OK', 'text/html', 
      { 
        protocol: 'HTTP/1.1', 
        encrypted: isEncrypted, 
        len: 1500, 
        payload: '<html>Login Success</html>',
        cookieInfo: 'Set-Cookie: session_id=xyz123; Secure; HttpOnly'
      },
      '保存会话 Cookie', '生成 Session ID')
    
    // 3.2 第二次请求 (带 Cookie)
    hasSession.value = true
    addPacket('c2s', 'http', 'GET', '/profile', 
      { 
        protocol: 'HTTP/1.1', 
        encrypted: isEncrypted, 
        len: 320,
        cookieInfo: 'Cookie: session_id=xyz123'
      },
      '携带凭证访问', '验证 Session')
    
    addPacket('s2c', 'http', '200 OK', 'application/json', 
      { protocol: 'HTTP/1.1', encrypted: isEncrypted, len: 800, payload: '{"user": "admin"}' },
      '渲染用户数据', '返回敏感数据')
  
  } else if (protocolVersion.value === 'HTTP/2') {
    // HTTP/2 演示
    addPacket('c2s', 'http', 'HEADERS', 'Stream 1: GET /', 
      { protocol: 'HTTP/2', encrypted: isEncrypted, payload: ':path: /' },
      '打开流 1', 'HPACK 解码')
    
    addPacket('s2c', 'http', 'HEADERS', 'Stream 1: 200 OK', 
      { protocol: 'HTTP/2', encrypted: isEncrypted, cookieInfo: 'set-cookie: sess=abc' },
      '保存 Cookie', '发送响应头')
    
    hasSession.value = true
    addPacket('s2c', 'http', 'DATA', 'Stream 1 Body', 
      { protocol: 'HTTP/2', encrypted: isEncrypted, len: 1024 },
      '处理页面', '推送数据帧')
      
    addPacket('c2s', 'http', 'HEADERS', 'Stream 3: GET /img', 
      { protocol: 'HTTP/2', encrypted: isEncrypted, cookieInfo: 'cookie: sess=abc' },
      '复用连接请求资源', '并发处理流 3')
  
  } else if (protocolVersion.value === 'HTTP/3') {
    // HTTP/3 演示
    addPacket('c2s', 'quic', 'HEADERS', 'Stream 0: GET /', 
      { protocol: 'HTTP/3', encrypted: true, len: 80 },
      'QPACK 编码请求', '解码流 0')
    
    addPacket('s2c', 'quic', 'HEADERS', 'Stream 0: 200 OK', 
      { protocol: 'HTTP/3', encrypted: true, len: 60, cookieInfo: 'set-cookie: token=jwt...' },
      '存储 Token', '发送响应头')
      
    hasSession.value = true
    addPacket('s2c', 'quic', 'STREAM', 'Stream 0: Data', 
      { protocol: 'HTTP/3', encrypted: true, len: 1200 },
      '接收加密负载', '发送 Body')
  }

  // === 4. 断开连接 (四次挥手) ===
  if (protocolVersion.value !== 'HTTP/3') {
    // 第一次挥手: 客户端发送 FIN, ACK
    addPacket('c2s', 'tcp', 'FIN, ACK', 'Seq=1000 Ack=2000 Win=64240', 
      { flags: 'FIN, ACK', seq: 1000, ack: 2000, win: 64240 },
      '发起关闭', '被动关闭')
    // 第二次挥手: 服务器发送 ACK
    addPacket('s2c', 'tcp', 'ACK', 'Seq=2000 Ack=1001 Win=29200', 
      { flags: 'ACK', seq: 2000, ack: 1001, win: 29200 },
      '连接关闭', '确认 FIN')
    // 第三次挥手: 服务器发送 FIN, ACK
    addPacket('s2c', 'tcp', 'FIN, ACK', 'Seq=2000 Ack=1001 Win=29200', 
      { flags: 'FIN, ACK', seq: 2000, ack: 1001, win: 29200 },
      '服务器关闭', '主动关闭')
    // 第四次挥手: 客户端发送 ACK
    addPacket('c2s', 'tcp', 'ACK', 'Seq=1001 Ack=2001 Win=64240', 
      { flags: 'ACK', seq: 1001, ack: 2001, win: 64240 },
      '连接终止', '确认关闭')
  }

  flowData.value = flows
}

const viewRawData = () => {
  jsonVisible.value = true
}

onMounted(() => {
  regenerateFlow()
})

// 监听配置变化自动刷新
watch([protocolVersion, isHttps, tlsVersion], () => {
  // 延迟极短，提升响应速度
  setTimeout(regenerateFlow, 10)
})
</script>

<style scoped>
/* ================= 全局布局修改 ================= */
.topology-page {
  background-color: #f8fafc;
  min-height: 100vh;
  /* 1. 去掉原来的 padding: 20px 40px; 改为 0，让 Header 可以全宽 */
  padding: 0;
  color: #334155;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  display: flex;
  flex-direction: column;
}

/* 2. 新增 content-wrapper 来恢复原来内容的间距 */
.content-wrapper {
  padding: 24px 40px; /* 这里恢复原有的内边距 */
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* ================= 顶部导航栏 (磨砂玻璃效果) ================= */
.page-navbar {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px); /* 磨砂玻璃效果 */
  padding: 0 30px;
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid rgba(0,0,0,0.05);
  height: 60px; flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03); /* 轻微阴影增加层次 */
  position: sticky; top: 0; z-index: 100;
}

.navbar-left { display: flex; align-items: center; gap: 16px; }

/* 返回按钮样式 */
.back-btn {
  color: #64748b;
  padding: 0;
  height: 32px; width: 32px;
  border-radius: 50%;
}
.back-btn:hover { background: #f1f5f9; color: #3b82f6; }

.brand { display: flex; align-items: center; gap: 12px; }

.logo-icon {
  width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: white; font-size: 20px;
}

/* 定义拓扑专属主题色 (蓝色渐变) */
.logo-icon.net-theme {
  background: linear-gradient(135deg, #0ea5e9, #2563eb);
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.2);
}

.brand-text h1 { margin: 0; font-size: 16px; color: #1e293b; font-weight: 600; }

.header-tag { font-weight: 500; letter-spacing: 0.5px; }

/* ================= 控制面板 ================= */
.control-panel {
  margin-bottom: 30px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: white;
}

.control-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 30px;
  margin-bottom: 20px;
}

.control-item { display: flex; align-items: center; gap: 12px; }
.label { font-weight: 600; font-size: 14px; color: #64748b; }
.right-actions { margin-left: auto; }

/* 切换动画 */
.fade-slide-enter-active, .fade-slide-leave-active { transition: all 0.3s ease; }
.fade-slide-enter-from, .fade-slide-leave-to { opacity: 0; transform: translateX(-10px); }

/* 安全提示 */
.security-note { font-size: 13px; color: #334155; line-height: 1.5; }

/* ================= 拓扑画布 ================= */
.topology-canvas {
  position: relative;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  padding: 40px 0;
  min-height: 600px;
  overflow: hidden;
  border: 1px solid #f1f5f9;
}

.grid-bg {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(#f1f5f9 1px, transparent 1px), linear-gradient(90deg, #f1f5f9 1px, transparent 1px);
  background-size: 40px 40px;
  opacity: 0.5;
  z-index: 0;
}

/* ================= 实体层 ================= */
.entities-layer {
  display: flex;
  justify-content: space-between;
  padding: 0 15%; 
  position: relative;
  z-index: 2;
  margin-bottom: 40px;
}

.entity {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  width: 140px;
  cursor: help;
}

.entity-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-bottom: 12px;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
  position: relative;
}

.client-glow { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.server-glow { background: linear-gradient(135deg, #10b981, #059669); }

.animated-pulse { animation: pulse-glow 3s infinite; }
@keyframes pulse-glow {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
  50% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}
.server-glow.animated-pulse { animation-name: pulse-glow-green; }
@keyframes pulse-glow-green {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
  50% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.entity:hover .entity-icon { transform: translateY(-5px) scale(1.05); }

.entity-info {
  text-align: center;
  background: rgba(255,255,255,0.95);
  padding: 8px;
  border-radius: 8px;
  backdrop-filter: blur(2px);
  z-index: 2;
}

.entity-info h3 { margin: 0 0 4px 0; font-size: 15px; font-weight: 700; }
.ip-tag { font-family: 'Monaco', monospace; font-size: 12px; color: #64748b; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; margin-bottom: 2px; }
.port-tag { font-size: 11px; color: #94a3b8; }

.entity-detail-card h4 { margin: 0 0 8px 0; color: #1e293b; }
.entity-detail-card p { margin: 4px 0; font-size: 13px; color: #64748b; }

.timeline-line {
  position: absolute;
  top: 100px;
  left: 50%;
  bottom: -10000px;
  width: 2px;
  background: repeating-linear-gradient(to bottom, #cbd5e1 0, #cbd5e1 6px, transparent 6px, transparent 12px);
  transform: translateX(-50%);
  z-index: -1;
}

/* ================= 数据流层 ================= */
.flow-layer {
  position: relative;
  z-index: 10;
  padding: 0 15%; 
  margin-top: 20px;
}

.packet-row-grid {
  display: grid;
  grid-template-columns: 140px 1fr 140px; 
  align-items: center;
  margin-bottom: 28px;
  position: relative;
  opacity: 0;
  animation: fadeIn 0.3s forwards; /* 加快淡入速度 */
}

.side-action {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.left-side { text-align: right; padding-right: 16px; }
.right-side { text-align: left; padding-left: 16px; }

.action-note {
  position: relative;
  font-size: 12px;
  color: #64748b;
  background: #fff;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  display: inline-block;
  white-space: nowrap;
}

.curved-arrow { position: absolute; width: 20px; height: 20px; bottom: -22px; opacity: 0.6; }
.left-side .curved-arrow { right: 0; }
.right-side .curved-arrow { left: 0; }
.mirror { transform: scaleX(-1); }

.packet-meta { font-size: 10px; color: #94a3b8; font-family: monospace; margin-top: 4px; }

.packet-arrow-container {
  position: relative;
  width: 100%;
  margin: 0 -1px; 
  display: flex;
  justify-content: center;
}

.arrow-body {
  position: relative;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  width: 100%;
}
.arrow-body:hover { transform: scaleY(1.1); }

.packet-label {
  position: absolute;
  top: -20px;
  background: white;
  padding: 2px 10px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  z-index: 5;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  display: flex;
  align-items: center;
  gap: 6px;
}

.line-graphic {
  width: 100%;
  height: 2px;
  position: relative;
  overflow: visible;
}

.arrow-head {
  position: absolute;
  width: 0;
  height: 0;
  top: -5px;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
}

/* ====== 动效：握手流光 (Streamer) ====== */
.streamer-line {
  background: linear-gradient(90deg, transparent, currentColor, transparent);
  background-size: 200% 100%;
  animation: streamer-flow 1.5s linear infinite;
}
@keyframes streamer-flow {
  0% { background-position: 100% 0; opacity: 0.5; }
  50% { opacity: 1; }
  100% { background-position: -100% 0; opacity: 0.5; }
}

/* ====== 动效：数据粒子 (Particle) ====== */
.particle-line {
  /* 基础线 */
  background: currentColor; 
  opacity: 0.3;
}
.moving-particle {
  position: absolute;
  top: -2px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: currentColor;
  box-shadow: 0 0 8px currentColor;
  opacity: 1;
  z-index: 2;
}

/* C2S: 左 -> 右 */
.c2s .arrow-head { right: -1px; border-left: 10px solid currentColor; }
.c2s .packet-label { border-color: currentColor; color: currentColor; }
.c2s .moving-particle { animation: particle-move-right 1.5s ease-in-out infinite; }

/* S2C: 右 -> 左 */
.s2c .arrow-head { left: -1px; border-right: 10px solid currentColor; }
.s2c .packet-label { border-color: currentColor; color: currentColor; }
.s2c .moving-particle { animation: particle-move-left 1.5s ease-in-out infinite; }

@keyframes particle-move-right {
  0% { left: 0; }
  50% { left: 100%; }
  100% { left: 0; }
}
@keyframes particle-move-left {
  0% { right: 0; }
  50% { right: 100%; }
  100% { right: 0; }
}

/* 颜色定义 */
.tcp { color: #3b82f6; }
.tcp .line-graphic { height: 1px; border-bottom: 1px dashed currentColor; background: none; } /* TCP 保持虚线 */
.tls { color: #8b5cf6; }
.tls .line-graphic { height: 3px; }
.http { color: #10b981; }
.http .line-graphic { height: 3px; }
.quic { color: #f97316; }
.quic .line-graphic { height: 3px; }

.lock-icon { font-size: 12px; }

/* 详情 Popover */
.packet-detail { font-size: 13px; }
.detail-header { font-weight: bold; padding-bottom: 8px; border-bottom: 1px solid #eee; margin-bottom: 8px; }
.detail-header.tcp { color: #3b82f6; }
.detail-header.tls { color: #8b5cf6; }
.detail-header.http { color: #10b981; }
.detail-header.quic { color: #f97316; }

.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.d-item span { color: #94a3b8; margin-right: 4px; }
.d-item.full { grid-column: span 2; }
.cookie-highlight { margin-top: 4px; border-top: 1px dashed #e2e8f0; padding-top: 4px; color: #d97706; }

@keyframes fadeIn { to { opacity: 1; } }
</style>