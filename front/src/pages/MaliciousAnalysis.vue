<!-- /front/src/pages/MaliciousAnalysis.vue -->
<template>
  <div class="analysis-page">
    <div class="page-navbar">
      <div class="brand">
        <div class="logo-icon security-theme">
          <el-icon><Warning /></el-icon>
        </div>
        <div class="brand-text">
          <h1>恶意流量监测中心</h1>
        </div>
      </div>
    </div>

    <el-row :gutter="24" class="main-content">

      <!-- 左侧：控制台 (支持 Tab 切换) -->
      <el-col :span="10" :xs="24" class="col-left">
        <el-card shadow="never" class="control-panel glass-panel">

          <!-- 核心修改：Tab 切换 -->
          <el-tabs v-model="activeTab" class="custom-tabs" stretch>

            <!-- Tab 1: 单条检测 -->
            <el-tab-pane label="实时检测" name="single">
              <div class="tab-content">
                <div class="action-bar">
                  <span class="sub-label">输入报文样本:</span>
                  <div class="sample-btns">
                    <el-button type="info" link size="small" @click="loadSample('normal')">正常样本</el-button>
                    <el-button type="danger" link size="small" @click="loadSample('malicious')">恶意样本</el-button>
                  </div>
                </div>

                <el-input
                  v-model="requestContent"
                  type="textarea"
                  :rows="12"
                  placeholder="请输入 HTTP 请求报文或 URL Payload..."
                  class="code-input dark-theme-input"
                  resize="none"
                />

                <div class="single-footer">
                  <el-button
                    type="primary"
                    class="analyze-btn shadow-btn"
                    :loading="analyzing"
                    @click="startSingleDetection"
                    round
                    block
                  >
                    <el-icon><Aim /></el-icon> 立即检测
                  </el-button>
                </div>
              </div>
            </el-tab-pane>

            <!-- Tab 2: AI 样本生成 (替换了原来的文件上传) -->
            <el-tab-pane label="AI 样本生成" name="batch">
              <div class="tab-content ai-gen-container">
                <div class="gen-wrapper">
                  <div class="icon-box">
                    <el-icon class="gen-icon"><Cpu /></el-icon>
                  </div>
                  <h3>AI 攻击样本生成器</h3>
                  <p class="desc">
                    利用大模型自动生成 {{ generateCount }} 条 HTTP 请求报文（混合正常业务与常见的 Web 攻击 Payload），并自动送入检测模型进行验证。
                  </p>

                  <div class="slider-box">
                    <span class="label">生成数量:</span>
                    <el-slider v-model="generateCount" :min="5" :max="50" show-input />
                  </div>
                </div>

                <div class="batch-footer">
                  <el-button
                    type="success"
                    class="analyze-btn shadow-btn"
                    :loading="generating"
                    @click="startAiGeneration"
                    round
                    block
                  >
                    <el-icon><MagicStick /></el-icon>
                    {{ generating ? 'AI 正在生成数据中...' : '开始生成并检测' }}
                  </el-button>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>

        </el-card>

        <!-- 检测结果速览 (仅单条模式显示) -->
        <transition name="el-fade-in">
          <div class="result-quick-view glass-panel mt-3" v-if="activeTab === 'single' && lastSingleResult">
            <div class="result-header">当前检测结果</div>
            <div class="result-body" :class="lastSingleResult.result === '恶意请求' ? 'is-danger' : 'is-safe'">
              <div class="result-icon">
                <el-icon v-if="lastSingleResult.result === '恶意请求'"><CircleCloseFilled /></el-icon>
                <el-icon v-else><CircleCheckFilled /></el-icon>
              </div>
              <div class="result-text">
                <h2>{{ lastSingleResult.result }}</h2>
                <p>置信度: {{ (lastSingleResult.confidence * 100).toFixed(2) }}%</p>
              </div>
            </div>
          </div>
        </transition>

        <!-- 批量结果速览 -->
        <transition name="el-fade-in">
          <div class="result-quick-view glass-panel mt-3" v-if="activeTab === 'batch' && batchResult">
            <div class="result-header">
              <span>批量分析报告</span>
              <!-- 新增：查看详情按钮 -->
              <el-button type="primary" link size="small" @click="showDetails = true">
                查看具体报文 >
              </el-button>
            </div>

            <div class="stats-grid">
              <div class="stat-item total">
                <div class="num">{{ batchResult.total }}</div>
                <div class="label">总条数</div>
              </div>
              <div class="stat-item safe">
                <div class="num">{{ batchResult.normal }}</div>
                <div class="label">正常请求</div>
              </div>
              <div class="stat-item danger">
                <div class="num">{{ batchResult.malicious }}</div>
                <div class="label">恶意请求</div>
              </div>
            </div>
          </div>
        </transition>

      </el-col>

      <!-- ================= 新增：详情抽屉 ================= -->
      <el-drawer
        v-model="showDetails"
        title="AI 生成报文检测详情"
        direction="rtl"
        size="50%"
        destroy-on-close
      >
        <el-table :data="batchResult?.details || []" style="width: 100%" stripe border height="calc(100vh - 100px)">
          <!-- ID列 -->
          <el-table-column prop="id" label="#" width="50" align="center" />

          <!-- 类型列 -->
          <el-table-column prop="result" label="检测结果" width="100" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.result === '恶意请求' ? 'danger' : 'success'">
                {{ scope.row.result }}
              </el-tag>
            </template>
          </el-table-column>

          <!-- 概率列 -->
          <el-table-column prop="malicious_prob" label="恶意值" width="80" align="center">
            <template #default="scope">
              <span :style="{ color: getRiskColor(scope.row.malicious_prob) }">
                {{ (scope.row.malicious_prob * 100).toFixed(1) }}%
              </span>
            </template>
          </el-table-column>

          <!-- 内容列 (支持展开查看长文本) -->
          <el-table-column label="报文内容" min-width="200">
            <template #default="scope">
              <div class="code-preview">
                {{ scope.row.content }}
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-drawer>

      <!-- 右侧：图表可视化 (柱状图 + 饼图) -->
      <el-col :span="14" :xs="24" class="col-right">
        <div class="charts-container">

          <!-- 图表 1: 饼图 (比例) -->
          <div class="chart-card glass-panel mb-3" style="flex: 1;">
            <div class="chart-header">
              <span class="dot purple"></span>
              <span class="chart-title">流量成分占比 (Pie Chart)</span>
            </div>
            <div class="chart-body" ref="pieChartRef"></div>
          </div>

          <!-- 图表 2: 柱状图 (数量) -->
          <div class="chart-card glass-panel" style="flex: 1;">
            <div class="chart-header">
              <span class="dot blue"></span>
              <span class="chart-title">检测数量统计 (Bar Chart)</span>
            </div>
            <div class="chart-body" ref="barChartRef"></div>
          </div>

        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import {
  Warning, Aim, CircleCloseFilled, CircleCheckFilled,
  MagicStick, Cpu
} from '@element-plus/icons-vue'
import request from '@/utils/request'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'

