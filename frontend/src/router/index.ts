import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../pages/LoginPage.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/employee',
    name: 'Employee',
    component: () => import('../pages/EmployeePage.vue'),
  },
  {
    path: '/agent',
    name: 'Agent',
    component: () => import('../pages/AgentPage.vue'),
  },
  {
    path: '/qc',
    name: 'QC',
    component: () => import('../pages/QCPage.vue'),
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('../pages/KnowledgePage.vue'),
  },
  {
    path: '/',
    redirect: '/employee',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录重定向到 /login
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth === false) {
    next()
  } else if (!token) {
    next('/login')
  } else {
    next()
  }
})

export default router
