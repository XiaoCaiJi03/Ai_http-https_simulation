<template>
  <div class="history-page-container">
    
    <!-- 1. 顶部导航栏 (与仿真页面风格统一) -->
    <div class="page-navbar">
      <div class="brand">
        <div class="logo-icon history-theme">
          <el-icon><Clock /></el-icon>
        </div>
        <div class="brand-text">
          <h1>历史记录</h1>
        </div>
      </div>
    </div>

    <div class="main-content">
      
      <!-- 2. 数据概览卡片 (新增) -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon bg-blue"><el-icon><Files /></el-icon></div>
          <div class="stat-info">
            <span class="label">日志总数</span>
            <span class="value">{{ logRecords.length }}</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon bg-green"><el-icon><Key /></el-icon></div>
          <div class="stat-info">
            <span class="label">证书记录</span>
            <span class="value">{{ countByType('certificate_generation') }}</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon bg-orange"><el-icon><Odometer /></el-icon></div>
          <div class="stat-info">
            <span class="label">并发模拟</span>
            <span class="value">{{ countByType('big_concurrent_simulation') }}</span>
          </div>
        </div>
      </div>

      <!-- 3. 核心日志表格 -->
      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="card-header">
            <span class="header-title"><el-icon class="mr-1"><Memo /></el-icon> 详细记录列表</span>
            <el-button :loading="loadingLogs" icon="Refresh" circle size="small" @click="fetchLogRecords" />
          </div>
        </template>
        
        <el-table 
          :data="paginatedLogRecords" 
          style="width: 100%" 
          size="default"
          v-loading="loadingLogs"
          highlight-current-row
          header-row-class-name="custom-header"
          @row-click="handleViewLogDetail"
        >
          <!-- 状态指示灯列 -->
          <el-table-column width="60" align="center">
            <template #default="scope">
               <div class="status-dot" :class="getStatusColor(scope.row.operation)"></div>
            </template>
          </el-table-column>

          <!-- 业务类型 -->
          <el-table-column label="业务类型" width="180">
            <template #default="scope">
              <el-tag 
                :type="getOperationTypeTag(scope.row.operation)" 
                effect="light" 
                size="small"
                class="custom-tag"
              >
                {{ getOperationTypeText(scope.row.operation) }}
              </el-tag>
            </template>
          </el-table-column>

          <!-- 关键摘要 -->
          <el-table-column label="摘要信息" min-width="300" show-overflow-tooltip>
             <template #default="scope">
                <span class="summary-text">{{ getLogSummary(scope.row) }}</span>
             </template>
          </el-table-column>
          
          <!-- 时间 (使用等宽字体) -->
          <el-table-column label="记录时间" width="220" prop="timestamp">
            <template #default="scope">
              <span class="mono-font">{{ formatDateTime(scope.row.timestamp) }}</span>
            </template>
          </el-table-column>
          
          <!-- 操作 -->
          <el-table-column label="操作" width="100" align="center" fixed="right">
            <template #default="scope">
              <el-button 
                link 
                type="primary" 
                size="small"
                @click.stop="handleViewLogDetail(scope.row)"
              >
                查看报文
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 表格底部 - 分页控件 -->
        <div class="pagination-footer">
          <el-pagination
            v-model:current-page="pagination.currentPage"
            v-model:page-size="pagination.pageSize"
            :page-sizes="pagination.pageSizes"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next, jumper"
            :small="false"
            @size-change="handlePageSizeChange"
            @current-change="handleCurrentPageChange"
          />
        </div>
      </el-card>

      <!-- 4. 数据包详情弹窗 -->
      <el-dialog 
        v-model="packetDetailVisible" 
        width="750px"
        align-center
        destroy-on-close
        class="custom-dialog"
      >
        <template #header>
          <div class="dialog-header">
            <el-icon><Document /></el-icon>
            <span>{{ currentLogDetail ? getLogDetailTitle(currentLogDetail) : '数据包详情' }}</span>
          </div>
        </template>
        
        <div class="json-wrapper">
           <div class="json-toolbar">
              <span class="json-label">JSON Payload</span>
           </div>
           <json-viewer 
            :value="currentLogDetail || {}" 
            :expand-depth="3" 
            copyable 
            boxed 
            sort
            theme="jv-light"
          ></json-viewer>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import JSONViewer from 'vue-json-viewer'
