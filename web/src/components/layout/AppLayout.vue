<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Check, ChevronDown, LayoutDashboard, Images, Tags, Settings, LogOut, Moon, Palette, Sun } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { logout } from '@/lib/api'
import { cn } from '@/lib/utils'
import { APP_VERSION } from '@/lib/version'
import {
  applyTheme,
  currentTheme,
  renderedDark,
  setMode,
  setTheme,
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
  collection: '素材志',
}
/* 已定稿待实现的方向：菜单里以禁用项示知路线，不做假开关 */
const upcomingThemes = ['暗房印样 · 制作中', '标准后台 · 制作中']

const isActive = (name: string) => route.name === name

/* 主题菜单：全部列出可选方向，当前项打勾 */
const themeMenuOpen = ref(false)
function onDocumentClick(event: MouseEvent) {
  const node = event.target as HTMLElement | null
  if (!node?.closest('[data-theme-menu]')) themeMenuOpen.value = false
}
onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

function pickTheme(key: ThemeKey) {
  setTheme(key)
  themeMenuOpen.value = false
}

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
    <!-- 顶部导航条：素材页目录成为唯一左栏，内容独占整宽 -->
    <header class="top-rules sticky top-0 z-30 border-b border-transparent bg-ink-bg/95 backdrop-blur">
      <div class="mx-auto flex h-14 max-w-[1440px] items-center gap-2 px-4 min-[820px]:px-8">
        <RouterLink :to="{ name: 'dashboard' }" class="mr-2 flex shrink-0 items-center gap-2.5">
          <svg class="mast-seal hidden h-8 w-8 text-gold min-[400px]:block" viewBox="0 0 52 52" aria-hidden="true">
            <rect x="2" y="2" width="48" height="48" rx="5" fill="none" stroke="currentColor" stroke-width="3.5" />
            <text x="26" y="37" text-anchor="middle" font-size="27" font-weight="700" fill="currentColor">档</text>
          </svg>
          <span class="font-display text-lg font-bold tracking-[0.2em] text-steam">素材志</span>
        </RouterLink>

        <nav class="hidden h-full items-stretch gap-1 md:flex" aria-label="主导航">
          <RouterLink
            v-for="item in nav"
            :key="item.name"
            :to="{ name: item.name }"
            :aria-current="isActive(item.name) ? 'page' : undefined"
            :class="cn(
              'relative flex items-center gap-2 px-3.5 text-sm transition-colors',
              isActive(item.name) ? 'text-gold' : 'text-steam-dim hover:text-steam',
            )"
          >
            <component :is="item.icon" class="h-4 w-4" />
            {{ item.label }}
            <span v-if="isActive(item.name)" class="absolute inset-x-3 bottom-0 h-[2px] bg-gold" aria-hidden="true"></span>
          </RouterLink>
        </nav>

        <div class="ml-auto flex items-center gap-1" data-theme-menu>
          <div class="relative">
            <button
              type="button"
              class="flex h-9 cursor-pointer items-center gap-1.5 rounded-md px-2.5 text-sm text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
              aria-haspopup="menu"
              :aria-expanded="themeMenuOpen"
              title="切换主题"
              @click="themeMenuOpen = !themeMenuOpen"
            >
              <Palette class="h-4 w-4" />
              <span class="hidden min-[480px]:inline">{{ themeLabels[currentTheme] }}</span>
              <ChevronDown class="h-3.5 w-3.5 transition-transform" :class="themeMenuOpen && 'rotate-180'" />
            </button>
            <div
              v-if="themeMenuOpen"
              role="menu"
              class="absolute right-0 top-full z-40 mt-1.5 w-44 rounded-md border border-ink-line bg-ink-surface p-1 shadow-lg"
            >
              <button
                v-for="(label, key) in themeLabels"
                :key="key"
                type="button"
                role="menuitemradio"
                :aria-checked="currentTheme === key"
                class="flex w-full cursor-pointer items-center justify-between gap-2 rounded px-2.5 py-2 text-left text-sm transition-colors"
                :class="currentTheme === key ? 'text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
                @click="pickTheme(key)"
              >
                {{ label }}
                <Check v-if="currentTheme === key" class="h-3.5 w-3.5 shrink-0" />
              </button>
              <p
                v-for="label in upcomingThemes"
                :key="label"
                class="cursor-default rounded px-2.5 py-2 text-left text-sm text-steam-dim/40"
              >
                {{ label }}
              </p>
            </div>
          </div>

          <button
            type="button"
            class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-md text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
            :aria-label="renderedDark ? '切换浅色' : '切换深色'"
            :title="renderedDark ? '切换浅色' : '切换深色'"
            @click="setMode(renderedDark ? 'light' : 'dark')"
          >
            <Sun v-if="renderedDark" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
          </button>

          <button
            type="button"
            class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-md text-steam-dim transition-colors hover:bg-ink-raised hover:text-destructive"
            aria-label="退出登录"
            title="退出登录"
            @click="onLogout"
          >
            <LogOut class="h-4 w-4" />
          </button>

          <span class="ml-1 hidden font-mono text-[9px] tracking-[0.2em] text-steam-dim/50 lg:inline">v{{ APP_VERSION }}</span>
        </div>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="min-w-0 pb-24 md:pb-0">
      <RouterView />
    </main>

    <!-- 移动端底部 tab 栏（顶栏在移动端只留品牌与工具钮） -->
    <nav
      v-if="shouldShowNav"
      aria-label="移动端导航"
      class="fixed bottom-4 left-1/2 z-40 flex w-[min(calc(100vw-2rem),18rem)] -translate-x-1/2 items-center justify-between gap-0 rounded-2xl border border-ink-line/70 bg-ink-surface/90 px-1.5 py-1.5 shadow-lg backdrop-blur-md md:hidden"
    >
      <RouterLink
        v-for="item in nav"
        :key="item.name"
        :to="{ name: item.name }"
        :aria-current="isActive(item.name) ? 'page' : undefined"
        :aria-label="item.label"
        :class="cn(
          'flex min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-xl py-1 text-[10px] transition-colors',
          isActive(item.name) ? 'text-gold' : 'text-steam-dim hover:text-steam',
        )"
      >
        <component :is="item.icon" class="h-5 w-5" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>