// --- 状态数据 ---
const activeTab = ref('single')
const requestContent = ref('')
const analyzing = ref(false)
// --- 修改点：AI 生成相关状态 ---
const generating = ref(false) // 替换了 uploading
const generateCount = ref(20) // 默认生成 20 条

// 结果数据
const lastSingleResult = ref(null)
const batchResult = ref(null)
const showDetails = ref(false) // 控制抽屉显示

// 统计数据 (用于图表)
const statsData = ref({
  normal: 0,
  malicious: 0
})

// ECharts 实例
const pieChartRef = ref(null)
const barChartRef = ref(null)
let pieChart = null
let barChart = null

// --- Mock 样本 ---
const samples = {
  normal: `GET /index.html HTTP/1.1
Host: www.example.com
User-Agent: Mozilla/5.0
Accept: text/html`,
  // 注意这里的转义
  malicious: `GET /login.php?user=<script>alert(1)<\/script> HTTP/1.1
Host: www.target.com
User-Agent: sqlmap/1.0
Connection: close`
}

const loadSample = (type) => {
  requestContent.value = samples[type]
}

// --- 新增：辅助函数 ---
// 根据恶意概率返回颜色
const getRiskColor = (prob) => {
  if (prob > 0.8) return '#F56C6C' // 红
  if (prob > 0.5) return '#E6A23C' // 橙
  return '#67C23A' // 绿
}

