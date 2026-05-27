import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import request from '@/utils/request' // 对应你的request.js


export const useSimulationStore = defineStore('simulation', {
  state: () => ({
    loading: false,
    history: {
      list: [],
      currentDetail: null,
      pagination: {
        page: 1,
        size: 10,
        total: 0
      },
      loading: {
        list: false,
        detail: false,
        delete: false
      }
    }
  }),

  actions: {
    setLoading(val) {
      this.loading = val
    },

    /**
     * 获取历史记录列表（与你的request.js完全适配）
     */
    async fetchHistoryList(params = {}) {
      try {
        this.history.loading.list = true
        // 补充分页参数（与后端接口一致）
        const requestParams = {
          page: this.history.pagination.page,
          size: this.history.pagination.size,
          ...params
        }
        // 调用接口（你的request.js已处理code校验）
        const res = await request({
          url: '/history/list', // 后端实际列表接口
          method: 'GET',
          params: requestParams
        })
        // 直接读取res.data（你的request.js返回的是后端{code:200, data:..., message:...}中的res）
        this.history.list = res.data.list || []
        this.history.pagination.total = res.data.pagination.total || 0
      } catch (err) {
        console.error('历史记录列表查询失败：', err)
      } finally {
        this.history.loading.list = false
      }
    },

    /**
     * 获取单条历史记录详情
     */
    async fetchHistoryDetail(id) {
      if (!id) {
        ElMessage.warning('历史记录ID不能为空')
        return null
      }
      try {
        this.history.loading.detail = true
        const res = await request({
          url: `/history/detail/${id}`, // 后端实际详情接口
          method: 'GET'
        })
        // 直接读取res.data（后端返回的单条记录详情）
        this.history.currentDetail = res.data
        return res.data
      } catch (err) {
        console.error('历史记录详情查询失败：', err)
        return null
      } finally {
        this.history.loading.detail = false
      }
    },

    /**
     * 删除单条历史记录
     */
    async deleteHistoryItem(id) {
      if (!id) {
        ElMessage.warning('历史记录ID不能为空')
        return false
      }
      try {
        this.history.loading.delete = true
        await request({
          url: `/history/delete/${id}`, // 后端实际删除接口
          method: 'DELETE'
        })
        ElMessage.success('删除历史记录成功')
        // 本地更新列表
        this.history.list = this.history.list.filter(item => item.id !== id)
        this.history.pagination.total -= 1
        return true
      } catch (err) {
        console.error('历史记录删除失败：', err)
        return false
      } finally {
        this.history.loading.delete = false
      }
    },

    resetHistoryPagination() {
      this.history.pagination = {
        page: 1,
        size: 10,
        total: 0
      }
    }
  }
})