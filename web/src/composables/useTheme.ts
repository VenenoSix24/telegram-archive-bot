import { computed, ref } from 'vue'

export type ThemeKey = 'collection' | 'projector' | 'midnight' | 'moss'
/** mode：dark/light 为显式，system 跟随系统 prefers-color-scheme */
export type Mode = 'dark' | 'light' | 'system'

/* v2：默认主题换为素材志。换存储 key 让旧默认值（projector）一次性失效，
   否则老用户 localStorage 里的旧默认会一直压住新默认。 */
const THEME_KEY = 'archive:theme:v2'
const MODE_KEY = 'archive:mode'

/** 主题名 → 模块路径；动态 import 让 Vite 按主题 code-split，切到才加载对应 CSS。 */
const THEME_LOADERS: Record<ThemeKey, () => Promise<unknown>> = {
  collection: () => import('@/themes/collection.css'),
  projector: () => import('@/themes/projector.css'),
  midnight: () => import('@/themes/midnight.css'),
  moss: () => import('@/themes/moss.css'),
}

function initialTheme(): ThemeKey {
  const stored = localStorage.getItem(THEME_KEY)
  return stored === 'collection' || stored === 'projector' || stored === 'midnight' || stored === 'moss'
    ? stored
    : 'collection'
}

function initialMode(): Mode {
  const stored = localStorage.getItem(MODE_KEY)
  return stored === 'light' || stored === 'dark' ? stored : 'system'
}

const theme = ref<ThemeKey>(initialTheme())
const mode = ref<Mode>(initialMode())

/** 取实际生效的明暗：system 时读系统偏好 */
function effectiveMode(): 'dark' | 'light' {
  if (mode.value !== 'system') return mode.value
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function applyTheme() {
  const el = document.documentElement
  el.dataset.theme = theme.value
  el.dataset.mode = effectiveMode()
  el.style.colorScheme = effectiveMode()
  localStorage.setItem(THEME_KEY, theme.value)
  localStorage.setItem(MODE_KEY, mode.value)
  void THEME_LOADERS[theme.value]()
}

export function setTheme(t: ThemeKey) {
  if (t === theme.value) return
  theme.value = t
  applyTheme()
}

export function setMode(m: Mode) {
  if (m === mode.value) return
  mode.value = m
  applyTheme()
}

export function cycleTheme() {
  const order: ThemeKey[] = ['collection', 'projector', 'midnight', 'moss']
  setTheme(order[(order.indexOf(theme.value) + 1) % order.length])
}

/** 跟随系统时监听系统偏好变化，无需刷新即换肤 */
if (window.matchMedia) {
  const mq = window.matchMedia('(prefers-color-scheme: light)')
  mq.addEventListener('change', () => {
    if (mode.value === 'system') applyTheme()
  })
}

export const currentTheme = computed(() => theme.value)
export const currentMode = computed(() => mode.value)
/** 实际渲染明暗（system 已解析） */
export const renderedDark = computed(() => effectiveMode() === 'dark')

// 模块加载即应用（含 build 后首屏）；App 挂载后再 apply 一次以同步 local 变化
applyTheme()