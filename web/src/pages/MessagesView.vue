<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertTriangle,
  Loader2,
  RotateCcw,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-vue-next'
import { getStats, getTags, listMessages, patchMessage } from '@/lib/api'
import type { Message, MessagesResponse, Stats, TagCount, Target } from '@/lib/types'
import MessageCard from '@/components/MessageCard.vue'
import MessageDrawer from '@/components/MessageDrawer.vue'
import Button from '@/components/ui/Button.vue'
import { toastError, toastSuccess } from '@/composables/useToast'
import { displayChatId } from '@/lib/format'

const route = useRoute()
const router = useRouter()

const data = ref<MessagesResponse | null>(null)
const loading = ref(true)
const error = ref('')
const q = ref('')
const mediaType = ref('')
const rating = ref<number | ''>('')
const tagFilter = ref('')
const targetFilter = ref<number | ''>('')
const statusFilter = ref<'active' | 'deleted' | 'all'>('active')
const targets = ref<Target[]>([])
const stats = ref<Stats | null>(null)
const tagIndex = ref<TagCount[]>([])
const selected = ref<Message | null>(null)
const tocOpen = ref(false)
const searchInput = ref<HTMLInputElement | null>(null)

const PAGE = 30
const mediaOptions = [
  { value: '', label: '全卷' },
  { value: 'photo', label: '图版' },
  { value: 'video', label: '影像' },
  { value: 'document', label: '附件' },
  { value: 'text', label: '抄本' },
]
/* 评级词与抽屉评鉴提示一致；接口无评级分布，目录不标计数 */
const ratingOptions = [
  { value: 5, label: '五星 · 珍藏' },
  { value: 4, label: '四星 · 优质' },
  { value: 3, label: '三星 · 有用' },
  { value: 2, label: '二星 · 可留' },
  { value: 1, label: '一星 · 普通' },
  { value: 0, label: '待评鉴' },
]
const statusOptions: { value: 'active' | 'deleted' | 'all'; label: string }[] = [
  { value: 'active', label: '活跃' },
  { value: 'deleted', label: '已删除' },
  { value: 'all', label: '全部' },
]

const shown = computed(() => data.value?.items.length ?? 0)
const hasMore = computed(() => (data.value ? shown.value < data.value.total : false))
const isFilterActive = computed(
  () =>
    !!(
      q.value ||
      mediaType.value ||
      rating.value !== '' ||
      tagFilter.value ||
      targetFilter.value !== '' ||
      statusFilter.value !== 'active'
    ),
)

/** 刊头卷号：ISO 周数当卷号，配「不定期刊」的自嘲 */
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

/** 类目快捷切换条：热度前 12 + 当前类目（不在前 12 则补进来） */
const stripTags = computed<TagCount[]>(() => {
  const top = tagIndex.value.slice(0, 12)
  const current = tagFilter.value
  if (current && !top.some((t) => t.name === current)) {
    const found = tagIndex.value.find((t) => t.name === current)
    top.unshift(found ?? { name: current, count: 0 })
  }
  return top
})

// URL ?tag=（从标签页点来）作为标签筛选的初始值
function syncFromQuery() {
  const t = route.query.tag
  if (typeof t === 'string' && t) tagFilter.value = t
}

// 标签筛选变更时同步回 URL，可分享/前进后退
function syncToQuery() {
  router.replace({
    query: tagFilter.value ? { tag: tagFilter.value } : {},
  })
}

// 抽屉点类目等场景在同一页改 query：路由变化要反映到筛选。
// 仅在与当前值不同才回写，避免和 syncToQuery 打环。
watch(
  () => route.query.tag,
  (t) => {
    const v = typeof t === 'string' && t ? t : ''
    if (v !== tagFilter.value) tagFilter.value = v
  },
)

