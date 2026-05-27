// /front/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import SimulationPage from '@/pages/SimulationPage.vue'
import HistoryPage from '@/pages/HistoryPage.vue'
import HttpTcpPage from '@/pages/HttpTcp.vue' // 【新增：导入拓扑图组件】
import SecuritySimulation from '@/pages/SecuritySimulation.vue' // 【新增：导入安全模拟组件】
import Big from '@/pages/Big.vue' // 【新增：导入大并发模拟组件】
import Ai_analyze from "@/pages/Ai_analyze.vue";
import MaliciousAnalysis from '@/pages/MaliciousAnalysis.vue' // 1. 导入新组件

const routes = [
  {
    path: '/simulation',
    name: 'Simulation',
    component: SimulationPage,
    meta: { title: 'HTTP/HTTPS请求仿真' }
  },
  // 【新增：安全模拟路由，插入到第二个位置，匹配侧边栏顺序】
  {
    path: '/security-simulation',
    name: 'SecuritySimulation',
    component: SecuritySimulation,
    meta: { title: '安全模拟功能' }
  },
  // 【新增：大并发模拟路由，插入到第三个位置，匹配侧边栏顺序】
  {
    path: '/big-simulation',
    name: 'BigSimulation',
    component: Big,
    meta: { title: '大并发模拟' }
  },
  // 【新增：拓扑图路由，插入到第四个位置，匹配侧边栏顺序】
  {
    path: '/tcp-topology',
    name: 'TcpTopology',
    component: HttpTcpPage,
    meta: { title: 'TCP/HTTP报文拓扑图' }
  },
  {
    path: '/ai-analyze',
    name: 'AiAnalysis',
    component: Ai_analyze,
    meta: { title: 'AI智能报文分析' }
  },
  // 2. 【新增】在 Ai_analyze 下方插入
  {
    path: '/malicious-analysis',
    name: 'MaliciousAnalysis',
    component: MaliciousAnalysis,
    meta: { title: '恶意流量检测仪表盘' }
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryPage,
    meta: { title: '仿真历史记录' }
  },
  // 保留根路径重定向，后续在守卫中覆盖其默认行为
  {
    path: '/',
    redirect: '/simulation'
  },
  // 404 兜底路由
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: { template: '<div style="text-align:center;padding:100px"><h1>404</h1><p>页面未找到</p></div>' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  // 【新增核心逻辑1：读取localStorage中保存的最后访问路由】
  const lastVisitedRoute = localStorage.getItem('lastVisitedRoute')
  // 【修改：更新合法路由列表，添加安全模拟、大并发模拟和拓扑图路由，避免无效值报错】
  const validRoutes = [
    '/simulation',
    '/security-simulation',
    '/big-simulation',
    '/tcp-topology',
    '/ai-analyze',
    '/malicious-analysis',
    '/history'
  ]

  // 【新增核心逻辑2：访问根路径时，优先重定向到最后访问的合法路由】
  if (to.path === '/') {
    if (lastVisitedRoute && validRoutes.includes(lastVisitedRoute)) {
      // 有保存的合法路由，重定向到该路由
      next(lastVisitedRoute)
    } else {
      // 无有效保存路由，使用默认重定向
      next('/simulation')
    }
    return // 终止后续默认逻辑，避免重复导航
  }

  // 【保留原有逻辑：设置页面标题】
  document.title = to.meta.title || 'HTTP/HTTPS仿真工具'
  
  // 【新增核心逻辑3：非根路径访问时，更新localStorage中的最后访问路由（可选，增强鲁棒性）】
  if (validRoutes.includes(to.path)) {
    localStorage.setItem('lastVisitedRoute', to.path)
  }

  next()
})

export default router