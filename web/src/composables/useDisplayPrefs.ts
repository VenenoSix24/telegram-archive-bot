import { computed, ref } from 'vue'
import { currentTheme, type ThemeKey } from '@/composables/useTheme'

/**
 * 显示偏好（纯前端、localStorage，与主题同级，不进后端配置）。
 * 缩略图展示三模式，两套主题通用：
 * - fit     完整展示（16:9 画布 + 深色托底，竖图完整不裁）
 * - crop    裁剪填充（16:9 画布裁满，所有卡片完全统一）
 * - masonry 瀑布流（缩略图多大画布就多大）
 * 每套主题独立记忆（用户定稿）：切主题即切到该主题上次的选择；
 * 该主题没选过时按主题默认：素材志 = 瀑布流，标准后台 = 完整展示。
 */
export type ThumbMode = 'fit' | 'crop' | 'masonry'

const KEY_PREFIX = 'archive:thumb:mode:'
const THEMES: ThemeKey[] = ['collection', 'minimal']

function readStored(theme: ThemeKey): ThumbMode | null {
  if (typeof localStorage === 'undefined') return null
  const saved = localStorage.getItem(KEY_PREFIX + theme)
  return saved === 'fit' || saved === 'crop' || saved === 'masonry' ? saved : null
}

function readAll(): Partial<Record<ThemeKey, ThumbMode>> {
  const out: Partial<Record<ThemeKey, ThumbMode>> = {}
  for (const theme of THEMES) {
    const saved = readStored(theme)
    if (saved) out[theme] = saved
  }
  return out
}

/* 每主题一份覆盖值；模块级单例，设置页改一处全站即时响应 */
const overrides = ref<Partial<Record<ThemeKey, ThumbMode>>>(readAll())

const thumbMode = computed<ThumbMode>(() => {
  const theme = currentTheme.value
  return overrides.value[theme] ?? (theme === 'minimal' ? 'fit' : 'masonry')
})

export function useThumbMode() {
  function setThumbMode(next: ThumbMode) {
    const theme = currentTheme.value
    overrides.value = { ...overrides.value, [theme]: next }
    localStorage.setItem(KEY_PREFIX + theme, next)
  }
  return { thumbMode, setThumbMode }
}

/* v2.1 早期是全局单键，与「每主题独立记忆」语义冲突：一次性清掉，选择回到主题默认 */
if (typeof localStorage !== 'undefined') {
  localStorage.removeItem('archive:thumb:mode')
}
