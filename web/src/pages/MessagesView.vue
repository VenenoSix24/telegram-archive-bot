<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertTriangle,
  LayoutGrid,
  Loader2,
  RotateCcw,
  Rows3,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-vue-next'
import { listMessages, patchMessage } from '@/lib/api'
import type { Message, MessagesResponse, TagCount } from '@/lib/types'
import MessageCard from '@/components/MessageCard.vue'
import MessageCardVault from '@/components/MessageCardVault.vue'
import MessageRow from '@/components/MessageRow.vue'
import MessageDrawer from '@/components/MessageDrawer.vue'
import Button from '@/components/ui/Button.vue'
import { toastError, toastSuccess } from '@/composables/useToast'
import { useCatalogFilters } from '@/composables/useCatalogFilters'
import { useThumbMode } from '@/composables/useDisplayPrefs'
import { displayChatId } from '@/lib/format'
import { STAGGER_CAP, STAGGER_STEP, staggerDelay } from '@/lib/motion'
import { isVault, useVocab } from '@/lib/vocab'

const route = useRoute()
const router = useRouter()
const L = useVocab()
const { thumbMode } = useThumbMode()

/* 筛选状态与索引：与标准后台侧栏树共用（useCatalogFilters） */
const {
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
} = useCatalogFilters()

const data = ref<MessagesResponse | null>(null)
const loading = ref(true)
const error = ref('')
const selected = ref<Message | null>(null)
const tocOpen = ref(false)
const searchInput = ref<HTMLInputElement | null>(null)

/* B2 首屏 stagger：仅页面首次载入的进场逐项延迟（筛选变更不 stagger） */
const revealStagger = ref(false)
let firstLoad = true
function itemStyle(index: number) {
  // 瀑布流是 CSS columns：按列填充，索引序 = 纵列序，逐项 stagger 会呈现
  // 「从左往右」的扫掠（用户实测困惑）——瀑布流降级为整波 fade-up，不逐项延迟
  if (thumbMode.value === 'masonry') return undefined
  return revealStagger.value ? { transitionDelay: staggerDelay(index) } : undefined
}

/* 骨架延迟显示：本地接口很快，骨架（假卡片块）挂载一帧就被替换，
   看起来像「卡片闪一下」（用户实测反馈）；慢网 200ms 后才兜底出现 */
const skeletonReady = ref(false)
let skeletonTimer: ReturnType<typeof setTimeout> | undefined
watch(
  loading,
  (busy) => {
    clearTimeout(skeletonTimer)
    if (busy) skeletonTimer = setTimeout(() => (skeletonReady.value = true), 200)
    else skeletonReady.value = false
  },
  { immediate: true },
)

/* 标准后台：视图切换与常驻详情栏 */
const viewMode = ref<'grid' | 'list'>(
  localStorage.getItem('archive:view:v1') === 'list' ? 'list' : 'grid',
)
watch(viewMode, (v) => localStorage.setItem('archive:view:v1', v))
/* 网格容器：统一画布走均匀网格；瀑布流走 columns 瀑布流（两态都随显示偏好切换） */
const gridClass = computed(() =>
  thumbMode.value === 'masonry'
    ? 'columns-1 gap-3.5 min-[480px]:columns-2 xl:columns-3 min-[1600px]:columns-4'
    : 'feed-grid',
)
const paneOpen = ref(false)
const isNarrow = ref(
  typeof window !== 'undefined' ? window.matchMedia('(max-width: 1279px)').matches : false,
)

const PAGE = 30
const mediaOptions = computed(() => [
  { value: '', label: L.value.all },
  { value: 'photo', label: L.value.photo },
  { value: 'video', label: L.value.video },
  { value: 'document', label: L.value.document },
  { value: 'text', label: L.value.text },
  { value: 'audio', label: L.value.audio },
  { value: 'voice', label: L.value.voice },
  { value: 'sticker', label: L.value.sticker },
  { value: 'other', label: L.value.other },
])
const ratingOptions = computed(() => [
  { value: 5, label: isVault.value ? L.value.ratingHint[4] : `五星 · ${L.value.ratingHint[4]}` },
  { value: 4, label: isVault.value ? L.value.ratingHint[3] : `四星 · ${L.value.ratingHint[3]}` },
  { value: 3, label: isVault.value ? L.value.ratingHint[2] : `三星 · ${L.value.ratingHint[2]}` },
  { value: 2, label: isVault.value ? L.value.ratingHint[1] : `二星 · ${L.value.ratingHint[1]}` },
  { value: 1, label: isVault.value ? L.value.ratingHint[0] : `一星 · ${L.value.ratingHint[0]}` },
  { value: 0, label: L.value.unrated },
])
const statusOptions = computed(() => [
  { value: 'active' as const, label: L.value.statusActive },
  { value: 'deleted' as const, label: '已删除' },
  { value: 'all' as const, label: '全部' },
])

