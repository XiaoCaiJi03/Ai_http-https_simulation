import axios from 'axios'
import { ElMessage } from 'element-plus'

// 创建Axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/', // 接口基础路径（从环境变量读取）
  timeout: 30000, // 请求超时时间（30秒）
  headers: {
    'Content-Type': 'application/json;charset=utf-8'
  }
})

// 请求拦截器：添加请求头、处理加载状态等
service.interceptors.request.use(
  (config) => {
    // 可在此添加token等认证信息（后续扩展）
    return config
  },
  (error) => {
    // 请求错误处理
    ElMessage.error(`请求发送失败：${error.message}`)
    console.error('Axios请求拦截器错误：', error)
    return Promise.reject(error)
  }
)

// 响应拦截器：处理响应数据、统一错误处理
service.interceptors.response.use(
  (response) => {
    const res = response.data

    // 接口返回非200状态码（业务错误）
    if (res.code !== 200) {
      ElMessage.warning(res.message || '接口返回异常')
      return Promise.reject(new Error(res.message || '接口返回异常'))
    }

    // 接口返回成功
    return res
  },
  (error) => {
    // 网络错误、超时等系统错误
    let errorMsg = '请求失败，请检查网络连接'
    if (error.code === 'ECONNABORTED') {
      errorMsg = '请求超时，请稍后重试'
    } else if (error.response) {
      errorMsg = `请求错误 [${error.response.status}]：${error.response.statusText}`
    }

    ElMessage.error(errorMsg)
    console.error('Axios响应拦截器错误：', error)
    return Promise.reject(error)
  }
)

// 暴露封装后的Axios实例（兼容用户原代码中的request调用）
export default service