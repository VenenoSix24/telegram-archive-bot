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