const shown = computed(() => data.value?.items.length ?? 0)
const hasMore = computed(() => (data.value ? shown.value < data.value.total : false))

/** 刊头卷号：ISO 周数当卷号，配「不定期刊」的自嘲（素材志报眉用） */
const issue = computed(() => {
  const now = new Date()
  const d = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()))
  const dayNum = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - dayNum)
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
  return `第 ${week} 卷 · ${now.getFullYear()} 年 ${now.getMonth() + 1} 月`
})

/** 体例计数：全部 = 总数，其余取 stats.by_type；统计未载返回 null 不展示 */
function typeCount(value: string): number | null {
  if (!stats.value) return null
  if (value === '') return stats.value.messages.total
  return stats.value.messages.by_type[value] ?? 0
}

/** 类目快捷切换条：热度前 12 + 当前所选类目（不在前 12 则补进来） */
const stripTags = computed<TagCount[]>(() => {
  const top = tagIndex.value.slice(0, 12)
  for (const current of tagFilter.value) {
    if (!top.some((t) => t.name === current)) {
      const found = tagIndex.value.find((t) => t.name === current)
      top.unshift(found ?? { name: current, count: 0 })
    }
  }
  return top
})

// URL ?tag=（从标签页点来，可多值）作为标签筛选的初始值
function tagsFromQuery(value: unknown): string[] {
  if (typeof value === 'string') return value ? [value] : []
  if (Array.isArray(value)) return value.filter((v): v is string => typeof v === 'string' && !!v)
  return []
}

function syncFromQuery() {
  const next = tagsFromQuery(route.query.tag)
  const cur = tagFilter.value
  if (next.length !== cur.length || next.some((t, i) => t !== cur[i])) tagFilter.value = next
}

// 标签筛选变更时同步回 URL，可分享/前进后退（多值 ?tag=A&tag=B）
function syncToQuery() {
  router.replace({
    query: tagFilter.value.length ? { tag: tagFilter.value } : {},
  })
}

// 详情面板点标签等场景在同一页改 query：路由变化要反映到筛选。
// 仅在与当前值不同才回写，避免和 syncToQuery 打环。
watch(
  () => route.query.tag,
  (t) => {
    const next = tagsFromQuery(t)
    const cur = tagFilter.value
    if (next.length !== cur.length || next.some((name, i) => name !== cur[i])) tagFilter.value = next
  },
)

// 窄屏判定：详情栏在 <1280 转覆盖层，需要给遮罩做条件渲染
function onNarrowChange(e: MediaQueryListEvent) {
  isNarrow.value = e.matches
}
onMounted(() => {
  window.matchMedia('(max-width: 1279px)').addEventListener('change', onNarrowChange)
})
onBeforeUnmount(() => {
  window.matchMedia('(max-width: 1279px)').removeEventListener('change', onNarrowChange)
})

let timer: ReturnType<typeof setTimeout> | undefined
let requestGeneration = 0
// 筛选变更不清空旧数据：旧列表原地保留到新数据到达，由 TransitionGroup
// 做离场/进场/FLIP 衔接（清空会强制路过骨架，快加载下像卡片闪现）
watch([q, mediaType, rating, targetFilter, statusFilter], () => {
  clearTimeout(timer)
  timer = setTimeout(load, 300)
})
watch(tagFilter, () => {
  syncToQuery()
  clearTimeout(timer)
  timer = setTimeout(load, 300)
})

async function load() {
  const generation = ++requestGeneration
  loading.value = true
  error.value = ''
  try {
    const result = await listMessages({
      q: q.value || undefined,
      media_type: mediaType.value || undefined,
      rating: rating.value === '' ? undefined : Number(rating.value),
      tag: tagFilter.value.length ? tagFilter.value : undefined,
      target_chat_id: targetFilter.value === '' ? undefined : Number(targetFilter.value),
      status: statusFilter.value,
      limit: PAGE,
    })
    if (generation === requestGeneration) {
      data.value = result
      if (firstLoad && result.items.length) {
        firstLoad = false
        revealStagger.value = true
        // 收尾波次入场完毕（cap*step 延迟 + 一段动画时长）后再摘除内联延迟
        setTimeout(() => (revealStagger.value = false), STAGGER_CAP * STAGGER_STEP + 400)
      }
    }
  } catch (e) {
    if (generation === requestGeneration) error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    if (generation === requestGeneration) loading.value = false
  }
}

