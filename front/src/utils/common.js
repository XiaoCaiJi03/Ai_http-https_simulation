/**
 * 公共工具函数库，提升代码复用性和容错性
 */

/**
 * 格式化日期时间（返回YYYY-MM-DD HH:mm:ss格式）
 * @param {Date|String|Number} date - 日期数据
 * @returns {String} 格式化后的日期字符串
 */
export const formatDateTime = (date) => {
  if (!date) return ''
  const targetDate = new Date(date)
  if (isNaN(targetDate.getTime())) return ''

  const year = targetDate.getFullYear()
  const month = String(targetDate.getMonth() + 1).padStart(2, '0')
  const day = String(targetDate.getDate()).padStart(2, '0')
  const hours = String(targetDate.getHours()).padStart(2, '0')
  const minutes = String(targetDate.getMinutes()).padStart(2, '0')
  const seconds = String(targetDate.getSeconds()).padStart(2, '0')

  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

/**
 * 安全解析JSON（防止解析失败报错）
 * @param {String} str - 要解析的JSON字符串
 * @param {*} defaultValue - 解析失败时的默认值
 * @returns {*} 解析结果或默认值
 */
export const safeJsonParse = (str, defaultValue = {}) => {
  if (!str || typeof str !== 'string') return defaultValue
  try {
    return JSON.parse(str)
  } catch (e) {
    console.warn('JSON解析失败，返回默认值：', e)
    return defaultValue
  }
}

/**
 * 验证URL格式合法性（支持HTTP/HTTPS）
 * @param {String} url - 要验证的URL
 * @returns {Object} { valid: 布尔值, message: 提示信息 }
 */
export const validateUrlFormat = (url) => {
  if (!url || typeof url !== 'string' || !url.trim()) {
    return { valid: false, message: 'URL不能为空' }
  }

  const trimUrl = url.trim()
  const urlRegex = /^(https?:\/\/)?([\da-z.-]+|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d{1,5})?([\/\w.-]*)*\/?(\?[^\s]*)?$/i

  if (!urlRegex.test(trimUrl)) {
    return { valid: false, message: 'URL格式非法，请输入类似 http://example.com 的有效地址' }
  }

  return { valid: true, message: 'URL格式合法' }
}