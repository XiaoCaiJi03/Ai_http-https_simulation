<template>
  <div class="cookie-viewer-container">
    <el-card title="🍪 Cookie交互详情可视化" size="small">
      <!-- 无结果提示 -->
      <el-empty description="暂无Cookie交互数据" v-if="!hasCookieData" />

      <!-- Cookie数据可视化 -->
      <div v-else class="cookie-content">
        <!-- Cookie概览统计 -->
        <el-row :gutter="20" class="cookie-stats" style="margin-bottom: 20px;">
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-label">总Cookie数量</div>
              <div class="stat-value">{{ cookieList.length }}</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-label">Secure Cookie数量</div>
              <div class="stat-value">{{ secureCookieCount }}</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-label">HttpOnly Cookie数量</div>
              <div class="stat-value">{{ httpOnlyCookieCount }}</div>
            </div>
          </el-col>
        </el-row>

        <!-- Cookie列表表格 -->
        <el-table
          :data="cookieList"
          border
          size="mini"
          style="width: 100%; margin-bottom: 20px;"
          highlight-current-row
        >
          <el-table-column label="序号" width="60" align="center">
            <template #default="scope">{{ scope.$index + 1 }}</template>
          </el-table-column>
          <el-table-column prop="name" label="Cookie名称" min-width="150" />
          <el-table-column prop="value" label="Cookie值" min-width="200" />
          <el-table-column prop="domain" label="作用域(Domain)" min-width="150" />
          <el-table-column prop="path" label="路径(Path)" width="100" />
          <el-table-column label="Secure" width="80" align="center">
            <template #default="scope">
              <el-icon :color="scope.row.secure ? '#409eff' : '#c0c4cc'">
                <Check v-if="scope.row.secure" />
                <Close v-else />
              </el-icon>
            </template>
          </el-table-column>
          <el-table-column label="HttpOnly" width="80" align="center">
            <template #default="scope">
              <el-icon :color="scope.row.httpOnly ? '#409eff' : '#c0c4cc'">
                <Check v-if="scope.row.httpOnly" />
                <Close v-else />
              </el-icon>
            </template>
          </el-table-column>
          <el-table-column prop="expires" label="过期时间" min-width="180" />
        </el-table>

        <!-- Cookie交互说明（根据HTTPS状态调整） -->
        <el-card title="📝 Cookie交互说明" size="mini" class="cookie-desc">
          <div class="desc-content">{{ cookieDescription }}</div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { defineProps, computed } from 'vue'
import { Check, Close } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/common'

// 定义Props（接收父组件传递的仿真结果和HTTPS状态）
const props = defineProps({
  simulationResult: {
    type: Object,
    default: () => ({})
  },
  isHttps: {
    type: Boolean,
    default: false
  }
})

// 计算属性：提取Cookie列表（从请求头和响应头中解析）
const cookieList = computed(() => {
  const result = props.simulationResult
  if (!result || !result.request || !result.response) return []

  // 解析响应头中的Set-Cookie（核心Cookie来源）
  const setCookieHeaders = result.response.headers?.['Set-Cookie'] || []
  const cookieArr = Array.isArray(setCookieHeaders) ? setCookieHeaders : [setCookieHeaders]

  return cookieArr
    .filter(Boolean)
    .map(cookieStr => {
      const cookieObj = {
        name: '',
        value: '',
        domain: '',
        path: '/',
        secure: props.isHttps,
        httpOnly: false,
        expires: '会话级（关闭浏览器失效）'
      }

      // 拆分Cookie键值对和属性
      const parts = cookieStr.split(';').map(part => part.trim())
      const [nameValue, ...attrs] = parts

      // 解析名称和值
      if (nameValue.includes('=')) {
        const eqIndex = nameValue.indexOf('=')
        cookieObj.name = nameValue.substring(0, eqIndex)
        cookieObj.value = nameValue.substring(eqIndex + 1) || ''
      } else {
        cookieObj.name = nameValue
        cookieObj.value = ''
      }

      // 解析其他属性
      attrs.forEach(attr => {
        if (attr.toLowerCase().startsWith('domain=')) {
          cookieObj.domain = attr.split('=')[1] || ''
        } else if (attr.toLowerCase().startsWith('path=')) {
          cookieObj.path = attr.split('=')[1] || '/'
        } else if (attr.toLowerCase() === 'secure') {
          cookieObj.secure = true
        } else if (attr.toLowerCase() === 'httponly') {
          cookieObj.httpOnly = true
        } else if (attr.toLowerCase().startsWith('expires=')) {
          const expiresStr = attr.split('=')[1] || ''
          cookieObj.expires = formatDateTime(new Date(expiresStr)) || expiresStr
        }
      })

      return cookieObj
    })
})

// 计算属性：是否有Cookie数据
const hasCookieData = computed(() => cookieList.value.length > 0)

// 计算属性：Secure Cookie数量
const secureCookieCount = computed(() => {
  return cookieList.value.filter(cookie => cookie.secure).length
})

// 计算属性：HttpOnly Cookie数量
const httpOnlyCookieCount = computed(() => {
  return cookieList.value.filter(cookie => cookie.httpOnly).length
})

// 计算属性：Cookie交互说明（根据HTTPS状态动态生成）
const cookieDescription = computed(() => {
  const lines = [
    '1. Cookie通过响应头Set-Cookie从服务端传递到客户端，后续请求通过请求头Cookie携带到服务端。',
    '2. 会话级Cookie无Expires属性，关闭浏览器后失效；持久化Cookie通过Expires指定过期时间。'
  ]

  if (props.isHttps) {
    lines.push('3. HTTPS环境下，Secure属性的Cookie仅通过加密连接（HTTPS/TLS）传输，防止明文泄露。')
    lines.push('4. HttpOnly属性的Cookie无法被JavaScript（document.cookie）访问，可有效防御XSS攻击窃取Cookie。')
  } else {
    lines.push('3. HTTP环境下，Cookie以明文形式传输，存在被中间人劫持窃取的风险。')
    lines.push('4. HTTP环境下，Secure属性的Cookie会被浏览器忽略，无法生效。')
  }

  return lines.join('\n')
})
</script>

<style scoped>
.cookie-viewer-container {
  width: 100%;
  height: 100%;
  overflow: auto;
  padding: 10px 0;
}

.cookie-content {
  padding: 10px;
}

.cookie-stats {
  width: 100%;
}

.stat-card {
  background-color: #f5f7fa;
  border-radius: 8px;
  padding: 15px;
  text-align: center;
  height: 100%;
}

.stat-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.cookie-desc {
  margin-top: 10px;
}

.desc-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
}

.desc-content code {
  background-color: #f0f0f0;
  padding: 2px 4px;
  border-radius: 4px;
  color: #f56c6c;
  font-family: "Consolas", "Monaco", monospace;
}
</style>