import 'vue-json-viewer/style.css'
import { 
  Clock, Refresh, Memo, Document, 
  Files, Key, Odometer 
} from '@element-plus/icons-vue'

// --- 状态定义 ---
const route = useRoute()
const logRecords = ref([]) // 原始数据
const loadingLogs = ref(false)
const packetDetailVisible = ref(false)
const currentLogDetail = ref(null)

// --- 分页状态 ---
const pagination = ref({
  currentPage: 1,
  pageSize: 10, // 默认每页10条
  pageSizes: [10, 20, 30, 50, 100], // 可选择的每页条数
  total: 0 // 总记录数
})

// --- 计算属性：分页后的数据 ---
const paginatedLogRecords = computed(() => {
  const startIndex = (pagination.value.currentPage - 1) * pagination.value.pageSize
  const endIndex = startIndex + pagination.value.pageSize
  return logRecords.value.slice(startIndex, endIndex)
})

// --- API 请求 ---
const fetchLogRecords = async () => {
  loadingLogs.value = true
  try {
    // 并行请求提高速度
    const [certRes, concurrentRes] = await Promise.all([
      request.get('/api/logs/cert/list'),
      request.get('/api/logs/big-concurrent/list')
    ])

    // 合并数据
    const allLogs = [
      ...(certRes.data || []),
      ...(concurrentRes.data || [])
    ]
    
    // 按时间倒序
    allLogs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    logRecords.value = allLogs
    
    // 更新分页总数
    pagination.value.total = allLogs.length
    pagination.value.currentPage = 1 // 重置到第一页

  } catch (error) {
    console.error('Fetch Logs Error:', error)
    ElMessage.error('无法连接至日志服务器')
  } finally {
    loadingLogs.value = false
  }
}

// --- 辅助逻辑 ---
onMounted(() => {
  fetchLogRecords()
  // 可选：记录路由
  if(route.path) localStorage.setItem('lastVisitedRoute', route.path)
})

const handleViewLogDetail = (row) => {
  if (!row) return
  currentLogDetail.value = row
  packetDetailVisible.value = true
}

const countByType = (type) => {
  return logRecords.value.filter(item => item.operation === type).length
}

// --- 格式化显示 ---
const formatDateTime = (ts) => {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleString('zh-CN', { 
      hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute:'2-digit', second:'2-digit'
    })
  } catch(e) { return ts }
}

const getStatusColor = (op) => {
  if (op === 'certificate_generation') return 'bg-green'
  if (op === 'big_concurrent_simulation') return 'bg-orange'
  return 'bg-gray'
}

const getOperationTypeTag = (op) => {
  const map = { 'certificate_generation': 'success', 'big_concurrent_simulation': 'warning' }
  return map[op] || 'info'
}

const getOperationTypeText = (op) => {
  const map = { 'certificate_generation': '证书生成', 'big_concurrent_simulation': '并发测试' }
  return map[op] || '未知操作'
}

const getLogSummary = (row) => {
  if (row.operation === 'certificate_generation') {
    return `Subject: ${row.subject?.common_name || 'N/A'} | Issuer: ${row.issuer || 'Self'}`
  }
  if (row.operation === 'big_concurrent_simulation') {
    return `Requests: ${row.config?.requests} | Concurrency: ${row.config?.concurrency}`
  }
  return row.request?.url || 'No summary available'
}

const getLogDetailTitle = (log) => {
  if (log.operation === 'certificate_generation') return `Audit: Certificate Forgery (${log.subject?.common_name})`
  if (log.operation === 'big_concurrent_simulation') return `Audit: Load Test (${log.config?.requests} reqs)`
  return 'Raw Log Data'
}

