import { computed, ref } from 'vue'
import { getStats, getTags } from '@/lib/api'
import type { Stats, TagCount, Target } from '@/lib/types'

/*
 * 目录筛选的单一状态源。
 * 素材页（两种变体）与标准后台的侧栏筛选树共用同一批 ref：
 * 侧栏改筛选 → 素材页的 debounce watch 自动重查；跨页点标签 → 先改状态再跳路由。
 */

const q = ref('')
const mediaType = ref('')
const rating = ref<number | ''>('')
/** 标签筛选：多选交集（后端 ?tag=A&tag=B 同时命中才返回） */
const tagFilter = ref<string[]>([])
const targetFilter = ref<number | ''>('')
const statusFilter = ref<'active' | 'deleted' | 'all'>('active')
const stats = ref<Stats | null>(null)
const tagIndex = ref<TagCount[]>([])
const targets = ref<Target[]>([])

let statsLoaded = false

export function useCatalogFilters() {
  /** 统计与索引；失败允许下次进页面重试 */
  async function loadStats() {
    if (statsLoaded) return
    statsLoaded = true
    try {
      const [s, t] = await Promise.all([getStats(), getTags()])
      stats.value = s
      targets.value = s.targets
      tagIndex.value = [...t.items].sort((a, b) => b.count - a.count).slice(0, 14)
    } catch {
      statsLoaded = false
      stats.value = null
      targets.value = []
      tagIndex.value = []
    }
  }

  const isFilterActive = computed(
    () =>
      !!(
        q.value ||
        mediaType.value ||
        rating.value !== '' ||
        tagFilter.value.length ||
        targetFilter.value !== '' ||
        statusFilter.value !== 'active'
      ),
  )

  function resetFilters() {
    q.value = ''
    mediaType.value = ''
    rating.value = ''
    targetFilter.value = ''
    statusFilter.value = 'active'
    tagFilter.value = [] // 触发 URL 同步与重查
  }

  /* 各筛选单选可反选（与重构前行为一致） */
  function toggleMedia(value: string) {
    mediaType.value = mediaType.value === value && value !== '' ? '' : value
  }
  function toggleRating(value: number) {
    rating.value = rating.value === value ? '' : value
  }
  function toggleTarget(value: number) {
    targetFilter.value = targetFilter.value === value ? '' : value
  }
  function toggleStatus(value: 'active' | 'deleted' | 'all') {
    statusFilter.value = statusFilter.value === value ? 'active' : value
  }
  /** 标签多选：点已选的移除，未选的加入（交集语义） */
  function toggleTag(name: string) {
    tagFilter.value = tagFilter.value.includes(name)
      ? tagFilter.value.filter((t) => t !== name)
      : [...tagFilter.value, name]
  }
  /** 从当前标签选中态里移除单个（chips 的 × 用） */
  function removeTag(name: string) {
    if (tagFilter.value.includes(name)) toggleTag(name)
  }

  return {
    q,
    mediaType,
    rating,
    tagFilter,
    targetFilter,
    statusFilter,
    stats,
    tagIndex,
    targets,
    isFilterActive,
    loadStats,
    resetFilters,
    toggleMedia,
    toggleRating,
    toggleTarget,
    toggleStatus,
    toggleTag,
    removeTag,
  }
}
