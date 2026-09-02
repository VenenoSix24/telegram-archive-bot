<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, watchEffect } from 'vue'
import { Check, ChevronDown, LayoutDashboard, Images, Menu, Moon, Paintbrush, Settings, LogOut, Sun, Tags } from 'lucide-vue-next'
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
import { isVault } from '@/lib/vocab'
import SidebarCatalog from '@/components/layout/SidebarCatalog.vue'

const route = useRoute()
const router = useRouter()

onMounted(applyTheme)

/* 换页滚动复位：标准后台的滚动容器是 main（RouterView 之外，跨路由存活），
   由这里复位；素材志滚文档，由 router.scrollBehavior 管。只在 path 变化时
   复位——素材页标签筛选只改 query，复位会把用户甩回顶部 */
const mainEl = ref<HTMLElement | null>(null)
watch(
  () => route.path,
  () => {
    if (isVault.value && mainEl.value) mainEl.value.scrollTop = 0
  },
)

/* 滚动条槽位只给文档滚动壳（素材志/登录）：标准后台整壳 h-screen 不滚文档，
   预留会留出右侧死条。登录页无 AppLayout 不带类，页面本身不出滚动条 */
watchEffect(() => {
  document.documentElement.classList.toggle('doc-scroll', !isVault.value)
})
onBeforeUnmount(() => document.documentElement.classList.remove('doc-scroll'))

const nav = [
  { name: 'dashboard', label: '概览', icon: LayoutDashboard },
  { name: 'messages', label: '素材', icon: Images },
  { name: 'tags', label: '标签', icon: Tags },
  { name: 'settings', label: '设置', icon: Settings },
]

const themeLabels: Record<ThemeKey, string> = {
  collection: '素材志',
  minimal: '标准后台',
}
/* 已定稿待实现的方向：菜单里以禁用项示知路线，不做假开关 */
const isActive = (name: string) => route.name === name
const currentTitle = computed(
  () => nav.find((item) => item.name === route.name)?.label ?? '素材库',
)
const shouldShowNav = computed(() => !!route.name)

/* ===== 标准后台：侧栏抽屉（移动端）/常驻（桌面）===== */
const sidebarOpen = ref(false)
function closeSidebar() {
  sidebarOpen.value = false
}

/* ===== 主题菜单（两种壳共用一套状态）===== */
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
</script>

