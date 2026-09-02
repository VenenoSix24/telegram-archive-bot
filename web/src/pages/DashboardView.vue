<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { FileText, Film, Headphones, Image as ImageIcon, Music, Sticker } from 'lucide-vue-next'
import { getStats, getTags, listMessages } from '@/lib/api'
import type { Message, Stats, TagCount } from '@/lib/types'
import MessageDrawer from '@/components/MessageDrawer.vue'
import Button from '@/components/ui/Button.vue'
import { displayChatId, durationLabel, shortDate, splitBodyTitleDesc } from '@/lib/format'
import { useAspectRatio } from '@/composables/useAspectRatio'

const stats = ref<Stats | null>(null)
const recent = ref<Message[]>([])
const tagDist = ref<TagCount[]>([])
const loading = ref(true)
const loadError = ref('')
const selected = ref<Message | null>(null)
const coverFailed = ref(false)

/* 本期封面图版：随图片真实比例 */
const { ratio: coverRatio, onLoad: onCoverLoad } = useAspectRatio()

/* 体例沿用素材志词汇，与卡片图签一致 */
const TYPE_LABEL: Record<string, string> = {
  photo: '图版',
  video: '影像',
  audio: '音频',
  voice: '语音',
  sticker: '贴纸',
  document: '附件',
  text: '抄本',
  other: '其他',
}

function iconOf(m: Message) {
  switch (m.media_type) {
    case 'video': return Film
    case 'audio': return Music
    case 'voice': return Headphones
    case 'sticker': return Sticker
    case 'photo': return ImageIcon
    default: return FileText
  }
}

/** 本期封面 = 最新一条未注销素材；列表里去掉封面避免重复 */
const cover = computed(() => recent.value.find((m) => m.status !== 'deleted') ?? null)
const recentList = computed(() =>
  cover.value ? recent.value.filter((m) => m.material_id !== cover.value?.material_id) : recent.value,
)
const coverImg = computed(() => {
  const m = cover.value
  if (!m || coverFailed.value) return null
  if (m.media_type !== 'photo' && m.media_type !== 'video') return null
  const target = m.target_id
  return `/api/v1/messages/${m.id}/thumb${target == null ? '' : `?target_id=${target}`}`
})
const coverIcon = computed(() => (cover.value ? iconOf(cover.value) : FileText))
const coverFigMeta = computed(() => {
  const m = cover.value
  if (!m) return ''
  const parts = [TYPE_LABEL[m.media_type] ?? '素材']
  const d = durationLabel(m.duration)
  if (d) parts.push(d)
  return parts.join(' · ')
})

const ledger = computed(() => {
  if (!stats.value) return []
  return [
    { label: '总件数', value: String(stats.value.messages.total) },
    { label: '已归档', value: String(stats.value.messages.archived) },
    { label: '来源', value: String(stats.value.messages.sources) },
    {
      label: '类目',
      value: `${stats.value.tags.with_messages}/${stats.value.tags.total}`,
    },
  ]
})

/** 卷首语：由统计自动生成的一句话编辑摘要 */
const intro = computed(() => {
  if (!stats.value) return ''
  const m = stats.value.messages
  const parts: string[] = [`本卷共编目 ${m.total} 件`]
  const topTypes = Object.entries(m.by_type)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([type, n]) => `${TYPE_LABEL[type] ?? type} ${n}`)
  if (topTypes.length) parts.push(`以${topTypes.join('、')}为主`)
  const q = stats.value.queue
  if (q && q.failed > 0) parts.push(`尚有 ${q.failed} 件印制失败待查`)
  else if (q && q.pending + q.processing > 0) parts.push(`${q.pending + q.processing} 件正在路上`)
  else parts.push('全部归档完毕')
  return `${parts.join('，')}。`
})

const mediaLine = computed(() => {
  if (!stats.value) return ''
  const entries = Object.entries(stats.value.messages.by_type)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([type, n]) => `${TYPE_LABEL[type] ?? type} ${n}`)
  return entries.join(' · ')
})

const queueRows = computed(() => {
  if (!stats.value?.queue) return []
  const q = stats.value.queue
  return [
    { label: '待发', value: q.pending, tone: 'normal' as const },
    { label: '印制中', value: q.processing, tone: 'normal' as const },
    { label: '已完成', value: q.success, tone: 'normal' as const },
    { label: '失败', value: q.failed, tone: q.failed > 0 ? ('alert' as const) : ('normal' as const) },
  ]
})
const queueIdle = computed(
  () =>
    !!stats.value?.queue &&
    stats.value.queue.pending + stats.value.queue.processing + stats.value.queue.failed === 0,
)

