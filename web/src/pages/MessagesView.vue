<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loader2, SearchX, X } from 'lucide-vue-next'
import { getStats, listMessages, patchMessage } from '@/lib/api'
import type { Message, MessagesResponse, Target } from '@/lib/types'
import MessageCard from '@/components/MessageCard.vue'
import MessageDrawer from '@/components/MessageDrawer.vue'
import Input from '@/components/ui/Input.vue'
import Button from '@/components/ui/Button.vue'
import { toastError, toastSuccess } from '@/composables/useToast'

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
const selected = ref<Message | null>(null)

const PAGE = 30
const mediaOptions = [
  { value: '', label: '全部类型' },
  { value: 'photo', label: '图片' },
  { value: 'video', label: '视频' },
  { value: 'document', label: '文件' },
  { value: 'text', label: '文本' },
]
const ratingOptions = [
  { value: '', label: '全部评级' },
  { value: '5', label: '5 星' },
  { value: '4', label: '4 星' },
  { value: '3', label: '3 星' },
  { value: '2', label: '2 星' },
  { value: '1', label: '1 星' },
  { value: '0', label: '未评级' },
]

const shown = computed(() => data.value?.items.length ?? 0)
const hasMore = computed(() => data.value ? shown.value < data.value.total : false)

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

async function loadStats() {
  try {
    targets.value = (await getStats()).targets
  } catch {
    targets.value = []
  }
}

let timer: ReturnType<typeof setTimeout> | undefined
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
  loading.value = true
  error.value = ''
  try {
    data.value = await listMessages({
      q: q.value || undefined,
      media_type: mediaType.value || undefined,
      rating: rating.value === '' ? undefined : Number(rating.value),
      tag: tagFilter.value || undefined,
      target_chat_id: targetFilter.value === '' ? undefined : Number(targetFilter.value),
      status: statusFilter.value,
      limit: PAGE,
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
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
    const updated = await patchMessage(msg.id, { rating: value })
    const item = data.value?.items.find((m) => m.id === msg.id)
    if (item) Object.assign(item, updated)
    toastSuccess(value === 0 ? '已清除评级' : `评级设为 ${value} 星`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
    toastError(e instanceof Error ? e.message : '保存失败')
  }
}

function onDrawerUpdate(updated: Message) {
  const idx = data.value?.items.findIndex((m) => m.id === updated.id)
  if (data.value && idx != null && idx >= 0) data.value.items[idx] = updated
  if (selected.value?.id === updated.id) selected.value = updated
}

onMounted(() => {
  syncFromQuery()
  loadStats()
  load()
})
</script>

<template>
  <div class="mx-auto max-w-6xl px-6 py-8">
    <header class="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-display text-3xl font-semibold tracking-tight">素材</h1>
        <p v-if="data" class="mt-1 text-sm text-steam-dim">共 {{ data.total }} 条</p>
      </div>
    </header>

    <!-- 筛选栏 -->
    <div class="mb-6 flex flex-wrap items-center gap-3">
      <Input v-model="q" placeholder="搜索正文…" class="max-w-xs" aria-label="搜索正文" />
      <label class="flex items-center gap-1.5 text-sm text-steam-dim">
        <select
          v-model="targetFilter"
          class="h-9 rounded-md border border-ink-line bg-ink-raised px-2 text-sm text-steam focus:border-gold focus:outline-none"
          aria-label="按目标频道筛选"
        >
          <option value="">全部频道</option>
          <option v-for="t in targets" :key="t.chat_id" :value="t.chat_id">
            频道 {{ t.chat_id }}（{{ t.count }}）
          </option>
        </select>
      </label>
      <label class="flex items-center gap-1.5 text-sm text-steam-dim">
        <select v-model="statusFilter" class="h-9 rounded-md border border-ink-line bg-ink-raised px-2 text-sm text-steam focus:border-gold focus:outline-none" aria-label="消息状态">
          <option value="active">活跃消息</option>
          <option value="deleted">已删除消息</option>
          <option value="all">全部消息</option>
        </select>
      </label>
      <label class="flex items-center gap-1.5 text-sm text-steam-dim">
        <select
          v-model="mediaType"
          class="h-9 rounded-md border border-ink-line bg-ink-raised px-2 text-sm text-steam focus:border-gold focus:outline-none"
        >
          <option v-for="op in mediaOptions" :key="op.value" :value="op.value">{{ op.label }}</option>
        </select>
      </label>
      <label class="flex items-center gap-1.5 text-sm text-steam-dim">
        <select
          v-model="rating"
          class="h-9 rounded-md border border-ink-line bg-ink-raised px-2 text-sm text-steam focus:border-gold focus:outline-none"
        >
          <option v-for="op in ratingOptions" :key="op.value" :value="op.value">{{ op.label }}</option>
        </select>
      </label>
      <Button variant="secondary" size="sm" @click="load">刷新</Button>
      <span v-if="error" class="text-xs text-destructive">{{ error }}</span>
    </div>

    <!-- 标签筛选 chip：点 × 清除 -->
    <div v-if="tagFilter" class="mb-4 inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/10 px-3 py-1 text-sm text-gold">
      <span>标签筛选：#{{ tagFilter }}</span>
      <button
        type="button"
        class="rounded-full p-0.5 transition-colors hover:bg-gold/20 cursor-pointer"
        aria-label="清除标签筛选"
        @click="tagFilter = ''"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </div>

    <div v-if="loading && !shown" class="flex items-center gap-2 text-steam-dim">
      <Loader2 class="h-4 w-4 animate-spin" /> 载入中…
    </div>

    <div
      v-else-if="data && data.items.length"
      class="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4"
    >
      <MessageCard
        v-for="m in data.items"
        :key="m.id"
        :message="m"
        @rate="(n) => rate(m, n)"
        @open="selected = m"
      />
    </div>

    <div v-else-if="data" class="flex flex-col items-center gap-2 py-16 text-steam-dim">
      <SearchX class="h-8 w-8" />
      <p class="text-sm">没有匹配的素材</p>
    </div>

    <div v-if="hasMore" class="mt-6 flex justify-center">
      <Button
        variant="secondary"
        :disabled="loading"
        @click="loadMore"
      >
        <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
        {{ loading ? '载入中…' : `加载更多（${shown} / ${data?.total}）` }}
      </Button>
    </div>

    <MessageDrawer :message="selected" @close="selected = null" @update="onDrawerUpdate" />
  </div>
</template>