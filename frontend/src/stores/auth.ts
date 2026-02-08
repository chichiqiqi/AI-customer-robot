import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')

  const isAuthenticated = computed(() => !!token.value)

  async function login(user: string, password: string) {
    const res = await api.post('/api/auth/login', { username: user, password })
    const data = res.data
    if (data.success) {
      token.value = data.data.token
      username.value = data.data.username
      localStorage.setItem('token', token.value)
      localStorage.setItem('username', username.value)
      router.push('/employee')
    } else {
      throw new Error(data.error || '登录失败')
    }
  }

  function logout() {
    token.value = ''
    username.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    router.push('/login')
  }

  return { token, username, isAuthenticated, login, logout }
})