async function loadMore() {
  if (!data.value || loading.value) return
  loading.value = true
  try {
    const next = await listMessages({
      q: q.value || undefined,
      media_type: mediaType.value || undefined,
      rating: rating.value === '' ? undefined : Number(rating.value),
      tag: tagFilter.value.length ? tagFilter.value : undefined,
      target_chat_id: targetFilter.value === '' ? undefined : Number(targetFilter.value),
      status: statusFilter.value,
      limit: PAGE,
      offset: shown.value,
    })
    data.value = { ...next, items: [...data.value.items, ...next.items] }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function rate(msg: Message, value: number) {
  try {
    const updated = await patchMessage(msg.id, { target_id: msg.target_id ?? undefined, rating: value })
    const item = data.value?.items.find((m) => m.material_id === msg.material_id)
    if (item) Object.assign(item, {
      ...updated,
      id: item.id,
      material_id: item.material_id,
      target_id: item.target_id,
      target_chat_id: item.target_chat_id,
      target_message_id: item.target_message_id,
      target_url: item.target_url,
      original_text: item.target_id == null ? updated.original_text : updated.targets.find((target) => target.id === item.target_id)?.original_text ?? item.original_text,
      original_html: item.target_id == null ? updated.original_html : updated.targets.find((target) => target.id === item.target_id)?.original_html ?? item.original_html,
      rendered_text: item.target_id == null ? updated.rendered_text : updated.targets.find((target) => target.id === item.target_id)?.rendered_text ?? item.rendered_text,
      rating: item.target_id == null ? updated.rating : updated.targets.find((target) => target.id === item.target_id)?.rating ?? value,
      tags: item.target_id == null ? updated.tags : updated.targets.find((target) => target.id === item.target_id)?.tags ?? item.tags,
      targets: item.targets,
    })
    toastSuccess(value === 0 ? '已清除评级' : `评级设为 ${value} 星`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
    toastError(e instanceof Error ? e.message : '保存失败')
  }
}

function onDrawerUpdate(updated: Message) {
  const idx = data.value?.items.findIndex((m) => m.material_id === updated.material_id)
  if (data.value && idx != null && idx >= 0) data.value.items[idx] = { ...data.value.items[idx], ...updated, material_id: data.value.items[idx].material_id }
  if (selected.value?.material_id === updated.material_id) selected.value = { ...selected.value, ...updated, material_id: selected.value.material_id }
}

/* 目录条目单选可反选；移动端选中后收起目录（素材志） */
function closeTocOnMobile() {
  if (window.innerWidth < 1024) tocOpen.value = false
}
function setMedia(value: string) {
  toggleMedia(value)
  closeTocOnMobile()
}
function setRating(value: number) {
  toggleRating(value)
  closeTocOnMobile()
}
function setTarget(value: number) {
  toggleTarget(value)
  closeTocOnMobile()
}
function setStatus(value: 'active' | 'deleted' | 'all') {
  toggleStatus(value)
  closeTocOnMobile()
}
function setTag(name: string) {
  toggleTag(name)
  closeTocOnMobile()
}

function resetAll() {
  resetFilters()
  tocOpen.value = false
}

/* 标准后台：点卡片 = 选中并展开详情栏 */
function openCard(m: Message) {
  selected.value = m
  paneOpen.value = true
}

/* 「/」聚焦检索；Esc 优先收目录（素材志）/详情栏（标准后台） */
function onGlobalKey(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (tocOpen.value) {
      tocOpen.value = false
      return
    }
    if (paneOpen.value && isNarrow.value) paneOpen.value = false
    return
  }
  const tag = document.activeElement?.tagName ?? ''
  if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(tag)) {
    e.preventDefault()
    if (isVault.value) {
      searchInput.value?.focus()
    } else {
      if (window.innerWidth < 1024) tocOpen.value = true
      void nextTick(() => searchInput.value?.focus())
    }
  }
}

onMounted(() => {
  syncFromQuery()
  loadStats()
  load()
  window.addEventListener('keydown', onGlobalKey)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKey)
  clearTimeout(skeletonTimer)
})
</script>