async function loadStats() {
  try {
    const [s, t] = await Promise.all([getStats(), getTags()])
    stats.value = s
    targets.value = s.targets
    tagIndex.value = [...t.items].sort((a, b) => b.count - a.count).slice(0, 14)
  } catch {
    stats.value = null
    targets.value = []
    tagIndex.value = []
  }
}

let timer: ReturnType<typeof setTimeout> | undefined
let requestGeneration = 0
watch([q, mediaType, rating, targetFilter, statusFilter], () => {
  clearTimeout(timer)
  data.value = null
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
      tag: tagFilter.value || undefined,
      target_chat_id: targetFilter.value === '' ? undefined : Number(targetFilter.value),
      status: statusFilter.value,
      limit: PAGE,
    })
    if (generation === requestGeneration) data.value = result
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
      tag: tagFilter.value || undefined,
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

/* 目录条目单选可反选；移动端选中后收起目录 */
function closeTocOnMobile() {
  if (window.innerWidth < 1024) tocOpen.value = false
}
function setMedia(value: string) {
  mediaType.value = mediaType.value === value && value !== '' ? '' : value
  closeTocOnMobile()
}
function setRating(value: number) {
  rating.value = rating.value === value ? '' : value
  closeTocOnMobile()
}
function setTarget(value: number) {
  targetFilter.value = targetFilter.value === value ? '' : value
  closeTocOnMobile()
}
function setStatus(value: 'active' | 'deleted' | 'all') {
  statusFilter.value = statusFilter.value === value ? 'active' : value
  closeTocOnMobile()
}
function setTag(name: string) {
  tagFilter.value = tagFilter.value === name ? '' : name
  closeTocOnMobile()
}

function resetFilters() {
  q.value = ''
  mediaType.value = ''
  rating.value = ''
  targetFilter.value = ''
  statusFilter.value = 'active'
  tagFilter.value = '' // 触发 URL 同步与重查
  tocOpen.value = false
}

/* 「/」聚焦检索；Esc 优先收目录（抽屉自管 Esc） */
function onGlobalKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && tocOpen.value) {
    tocOpen.value = false
    return
  }
  const tag = document.activeElement?.tagName ?? ''
  if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(tag)) {
    e.preventDefault()
    if (window.innerWidth < 1024) tocOpen.value = true
    void nextTick(() => searchInput.value?.focus())
  }
}

onMounted(() => {
  syncFromQuery()
  loadStats()
  load()
  window.addEventListener('keydown', onGlobalKey)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalKey))
</script>

