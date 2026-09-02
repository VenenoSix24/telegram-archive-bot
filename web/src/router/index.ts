import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/pages/LoginView.vue') },
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'dashboard', component: () => import('@/pages/DashboardView.vue') },
      { path: 'messages', name: 'messages', component: () => import('@/pages/MessagesView.vue') },
      { path: 'tags', name: 'tags', component: () => import('@/pages/TagsView.vue') },
      { path: 'settings', name: 'settings', component: () => import('@/pages/SettingsView.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // 后退/前进回原位；仅 query 变化（素材页标签筛选同步 URL）不动滚动；
    // 真换页回顶——避免 out-in 换页中新页高度不足导致的滚动 clamp 跳动
    if (savedPosition) return savedPosition
    if (to.path === from.path) return false
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  const authed = sessionStorage.getItem('archive_authed') === '1'
  if (to.name !== 'login' && !authed) {
    return { name: 'login' }
  }
  if (to.name === 'login' && authed) {
    return { path: '/dashboard' }
  }
  return true
})

export default router