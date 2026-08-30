import { computed, ref } from 'vue'

export type ThemeKey = 'projector' | 'midnight' | 'moss'
export type Mode = 'dark' | 'light'

const THEME_KEY = 'archive:theme'
const MODE_KEY = 'archive:mode'

/** 主题名 → 模块路径；动态 import 让 Vite 按主题 code-split，切到才加载对应 CSS。 */
const THEME_LOADERS: Record<ThemeKey, () => Promise<unknown>> = {
  projector: () => import('@/themes/projector.css'),
  midnight: () => import('@/themes/midnight.css'),
  moss: () => import('@/themes/moss.css'),
}

function initialTheme(): ThemeKey {
  const stored = localStorage.getItem(THEME_KEY)
  return stored === 'midnight' || stored === 'moss' ? stored : 'projector'
}

function initialMode(): Mode {
  return localStorage.getItem(MODE_KEY) === 'light' ? 'light' : 'dark'
}

const theme = ref<ThemeKey>(initialTheme())
const mode = ref<Mode>(initialMode())

export function isDark() {
  return mode.value === 'dark'
}

export function applyTheme() {
  const el = document.documentElement
  el.dataset.theme = theme.value
  el.dataset.mode = mode.value
  localStorage.setItem(THEME_KEY, theme.value)
  localStorage.setItem(MODE_KEY, mode.value)
  // 让浏览器弹窗/下拉等原生控件跟随配色
  el.style.colorScheme = mode.value
  void THEME_LOADERS[theme.value]()
}

export function setTheme(t: ThemeKey) {
  if (t === theme.value) return
  theme.value = t
  applyTheme()
}

export function toggleMode() {
  mode.value = mode.value === 'dark' ? 'light' : 'dark'
  applyTheme()
}

export function cycleTheme() {
  const order: ThemeKey[] = ['projector', 'midnight', 'moss']
  setTheme(order[(order.indexOf(theme.value) + 1) % order.length])
}

export const currentTheme = computed(() => theme.value)
export const currentMode = computed(() => mode.value)

// 模块加载即应用（含 build 后首屏）；App 挂载后再 apply 一次以同步 local 变化
applyTheme()