const maxTagCount = computed(() => Math.max(1, ...tagDist.value.map((t) => t.count)))

function rowTitle(m: Message) {
  const split = splitBodyTitleDesc(
    m.original_text || m.rendered_text || '',
    (m.tags ?? []).map((t) => t.name),
  )
  return split.title || m.file_name || `素材 #${m.id}`
}

function rowChan(m: Message) {
  return m.targets[0]?.name || displayChatId(m.target_chat_id)
}

function onDrawerUpdate(updated: Message) {
  recent.value = recent.value.map((m) => (m.material_id === updated.material_id ? updated : m))
  if (selected.value?.material_id === updated.material_id) selected.value = updated
}

async function load() {
  loadError.value = ''
  coverFailed.value = false
  try {
    const [s, t, r] = await Promise.all([getStats(), getTags(), listMessages({ limit: 8 })])
    stats.value = s
    tagDist.value = [...t.items].sort((a, b) => b.count - a.count).slice(0, 8)
    recent.value = r.items
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-6xl px-5 py-8 min-[820px]:px-8">
    <header class="mb-7">
      <h1 class="font-display text-2xl font-bold tracking-[0.18em] text-steam min-[480px]:text-3xl">概 览</h1>
      <p class="mt-2 font-mono text-[10.5px] tracking-[0.3em] text-steam-dim">FRONT MATTER</p>
    </header>

    <!-- 骨架 -->
    <div v-if="loading" aria-hidden="true">
      <div class="grid grid-cols-2 gap-px border border-ink-line bg-ink-line sm:grid-cols-4">
        <div v-for="i in 4" :key="i" class="bg-ink-surface p-5">
          <div class="h-2.5 w-12 animate-pulse bg-ink-raised" />
          <div class="mt-3 h-7 w-16 animate-pulse bg-ink-raised" />
        </div>
      </div>
      <div class="mt-8 space-y-3">
        <div v-for="i in 5" :key="i" class="h-4 animate-pulse bg-ink-raised" />
      </div>
    </div>

    <!-- 加载失败：整块错误态 + 重试 -->
    <div v-else-if="loadError" class="flex flex-col items-center gap-3 border-t border-ink-line py-16 text-steam-dim">
      <p class="text-sm">{{ loadError }}</p>
      <Button variant="secondary" size="sm" @click="load">重试</Button>
    </div>

    <template v-else-if="stats">
      <!-- 卷首台账：hairline 网格，不是卡片堆 -->
      <section aria-label="卷首台账">
        <div class="grid grid-cols-2 gap-px border border-ink-line bg-ink-line sm:grid-cols-4">
          <div v-for="cell in ledger" :key="cell.label" class="bg-ink-surface p-4 min-[480px]:p-5">
            <p class="font-mono text-[10px] tracking-[0.24em] text-steam-dim">{{ cell.label }}</p>
            <p class="mt-2 font-display text-2xl font-bold tabular-nums text-steam min-[480px]:text-3xl">
              {{ cell.value }}
            </p>
          </div>
        </div>
        <p v-if="mediaLine" class="mt-2.5 font-mono text-[10px] tracking-[0.1em] text-steam-dim">
          {{ mediaLine }}
        </p>
      </section>

      <!-- 本期封面 + 卷首语 -->
      <section class="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <figure v-if="cover" class="min-w-0 cursor-pointer" @click="selected = cover">
          <div class="relative border border-ink-line bg-ink-surface p-2.5 transition-[border-color,box-shadow] duration-200 hover:border-steam-dim">
            <div class="relative overflow-hidden" :style="{ aspectRatio: coverImg ? coverRatio : '16 / 10' }">
              <img
                v-if="coverImg"
                :src="coverImg"
                :alt="'本期封面 · 素材 #' + cover.id"
                class="h-full w-full object-cover"
                @load="onCoverLoad"
                @error="coverFailed = true"
              />
              <div v-else class="flex h-full w-full items-center justify-center bg-ink-raised text-steam-dim/60">
                <component :is="coverIcon" class="h-10 w-10" />
              </div>
            </div>
          </div>
          <figcaption class="px-1 pt-3">
            <div class="flex items-center gap-2 font-mono text-[10px] tracking-[0.2em] text-steam-dim">
              <span class="shrink-0 font-semibold text-gold">本期封面</span>
              <span class="min-w-0 shrink truncate">{{ coverFigMeta }}</span>
              <span class="flex-1 border-b border-ink-line" aria-hidden="true"></span>
            </div>
            <p class="mt-2 truncate font-display text-lg font-bold text-steam">{{ rowTitle(cover) }}</p>
          </figcaption>
        </figure>
        <div class="min-w-0 self-center">
          <p class="font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">卷首语 · EDITOR'S NOTE</p>
          <p class="mt-4 font-display text-lg leading-[2.1] text-steam min-[480px]:text-xl">{{ intro }}</p>
        </div>
      </section>

      <!-- 印制 · 队列状态：失败必须被看见 -->
      <section class="mt-8" aria-label="队列状态">
        <h2 class="font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">印制 · QUEUE</h2>
        <p v-if="queueIdle" class="mt-3 text-sm text-steam-dim">队列空闲，全部素材均已处理。</p>
        <div v-else class="mt-3 flex flex-wrap gap-x-6 gap-y-2">
          <span
            v-for="row in queueRows"
            :key="row.label"
            class="inline-flex items-baseline gap-2 text-sm"
            :class="row.tone === 'alert' ? 'text-gold' : 'text-steam-dim'"
          >
            {{ row.label }}
            <span class="font-mono tabular-nums" :class="row.tone === 'alert' ? 'font-bold' : 'text-steam'">
              {{ row.value }}
            </span>
          </span>
        </div>
        <p v-if="queueRows.some((r) => r.tone === 'alert')" class="mt-2 text-xs text-steam-dim">
          存在失败任务：已按重试次数处理，可重启进程后观察，或在源群用 /queue 查看明细。
        </p>
      </section>

      <div class="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
        <!-- 类目分布：点线 + 细条，点击直达筛选 -->
        <section aria-label="类目分布">
          <div class="flex items-baseline justify-between">
            <h2 class="font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">类目 · TAGS</h2>
            <RouterLink
              v-if="tagDist.length"
              :to="{ name: 'tags' }"
              class="font-mono text-[10px] text-gold underline underline-offset-4"
            >
              全部类目
            </RouterLink>
          </div>
          <ul v-if="tagDist.length" class="mt-3 space-y-3">
            <li v-for="tag in tagDist" :key="tag.name">
              <RouterLink
                :to="{ name: 'messages', query: { tag: tag.name } }"
                class="group flex cursor-pointer items-baseline gap-2"
              >
                <span class="min-w-0 shrink truncate text-[13.5px] text-steam-dim transition-colors group-hover:text-steam">
                  {{ tag.name }}
                </span>
                <span class="hidden flex-1 border-b border-dotted border-steam-dim/50 lg:block" aria-hidden="true"></span>
                <span class="ml-auto shrink-0 font-mono text-xs tabular-nums text-steam-dim lg:ml-0">{{ tag.count }}</span>
              </RouterLink>
              <div class="mt-1 h-[3px] bg-ink-raised">
                <div class="h-full bg-gold/60 transition-[width]" :style="{ width: `${(tag.count / maxTagCount) * 100}%` }" />
              </div>
            </li>
          </ul>
          <p v-else class="mt-3 text-sm text-steam-dim">还没有类目。</p>
        </section>

        <!-- 近期编目：目录式列表，点击开抽屉 -->
        <section aria-label="近期编目">
          <div class="flex items-baseline justify-between">
            <h2 class="font-mono text-[10px] font-medium tracking-[0.28em] text-steam-dim">近期编目 · RECENT</h2>
            <RouterLink
              v-if="recentList.length"
              :to="{ name: 'messages' }"
              class="font-mono text-[10px] text-gold underline underline-offset-4"
            >
              翻阅全部
            </RouterLink>
          </div>
          <ul v-if="recentList.length" class="mt-2 divide-y divide-ink-line">
            <li v-for="m in recentList" :key="m.material_id">
              <button
                type="button"
                class="flex w-full cursor-pointer items-baseline gap-3 py-2.5 text-left transition-colors hover:text-gold"
                @click="selected = m"
              >
                <span class="w-12 shrink-0 font-mono text-[10px] tracking-[0.1em] text-gold">#{{ m.id }}</span>
                <span class="min-w-0 flex-1 truncate text-sm text-steam">{{ rowTitle(m) }}</span>
                <span class="ml-auto min-w-0 max-w-[45%] shrink truncate font-mono text-[10px] text-steam-dim sm:ml-0">
                  {{ rowChan(m) }} · {{ shortDate(m.created_at) }}
                </span>
              </button>
            </li>
          </ul>
          <div v-else-if="!recent.length" class="mt-3 border border-dashed border-ink-line p-6 text-center text-sm text-steam-dim">
            还没有归档素材，去源群发一条消息试试
          </div>
        </section>
      </div>

      <MessageDrawer :message="selected" @close="selected = null" @update="onDrawerUpdate" />
    </template>
  </div>
</template>