// --- 分页事件处理 --- 
const handlePageSizeChange = (size) => {
  pagination.value.pageSize = size
  pagination.value.currentPage = 1 // 每页条数变化时重置到第一页
}

const handleCurrentPageChange = (page) => {
  pagination.value.currentPage = page
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

/* --- 核心变量 (与主页统一) --- */
.history-page-container {
  --primary: #3b82f6;
  --bg-main: #f1f5f9;
  --bg-card: #ffffff;
  --border: #e2e8f0;
  --text-main: #1e293b;
  --text-light: #64748b;
  
  min-height: 100vh;
  background-color: var(--bg-main);
  font-family: 'Inter', sans-serif;
  color: var(--text-main);
}

/* --- 顶部导航栏 --- */
.page-navbar {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  height: 64px;
  padding: 0 40px;
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 100;
}
.brand { display: flex; align-items: center; gap: 14px; }
.logo-icon {
  width: 38px; height: 38px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: white; font-size: 20px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.logo-icon.history-theme {
  background: linear-gradient(135deg, #6366f1, #4338ca); /* 紫色系区别于蓝色的仿真页 */
}
.brand-text h1 { font-size: 18px; font-weight: 700; margin: 0; color: #0f172a; }
.subtitle { font-size: 11px; color: var(--text-light); letter-spacing: 0.5px; }

/* --- 主内容区域 --- */
.main-content { max-width: 1200px; margin: 24px auto; padding: 0 20px; }

/* --- 统计卡片 --- */
.stats-row {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 24px;
}
.stat-card {
  background: #fff; border-radius: 10px; padding: 20px;
  border: 1px solid var(--border);
  display: flex; align-items: center; gap: 16px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  transition: transform 0.2s;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0,0,0,0.05); }
.stat-icon {
  width: 48px; height: 48px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; color: #fff;
}
.stat-info { display: flex; flex-direction: column; }
.stat-info .label { font-size: 12px; color: var(--text-light); font-weight: 500; }
.stat-info .value { font-size: 24px; font-weight: 700; color: var(--text-main); font-family: 'JetBrains Mono'; }

/* 颜色辅助类 */
.bg-blue { background: #3b82f6; }
.bg-green { background: #10b981; }
.bg-orange { background: #f59e0b; }
.bg-gray { background: #94a3b8; }

/* --- 表格卡片 --- */
.table-card { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
:deep(.el-card__header) { padding: 15px 20px; border-bottom: 1px solid var(--border); background: #f8fafc; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-title { font-weight: 600; font-size: 14px; display: flex; align-items: center; }

/* 表格样式微调 */
:deep(.custom-header th) {
  background-color: #f8fafc !important;
  color: var(--text-light);
  font-weight: 600;
  font-size: 12px;
}
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.custom-tag { border-radius: 4px; font-weight: 600; border: none; }
.summary-text { font-size: 13px; color: #334155; }
.mono-font { font-family: 'JetBrains Mono'; font-size: 12px; color: #64748b; }
.pagination-footer { padding: 12px 20px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; }
.footer-text { font-size: 12px; color: var(--text-light); }

/* --- 弹窗样式 --- */
.dialog-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 16px; }
.json-wrapper { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.json-toolbar { background: #f1f5f9; padding: 6px 12px; border-bottom: 1px solid var(--border); }
.json-label { font-size: 11px; font-weight: 700; color: var(--text-light); text-transform: uppercase; }

/* --- Element Plus 覆盖 --- */
:deep(.el-table__row) { cursor: pointer; transition: background 0.15s; }
:deep(.jv-container) { font-family: 'JetBrains Mono' !important; font-size: 12px; background: #fff; }
:deep(.jv-container .jv-code) { padding: 15px; }

/* --- Utils --- */
.mr-1 { margin-right: 6px; }
</style>