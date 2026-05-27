<template>
  <div class="security-simulation-page">
    <div class="page-navbar">
      <div class="brand">
        <div class="logo-icon security-theme">
          <el-icon><Lock /></el-icon>
        </div>
        <div class="brand-text">
          <h1>安全仿真实验室</h1>
        </div>
      </div>
      <div class="navbar-actions">
        <el-tag type="primary" effect="dark" round size="small" class="env-tag">
          <el-icon v-if="isGlobalLoading" class="is-loading"><Loading /></el-icon>
          <span v-else>Connected</span>
        </el-tag>
      </div>
    </div>
    
    <div class="main-content">
      <el-card shadow="never" class="simulation-card-container">
        <el-tabs v-model="activeTab" type="border-card" class="custom-tabs">
          
          <!-- Tab 1: 请求劫持 -->
          <el-tab-pane name="hijack">
            <template #label>
              <span class="custom-tab-label">
                <el-icon><Aim /></el-icon>
                <span>请求劫持模拟</span>
              </span>
            </template>

            <div class="tab-content-wrapper">
              <div class="scenario-title">
                <el-icon class="mr-2"><WarnTriangleFilled /></el-icon> 中间人攻击 (MITM) 链路仿真
              </div>
              <p class="scenario-desc">
                模拟数据流经恶意代理节点的完整过程。攻击者可在链路中拦截请求、篡改数据或窃取凭证。
              </p>

              <div class="hijack-grid-container">
                <!-- 节点：客户端 -->
                <div class="node-card client-card">
                  <div class="node-header">
                    <el-icon><User /></el-icon> 客户端 (Victim)
                  </div>
                  <div class="node-body">
                    <el-form label-position="top" size="small">
                      <el-form-item label="目标 URL">
                        <el-input v-model="hijackForm.targetUrl" placeholder="https://..." />
                      </el-form-item>
                       <el-form-item label="原始请求数据 (JSON)">
                         <el-input 
                            v-model="hijackForm.clientMessage" 
                            type="textarea" 
                            :rows="4" 
                            resize="none"
                         />
                       </el-form-item>
                    </el-form>
                    <div class="node-footer">
                      <span class="status-dot"></span> 准备就绪
                    </div>
                  </div>
                </div>

                <!-- 箭头 -->
                <div class="flow-arrow">
                  <div class="arrow-line"></div>
                  <el-icon><Right /></el-icon>
                </div>

                <!-- 节点：攻击者 -->
                <div class="node-card attacker-card">
                  <div class="node-header">
                    <el-icon><Hide /></el-icon> 中间人 (Attacker)
                    <el-tag type="danger" effect="dark" size="small" class="attacker-tag">INTERCEPTING</el-tag>
                  </div>
                  <div class="node-body">
                    <el-form :model="hijackForm" label-position="top" size="small">
                      <el-form-item label="攻击策略">
                        <el-radio-group v-model="hijackForm.hijackType" class="w-full">
                          <el-radio-button label="mitm">数据篡改</el-radio-button>
                          <el-radio-button label="session">Cookie窃取</el-radio-button>
                        </el-radio-group>
                      </el-form-item>
                      <el-form-item label="注入 Payload">
                        <el-input
                          v-model="hijackForm.hijackContent"
                          type="textarea"
                          :rows="4"
                          resize="none"
                          class="code-input"
                          placeholder="修改后的恶意数据..."
                        />
                      </el-form-item>
                      <el-button 
                        type="danger" 
                        :loading="hijackLoading" 
                        class="attack-btn"
                        @click="runHijackSimulation"
                      >
                        <el-icon class="mr-1"><VideoPlay /></el-icon> 执行拦截并转发
                      </el-button>
                    </el-form>
                  </div>
                </div>

                <!-- 箭头 -->
                <div class="flow-arrow dashed">
                  <div class="arrow-line"></div>
                  <el-icon><Right /></el-icon>
                </div>

                <!-- 节点：服务端 -->
                <div class="node-card server-card">
                  <div class="node-header">
                    <el-icon><Platform /></el-icon> 服务器 (Server)
                  </div>
                  <div class="node-body server-body-layout">
                    <div v-if="!hijackResult" class="server-idle">
                      <div class="pulse-ring"></div>
                      <el-icon class="idle-icon"><Connection /></el-icon>
                      <span>监听端口 8080...</span>
                    </div>
                    <div v-else class="server-result-content">
                      <div class="alert-box error">
                        <strong>DATA COMPROMISED</strong>
                        <span>数据已被篡改</span>
                      </div>
                      
                      <div class="data-group">
                        <label>Received Body:</label>
                        <div class="code-box">{{ hijackResult.server_received?.body || 'Empty' }}</div>
                      </div>
                      
                      <div class="data-group">
                        <label>Source IP:</label>
                        <div class="mono-text">{{ hijackResult.server_received?.source_ip }}</div>
                      </div>
                      
                      <div class="json-wrapper">
                         <JsonViewer 
                          :value="hijackResult" 
                          :expand-depth="0" 
                          boxed 
                          theme="jv-light"
                          style="font-size: 11px;"
                        />
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </div>
          </el-tab-pane>
          
          <!-- Tab 2: 证书伪造 -->
          <el-tab-pane name="cert-forge">
            <template #label>
              <span class="custom-tab-label">
                <el-icon><Key /></el-icon>
                <span>证书伪造实验室</span>
              </span>
            </template>

            <div class="tab-content-wrapper cert-layout-grid">
              <!-- 左侧：控制面板 -->
              <div class="cert-left-panel">
                <div class="panel-card">
                  <div class="panel-header-line">
                    <span class="bold-title">1. 证书构造器 (Forge Params)</span>
                  </div>
                  <el-form :model="certForgeForm" label-position="top" size="default">
                    <el-form-item label="目标域名 (Common Name)">
                      <el-input v-model="certForgeForm.domain" placeholder="www.google.com">
                        <template #prefix><el-icon><Link /></el-icon></template>
                      </el-input>
                    </el-form-item>
                    
                    <div class="form-row-2">
                      <el-form-item label="伪造类型">
                        <el-select v-model="certForgeForm.forgeType" @change="handleForgeTypeChange">
                          <el-option label="自签名 (Self-Signed)" value="self-signed" />
                          <el-option label="虚假 CA (Fake CA)" value="ca" />
                          <el-option label="过期证书 (Expired)" value="expired" />
                          <el-option label="弱加密 (Weak Key)" value="weak" />
                        </el-select>
                      </el-form-item>
                      <el-form-item label="有效期 (天)">
                        <el-input-number v-model="certForgeForm.validityDays" :min="1" controls-position="right" style="width: 100%" />
                      </el-form-item>
                    </div>

                    <div class="form-row-2" v-if="certForgeForm.forgeType === 'weak'">
                      <el-form-item label="密钥长度">
                        <el-select v-model="certForgeForm.keySize">
                          <el-option label="512 bits (极弱)" value="512" />
                          <el-option label="1024 bits (弱)" value="1024" />
                        </el-select>
                      </el-form-item>
                    </div>

                    <el-form-item label="组织信息 (O/C)">
                      <div class="flex gap-2">
                        <el-input v-model="certForgeForm.organization" placeholder="Org Name" />
                        <el-input v-model="certForgeForm.country" placeholder="CN" style="width: 80px;" maxlength="2" />
                      </div>
                    </el-form-item>

                    <el-button type="primary" :loading="certLoading" @click="runCertForgeSimulation" class="w-full mt-4">
                      <el-icon class="mr-1"><Tools /></el-icon> 生成恶意证书
                    </el-button>
                  </el-form>
                </div>
              </div>

              <!-- 右侧：结果与验证 -->
              <div class="cert-right-panel">
                <div class="panel-card flex-1">
                  <div class="panel-header-line space-between">
                    <span class="bold-title">2. 证书仓库 (Certificate Store)</span>
                    <el-button link icon="Refresh" type="primary" @click="fetchGeneratedCerts">刷新</el-button>
                  </div>
                  <el-table 
                    :data="generatedCerts" 
                    height="280" 
                    style="width: 100%" 
                    size="small"
                    highlight-current-row
                    @current-change="handleCertSelect"
                    border
                  >
                    <el-table-column width="45" align="center">
                      <template #default="scope">
                         <div class="radio-circle" :class="{active: selectedCert?.certificate_filename === scope.row.certificate_filename}"></div>
                      </template>
                    </el-table-column>
                    <el-table-column prop="certificate_filename" label="文件名" min-width="180" show-overflow-tooltip />
                    <el-table-column prop="certificate_type" label="类型" width="110">
                      <template #default="scope">
                        <el-tag size="small" :type="getCertTypeTag(scope.row.certificate_type)" effect="plain">
                          {{ scope.row.certificate_type }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" width="70" align="center">
                      <template #default="scope">
                        <el-button link type="primary" size="small" @click.stop="viewCertDetails(scope.row)">查看</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>

                <div class="panel-card mt-4">
                  <div class="panel-header-line">
                    <span class="bold-title">3. 证书真实性验证 (Verification)</span>
                  </div>
                  <div class="verify-layout">
                     <div class="verify-action-col">
                        <p class="hint-text">选中上方证书，模拟客户端验证逻辑</p>
                        <div class="btn-group-v">
                          <el-button 
                            type="success" 
                            plain
                            :disabled="!selectedCert" 
                            :loading="verifyLoading" 
                            @click="verifyCertificate"
                            class="w-full"
                          >
                            <el-icon class="mr-1"><Search /></el-icon> 验证安全性
                          </el-button>
                          <el-button v-if="certVerifyResult" icon="Delete" text bg @click="clearVerifyResult" class="w-full mt-2">清除</el-button>
                        </div>
                     </div>
                     
                     <div class="verify-result-col">
                        <div v-if="!certVerifyResult" class="placeholder-box">
                          <el-icon size="32"><Monitor /></el-icon>
                          <span>等待验证...</span>
                        </div>
                        <div v-else class="result-box" :class="certVerifyResult.verification_status">
                           <div class="result-header">
                             <el-icon v-if="certVerifyResult.verification_status === 'secure'" size="20"><Select /></el-icon>
                             <el-icon v-else size="20"><CloseBold /></el-icon>
                             <span class="status-text">{{ getVerifyResultText(certVerifyResult.verification_status) }}</span>
                           </div>
                           <el-divider style="margin: 8px 0" />
                           <div class="result-grid">
                             <div class="r-item"><span>Issuer:</span> {{ certVerifyResult.issuer }}</div>
                             <div class="r-item"><span>Chain:</span> {{ certVerifyResult.is_chain_complete ? 'Complete' : 'Broken' }}</div>
                             <div class="r-item"><span>Algorithm:</span> {{ certVerifyResult.signature_algorithm }}</div>
                             <div class="r-item"><span>Self-Signed:</span> {{ certVerifyResult.is_self_signed ? 'Yes' : 'No' }}</div>
                           </div>
                        </div>
                     </div>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- Tab 3: TLS 1.3 协议分析 (优化布局：上报文下详情) -->
          <el-tab-pane name="tls13">
            <template #label>
              <span class="custom-tab-label">
                <el-icon><Monitor /></el-icon>
                <span>TLS 1.3 协议分析</span>
              </span>
            </template>
            
            <div class="tab-content-wrapper tls-layout-container">
              <!-- 左侧：控制台 & 参数 -->
              <div class="tls-control-sidebar">
                <div class="sidebar-section">
                  <div class="sidebar-title">仿真控制台</div>
                  <div class="sidebar-body">
                    <label class="input-label">传输密文 (Secret Message)</label>
                    <el-input 
                      v-model="tlsForm.message" 
                      type="textarea" 
                      :rows="3" 
                      placeholder="输入需要加密传输的敏感数据..." 
                      class="custom-textarea"
                    />
                    
                    <div class="protocol-badges">
                      <el-tag effect="dark" type="info" size="small">RFC 8446</el-tag>
                      <el-tag effect="dark" type="success" size="small">ECDHE</el-tag>
                      <el-tag effect="dark" type="warning" size="small">AES-256-GCM</el-tag>
                    </div>

                    <el-button 
                      type="primary" 
                      :loading="tlsLoading" 
                      @click="runTlsSimulation" 
                      class="w-full mt-4 start-btn"
                    >
                      <el-icon class="mr-2"><VideoPlay /></el-icon> 启动握手仿真
                    </el-button>
                  </div>
                </div>

                <div class="sidebar-section mt-4" v-if="tlsResult">
                  <div class="sidebar-title">协商结果 (Parameters)</div>
                  <div class="param-list">
                    <div class="param-item">
                      <span class="lbl">Cipher Suite</span>
                      <span class="val">{{ tlsResult.cipher_suite || 'TLS_AES_256_GCM_SHA384' }}</span>
                    </div>
                    <div class="param-item">
                      <span class="lbl">Key Exchange</span>
                      <span class="val">X25519</span>
                    </div>
                     <div class="param-item">
                      <span class="lbl">RTT</span>
                      <span class="val">1-RTT</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 右侧：主显示区 (分为上下两部分) -->
              <div class="tls-main-view">
                
                <!-- 上部分：报文时间轴 (Packet Timeline) -->
                <div class="tls-timeline-panel">
                   <div v-if="!tlsResult" class="empty-timeline">
                      <el-icon size="60" color="#e2e8f0"><DArrowRight /></el-icon>
                      <p>请点击左侧按钮启动 TLS 1.3 协议仿真</p>
                   </div>
                   <div v-else class="timeline-scroll-wrapper">
                      <div class="timeline-header-bar">
                        <span><el-icon><Connection /></el-icon> 报文捕获 (Packet Capture)</span>
                        <div class="legend">
                          <span class="legend-item"><span class="dot tcp"></span>TCP</span>
                          <span class="legend-item"><span class="dot tls"></span>TLS 1.3 Handshake</span>
                          <span class="legend-item"><span class="dot data"></span>Application Data</span>
                        </div>
                      </div>
                      
                      <div class="timeline-content">
                        <div class="timeline-spine"></div>
                        <div 
                            v-for="(packet, index) in tlsResult.packets" 
                            :key="index"
                            class="timeline-row"
                            :class="getPacketClass(packet.info)"
                          >
                            <!-- 时间 -->
                            <div class="t-time">{{ packet.time }}</div>
                            <!-- 节点 -->
                            <div class="t-axis"><div class="t-dot"></div></div>
                            <!-- 报文详情 -->
                            <div class="t-content-wide">
                              <div class="packet-stripe">
                                <div class="pkt-meta">
                                   <span class="pkt-proto">{{ getPacketProtocol(packet) }}</span>
                                   <span class="pkt-dir">
                                     <span class="addr">{{ packet.source.includes('Client') ? 'Client' : 'Server' }}</span>
                                     <el-icon><Right /></el-icon>
                                     <span class="addr">{{ packet.destination.includes('Client') ? 'Client' : 'Server' }}</span>
                                   </span>
                                </div>
                                <div class="pkt-info-text">{{ cleanPacketInfo(packet.info) }}</div>
                              </div>
                            </div>
                        </div>
                      </div>
                   </div>
                </div>

                <!-- 下部分：解密详情 (Decryption Details) -->
                <div class="tls-details-panel" v-if="tlsResult">
                  <!-- 区域1：密钥日志 -->
                  <div class="detail-section keylog-section">
                    <div class="detail-header">
                       <span><el-icon><Key /></el-icon> 会话密钥 (SSL Keylog)</span>
                       <el-switch v-model="showKeyLog" size="small" active-text="显示" inactive-text="隐藏" inline-prompt />
                    </div>
                    <div class="detail-body dark-terminal">
                       <div v-if="showKeyLog" class="terminal-text">{{ tlsResult.keylog_content }}</div>
                       <div v-else class="blur-overlay">
                         <el-icon size="24"><Lock /></el-icon> 
                         <span>Sensitive Data Hidden</span>
                       </div>
                    </div>
                  </div>

                  <!-- 区域2：解密内容 -->
                  <div class="detail-section data-section">
                    <div class="detail-header success-theme">
                       <span><el-icon><Unlock /></el-icon> 解密后数据 (Decrypted Application Data)</span>
                    </div>
                    <div class="detail-body black-terminal">
                       <div v-for="(log, idx) in tlsResult.client_log" :key="idx" class="term-line">
                         <span class="prompt">$</span> {{ log }}
                       </div>
                       <div v-if="!tlsResult.client_log || tlsResult.client_log.length === 0" class="no-data">
                         Waiting for Application Data...
                       </div>
                    </div>
                  </div>
                </div>

              </div>
            </div>
          </el-tab-pane>

        </el-tabs>
      </el-card>

      <!-- 证书详情弹窗 -->
      <el-dialog v-model="certDetailVisible" title="X.509 Certificate Details" width="600px" destroy-on-close>
        <div v-if="currentCertDetails" class="cert-modal-content">
          <div class="kv-list">
             <div class="kv-item"><label>File:</label> <span>{{ currentCertDetails.certificate_filename }}</span></div>
             <div class="kv-item"><label>Created:</label> <span>{{ formatDateTime(currentCertDetails.created_time) }}</span></div>
             <div class="kv-item"><label>Type:</label> <el-tag size="small">{{ currentCertDetails.certificate_type }}</el-tag></div>
          </div>
          <el-divider content-position="left">PEM Encoded</el-divider>
          <div class="pem-block">
            <pre>{{ currentCertContent || 'Loading content...' }}</pre>
          </div>
        </div>
      </el-dialog>    
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import JsonViewer from 'vue-json-viewer'
import 'vue-json-viewer/style.css'
import request from '@/utils/request'
import { 
  Aim, Loading, Key, Link, Right, DArrowRight,
  User, Platform, WarnTriangleFilled, Connection,
  Monitor, Select, Unlock, Lock, VideoPlay, Search,
  Hide, Tools, CloseBold
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// --- 全局状态 ---
const activeTab = ref('tls13') // 默认选中 TLS 用于查看效果
const hijackLoading = ref(false)
const certLoading = ref(false)
const tlsLoading = ref(false)
const isGlobalLoading = computed(() => hijackLoading.value || certLoading.value || tlsLoading.value)

// --- Hijack 状态 ---
const hijackForm = reactive({
  targetUrl: 'https://www.bank.com/transfer', 
  clientMessage: '{"action": "transfer", "amount": 1000, "currency": "USD"}',
  hijackType: 'mitm',
  hijackContent: '{"amount": 99999}'
})
const hijackResult = ref(null) 

// --- Cert 状态 ---
const certForgeForm = reactive({
  forgeType: 'self-signed',
  domain: 'www.example.com',
  validityDays: 365,
  organization: 'Test Organization',
  country: 'CN',
  keySize: '1024' 
})
const generatedCerts = ref([])
const selectedCert = ref(null) 
const certDetailVisible = ref(false) 
const currentCertDetails = ref(null) 
const currentCertContent = ref('')

// --- 证书验证状态 ---
const verifyLoading = ref(false) 
const certVerifyResult = ref(null) 
const verifyError = ref('') 

// --- TLS 1.3 状态 ---
const tlsForm = reactive({
  message: 'Hello TLS 1.3 World! This message will be encrypted.'
})
const tlsResult = ref(null)
const showKeyLog = ref(false)

// --- Hijack 方法 ---
const runHijackSimulation = async () => {
  if (!hijackForm.hijackType || !hijackForm.targetUrl) {
    ElMessage.warning('攻击手法和目标URL不能为空')
    return
  }
  hijackLoading.value = true
  hijackResult.value = null
  try {
    const requestData = {
      hijackType: hijackForm.hijackType,
      targetUrl: hijackForm.targetUrl,
      hijackContent: hijackForm.hijackContent 
    }
    const data = await request.post('/api/security/hijack/simulate', requestData)
    hijackResult.value = data.data 
    ElMessage.success('劫持模拟执行成功')
  } catch (e) {
    ElMessage.error(`模拟失败：${e.message}`)
  } finally {
    hijackLoading.value = false
  }
}

// --- Cert 方法 ---
const fetchGeneratedCerts = async (showMessage = false) => {
  try {
    const json = await request.get('/api/security/cert/list')
    generatedCerts.value = json.data
    if (showMessage) {
      ElMessage.success('证书列表刷新成功')
    }
  } catch (e) {
    ElMessage.error(`网络异常：${e.message}`)
  }
}
// 组件挂载时获取证书列表，但不显示消息
fetchGeneratedCerts(false)

const handleForgeTypeChange = () => {
  if (certForgeForm.forgeType === 'ca') certForgeForm.validityDays = 3650 
  else if (certForgeForm.forgeType === 'expired') certForgeForm.validityDays = 30 
  else certForgeForm.validityDays = 365 
}

const runCertForgeSimulation = async () => {
  certLoading.value = true
  try {
    const requestData = {
      certType: certForgeForm.forgeType,
      domain: certForgeForm.domain,
      validityDays: certForgeForm.validityDays,
      organization: certForgeForm.organization,
      country: certForgeForm.country,
      keySize: parseInt(certForgeForm.keySize) 
    }
    await request.post('/api/security/cert/generate', requestData)
    ElMessage.success('证书生成成功')
    fetchGeneratedCerts(true) 
  } catch (e) {
    ElMessage.error(`网络错误: ${e.message}`)
  } finally {
    certLoading.value = false
  }
}

const handleCertSelect = (val) => { selectedCert.value = val }

const viewCertDetails = async (row) => {
  currentCertDetails.value = row
  certDetailVisible.value = true
  currentCertContent.value = 'Loading...'
  try {
    const json = await request.post('/api/security/cert/content', { certificate_filename: row.certificate_filename })
    currentCertContent.value = json.data.content
  } catch (e) {
    currentCertContent.value = `网络异常：${e.message}`
  }
}

const getCertTypeTag = (type) => {
  const map = { 
    'self_signed': 'warning', 'expired': 'danger', 'weak': 'info', 
    'ca': 'success', 'ca_signed': 'primary', 'self-signed': 'warning' 
  }
  return map[type] || ''
}

// --- TLS 1.3 方法 ---
const runTlsSimulation = async () => {
  tlsLoading.value = true
  tlsResult.value = null
  showKeyLog.value = false
  try {
    const json = await request.post('/api/security/tls13/simulate', { message: tlsForm.message })
    tlsResult.value = json.data
    ElMessage.success('TLS 1.3 握手仿真完成')
  } catch (e) {
    ElMessage.error(`网络异常: ${e.message}`)
  } finally {
    tlsLoading.value = false
  }
}

// --- TLS 辅助函数 ---
const getPacketProtocol = (packet) => {
  if (packet.protocol === 'TLSv1.3') return 'TLS 1.3'
  if (packet.info.includes('SYN') || packet.info.includes('ACK')) return 'TCP'
  return packet.protocol
}

const cleanPacketInfo = (info) => {
  return info.replace('Application Data', 'Application Data (Encrypted)')
}

const getPacketClass = (info) => {
  // 核心逻辑：区分 TCP握手 vs TLS握手 vs AppData
  if (info.includes('SYN') || (info.includes('ACK') && !info.includes('Hello') && !info.includes('Change'))) {
    return 'is-tcp'
  }
  if (info.includes('Client Hello') || info.includes('Server Hello') || info.includes('Change Cipher Spec') || info.includes('Handshake')) {
    return 'is-tls-handshake'
  }
  if (info.includes('Application Data')) {
    return 'is-app-data'
  }
  return ''
}

// --- Utils ---
const formatDateTime = (str) => {
  if (!str) return '未知时间'
  try { return new Date(str).toLocaleString() } catch (e) { return str }
}

// --- 证书验证 ---
const verifyCertificate = async () => {
  if (!selectedCert.value) {
    ElMessage.warning('请先选择一个证书')
    return
  }
  verifyLoading.value = true
  verifyError.value = ''
  try {
    await new Promise(resolve => setTimeout(resolve, 800))
    const certContentData = await request.post('/api/security/cert/content', { certificate_filename: selectedCert.value.certificate_filename })
    
    // Mock验证逻辑 (为了演示效果，实际逻辑应在后端)
    const mockVerifyResult = {
      verification_status: selectedCert.value.certificate_type === 'ca' ? 'secure' : 'insecure',
      certificate_type: selectedCert.value.certificate_type,
      domain: certForgeForm.domain,
      validity_days: certForgeForm.validityDays,
      issuer: certForgeForm.organization || 'Unknown',
      signature_algorithm: getMockSignatureAlgorithm(selectedCert.value.certificate_type),
      key_size: parseInt(certForgeForm.keySize),
      is_expired: selectedCert.value.certificate_type === 'expired',
      is_self_signed: selectedCert.value.certificate_type.includes('self'),
      is_weak_signature: selectedCert.value.certificate_type === 'weak',
      is_chain_complete: selectedCert.value.certificate_type.includes('ca'),
      certificate_content: certContentData.data.content
    }
    certVerifyResult.value = mockVerifyResult
    ElMessage.success('证书验证完成')
  } catch (e) {
    verifyError.value = `证书验证失败: ${e.message}`
    ElMessage.error(verifyError.value)
  } finally {
    verifyLoading.value = false
  }
}

const clearVerifyResult = () => { certVerifyResult.value = null; verifyError.value = '' }
const getVerifyResultText = (status) => ({ 'secure': 'Verified Secure', 'insecure': 'Security Risk', 'warning': 'Warning' }[status] || 'Unknown')
const getMockSignatureAlgorithm = (certType) => ({
    'self_signed': 'SHA256withRSA', 'weak': 'MD5withRSA', 'ca': 'SHA256withECDSA'
  }[certType] || 'SHA256withRSA')
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

/* --- 通用变量 --- */
.security-simulation-page {
  --primary: #3b82f6;
  --success: #10b981;
  --danger: #ef4444;
  --warning: #f59e0b;
  --bg-main: #f1f5f9;
  --bg-card: #ffffff;
  --border: #e2e8f0;
  --text-main: #1e293b;
  --text-light: #64748b;
  
  /* 协议颜色 */
  --tcp-color: #94a3b8;
  --tls-color: #7c3aed; /* Deeper purple for better contrast */
  --app-color: #059669;

  min-height: 100vh;
  background-color: var(--bg-main);
  font-family: 'Inter', sans-serif;
  color: var(--text-main);
}

/* --- Header --- */
.page-navbar {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  height: 64px;
  padding: 0 40px;
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 100;
}
.brand { display: flex; align-items: center; gap: 14px; }
.logo-icon {
  width: 38px; height: 38px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: white; font-size: 20px;
  box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2);
}
.brand-text h1 { font-size: 18px; font-weight: 700; margin: 0; color: #0f172a; }
/* 修改Loading动效：移除旋转，改为发光闪烁 */
.is-loading { 
  animation: pulse-glow 1.5s ease-in-out infinite alternate; 
}

/* --- Layout --- */
.main-content { max-width: 1300px; margin: 24px auto; padding: 0 20px; }
.simulation-card-container { border: none; background: transparent; }
:deep(.el-card__body) { padding: 0; }
:deep(.el-tabs__header) { margin-bottom: 0; border-bottom: 1px solid var(--border); background: #f8fafc; }
:deep(.el-tabs__item) { height: 45px; line-height: 45px; font-weight: 500; }
:deep(.el-tabs__item.is-active) { font-weight: 600; background: #fff; }
.custom-tab-label { display: flex; align-items: center; gap: 6px; }
.tab-content-wrapper { background: #fff; padding: 30px; min-height: 600px; }

/* --- TLS 1.3 New Layout Styles --- */
.tls-layout-container { display: flex; padding: 0 !important; height: 800px; overflow: hidden; }

/* Sidebar */
.tls-control-sidebar { flex: 0 0 250px; background: #fff; border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 20px; z-index: 2; box-shadow: 2px 0 10px rgba(0,0,0,0.02); }
.sidebar-title { font-weight: 700; font-size: 13px; color: var(--text-main); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.input-label { font-size: 11px; color: var(--text-light); margin-bottom: 6px; display: block; }
.custom-textarea :deep(.el-textarea__inner) { background: #f8fafc; border-color: #e2e8f0; font-size: 12px; }
.protocol-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.param-list { background: #f8fafc; border-radius: 6px; padding: 12px; }
.param-item { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 11px; }
.param-item .lbl { color: var(--text-light); }
.param-item .val { font-weight: 600; color: #334155; }

/* Main View (Right Side) */
.tls-main-view { flex: 1; display: flex; flex-direction: column; min-width: 0; }

/* Top: Timeline Panel */
.tls-timeline-panel { flex: 1; display: flex; flex-direction: column; border-bottom: 1px solid var(--border); background: #fff; overflow: hidden; }
.empty-timeline { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #cbd5e1; gap: 15px; }

.timeline-header-bar { height: 40px; background: #f1f5f9; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; font-size: 12px; font-weight: 600; color: #475569; border-bottom: 1px solid #e2e8f0; }
.legend { display: flex; gap: 15px; font-weight: normal; }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 11px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.tcp { background: var(--tcp-color); }
.dot.tls { background: var(--tls-color); }
.dot.data { background: var(--app-color); }

.timeline-scroll-wrapper { flex: 1; overflow-y: auto; position: relative; padding: 10px 0; }
.timeline-content { position: relative; padding: 0 20px; }
.timeline-spine { position: absolute; left: 100px; top: 0; bottom: 0; width: 1px; background: #e2e8f0; z-index: 0; }

/* Timeline Row */
.timeline-row { display: flex; margin-bottom: 4px; position: relative; z-index: 1; align-items: stretch; }
.t-time { width: 80px; text-align: right; padding-right: 20px; font-family: 'JetBrains Mono'; font-size: 11px; color: #94a3b8; padding-top: 8px; }
.t-axis { width: 40px; display: flex; justify-content: center; padding-top: 10px; }
.t-dot { width: 10px; height: 10px; background: #fff; border: 2px solid #ccc; border-radius: 50%; z-index: 2; }
.t-content-wide { flex: 1; padding-bottom: 6px; }

/* Packet Stripe Design */
.packet-stripe { 
  display: flex; align-items: center; gap: 12px; 
  background: #fff; border: 1px solid #e2e8f0; border-left-width: 4px;
  padding: 6px 12px; border-radius: 4px;
  font-size: 12px; 
  transition: all 0.2s;
}
.packet-stripe:hover { transform: translateX(2px); box-shadow: 0 2px 4px rgba(0,0,0,0.05); }

.pkt-meta { display: flex; align-items: center; gap: 10px; min-width: 180px; }
.pkt-proto { font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px; min-width: 50px; text-align: center; }
.pkt-dir { color: #64748b; font-size: 11px; display: flex; align-items: center; gap: 4px; }
.pkt-info-text { font-family: 'JetBrains Mono'; color: #334155; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Dynamic Styles for Packets */
.is-tcp .t-dot { background: var(--tcp-color); border-color: var(--tcp-color); }
.is-tcp .packet-stripe { border-left-color: var(--tcp-color); }
.is-tcp .pkt-proto { background: #f1f5f9; color: var(--tcp-color); }

.is-tls-handshake .t-dot { background: var(--tls-color); border-color: var(--tls-color); box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.2); }
.is-tls-handshake .packet-stripe { border-left-color: var(--tls-color); background: #fcfaff; }
.is-tls-handshake .pkt-proto { background: #ede9fe; color: var(--tls-color); }

.is-app-data .t-dot { background: var(--app-color); border-color: var(--app-color); }
.is-app-data .packet-stripe { border-left-color: var(--app-color); background: #f0fdf4; }
.is-app-data .pkt-proto { background: #d1fae5; color: var(--app-color); }

/* Bottom: Details Panel */
.tls-details-panel { height: 280px; background: #0f172a; display: flex; border-top: 1px solid #334155; }
.detail-section { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.keylog-section { border-right: 1px solid #334155; flex: 0 0 40%; } /* Keylog takes 40% width */

.detail-header { height: 36px; padding: 0 15px; background: #1e293b; display: flex; align-items: center; justify-content: space-between; color: #94a3b8; font-size: 11px; font-weight: 600; border-bottom: 1px solid #334155; }
.detail-header.success-theme { color: #34d399; }

.detail-body { flex: 1; overflow-y: auto; padding: 15px; position: relative; font-family: 'JetBrains Mono'; font-size: 11px; }
.dark-terminal { color: #e2e8f0; }
.black-terminal { background: #000; color: #4ade80; }

.terminal-text { white-space: pre-wrap; word-break: break-all; line-height: 1.5; color: #cbd5e1; }
.term-line { margin-bottom: 4px; border-bottom: 1px solid #112; padding-bottom: 2px; }
.prompt { color: #3b82f6; margin-right: 8px; }
.no-data { color: #4b5563; font-style: italic; margin-top: 10px; }

.blur-overlay { position: absolute; inset: 0; background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(4px); display: flex; flex-direction: column; align-items: center; justify-content: center; color: #94a3b8; gap: 8px; }

/* Existing Styles for other tabs (Kept for compatibility) */
.hijack-grid-container { display: grid; grid-template-columns: 1fr 60px 1fr 60px 1fr; gap: 10px; align-items: stretch; }
.node-card { border: 1px solid var(--border); border-radius: 12px; background: #fff; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.02); transition: all 0.3s; }
.node-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
.client-card { border-top: 4px solid var(--primary); }
.attacker-card { border-top: 4px solid var(--danger); }
.server-card { border-top: 4px solid var(--success); }
.node-header { padding: 12px 16px; background: #f8fafc; border-bottom: 1px solid var(--border); font-weight: 600; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.node-body { padding: 20px; flex: 1; display: flex; flex-direction: column; }
.server-body-layout { padding: 0; }
.flow-arrow { display: flex; align-items: center; justify-content: center; position: relative; color: var(--text-light); }
.arrow-line { height: 2px; background: #cbd5e1; width: 100%; position: absolute; z-index: 0; }
.flow-arrow.dashed .arrow-line { background: transparent; border-top: 2px dashed var(--danger); }
.flow-arrow .el-icon { background: #fff; z-index: 1; padding: 0 4px; color: #94a3b8; font-size: 16px; }
.server-idle { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-light); min-height: 200px; }
.idle-icon { font-size: 32px; margin-bottom: 10px; color: #cbd5e1; }
.pulse-ring { width: 50px; height: 50px; border-radius: 50%; border: 2px solid #e2e8f0; position: absolute; animation: pulse 2s infinite; }
.server-result-content { padding: 20px; font-size: 12px; }
.alert-box.error { background: #fef2f2; border: 1px solid #fee2e2; color: var(--danger); padding: 10px; border-radius: 6px; margin-bottom: 15px; display: flex; flex-direction: column; text-align: center; }
.data-group { margin-bottom: 12px; }
.data-group label { display: block; font-size: 11px; color: var(--text-light); margin-bottom: 4px; font-weight: 600; }
.code-box { background: #1e293b; color: #f8fafc; padding: 8px; border-radius: 4px; font-family: 'JetBrains Mono'; word-break: break-all; }
.mono-text { font-family: 'JetBrains Mono'; color: var(--text-main); }
.attack-btn { width: 100%; margin-top: auto; }
.cert-layout-grid { display: flex; gap: 20px; padding: 24px; background: #f8fafc; }
.cert-left-panel { flex: 0 0 340px; }
.cert-right-panel { flex: 1; display: flex; flex-direction: column; }
.panel-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.panel-header-line { display: flex; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9; }
.panel-header-line.space-between { justify-content: space-between; }
.bold-title { font-weight: 700; font-size: 14px; color: var(--text-main); }
.radio-circle { width: 12px; height: 12px; border: 2px solid #cbd5e1; border-radius: 50%; }
.radio-circle.active { border-color: var(--primary); background: var(--primary); box-shadow: 0 0 0 2px #dbeafe; }
.verify-layout { display: flex; gap: 16px; }
.verify-action-col { flex: 0 0 160px; display: flex; flex-direction: column; justify-content: center; }
.hint-text { font-size: 11px; color: var(--text-light); margin-bottom: 8px; line-height: 1.4; }
.verify-result-col { flex: 1; border: 1px dashed var(--border); border-radius: 6px; background: #f9fafb; min-height: 120px; padding: 10px; display: flex; align-items: center; justify-content: center; }
.placeholder-box { display: flex; flex-direction: column; align-items: center; color: #cbd5e1; gap: 8px; font-size: 13px; }
.result-box { width: 100%; height: 100%; background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 15px; }
.result-box.secure { border-color: var(--success); background: #f0fdf4; }
.result-box.insecure { border-color: var(--danger); background: #fef2f2; }
.result-header { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; }
.secure .result-header { color: var(--success); }
.insecure .result-header { color: var(--danger); }
.result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; }
.r-item span { font-weight: 600; color: #64748b; }
.cert-modal-content { font-size: 13px; }
.kv-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #e2e8f0; }
.pem-block pre { background: #1e293b; color: #f1f5f9; padding: 12px; border-radius: 6px; font-size: 11px; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow: auto; }
.flex { display: flex; }
.gap-2 { gap: 8px; }
.mr-1 { margin-right: 4px; }
.mr-2 { margin-right: 8px; }
.mt-2 { margin-top: 8px; }
.mt-4 { margin-top: 16px; }
.w-full { width: 100%; }

/* 发光动画（替代旋转） */
@keyframes pulse-glow {
  0% {
    box-shadow: 0 0 5px rgba(59, 130, 246, 0.5);
    opacity: 0.8;
  }
  100% {
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.8), 0 0 30px rgba(59, 130, 246, 0.5);
    opacity: 1;
  }
}

/* 保留原有脉冲动画（非旋转类） */
@keyframes pulse { 
  0% { transform: scale(0.95); opacity: 0.5; } 
  100% { transform: scale(1.5); opacity: 0; } 
}
</style>