<template>
  <!-- ================= 标准后台：工具条 + 视图切换 + 常驻详情栏 ================= -->
  <div v-if="isVault" class="flex h-full min-w-0">
    <div class="flex min-w-0 flex-1 flex-col">
      <div class="min-h-0 flex-1 overflow-y-auto">
        <!-- 语境条 + 类型 chips：吸顶毛玻璃，内容从其下方滚过 -->
        <div class="sticky top-0 z-20 space-y-2 border-b border-ink-line bg-ink-bg/85 px-4 py-2.5 backdrop-blur-xl backdrop-saturate-150">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 class="text-[15px] font-semibold text-steam">素材</h1>
            <span v-if="data" class="font-mono text-[11px] tabular-nums text-steam-dim">{{ shown }} / {{ data.total }}</span>
            <!-- 焦点态由容器 focus-within 承担（描边 + 轻环，与卡片选中态同一语言）；
                 输入本体 focus:outline-none 压过全局 :focus-visible 外圈（简档下是刺眼默认蓝） -->
            <label
              class="flex h-9 w-full min-w-[180px] max-w-md flex-1 items-center gap-2 rounded-lg border border-ink-line bg-ink-raised px-2.5 transition-[border-color,box-shadow,background-color] [transition-duration:var(--motion-fast)] [transition-timing-function:var(--ease-standard)] focus-within:border-gold focus-within:bg-ink-surface focus-within:ring-2 focus-within:ring-gold/15"
            >
              <Search class="h-4 w-4 shrink-0 text-steam-dim" />
              <input
                ref="searchInput"
                v-model="q"
                type="search"
                :placeholder="L.searchPlaceholder"
                aria-label="检索素材"
                class="w-full min-w-0 bg-transparent text-[13px] text-steam focus:outline-none placeholder:text-steam-dim/60"
              />
              <kbd class="hidden shrink-0 rounded border border-ink-line bg-ink-surface px-1 font-mono text-[10px] text-steam-dim/70 min-[480px]:block">/</kbd>
            </label>
            <button
              v-if="isFilterActive"
              type="button"
              class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-ink-line px-2.5 text-xs text-steam-dim transition-colors hover:border-gold/50 hover:text-gold"
              @click="resetAll"
            >
              <RotateCcw class="h-3 w-3" /> {{ L.reset }}
            </button>
            <div class="ml-auto flex items-center gap-0.5 rounded-lg border border-ink-line bg-ink-raised p-0.5" role="tablist" aria-label="视图切换">
              <button
                type="button"
                class="grid h-7 w-7 cursor-pointer place-items-center rounded-md transition-colors"
                :class="viewMode === 'grid' ? 'bg-ink-surface text-steam shadow-sm' : 'text-steam-dim hover:text-steam'"
                aria-label="网格视图"
                :aria-pressed="viewMode === 'grid'"
                @click="viewMode = 'grid'"
              >
                <LayoutGrid class="h-4 w-4" />
              </button>
              <button
                type="button"
                class="grid h-7 w-7 cursor-pointer place-items-center rounded-md transition-colors"
                :class="viewMode === 'list' ? 'bg-ink-surface text-steam shadow-sm' : 'text-steam-dim hover:text-steam'"
                aria-label="列表视图"
                :aria-pressed="viewMode === 'list'"
                @click="viewMode = 'list'"
              >
                <Rows3 class="h-4 w-4" />
              </button>
            </div>
          </div>

          <!-- 类型 chips + 当前标签 -->
          <div class="flex flex-wrap items-center gap-1.5">
            <button
              v-for="op in mediaOptions"
              :key="op.value"
              type="button"
              class="inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-full border px-2.5 text-xs transition-colors"
              :class="mediaType === op.value ? 'border-gold bg-gold/10 text-gold' : 'border-ink-line text-steam-dim hover:text-steam'"
              :aria-pressed="mediaType === op.value"
              @click="setMedia(op.value)"
            >
              {{ op.label }}
            </button>
            <template v-if="tagFilter.length">
              <span class="mx-1 hidden h-4 w-px bg-ink-line min-[480px]:block" aria-hidden="true"></span>
              <TransitionGroup name="v-list">
                <span
                  v-for="t in tagFilter"
                  :key="t"
                  class="inline-flex h-7 items-center gap-1.5 rounded-full border border-gold bg-gold/10 px-2.5 text-xs text-gold"
                >
                  #{{ t }}
                  <button
                    type="button"
                    class="cursor-pointer transition-opacity hover:opacity-60"
                    :aria-label="`移除标签 ${t}`"
                    @click="removeTag(t)"
                  >
                    <X class="h-3 w-3" />
                  </button>
                </span>
              </TransitionGroup>
              <RouterLink :to="{ name: 'tags' }" class="text-[11px] text-gold underline underline-offset-4">
                全部{{ L.tag }}
              </RouterLink>
            </template>
          </div>
        </div>

        <!-- 内容区（工具条吸顶，独立滚动）。
             分支链 out-in 淡切（B4）；网格/列表 TransitionGroup：进场 fade-up、离场 fade，
             非瀑布流才启用 FLIP move（columns 布局量测不准，降级只做进出，B1）；
             grid↔list 走交叉淡切（B3）；首屏进场逐项延迟（B2） -->
        <div class="px-4 pb-24 pt-4 lg:pb-6">
          <Transition name="v-dialog" mode="out-in">
            <!-- 骨架屏（延迟 200ms 才出现：快加载不闪骨架） -->
            <div v-if="loading && !shown && skeletonReady" key="skeleton" :class="gridClass" aria-hidden="true">
              <div
                v-for="i in 8"
                :key="i"
                class="animate-pulse overflow-hidden rounded-xl border border-ink-line bg-ink-surface"
                :class="thumbMode === 'masonry' && 'mb-3.5 break-inside-avoid'"
              >
                <div class="aspect-video border-b border-ink-line bg-ink-raised" />
                <div class="space-y-2 p-3">
                  <div class="h-2.5 w-16 rounded bg-ink-raised" />
                  <div class="h-3.5 w-3/4 rounded bg-ink-raised" />
                  <div class="h-2.5 w-1/2 rounded bg-ink-raised" />
                </div>
              </div>
            </div>

            <!-- 首载失败 -->
            <div
              v-else-if="error"
              key="error"
              class="flex flex-col items-center gap-3 rounded-xl border border-ink-line bg-ink-surface py-16 text-steam-dim"
            >
              <AlertTriangle class="h-8 w-8" />
              <p class="text-sm">{{ error }}</p>
              <Button variant="secondary" size="sm" @click="load">重试</Button>
            </div>

            <div v-else-if="data && data.items.length" key="content">
              <Transition name="v-dialog" mode="out-in">
                <TransitionGroup
                  v-if="viewMode === 'grid'"
                  :key="`grid-${thumbMode}`"
                  tag="div"
                  name="v-list"
                  appear
                  :move-class="thumbMode === 'masonry' ? '' : 'v-list-move'"
                  :class="gridClass"
                >
                  <MessageCardVault
                    v-for="(m, i) in data.items"
                    :key="m.material_id"
                    :message="m"
                    :style="itemStyle(i)"
                    :selected="selected?.material_id === m.material_id"
                    @rate="(n) => rate(m, n)"
                    @open="openCard(m)"
                  />
                </TransitionGroup>
                <TransitionGroup
                  v-else
                  :key="`list-${thumbMode}`"
                  tag="div"
                  name="v-list"
                  appear
                  move-class="v-list-move"
                  class="overflow-hidden rounded-xl border border-ink-line bg-ink-surface shadow-sm"
                >
                  <MessageRow
                    v-for="(m, i) in data.items"
                    :key="m.material_id"
                    :message="m"
                    :style="itemStyle(i)"
                    :selected="selected?.material_id === m.material_id"
                    @rate="(n) => rate(m, n)"
                    @open="openCard(m)"
                  />
                </TransitionGroup>
              </Transition>

              <!-- 加载更多 -->
              <div v-if="hasMore" class="mt-4 flex justify-center">
                <Button variant="secondary" size="sm" :disabled="loading" @click="loadMore">
                  <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
                  {{ loading ? L.loading : `加载更多（${shown} / ${data.total}）` }}
                </Button>
              </div>
            </div>

            <!-- 空态 -->
            <div v-else-if="data" key="empty" class="py-16 text-center">
              <p class="text-[15px] font-semibold text-steam">{{ L.noMatch }}</p>
              <p class="mt-2 text-[13px] text-steam-dim">
                {{ L.noMatchHint }}
                <button type="button" class="cursor-pointer text-gold underline underline-offset-4" @click="resetAll">
                  {{ L.reset }}
                </button>
              </p>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- 窄屏详情遮罩 -->
    <Transition name="v-dialog">
      <div
        v-if="paneOpen && isNarrow"
        class="fixed inset-0 z-40 bg-ink-bg/50 backdrop-blur-[2px]"
        aria-hidden="true"
        @click="paneOpen = false"
      />
    </Transition>
    <!-- 详情栏：≥1280 常驻右栏（内衬圆角面板，宽度+透明度过渡）；窄屏覆盖层（点卡片滑出） -->
    <div
      class="anim-pane max-xl:fixed max-xl:inset-y-0 max-xl:right-0 max-xl:z-50 max-xl:w-[min(94vw,380px)] max-xl:shadow-2xl max-xl:transition-transform xl:relative xl:h-full xl:shrink-0 xl:overflow-hidden"
      :class="paneOpen ? 'anim-pane--open max-xl:translate-x-0 xl:w-[360px]' : 'max-xl:translate-x-full xl:w-0'"
    >
      <!-- 内层定宽：收起动画期间内容不被压缩重排，由外层裁切 -->
      <div class="h-full w-full xl:w-[360px] xl:py-2.5 xl:pr-2.5">
        <MessageDrawer pane :message="selected" @close="paneOpen = false" @update="onDrawerUpdate" />
      </div>
    </div>
  </div>

  <!-- ================= 素材志：报眉 + 目录 + 瀑布流（原样保留） ================= -->
  <div v-else class="mx-auto max-w-[1440px] px-5 py-8 min-[820px]:px-8">
    <!-- 报眉：顶栏即报头，页面以一行元信息 + 双规则线开场，不再重复刊名 -->
    <header>
      <div
        class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 pb-2.5 font-mono text-[10.5px] tracking-[0.18em] text-steam-dim"
      >
        <span>COLLECTED FROM TELEGRAM</span>
        <span class="hidden min-[480px]:inline">{{ issue }} · 私人归档</span>
        <span v-if="data">共 {{ data.total }} 件 · 已载 {{ shown }} 件</span>
      </div>
      <div class="mast-rules mast-rules--flush hidden" aria-hidden="true"></div>
    </header>

    <div class="mt-7 flex items-start">
      <!-- 移动端目录遮罩 -->
      <Transition name="v-dialog">
        <div
          v-if="tocOpen"
          class="fixed inset-0 z-40 bg-ink-bg/70 backdrop-blur-sm lg:hidden"
          aria-hidden="true"
          @click="tocOpen = false"
        />
      </Transition>

      <!-- 目录页：桌面常驻左栏，移动端全屏抽屉 -->
      <aside
        class="fixed inset-y-0 left-0 z-50 w-[min(84vw,320px)] overflow-y-auto overscroll-contain [scrollbar-gutter:stable] border-r border-ink-line bg-ink-bg px-6 pb-10 pt-6 transition-transform duration-300 ease-out lg:sticky lg:top-14 lg:z-auto lg:max-h-[calc(100vh-3.5rem)] lg:w-[236px] lg:shrink-0 lg:bg-transparent lg:px-0 lg:pb-16 lg:pr-7 lg:pt-0 lg:transition-none"
        :class="tocOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'"
        aria-label="目录与筛选"
      >
        <div class="flex items-center justify-between lg:block">
          <h2 class="font-display text-[17px] font-bold tracking-[0.3em] text-steam">目 录</h2>
          <button
            type="button"
            class="flex h-10 w-10 cursor-pointer items-center justify-center rounded-md text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam lg:hidden"
            aria-label="收起目录"
            @click="tocOpen = false"
          >
            <X class="h-5 w-5" />
          </button>
        </div>

        <label
          class="toc-search mt-5 flex items-center gap-2.5 border border-ink-line bg-ink-surface px-3.5 py-2.5 transition-[border-color] [transition-duration:var(--motion-fast)] [transition-timing-function:var(--ease-standard)]"
        >
          <Search class="h-4 w-4 shrink-0 text-steam-dim" />
          <input
            ref="searchInput"
            v-model="q"
            type="search"
            placeholder="检索本卷…"
            aria-label="检索素材"
            class="w-full bg-transparent text-sm text-steam focus:outline-none placeholder:text-steam-dim/70"
          />
        </label>

        <!-- 体例 -->
        <nav class="mt-7" aria-label="体例索引">
          <h3 class="mb-1.5 font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">体例 · TYPE</h3>
          <ul>
            <li v-for="op in mediaOptions" :key="op.label">
              <button
                type="button"
                class="flex w-full cursor-pointer items-baseline gap-2 px-0.5 py-[7px] text-left text-[13.5px] transition-colors"
                :class="mediaType === op.value ? 'text-gold' : 'text-steam-dim hover:text-steam'"
                :aria-pressed="mediaType === op.value"
                @click="setMedia(op.value)"
              >
                <span class="shrink-0">{{ op.label }}</span>
                <span class="toc-lead hidden" aria-hidden="true"></span>
                <span
                  v-if="typeCount(op.value) !== null"
                  class="ml-auto font-mono text-xs"
                  :class="mediaType === op.value ? 'font-bold text-gold' : 'text-steam-dim/80'"
                >
                  {{ typeCount(op.value) }}
                </span>
              </button>
            </li>
          </ul>
        </nav>

        <!-- 类目 -->
        <nav v-if="tagIndex.length" class="mt-7" aria-label="类目索引">
          <h3 class="mb-1.5 font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">类目 · TAGS</h3>
          <ul>
            <li v-for="tag in tagIndex" :key="tag.name">
              <button
                type="button"
                class="flex w-full cursor-pointer items-baseline gap-2 px-0.5 py-[7px] text-left text-[13.5px] transition-colors"
                :class="tagFilter.includes(tag.name) ? 'text-gold' : 'text-steam-dim hover:text-steam'"
                :aria-pressed="tagFilter.includes(tag.name)"
                @click="setTag(tag.name)"
              >
                <span class="shrink-0 truncate">{{ tag.name }}</span>
                <span class="toc-lead hidden" aria-hidden="true"></span>
                <span
                  class="ml-auto shrink-0 font-mono text-xs"
                  :class="tagFilter.includes(tag.name) ? 'font-bold text-gold' : 'text-steam-dim/80'"
                >
                  {{ tag.count }}
                </span>
              </button>
            </li>
          </ul>
        </nav>

        <!-- 评鉴 -->
        <nav class="mt-7" aria-label="评鉴索引">
          <h3 class="mb-1.5 font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">评鉴 · RATING</h3>
          <ul>
            <li v-for="op in ratingOptions" :key="op.value">
              <button
                type="button"
                class="flex w-full cursor-pointer items-baseline gap-2 px-0.5 py-[7px] text-left text-[13.5px] transition-colors"
                :class="rating === op.value ? 'text-gold' : 'text-steam-dim hover:text-steam'"
                :aria-pressed="rating === op.value"
                @click="setRating(op.value)"
              >
                <span class="shrink-0">{{ op.label }}</span>
                <span class="toc-lead hidden" aria-hidden="true"></span>
              </button>
            </li>
          </ul>
        </nav>

        <!-- 目标：显示配置里的人读名称，缺失回退拼 ID -->
        <nav v-if="targets.length" class="mt-7" aria-label="目标索引">
          <h3 class="mb-1.5 font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">目标 · TARGETS</h3>
          <ul>
            <li v-for="t in targets" :key="t.chat_id">
              <button
                type="button"
                class="flex w-full cursor-pointer items-baseline gap-2 px-0.5 py-[7px] text-left text-[13.5px] transition-colors"
                :class="targetFilter === t.chat_id ? 'text-gold' : 'text-steam-dim hover:text-steam'"
                :aria-pressed="targetFilter === t.chat_id"
                @click="setTarget(t.chat_id)"
              >
                <span class="min-w-0 shrink truncate">{{ t.name || `目标 ${displayChatId(t.chat_id)}` }}</span>
                <span class="toc-lead hidden" aria-hidden="true"></span>
                <span
                  class="ml-auto shrink-0 font-mono text-xs"
                  :class="targetFilter === t.chat_id ? 'font-bold text-gold' : 'text-steam-dim/80'"
                >
                  {{ t.count }}
                </span>
              </button>
            </li>
          </ul>
        </nav>

        <!-- 状态 -->
        <nav class="mt-7" aria-label="状态索引">
          <h3 class="mb-1.5 font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">状态 · STATUS</h3>
          <ul>
            <li v-for="op in statusOptions" :key="op.value">
              <button
                type="button"
                class="flex w-full cursor-pointer items-baseline gap-2 px-0.5 py-[7px] text-left text-[13.5px] transition-colors"
                :class="statusFilter === op.value ? 'text-gold' : 'text-steam-dim hover:text-steam'"
                :aria-pressed="statusFilter === op.value"
                @click="setStatus(op.value)"
              >
                <span class="shrink-0">{{ op.label }}</span>
                <span class="toc-lead hidden" aria-hidden="true"></span>
              </button>
            </li>
          </ul>
        </nav>

        <p class="mt-8 border-t border-ink-line pt-4 text-xs leading-[2] text-steam-dim/80">
          条目来自已归档素材，点击即可筛选图录；按 / 快速检索。
        </p>
      </aside>

      <!-- 图录 -->
      <main class="min-w-0 flex-1 lg:pl-8">
        <div class="mb-6 flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h2 class="font-display text-xl font-bold tracking-[0.18em] text-steam min-[480px]:text-2xl">本卷图录</h2>
          <p v-if="data" class="font-mono text-[11px] tracking-[0.1em] text-steam-dim">
            {{ data.total }} 件<template v-if="isFilterActive"> · 显示 {{ shown }} 件</template>
          </p>
          <button
            v-if="isFilterActive"
            type="button"
            class="ml-auto inline-flex cursor-pointer items-center gap-1.5 font-mono text-[11px] text-gold underline underline-offset-4"
            @click="resetAll"
          >
            <RotateCcw class="h-3 w-3" /> {{ L.reset }}
          </button>
        </div>

        <!-- 类目快捷切换条：出现于带类目筛选时，点其他类目加入/移除多选（chips 增删过渡 B5） -->
        <div v-if="tagFilter.length && stripTags.length" class="mb-5 flex flex-wrap items-center gap-2">
          <span class="font-mono text-[10px] tracking-[0.22em] text-steam-dim">{{ L.tag }}</span>
          <TransitionGroup name="v-list">
            <button
              v-for="t in stripTags"
              :key="t.name"
              type="button"
              class="inline-flex cursor-pointer items-baseline gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors"
              :class="tagFilter.includes(t.name) ? 'border-gold bg-gold/10 text-gold' : 'border-ink-line text-steam-dim hover:text-steam'"
              :aria-pressed="tagFilter.includes(t.name)"
              @click="toggleTag(t.name)"
            >
              #{{ t.name }}
              <span v-if="t.count > 0" class="font-mono text-[10px] opacity-70">{{ t.count }}</span>
              <X
                v-if="tagFilter.includes(t.name)"
                class="h-3 w-3 cursor-pointer self-center transition-opacity hover:opacity-60"
                aria-label="移除该类目"
                @click.stop="removeTag(t.name)"
              />
            </button>
          </TransitionGroup>
          <RouterLink
            :to="{ name: 'tags' }"
            class="font-mono text-[10px] text-gold underline underline-offset-4"
          >
            全部类目
          </RouterLink>
        </div>

        <!-- 分支链 out-in 淡切（B4）；图录 TransitionGroup 进出场（B1，瀑布流降级只做进出）+ 首屏 stagger（B2） -->
        <Transition name="v-dialog" mode="out-in">
          <!-- 骨架屏：与图版同构的占位（延迟 200ms 才出现：快加载不闪骨架） -->
          <div
            v-if="loading && !shown && skeletonReady"
            :class="thumbMode === 'masonry' ? 'columns-1 gap-6 min-[480px]:columns-2 xl:columns-3 min-[1600px]:columns-4' : 'grid grid-cols-2 gap-5 xl:grid-cols-3 min-[1600px]:grid-cols-4'"
            aria-hidden="true"
          >
            <div v-for="i in 8" :key="i" class="mb-6 break-inside-avoid animate-pulse">
              <div class="border border-ink-line bg-ink-surface p-2.5">
                <div class="h-44 bg-ink-raised" />
              </div>
              <div class="px-1 pt-3">
                <div class="h-2.5 w-24 bg-ink-raised" />
                <div class="mt-2.5 h-4 w-3/4 bg-ink-raised" />
                <div class="mt-2 h-2.5 w-1/2 bg-ink-raised" />
              </div>
            </div>
          </div>

          <!-- 图录：瀑布流（原生装裱）或统一画布（跟随显示偏好） -->
          <TransitionGroup
            v-else-if="data && data.items.length"
            tag="div"
            name="v-list"
            appear
            :move-class="thumbMode === 'masonry' ? '' : 'v-list-move'"
            :class="thumbMode === 'masonry' ? 'columns-1 gap-6 min-[480px]:columns-2 xl:columns-3 min-[1600px]:columns-4' : 'grid grid-cols-2 gap-5 xl:grid-cols-3 min-[1600px]:grid-cols-4'"
          >
            <MessageCard
              v-for="(m, i) in data.items"
              :key="m.material_id"
              :message="m"
              :style="itemStyle(i)"
              @rate="(n) => rate(m, n)"
              @open="selected = m"
            />
          </TransitionGroup>

          <!-- 首载失败：整块错误态 + 重试 -->
          <div v-else-if="error" class="flex flex-col items-center gap-3 border-t border-ink-line py-16 text-steam-dim">
            <AlertTriangle class="h-8 w-8" />
            <p class="text-sm">{{ error }}</p>
            <Button variant="secondary" size="sm" @click="load">重试</Button>
          </div>

          <!-- 空态 -->
          <div v-else-if="data" class="border-t border-ink-line py-16 text-center">
            <p class="empty-title font-display text-xl text-steam">{{ L.noMatch }}</p>
            <p class="mt-2 text-[13px] text-steam-dim">
              目录下没有匹配的条目，
              <button
                type="button"
                class="cursor-pointer text-gold underline underline-offset-4"
                @click="resetAll"
              >
                {{ L.reset }}
              </button>
            </p>
          </div>
        </Transition>

        <!-- 加载更多 -->
        <div v-if="hasMore && data?.items.length" class="mt-2 flex justify-center">
          <Button variant="secondary" size="sm" :disabled="loading" @click="loadMore">
            <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
            {{ loading ? L.loading : `加载更多（${shown} / ${data?.total}）` }}
          </Button>
        </div>
      </main>
    </div>

    <!-- 移动端目录悬浮按钮（避开底栏；再点收起） -->
    <button
      type="button"
      class="fixed bottom-24 right-4 z-40 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-ink-line/70 bg-ink-surface/85 text-steam shadow-lg backdrop-blur-xl transition-transform active:scale-95 lg:hidden"
      :aria-label="tocOpen ? '收起目录' : '打开目录'"
      :aria-expanded="tocOpen"
      @click="tocOpen = !tocOpen"
    >
      <Transition name="v-dialog" mode="out-in">
        <component
          :is="tocOpen ? X : SlidersHorizontal"
          :key="tocOpen ? 'close' : 'open'"
          class="h-4 w-4"
        />
      </Transition>
    </button>

    <MessageDrawer :message="selected" @close="selected = null" @update="onDrawerUpdate" />
  </div>
</template>
