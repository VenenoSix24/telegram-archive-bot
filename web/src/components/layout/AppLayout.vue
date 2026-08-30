<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { LayoutDashboard, Images, Tags, Settings, LogOut, Sun, Moon, Palette } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { logout } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  applyTheme,
  currentTheme,
  cycleTheme,
  renderedDark,
  setMode,
  type ThemeKey,
} from '@/composables/useTheme'

const route = useRoute()
const router = useRouter()

onMounted(applyTheme)

const nav = [
  { name: 'dashboard', label: '概览', icon: LayoutDashboard },
  { name: 'messages', label: '素材', icon: Images },
  { name: 'tags', label: '标签', icon: Tags },
  { name: 'settings', label: '设置', icon: Settings },
]

const themeLabels: Record<ThemeKey, string> = {
  projector: '放映室',
  midnight: '深海',
  moss: '苔原',
}

const isActive = (name: string) => route.name === name

async function onLogout() {
  try {
    await logout()
  } finally {
    sessionStorage.removeItem('archive_authed')
    router.push('/login')
  }
}

const shouldShowNav = computed(() => !!route.name)
</script>

<template>
  <div class="min-h-screen">
    <!-- 桌面端侧边栏 -->
    <aside
      class="fixed inset-y-0 left-0 z-30 hidden w-44 shrink-0 flex-col border-r border-ink-line bg-ink-bg px-3 py-6 md:flex"
    >
      <div class="px-2 pb-6">
        <p class="font-display text-sm font-semibold tracking-tight text-gold">ARCHIVE</p>
        <p class="text-xs text-steam-dim">Telegram 归档库</p>
      </div>
      <nav class="flex flex-col gap-1" aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.name"
          :to="{ name: item.name }"
          :aria-current="isActive(item.name) ? 'page' : undefined"
          :class="cn(
            'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
            isActive(item.name)
              ? 'bg-gold/15 text-gold'
              : 'text-steam-dim hover:bg-ink-raised hover:text-steam',
          )"
        >
          <component :is="item.icon" class="h-4 w-4" />
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="mt-auto">
        <button
          type="button"
          class="mb-1 flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam cursor-pointer"
          :title="`循环切换主题，当前 ${themeLabels[currentTheme]}`"
          @click="cycleTheme"
        >
          <Palette class="h-4 w-4" />
          {{ themeLabels[currentTheme] }}
        </button>
        <button
          type="button"
          class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam cursor-pointer"
          :aria-label="renderedDark ? '切换浅色' : '切换深色'"
          @click="setMode(renderedDark ? 'light' : 'dark')"
        >
          <Sun v-if="renderedDark" class="h-4 w-4" />
          <Moon v-else class="h-4 w-4" />
          {{ renderedDark ? '浅色' : '深色' }}
        </button>
        <button
          type="button"
          class="mt-1 flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam cursor-pointer"
          @click="onLogout"
        >
          <LogOut class="h-4 w-4" />
          退出
        </button>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="min-w-0 pb-24 md:pl-44 md:pb-0">
      <RouterView />
    </main>

    <!-- 移动端底部 tab 栏（iOS 26 悬浮胶囊风格），主题设置放设置页 -->
    <nav
      v-if="shouldShowNav"
      aria-label="移动端导航"
      class="fixed inset-x-0 bottom-4 z-40 mx-auto flex max-w-[20rem] items-center justify-around gap-1 rounded-full border border-ink-line/70 bg-ink-surface/85 px-2 py-1.5 shadow-lg backdrop-blur-md md:hidden"
    >
      <RouterLink
        v-for="item in nav"
        :key="item.name"
        :to="{ name: item.name }"
        :aria-current="isActive(item.name) ? 'page' : undefined"
        :class="cn(
          'flex flex-col items-center gap-0.5 rounded-full px-3 py-1.5 text-[10px] transition-colors',
          isActive(item.name) ? 'bg-gold/15 text-gold' : 'text-steam-dim hover:text-steam',
        )"
      >
        <component :is="item.icon" class="h-5 w-5" />
        {{ item.label }}
      </RouterLink>
    </nav>
  </div>
</template>