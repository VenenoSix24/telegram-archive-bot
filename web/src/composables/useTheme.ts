import { computed, ref } from 'vue'

/*
 * 主题 = 双主题定稿：简档（minimal，默认）/ 素材志（collection，拓展印风）；
 * 暗房印样已取消不上线（2026-09-02）。「标准后台」更名「简档」用户定稿（2026-09-02）。
 * 旧版三主题（放映室/深海/苔原）随重构移除，不迁移。
 * 每个主题 = 一份 token 文件 + [data-theme] 作用域母题层；结构层共享。
 * mode：dark/light 为显式，system 跟随系统 prefers-color-scheme
 * accent：主题内配色方案（data-accent），token 文件里按主题给可选清单
 */
export type ThemeKey = 'collection' | 'minimal'
/** mode：dark/light 为显式，system 跟随系统 prefers-color-scheme */
export type Mode = 'dark' | 'light' | 'system'

const THEME_KEY = 'archive:theme:v2'
const MODE_KEY = 'archive:mode'
const ACCENT_KEY = 'archive:accent'

/** 主题名 → 模块路径；动态 import 让 Vite 按主题 code-split，切到才加载对应 CSS。 */
const THEME_LOADERS: Record<ThemeKey, () => Promise<unknown>> = {
  collection: () => import('@/themes/collection.css'),
  minimal: () => import('@/themes/minimal.css'),
}

/** 上线中的主题才可被选中；旧主题存值一律回落默认 */
const AVAILABLE: ThemeKey[] = ['collection', 'minimal']

/** 每个主题的配色方案清单（色值本体在各 token 文件里，这里只管 key/文案） */
export const THEME_ACCENTS: Record<ThemeKey, { key: string; label: string }[]> = {
  minimal: [
    { key: 'default', label: '蓝' },
    { key: 'teal', label: '青碧' },
    { key: 'violet', label: '紫罗兰' },
    { key: 'rose', label: '玫红' },
    { key: 'amber', label: '琥珀' },
  ],
  collection: [
    { key: 'default', label: '朱砂' },
    { key: 'indigo', label: '黛蓝' },
    { key: 'pine', label: '松绿' },
    { key: 'wisteria', label: '紫棠' },
  ],
}

function initialTheme(): ThemeKey {
  const stored = localStorage.getItem(THEME_KEY)
  return AVAILABLE.includes(stored as ThemeKey) ? (stored as ThemeKey) : 'minimal'
}

function initialAccent(): string {
  const stored = localStorage.getItem(ACCENT_KEY) ?? 'default'
  return THEME_ACCENTS[initialTheme()].some((a) => a.key === stored) ? stored : 'default'
}

function initialMode(): Mode {
  const stored = localStorage.getItem(MODE_KEY)
  return stored === 'light' || stored === 'dark' ? stored : 'system'
}

const theme = ref<ThemeKey>(initialTheme())
const accent = ref<string>(initialAccent())
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
  el.dataset.accent = accent.value
  el.style.colorScheme = effectiveMode()
  localStorage.setItem(THEME_KEY, theme.value)
  localStorage.setItem(MODE_KEY, mode.value)
  localStorage.setItem(ACCENT_KEY, accent.value)
  void THEME_LOADERS[theme.value]()
}

let themeFadeTimer: ReturnType<typeof setTimeout> | undefined

/** B8：切换瞬间给根节点挂 .theme-fading，颜色柔和过渡 300ms 后摘除（避免常驻全局 transition） */
function applyThemeWithFade() {
  const el = document.documentElement
  el.classList.add('theme-fading')
  applyTheme()
  clearTimeout(themeFadeTimer)
  themeFadeTimer = setTimeout(() => el.classList.remove('theme-fading'), 350)
}

export function setTheme(t: ThemeKey) {
  if (t === theme.value) return
  theme.value = t
  // 配色清单按主题各自定义：换主题后原配色不存在则回落默认
  if (!THEME_ACCENTS[t].some((a) => a.key === accent.value)) accent.value = 'default'
  applyThemeWithFade()
}

export function setAccent(a: string) {
  if (a === accent.value) return
  if (!THEME_ACCENTS[theme.value].some((item) => item.key === a)) return
  accent.value = a
  applyThemeWithFade()
}

export function setMode(m: Mode) {
  if (m === mode.value) return
  mode.value = m
  applyThemeWithFade()
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
export const currentAccent = computed(() => accent.value)
/** 实际渲染明暗（system 已解析） */
export const renderedDark = computed(() => effectiveMode() === 'dark')

// 模块加载即应用（含 build 后首屏）；App 挂载后再 apply 一次以同步 local 变化
applyTheme()