// --- ECharts 初始化与配置 ---
const initCharts = () => {
  // 1. 饼图 (Pie)
  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
    pieChart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)' // 鼠标悬停显示：名称: 数量 (百分比)
      },
      legend: {
        bottom: '0%',
        left: 'center',
        itemGap: 20
      },
      series: [
        {
          name: '流量类型',
          type: 'pie',
          radius: ['40%', '65%'], // 稍微调小一点外圆半径，给标签留出空间
          center: ['50%', '45%'], //稍微向上提一点，防止遮挡图例
          avoidLabelOverlap: true, // 防止标签重叠
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2
          },
          // ============ 核心修改开始 ============
          label: {
            show: true,             // 开启标签显示
            position: 'outside',    // 显示在扇区外侧
            formatter: '{b}\n{d}%', // 格式化内容：{b}=名称 \n=换行 {d}=百分比
            fontWeight: 'bold',
            fontSize: 13,
            color: '#4a4a4a'        // 字体颜色，深灰色更清晰
          },
          labelLine: {
            show: true,             // 显示连接线
            length: 15,             // 第一段线长
            length2: 15,            // 第二段线长
            smooth: true            // 平滑曲线
          },
          // ============ 核心修改结束 ============
          emphasis: {
            label: { show: true, fontSize: 16, fontWeight: 'bold' },
            scale: true,
            scaleSize: 10
          },
          data: [
            { value: 0, name: '正常请求', itemStyle: { color: '#67C23A' } },
            { value: 0, name: '恶意请求', itemStyle: { color: '#F56C6C' } }
          ]
        }
      ]
    })
  }

  // 2. 柱状图 (Bar)
  if (barChartRef.value) {
    barChart = echarts.init(barChartRef.value)
    barChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['正常请求', '恶意请求'],
        axisTick: { alignWithLabel: true }
      },
      yAxis: { type: 'value' },
      series: [
        {
          name: '数量',
          type: 'bar',
          barWidth: '50%',
          data: [
            { value: 0, itemStyle: { color: '#67C23A' } },
            { value: 0, itemStyle: { color: '#F56C6C' } }
          ]
        }
      ]
    })
  }
}

// --- 核心逻辑：刷新图表 ---
const refreshCharts = () => {
  const normal = statsData.value.normal
  const malicious = statsData.value.malicious

  // 更新饼图
  if (pieChart) {
    pieChart.setOption({
      series: [{
        data: [
          { value: normal, name: '正常请求', itemStyle: { color: '#67C23A' } },
          { value: malicious, name: '恶意请求', itemStyle: { color: '#F56C6C' } }
        ]
      }]
    })
  }

  // 更新柱状图
  if (barChart) {
    barChart.setOption({
      series: [{
        data: [
          { value: normal, itemStyle: { color: '#67C23A' } },
          { value: malicious, itemStyle: { color: '#F56C6C' } }
        ]
      }]
    })
  }
}

// --- 逻辑 1: 单条检测 ---
const startSingleDetection = async () => {
  if (!requestContent.value.trim()) return ElMessage.warning('请输入内容')

  analyzing.value = true
  try {
    const res = await request.post('/api/malicious/analyze', { http_request: requestContent.value })
    const data = res.data
    lastSingleResult.value = data

    // 单条模式下，我们累加数据来展示动态效果
    if (data.result === '恶意请求') statsData.value.malicious++
    else statsData.value.normal++

    refreshCharts()
    ElMessage.success('检测完成')
  } catch (e) {
    ElMessage.error('检测失败')
  } finally {
    analyzing.value = false
  }
}

// --- 修改点：新增 AI 生成逻辑 (替换了文件上传) ---
const startAiGeneration = async () => {
  generating.value = true
  // 重置图表数据，给用户一种重新开始的感觉
  statsData.value.normal = 0
  statsData.value.malicious = 0
  refreshCharts()

  try {
    // 调用新的后端接口
    const res = await request.post('/api/malicious/generate_analyze', {
      count: generateCount.value
    }, {
      timeout: 300000
    })

    const data = res.data
    batchResult.value = data

    // 更新统计数据
    statsData.value.normal = data.normal
    statsData.value.malicious = data.malicious

    refreshCharts()
    ElMessage.success(`生成完成！共 ${data.total} 条样本 (恶意: ${data.malicious})`)
  } catch (e) {
    // 如果超时（AI 生成可能较慢），提示用户
    if (e.code === 'ECONNABORTED') {
      ElMessage.warning('AI 生成耗时较长，请稍后刷新查看结果')
    } else {
      ElMessage.error('生成失败: ' + (e.message || '未知错误'))
    }
  } finally {
    generating.value = false
  }
}

