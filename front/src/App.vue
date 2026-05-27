<!-- /front/src/App.vue -->
<template>
  <div class="app-container">
    <el-container class="main-layout">
      <!-- 侧边栏 -->
      <el-aside width="240px" class="sidebar-container">
        <!-- 1. Logo 区域 -->
        <div class="logo-wrapper">
          <div class="logo-icon">
            <el-icon><Platform /></el-icon>
          </div>
          <div class="logo-text">
            <h1>AI 仿真实验室</h1>
          </div>
        </div>

        <!-- 2. 菜单区域 -->
        <el-scrollbar class="menu-scrollbar">
          <el-menu
            :default-active="route.path"
            router
            unique-opened
            class="custom-menu"
            :collapse-transition="false"
          >
            <div class="menu-group-title">核心功能</div>
            
            <el-menu-item index="/simulation">
              <el-icon><DataAnalysis /></el-icon>
              <span>仿真操作</span>
            </el-menu-item>

            <!-- 【新增】恶意检测菜单项 -->
            <el-menu-item index="/malicious-analysis">
              <el-icon><Warning /></el-icon>
              <span>恶意流量检测</span>
            </el-menu-item>

            <el-menu-item index="/security-simulation">
              <el-icon><Lock /></el-icon>
              <span>安全模拟</span>
            </el-menu-item>

            <el-menu-item index="/big-simulation">
              <el-icon><Connection /></el-icon>
              <span>大并发模拟</span>
            </el-menu-item>

            <div class="menu-group-title" style="margin-top: 20px;">分析与监控</div>

            <el-menu-item index="/tcp-topology">
              <el-icon><DataLine /></el-icon>
              <span>HTTP/HTTPS拓扑图</span>
            </el-menu-item>

            <el-menu-item index="/ai-analyze">
              <el-icon><Cpu /></el-icon>
              <span>AI 智能分析</span>
            </el-menu-item>

            <el-menu-item index="/history">
              <el-icon><Clock /></el-icon>
              <span>历史记录</span>
            </el-menu-item>
          </el-menu>
        </el-scrollbar>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="main-content-wrapper">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { 
  DataAnalysis, Clock, Lock, Connection, 
  Cpu, Platform, DataLine, Warning
} from '@element-plus/icons-vue'

const route = useRoute()
</script>

<style scoped>
/* 引入字体 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.app-container {
  width: 100%;
  height: 100vh;
  background-color: #f1f5f9;
  font-family: 'Inter', sans-serif;
  overflow: hidden; /* 防止最外层出现滚动条 */
}

.main-layout {
  height: 100%;
}

/* --- 侧边栏容器 --- */
.sidebar-container {
  /* 修改背景色：调整为更浅的蓝灰色渐变，不再是深黑色 */
  background: linear-gradient(180deg, #364156 0%, #2b3648 100%);
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.1); /* 阴影也稍微变淡 */
  z-index: 100;
  transition: width 0.3s;
}

/* --- Logo 区域 --- */
.logo-wrapper {
  height: 80px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  gap: 12px;
  flex-shrink: 0; /* 防止Logo区域被压缩 */
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #3b82f6, #6366f1); /* 调整图标渐变色，使其更亮 */
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.logo-text h1 {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  margin: 0;
  line-height: 1.2;
  letter-spacing: 0.5px;
}

/* --- 菜单区域 --- */
.menu-scrollbar {
  flex: 1;
  padding: 16px 12px;
}

/* 强制隐藏横向滚动条 (修复底部滑动条问题) */
:deep(.el-scrollbar__wrap) {
  overflow-x: hidden !important;
}

:deep(.el-scrollbar__bar.is-horizontal) {
  display: none !important;
  height: 0 !important;
  opacity: 0 !important;
}

.custom-menu {
  border-right: none;
  background: transparent !important;
}

.menu-group-title {
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8; /* 文字颜色稍微提亮，适应浅色背景 */
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* 菜单项基础样式 */
:deep(.el-menu-item) {
  height: 50px;
  line-height: 50px;
  margin-bottom: 4px;
  border-radius: 8px;
  color: #e2e8f0 !important; /* 字体颜色更亮，增强对比度 */
  font-size: 14px;
  font-weight: 500;
  transition: all 0.25s ease;
  padding-left: 16px !important;
}

:deep(.el-menu-item .el-icon) {
  font-size: 18px;
  margin-right: 12px;
  color: #cbd5e1; /* 图标颜色更亮 */
  transition: all 0.25s ease;
}

/* 悬停状态 */
:deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.1) !important;
  color: #fff !important;
  transform: translateX(4px);
}

:deep(.el-menu-item:hover .el-icon) {
  color: #fff;
}

/* 激活状态 */
:deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.2), transparent) !important;
  color: #60a5fa !important;
  position: relative;
  font-weight: 600;
}

/* 激活状态下的左侧装饰条 */
:deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  background-color: #3b82f6;
  border-radius: 0 4px 4px 0;
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.6);
}

:deep(.el-menu-item.is-active .el-icon) {
  color: #60a5fa !important;
}

/* --- 主内容区动画 --- */
.main-content-wrapper {
  padding: 0;
  background-color: #f1f5f9;
  position: relative;
  overflow-x: hidden;
}

/* 页面切换动画 */
.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.3s ease;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
</style>