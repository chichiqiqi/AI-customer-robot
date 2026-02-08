<template>
  <div class="navbar">
    <div class="navbar-left">
      <span class="logo">智能客服</span>
    </div>
    <div class="navbar-center">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="nav-tab"
        :class="{ active: currentPath === tab.path }"
      >
        {{ tab.label }}
      </router-link>
    </div>
    <div class="navbar-right">
      <span class="username">{{ authStore.username }}</span>
      <button class="logout-btn" @click="authStore.logout()">退出</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const currentPath = computed(() => route.path)

const tabs = [
  { path: '/employee', label: '员工咨询' },
  { path: '/agent', label: '坐席端' },
  { path: '/qc', label: '质检' },
  { path: '/knowledge', label: '知识库' },
]
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.navbar-left .logo {
  font-size: 18px;
  font-weight: 700;
  color: #409eff;
}

.navbar-center {
  display: flex;
  gap: 4px;
}

.nav-tab {
  padding: 8px 20px;
  border-radius: 20px;
  font-size: 14px;
  color: #606266;
  text-decoration: none;
  transition: all 0.2s;
}

.nav-tab:hover {
  background: #ecf5ff;
  color: #409eff;
}

.nav-tab.active {
  background: #409eff;
  color: #fff;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  font-size: 14px;
  color: #303133;
}

.logout-btn {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 16px;
  background: #fff;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  border-color: #409eff;
  color: #409eff;
}
</style>