<template>
  <div class="mx-auto max-w-[1440px] px-5 py-8 min-[820px]:px-8">
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
      <div
        v-if="tocOpen"
        class="fixed inset-0 z-40 bg-ink-bg/70 backdrop-blur-sm lg:hidden"
        aria-hidden="true"
        @click="tocOpen = false"
      />

      <!-- 目录页：桌面常驻左栏，移动端全屏抽屉 -->
      <aside
        class="fixed inset-y-0 left-0 z-50 w-[min(84vw,320px)] overflow-y-auto border-r border-ink-line bg-ink-bg px-6 pb-10 pt-6 transition-transform duration-300 ease-out lg:sticky lg:top-14 lg:z-auto lg:max-h-[calc(100vh-3.5rem)] lg:w-[236px] lg:shrink-0 lg:bg-transparent lg:px-0 lg:pb-16 lg:pr-7 lg:pt-0 lg:transition-none"
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

        <label class="toc-search mt-5 flex items-center gap-2.5 border border-ink-line bg-ink-surface px-3.5 py-2.5">
          <Search class="h-4 w-4 shrink-0 text-steam-dim" />
          <input
            ref="searchInput"
            v-model="q"
            type="search"
            placeholder="检索本卷…"
            aria-label="检索素材"
            class="w-full bg-transparent text-sm text-steam outline-none placeholder:text-steam-dim/70"
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
                :class="tagFilter === tag.name ? 'text-gold' : 'text-steam-dim hover:text-steam'"
                :aria-pressed="tagFilter === tag.name"
                @click="setTag(tag.name)"
              >
                <span class="shrink-0 truncate">{{ tag.name }}</span>
                <span class="toc-lead hidden" aria-hidden="true"></span>
                <span
                  class="ml-auto shrink-0 font-mono text-xs"
                  :class="tagFilter === tag.name ? 'font-bold text-gold' : 'text-steam-dim/80'"
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
            @click="resetFilters"
          >
            <RotateCcw class="h-3 w-3" /> 重置目录
          </button>
        </div>

        <!-- 类目快捷切换条：带类目筛选时出现，点其他类目直接换，× 清除 -->
        <div v-if="tagFilter && stripTags.length" class="mb-5 flex flex-wrap items-center gap-2">
          <span class="font-mono text-[10px] tracking-[0.22em] text-steam-dim">类目</span>
          <button
            v-for="t in stripTags"
            :key="t.name"
            type="button"
            class="inline-flex cursor-pointer items-baseline gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors"
            :class="t.name === tagFilter ? 'border-gold bg-gold/10 text-gold' : 'border-ink-line text-steam-dim hover:text-steam'"
            :aria-pressed="t.name === tagFilter"
            @click="tagFilter = t.name"
          >
            #{{ t.name }}
            <span v-if="t.count > 0" class="font-mono text-[10px] opacity-70">{{ t.count }}</span>
            <X
              v-if="t.name === tagFilter"
              class="h-3 w-3 cursor-pointer self-center transition-opacity hover:opacity-60"
              aria-label="清除类目筛选"
              @click.stop="tagFilter = ''"
            />
          </button>
          <RouterLink
            :to="{ name: 'tags' }"
            class="font-mono text-[10px] text-gold underline underline-offset-4"
          >
            全部类目
          </RouterLink>
        </div>

        <!-- 骨架屏：与图版同构的占位 -->
        <div
          v-if="loading && !shown"
          class="columns-1 gap-6 min-[480px]:columns-2 xl:columns-3 min-[1600px]:columns-4"
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

        <!-- 图录瀑布流 -->
        <div
          v-else-if="data && data.items.length"
          class="columns-1 gap-6 min-[480px]:columns-2 xl:columns-3 min-[1600px]:columns-4"
        >
          <MessageCard
            v-for="m in data.items"
            :key="m.material_id"
            :message="m"
            @rate="(n) => rate(m, n)"
            @open="selected = m"
          />
        </div>

        <!-- 首载失败：整块错误态 + 重试 -->
        <div v-else-if="error" class="flex flex-col items-center gap-3 border-t border-ink-line py-16 text-steam-dim">
          <AlertTriangle class="h-8 w-8" />
          <p class="text-sm">{{ error }}</p>
          <Button variant="secondary" size="sm" @click="load">重试</Button>
        </div>

        <!-- 空态 -->
        <div v-else-if="data" class="border-t border-ink-line py-16 text-center">
          <p class="empty-title font-display text-xl text-steam">查无此件</p>
          <p class="mt-2 text-[13px] text-steam-dim">
            目录下没有匹配的条目，
            <button
              type="button"
              class="cursor-pointer text-gold underline underline-offset-4"
              @click="resetFilters"
            >
              重置目录
            </button>
          </p>
        </div>

        <!-- 加载更多 -->
        <div v-if="hasMore && data?.items.length" class="mt-2 flex justify-center">
          <Button variant="secondary" size="sm" :disabled="loading" @click="loadMore">
            <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
            {{ loading ? '载入中…' : `加载更多（${shown} / ${data?.total}）` }}
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
      <X v-if="tocOpen" class="h-4 w-4" />
      <SlidersHorizontal v-else class="h-4 w-4" />
    </button>

    <MessageDrawer :message="selected" @close="selected = null" @update="onDrawerUpdate" />
  </div>
</template>
