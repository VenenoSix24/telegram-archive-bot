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

/* 主题改为可发现的选择：循环按钮在多主题下要盲猜下一个，改为菜单全列出 */
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
    <!-- 桌面端书脊：品牌 / 导航 / 外观与会话 分区，hairline 分隔 -->
    <aside
      class="fixed inset-y-0 left-0 z-30 hidden w-48 shrink-0 flex-col border-r border-ink-line bg-ink-bg px-4 py-6 md:flex"
    >
      <div class="px-2 pb-7">
        <p class="font-display text-lg font-bold tracking-[0.2em] text-steam">素材志</p>
        <p class="mt-1.5 font-mono text-[9px] tracking-[0.28em] text-steam-dim">TG ARCHIVE CATALOGUE</p>
      </div>

      <nav class="flex flex-col" aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.name"
          :to="{ name: item.name }"
          :aria-current="isActive(item.name) ? 'page' : undefined"
          :class="cn(
            'flex items-center gap-2.5 border-l-2 py-2 pl-3 pr-2 text-sm transition-colors',
            isActive(item.name)
              ? 'border-gold text-gold'
              : 'border-transparent text-steam-dim hover:text-steam',
          )"
        >
          <component :is="item.icon" class="h-4 w-4" />
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="mt-auto" data-theme-menu>
        <div class="relative border-t border-ink-line pt-2">
          <button
            type="button"
            class="flex w-full cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
            aria-haspopup="menu"
            :aria-expanded="themeMenuOpen"
            title="切换主题"
            @click="themeMenuOpen = !themeMenuOpen"
          >
            <Palette class="h-4 w-4" />
            <span class="min-w-0 flex-1 truncate text-left">{{ themeLabels[currentTheme] }}</span>
            <ChevronDown class="h-3.5 w-3.5 shrink-0 transition-transform" :class="themeMenuOpen && 'rotate-180'" />
          </button>
          <div
            v-if="themeMenuOpen"
            role="menu"
            class="absolute bottom-14 left-3 right-3 z-40 rounded-md border border-ink-line bg-ink-surface p-1 shadow-lg"
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
          class="flex w-full cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
          :aria-label="renderedDark ? '切换浅色' : '切换深色'"
          @click="setMode(renderedDark ? 'light' : 'dark')"
        >
          <Sun v-if="renderedDark" class="h-4 w-4" />
          <Moon v-else class="h-4 w-4" />
          {{ renderedDark ? '浅色' : '深色' }}
        </button>

        <button
          type="button"
          class="mt-2 flex w-full cursor-pointer items-center gap-2 border-t border-ink-line px-3 pb-1 pt-3 text-sm text-steam-dim transition-colors hover:text-destructive"
          @click="onLogout"
        >
          <LogOut class="h-4 w-4" />
          退出
        </button>

        <p class="px-3 pb-1 pt-2 font-mono text-[9px] tracking-[0.2em] text-steam-dim/60">v{{ APP_VERSION }}</p>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="min-w-0 pb-24 md:pl-48 md:pb-0">
      <RouterView />
    </main>

    <!-- 移动端底部 tab 栏：激活项朱砂字，无色块 -->
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
