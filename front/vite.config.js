import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    // 配置路径别名，方便项目内文件导入
    alias: {
      '@': resolve(__dirname, './src')
    }
  },
  server: {
    port: 8080, // 原开发环境端口8080
    open: true, // 启动后自动打开浏览器
    cors: true, // 允许跨域（对接后端时使用）
    // 新增：代理配置（核心，解决/api请求转发问题）
    proxy: {
      // 匹配所有以/api开头的请求路径
      '/api': {
        target: 'http://127.0.0.1:60110',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist', // 构建输出目录
    assetsDir: 'assets', // 静态资源目录
    sourcemap: false // 关闭生产环境sourcemap，减小包体积
  }
})