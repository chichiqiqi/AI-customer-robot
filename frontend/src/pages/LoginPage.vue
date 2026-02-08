<template>
  <div class="login-container">
    <div class="login-left">
      <div class="brand-content">
        <h1 class="brand-title">智能客服系统</h1>
        <p class="brand-subtitle">让每一次咨询都变得简单高效</p>
        <div class="brand-features">
          <div class="feature-item">
            <span class="feature-icon">🤖</span>
            <span>AI 智能问答</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">👨‍💼</span>
            <span>人工坐席协作</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">📊</span>
            <span>质检评分闭环</span>
          </div>
        </div>
      </div>
    </div>
    <div class="login-right">
      <div class="login-card">
        <h2 class="login-title">欢迎登录</h2>
        <form @submit.prevent="handleLogin" class="login-form">
          <div class="form-group">
            <label class="form-label">用户名</label>
            <input
              v-model="form.username"
              type="text"
              class="form-input"
              placeholder="请输入用户名"
              autofocus
            />
          </div>
          <div class="form-group">
            <label class="form-label">密码</label>
            <input
              v-model="form.password"
              type="password"
              class="form-input"
              placeholder="请输入密码"
              @keyup.enter="handleLogin"
            />
          </div>
          <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
          <button type="submit" class="login-btn" :disabled="loading">
            {{ loading ? '登录中...' : '立即登录' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  password: '',
})

async function handleLogin() {
  if (!form.username || !form.password) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    await authStore.login(form.username, form.password)
  } catch (e: any) {
    errorMsg.value = e.message || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.login-left {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: #fff;
}

.brand-content {
  padding: 40px;
  max-width: 420px;
}

.brand-title {
  font-size: 36px;
  font-weight: 700;
  margin-bottom: 12px;
}

.brand-subtitle {
  font-size: 16px;
  opacity: 0.85;
  margin-bottom: 40px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
}

.feature-icon {
  font-size: 24px;
}

.login-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-card {
  width: 400px;
  padding: 48px 40px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.login-title {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 32px;
  text-align: center;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.form-input {
  padding: 12px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 10px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}

.error-msg {
  color: #f56c6c;
  font-size: 13px;
  margin: -8px 0 0;
}

.login-btn {
  padding: 14px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  margin-top: 8px;
}

.login-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
