<script setup lang="ts">
import { LayoutDashboard, Images, Tags, Settings, LogOut } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { logout } from '@/lib/api'
import { cn } from '@/lib/utils'

const route = useRoute()
const router = useRouter()

const nav = [
  { name: 'dashboard', label: '概览', icon: LayoutDashboard },
  { name: 'messages', label: '素材', icon: Images },
  { name: 'tags', label: '标签', icon: Tags },
  { name: 'settings', label: '设置', icon: Settings },
]

async function onLogout() {
  try {
    await logout()
  } finally {
    sessionStorage.removeItem('archive_authed')
    router.push('/login')
  }
}
</script>

<template>
  <div class="flex min-h-screen">
    <aside class="sticky top-0 flex h-screen w-40 shrink-0 flex-col border-r border-ink-line bg-ink-bg">
      <div class="px-4 pb-6 pt-5">
        <p class="font-display text-sm font-semibold tracking-tight text-gold">ARCHIVE</p>
        <p class="text-xs text-steam-dim">Telegram 归档库</p>
      </div>
      <nav class="flex flex-col gap-1 px-2" aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.name"
          :to="{ name: item.name }"
          :aria-current="route.name === item.name ? 'page' : undefined"
          :class="cn(
            'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
            route.name === item.name
              ? 'bg-gold/15 text-gold'
              : 'text-steam-dim hover:bg-ink-raised hover:text-steam',
          )"
        >
          <component :is="item.icon" class="h-4 w-4" />
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="mt-auto mb-4 px-2">
        <button
          type="button"
          class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam cursor-pointer"
          @click="onLogout"
        >
          <LogOut class="h-4 w-4" />
          退出
        </button>
      </div>
    </aside>
    <main class="min-w-0 flex-1">
      <RouterView />
    </main>
  </div>
</template>