// --- 生命周期 ---
onMounted(() => {
  nextTick(() => {
    initCharts()
    window.addEventListener('resize', handleResize)
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (pieChart) pieChart.dispose()
  if (barChart) barChart.dispose()
})

const handleResize = () => {
  pieChart && pieChart.resize()
  barChart && barChart.resize()
}


</script>

<style scoped>
/* 全局布局与背景 */
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
.logo-icon.security-theme { background: linear-gradient(135deg, #f56c6c, #e6a23c); }
.brand-text h1 { margin: 0; font-size: 16px; color: #1a1a1a; }

.main-content { padding: 20px; flex: 1; margin: 0 !important; height: calc(100vh - 60px); }
.col-left, .col-right { height: 100%; display: flex; flex-direction: column; }

/* 玻璃拟态面板 */
.glass-panel {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

/* 左侧 Tab 样式覆写 */
.custom-tabs :deep(.el-tabs__header) { margin: 0; background: #fafafa; border-bottom: 1px solid #ebeef5; }
.custom-tabs :deep(.el-tabs__item) { height: 50px; line-height: 50px; font-weight: 600; }
.custom-tabs :deep(.el-tabs__content) { flex: 1; display: flex; flex-direction: column; height: calc(100% - 50px); }

/* Tab 内容布局 */
.control-panel { flex: 1; display: flex; flex-direction: column; margin-bottom: 0; }
.control-panel :deep(.el-card__body) { padding: 0; display: flex; flex-direction: column; flex: 1; height: 100%; }

.tab-content { padding: 0; display: flex; flex-direction: column; flex: 1; height: 100%; position: relative; }

/* 单条检测区域 */
.action-bar { padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; background: #fff; border-bottom: 1px solid #f2f2f2; }
.sub-label { font-size: 12px; color: #909399; font-weight: 600; }
.code-input :deep(.el-textarea__inner) {
  border: none; border-radius: 0; padding: 20px; flex: 1;
  background: #282c34; color: #abb2bf; font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 13px; line-height: 1.5; resize: none; box-shadow: none; height: 100% !important;
}
.single-footer { padding: 20px; background: #fff; border-top: 1px solid #ebeef5; margin-top: auto; }

/* 批量上传区域 */
.batch-container { padding: 30px; background: #fff; justify-content: center; }
.upload-wrapper { flex: 1; display: flex; flex-direction: column; justify-content: center; }
.upload-area :deep(.el-upload-dragger) { width: 100%; border: 2px dashed #dcdfe6; border-radius: 12px; transition: all 0.3s; }
.upload-area :deep(.el-upload-dragger:hover) { border-color: #409EFF; background: rgba(64, 158, 255, 0.05); }
.batch-footer { margin-top: 30px; }

/* 通用按钮 */
.shadow-btn { box-shadow: 0 4px 12px rgba(0,0,0,0.1); font-weight: 600; letter-spacing: 1px; }

/* 结果统计区域 */
.mt-3 { margin-top: 16px; }
.result-quick-view { padding: 20px; min-height: 120px; display: flex; flex-direction: column; justify-content: center; }
.result-header {
  font-size: 12px; color: #909399; font-weight: 600; text-transform: uppercase;
  margin-bottom: 12px;
  display: flex; justify-content: space-between; align-items: center; /* 修改点 */
}

/* 抽屉内代码预览样式 */
.code-preview {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  background: #f4f4f5;
  padding: 8px;
  border-radius: 4px;
  white-space: pre-wrap; /* 保留换行 */
  word-break: break-all;
  color: #303133;
  max-height: 150px;
  overflow-y: auto;
}

/* 单条结果样式 */
.result-body { display: flex; align-items: center; gap: 15px; padding: 10px; border-radius: 8px; }
.result-body.is-danger { background: rgba(245, 108, 108, 0.1); color: #F56C6C; }
.result-body.is-safe { background: rgba(103, 194, 58, 0.1); color: #67C23A; }
.result-icon { font-size: 40px; }
.result-text h2 { margin: 0; font-size: 20px; }
.result-text p { margin: 4px 0 0 0; font-size: 12px; opacity: 0.8; }

/* 批量结果 Grid 样式 */
.stats-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; text-align: center; }
.stat-item { padding: 10px; border-radius: 8px; background: #f5f7fa; }
.stat-item .num { font-size: 24px; font-weight: 700; color: #303133; }
.stat-item .label { font-size: 11px; color: #909399; margin-top: 4px; }
.stat-item.total .num { color: #409EFF; }
.stat-item.safe .num { color: #67C23A; }
.stat-item.danger .num { color: #F56C6C; }

/* 右侧图表区 */
.charts-container { height: 100%; display: flex; flex-direction: column; gap: 16px; }
.mb-3 { margin-bottom: 16px; }
.chart-card { display: flex; flex-direction: column; padding: 16px; }
.chart-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.chart-title { font-weight: 600; font-size: 14px; color: #606266; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.purple { background: #9b59b6; box-shadow: 0 0 8px rgba(155, 89, 182, 0.5); }
.dot.blue { background: #409EFF; box-shadow: 0 0 8px rgba(64, 158, 255, 0.5); }
.chart-body { flex: 1; width: 100%; min-height: 0; }
</style>