<template>
  <!-- 悬浮面板壳：页面底色留缝，左/中/右都是圆角面板（小屏贴边不留缝） -->
  <div
    class="min-h-screen"
    :class="isVault ? 'flex h-screen gap-2.5 overflow-hidden bg-ink-raised p-2.5 max-lg:gap-0 max-lg:p-0' : ''"
  >
    <!-- ===== 标准后台：左栏（导航 + 筛选树 + 主题/账户）===== -->
    <aside
      v-if="isVault"
      class="z-50 flex w-64 shrink-0 flex-col rounded-2xl border border-ink-line bg-ink-surface/85 backdrop-blur-xl backdrop-saturate-150 transition-transform duration-200 max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:w-72 max-lg:rounded-none max-lg:border-0 max-lg:bg-ink-surface max-lg:shadow-2xl max-lg:-translate-x-full"
      :class="sidebarOpen && 'max-lg:translate-x-0'"
      aria-label="导航与筛选"
    >
      <div class="flex flex-none items-center gap-2.5 px-4 pb-3 pt-4">
        <span class="grid h-7 w-7 place-items-center rounded-lg bg-steam font-mono text-[12px] font-bold text-ink-bg">A</span>
        <span class="text-[14px] font-semibold tracking-wide text-steam">素材库</span>
        <span class="ml-auto font-mono text-[9px] tracking-[0.18em] text-steam-dim/50">VAULT</span>
      </div>

      <nav class="flex flex-none flex-col gap-0.5 border-b border-ink-line px-2 pb-2.5" aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.name"
          :to="{ name: item.name }"
          :aria-current="isActive(item.name) ? 'page' : undefined"
          class="flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[13.5px] transition-colors"
          :class="isActive(item.name) ? 'bg-gold/10 font-medium text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
          @click="closeSidebar"
        >
          <component :is="item.icon" class="h-4 w-4" />
          {{ item.label }}
        </RouterLink>
      </nav>

      <SidebarCatalog class="min-h-0 flex-1 overflow-y-auto [scrollbar-gutter:stable]" @navigate="closeSidebar" />

      <!-- 主题/账户控件：移动端移至顶栏右侧（max-lg 隐藏） -->
      <div class="relative flex-none border-t border-ink-line p-2.5 max-lg:hidden" data-theme-menu>
        <Transition name="v-pop">
          <div v-if="themeMenuOpen" role="menu" class="absolute bottom-full left-2.5 right-2.5 z-40 mb-1.5 rounded-lg border border-ink-line bg-ink-surface p-1 shadow-xl [--pop-origin:bottom_left]">
            <button
              v-for="(label, key) in themeLabels"
              :key="key"
              type="button"
              role="menuitemradio"
              :aria-checked="currentTheme === key"
              class="flex w-full cursor-pointer items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors"
              :class="currentTheme === key ? 'text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
              @click="pickTheme(key)"
            >
              {{ label }}
              <Check v-if="currentTheme === key" class="h-3.5 w-3.5 shrink-0" />
            </button>
          </div>
        </Transition>
        <div class="flex items-center gap-1">
          <button
            type="button"
            class="flex h-9 min-w-0 flex-1 cursor-pointer items-center gap-1.5 rounded-lg px-2 text-[12.5px] text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
            aria-haspopup="menu"
            :aria-expanded="themeMenuOpen"
            title="切换主题"
            @click="themeMenuOpen = !themeMenuOpen"
          >
            <Paintbrush class="h-4 w-4 shrink-0" />
            <span class="truncate">{{ themeLabels[currentTheme] }}</span>
            <ChevronDown class="h-3.5 w-3.5 shrink-0 transition-transform" :class="themeMenuOpen && 'rotate-180'" />
          </button>
          <button
            type="button"
            class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
            :aria-label="renderedDark ? '切换浅色' : '切换深色'"
            :title="renderedDark ? '切换浅色' : '切换深色'"
            @click="setMode(renderedDark ? 'light' : 'dark')"
          >
            <Sun v-if="renderedDark" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-steam-dim transition-colors hover:bg-ink-raised hover:text-destructive"
            aria-label="退出登录"
            title="退出登录"
            @click="onLogout"
          >
            <LogOut class="h-4 w-4" />
          </button>
        </div>
        <p class="px-1 pb-0.5 pt-1 font-mono text-[9px] tracking-[0.16em] text-steam-dim/50">v{{ APP_VERSION }}</p>
      </div>
    </aside>

    <!-- 移动端侧栏遮罩 -->
    <Transition name="v-dialog">
      <div
        v-if="isVault && sidebarOpen"
        class="fixed inset-0 z-40 bg-ink-bg/50 backdrop-blur-[2px] lg:hidden"
        aria-hidden="true"
        @click="closeSidebar"
      />
    </Transition>

    <div
      class="flex min-w-0 flex-1 flex-col"
      :class="isVault ? 'min-h-0 overflow-hidden rounded-2xl border border-ink-line bg-ink-bg max-lg:rounded-none max-lg:border-0' : 'min-h-screen'"
    >
      <!-- 标准后台：移动端顶条（右侧承载主题/明暗/退出，替代侧栏底部）。
           backdrop-blur 会创建层叠上下文，必须自带 z 并压过素材页吸顶工具条（z-20），
           否则主题下拉会被工具条盖住 -->
      <div
        v-if="isVault"
        class="relative z-30 flex h-12 flex-none items-center gap-1 border-b border-ink-line bg-ink-surface/80 px-2 backdrop-blur-xl backdrop-saturate-150 lg:hidden"
      >
        <button
          type="button"
          class="flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
          aria-label="打开导航"
          @click="sidebarOpen = true"
        >
          <Menu class="h-5 w-5" />
        </button>
        <!-- 标题随路由渐变（out-in 位移为零，两 span 不并存） -->
        <Transition name="v-dialog" mode="out-in">
          <span :key="route.path" class="text-[14px] font-semibold text-steam">{{ currentTitle }}</span>
        </Transition>

        <div class="ml-auto flex items-center gap-0.5" data-theme-menu>
          <div class="relative">
            <button
              type="button"
              class="flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
              aria-haspopup="menu"
              :aria-expanded="themeMenuOpen"
              aria-label="切换主题"
              @click="themeMenuOpen = !themeMenuOpen"
            >
              <Paintbrush class="h-4 w-4" />
            </button>
            <Transition name="v-pop">
              <div
                v-if="themeMenuOpen"
                role="menu"
                class="absolute right-0 top-full z-50 mt-1 w-44 rounded-xl border border-ink-line bg-ink-surface/95 p-1 shadow-xl backdrop-blur-xl [--pop-origin:top_right]"
              >
                <button
                  v-for="(label, key) in themeLabels"
                  :key="key"
                  type="button"
                  role="menuitemradio"
                  :aria-checked="currentTheme === key"
                  class="flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors"
                  :class="currentTheme === key ? 'text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
                  @click="pickTheme(key)"
                >
                  {{ label }}
                  <Check v-if="currentTheme === key" class="h-3.5 w-3.5 shrink-0" />
                </button>
              </div>
            </Transition>
          </div>
          <button
            type="button"
            class="flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
            :aria-label="renderedDark ? '切换浅色' : '切换深色'"
            :title="renderedDark ? '切换浅色' : '切换深色'"
            @click="setMode(renderedDark ? 'light' : 'dark')"
          >
            <Sun v-if="renderedDark" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg text-steam-dim transition-colors hover:bg-ink-raised hover:text-destructive"
            aria-label="退出登录"
            title="退出登录"
            @click="onLogout"
          >
            <LogOut class="h-4 w-4" />
          </button>
        </div>
      </div>

      <!-- ===== 素材志：顶部导航条（原样保留） ===== -->
      <header
        v-if="!isVault"
        class="top-rules sticky top-0 z-30 border-b border-ink-line bg-ink-bg/95 backdrop-blur"
      >
        <div class="relative mx-auto flex h-14 max-w-[1440px] items-center gap-2 px-4 min-[820px]:px-8">
          <RouterLink :to="{ name: 'dashboard' }" class="mr-2 flex shrink-0 items-center gap-2.5">
            <svg class="mast-seal hidden h-8 w-8 text-gold min-[400px]:block" viewBox="0 0 52 52" aria-hidden="true">
              <rect x="2" y="2" width="48" height="48" rx="5" fill="none" stroke="currentColor" stroke-width="3.5" />
              <text x="26" y="37" text-anchor="middle" font-size="27" font-weight="700" fill="currentColor">档</text>
            </svg>
            <span class="font-display text-lg font-bold tracking-[0.2em] text-steam">素材志</span>
          </RouterLink>

          <!-- 桌面导航绝对居中：品牌与工具钮分列两侧，视觉重心平衡 -->
          <nav
            class="absolute left-1/2 top-0 hidden h-full -translate-x-1/2 items-stretch gap-1 md:flex"
            aria-label="主导航"
          >
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
              <Transition name="v-dialog">
                <span v-if="isActive(item.name)" class="absolute inset-x-3 bottom-0 h-[2px] bg-gold" aria-hidden="true"></span>
              </Transition>
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
                <Paintbrush class="h-4 w-4" />
                <span class="hidden min-[480px]:inline">{{ themeLabels[currentTheme] }}</span>
                <ChevronDown class="h-3.5 w-3.5 transition-transform" :class="themeMenuOpen && 'rotate-180'" />
              </button>
              <Transition name="v-pop">
                <div
                  v-if="themeMenuOpen"
                  role="menu"
                  class="absolute right-0 top-full z-40 mt-1.5 w-44 rounded-md border border-ink-line bg-ink-surface p-1 shadow-lg [--pop-origin:top_right]"
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
                </div>
              </Transition>
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

      <!-- 主内容：标准后台由页面自管滚动；素材志沿用文档滚动。
           路由换页 out-in：key 用 path（query 变化不重放过渡）。
           scrollbar-gutter 常驻槽位：中栏滚动条出没不再挤宽内容列 -->
      <main
        ref="mainEl"
        class="min-w-0"
        :class="isVault ? 'min-h-0 flex-1 overflow-y-auto [scrollbar-gutter:stable]' : 'flex-1 pb-24 md:pb-0'"
      >
        <RouterView v-slot="{ Component }">
          <Transition name="v-page" mode="out-in">
            <component :is="Component" :key="route.path" />
          </Transition>
        </RouterView>
      </main>

      <!-- 标准后台：移动端悬浮 Dock —— iOS 26 胶囊：容器圆角全弧、宽度随条目自适应，
           激活项为实心胶囊（参考素材志 dock 的紧凑节奏，间隙不留大空白） -->
      <nav
        v-if="isVault"
        class="fixed bottom-[calc(env(safe-area-inset-bottom)+0.75rem)] left-1/2 z-40 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-0.5 rounded-full border border-ink-line/70 bg-ink-surface/80 p-1 shadow-lg shadow-black/10 backdrop-blur-2xl backdrop-saturate-150 lg:hidden"
        aria-label="移动端导航"
      >
        <RouterLink
          v-for="item in nav"
          :key="item.name"
          :to="{ name: item.name }"
          :aria-current="isActive(item.name) ? 'page' : undefined"
          :aria-label="item.label"
          class="flex h-11 w-14 cursor-pointer flex-col items-center justify-center gap-0.5 rounded-full text-[10px] transition-colors"
          :class="isActive(item.name) ? 'bg-gold text-white shadow-sm' : 'text-steam-dim hover:text-steam'"
        >
          <component :is="item.icon" class="h-5 w-5" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </div>

    <!-- 素材志：移动端底部 dock（胶囊玻璃，宽度随条目数自适应；标准后台用实底标签栏） -->
    <nav
      v-if="!isVault && shouldShowNav"
      aria-label="移动端导航"
      class="fixed bottom-4 left-1/2 z-40 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center justify-center gap-1 rounded-full border border-ink-line/70 bg-ink-surface/75 px-2 py-1.5 shadow-lg backdrop-blur-xl md:hidden"
    >
      <RouterLink
        v-for="item in nav"
        :key="item.name"
        :to="{ name: item.name }"
        :aria-current="isActive(item.name) ? 'page' : undefined"
        :aria-label="item.label"
        :class="cn(
          'flex w-14 shrink-0 flex-col items-center justify-center gap-0.5 rounded-full py-1 text-[10px] transition-colors',
          isActive(item.name) ? 'text-gold' : 'text-steam-dim hover:text-steam',
        )"
      >
        <component :is="item.icon" class="h-5 w-5" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>
