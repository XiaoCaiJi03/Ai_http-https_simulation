<template>
  <div class="ssl-handshake-container">
    <el-card title="🔐 SSL/TLS握手流程可视化（{{ isHttps ? '已启用HTTPS' : '未启用HTTPS' }}）" size="small">
      <div v-if="!isHttps" class="ssl-disabled">
        <el-empty description="未开启HTTPS，不触发SSL/TLS握手流程" />
        <el-button type="primary" size="small" @click="triggerHttpsTip">开启HTTPS查看握手流程</el-button>
      </div>

      <div v-else class="ssl-handshake-flow">
        <!-- 握手状态提示 -->
        <div class="flow-status" :class="{ fakeCert: fakeCertEnableLocal }">
          <el-tag :type="fakeCertEnableLocal ? 'danger' : 'success'">
            {{ fakeCertEnableLocal ? '⚠️ 模拟伪造证书（不安全连接）' : '✅ 模拟合法证书（安全连接）' }}
          </el-tag>
        </div>

        <!-- 握手步骤可视化（时序图） -->
        <div class="flow-timeline">
          <!-- 步骤1：Client Hello -->
          <div class="flow-step">
            <div class="step-icon step-client">👨‍💻</div>
            <div class="step-content">
              <div class="step-title">步骤1：Client Hello（客户端问候）</div>
              <div class="step-detail">
                <ul>
                  <li>客户端发送支持的TLS版本（TLSv1.2/TLSv1.3）</li>
                  <li>客户端发送支持的加密套件（如AES-256-GCM、ChaCha20）</li>
                  <li>客户端生成随机数（Client Random）</li>
                  <li>客户端发送扩展信息（如SNI、ALPN）</li>
                </ul>
              </div>
            </div>
            <div class="step-arrow">→</div>
          </div>

          <!-- 步骤2：Server Hello + Certificate -->
          <div class="flow-step reverse">
            <div class="step-icon step-server">🖥️</div>
            <div class="step-content">
              <div class="step-title">步骤2：Server Hello + Certificate（服务端响应+证书）</div>
              <div class="step-detail">
                <ul>
                  <li>服务端确认TLS版本（选定最优版本）</li>
                  <li>服务端确认加密套件（选定最优套件）</li>
                  <li>服务端生成随机数（Server Random）</li>
                  <li>服务端发送数字证书（含公钥、域名、有效期，{{ fakeCertEnableLocal ? '伪造证书' : '合法证书' }}）</li>
                </ul>
              </div>
            </div>
            <div class="step-arrow">→</div>
          </div>

          <!-- 步骤3：Server Hello Done / Client Key Exchange -->
          <div class="flow-step">
            <div class="step-icon step-client">👨‍💻</div>
            <div class="step-content">
              <div class="step-title">步骤3：Client Key Exchange + Change Cipher Spec</div>
              <div class="step-detail">
                <ul>
                  <li>客户端验证证书有效性（{{ fakeCertEnableLocal ? '验证失败，忽略风险继续' : '验证通过' }}）</li>
                  <li>客户端生成预主密钥（Pre-Master Secret），用服务端公钥加密发送</li>
                  <li>客户端发送Change Cipher Spec（通知后续数据用协商的加密套件加密）</li>
                  <li>客户端生成会话密钥（Client Random + Server Random + Pre-Master Secret）</li>
                </ul>
              </div>
            </div>
            <div class="step-arrow">→</div>
          </div>

          <!-- 步骤4：Server Change Cipher Spec + Finished -->
          <div class="flow-step reverse">
            <div class="step-icon step-server">🖥️</div>
            <div class="step-content">
              <div class="step-title">步骤4：Server Change Cipher Spec + Finished（握手完成）</div>
              <div class="step-detail">
                <ul>
                  <li>服务端用私钥解密预主密钥，生成会话密钥</li>
                  <li>服务端发送Change Cipher Spec（通知后续数据加密传输）</li>
                  <li>服务端发送Finished消息（含握手数据摘要，验证握手完整性）</li>
                  <li>客户端验证Finished消息，SSL/TLS握手完成，开始加密传输应用数据</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- 伪造证书开关 -->
        <div class="fake-cert-switch" style="margin-top: 20px; text-align: center;">
          <el-switch
            v-model="fakeCertEnableLocal"
            active-text="开启伪造证书模拟"
            inactive-text="关闭伪造证书模拟"
            active-color="#f56c6c"
            inactive-color="#409eff"
          />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, ref, watchEffect, watch } from 'vue'
import { ElMessage } from 'element-plus'

// 定义Props（接收父组件传递的参数）
const props = defineProps({
  isHttps: {
    type: Boolean,
    default: false
  },
  fakeCertEnable: {
    type: Boolean,
    default: false
  }
})

// 定义Emits（向父组件传递数据）
const emit = defineEmits(['update:fakeCertEnable'])

// 响应式变量：同步伪造证书开关状态（使用独立名称避免与 prop 冲突）
const fakeCertEnableLocal = ref(props.fakeCertEnable)

// 监听 prop 变化，同步到本地 ref
watch(() => props.fakeCertEnable, (val) => {
  fakeCertEnableLocal.value = val
})

// 监听开关变化，向父组件同步
watchEffect(() => {
  emit('update:fakeCertEnable', fakeCertEnableLocal.value)
})

// 触发HTTPS提示
const triggerHttpsTip = () => {
  ElMessage.info('请在上方表单中开启「是否HTTPS」开关，以查看完整的SSL/TLS握手流程')
}
</script>

<style scoped>
.ssl-handshake-container {
  width: 100%;
  height: 100%;
  overflow: auto;
  padding: 10px 0;
}

.ssl-disabled {
  text-align: center;
  padding: 40px 0;
}

.ssl-handshake-flow {
  padding: 10px;
}

.flow-status {
  margin-bottom: 20px;
  text-align: center;
}

.fakeCert .el-tag {
  font-weight: bold;
}

.flow-timeline {
  position: relative;
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
}

.flow-step {
  display: flex;
  align-items: center;
  margin-bottom: 30px;
  position: relative;
}

.flow-step.reverse {
  flex-direction: row-reverse;
  text-align: right;
}

.step-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}

.step-client {
  background-color: #e6f7ff;
  border: 2px solid #409eff;
}

.step-server {
  background-color: #f0f9ff;
  border: 2px solid #1890ff;
}

.step-content {
  flex: 1;
  padding: 0 20px;
}

.step-title {
  font-weight: bold;
  color: #303133;
  margin-bottom: 8px;
  font-size: 15px;
}

.step-detail {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.step-detail ul {
  padding-left: 20px;
  margin: 0;
}

.step-arrow {
  font-size: 20px;
  color: #c0c4cc;
  width: 40px;
  text-align: center;
  flex-shrink: 0;
}

.flow-step.reverse .step-arrow {
  transform: rotate(180deg);
}

/* 响应式适配 */
@media (max-width: 768px) {
  .step-icon {
    width: 40px;
    height: 40px;
    font-size: 18px;
  }

  .step-title {
    font-size: 13px;
  }

  .step-detail {
    font-size: 12px;
  }
}
</style>