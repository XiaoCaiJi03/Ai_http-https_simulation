import { createApp, nextTick } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css' // 暗色系备用（提升扩展性）
import JsonViewer from 'vue-json-viewer'
import 'vue-json-viewer/style.css'
import './assets/styles/global.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'  // 全局注册图标

// 创建Vue应用实例
const app = createApp(App)

// 挂载全局依赖
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.use(JsonViewer)

// 关键修改1：全局注册所有Element Plus图标（新增Vue组件依赖此配置）
// 循环遍历所有图标，注册为全局组件，确保组件内可直接使用无需单独导入
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 全局挂载ElMessage（方便组件内直接调用）
import { ElMessage } from 'element-plus'
app.config.globalProperties.$message = ElMessage

// 关键修改2：增加DOM存在性判断，避免挂载失败报错（提升健壮性）
app.mount('#app')
nextTick(() => {
  const appDom = document.getElementById('app')
  if (appDom) {
    appDom.classList.add('loaded')
  }
})