<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CircleDot, ListFilter, Send, Star, Tags as TagsIcon } from 'lucide-vue-next'
import { useCatalogFilters } from '@/composables/useCatalogFilters'
import { useVocab, typeLabel as vocabTypeLabel } from '@/lib/vocab'

/*
 * 标准后台左栏的筛选树：当前筛选 / 来源与目标 / 标签 / 评分 / 状态。
 * 分组标题带图标徽章，子项沿竖向导轨缩进（分组层级一眼可辨）。
 * 与素材页共用 useCatalogFilters 状态；跨页点选时先改筛选再跳路由。
 */
const emit = defineEmits<{ navigate: [] }>()

const {
  q,
  mediaType,
  rating,
  statusFilter,
  tagFilter,
  targetFilter,
  tagIndex,
  targets,
  isFilterActive,
  loadStats,
  resetFilters,
  toggleMedia,
  toggleRating,
  toggleStatus,
  toggleTarget,
  toggleTag,
  removeTag,
} = useCatalogFilters()
const L = useVocab()
const route = useRoute()
const router = useRouter()

function goMessages(query: Record<string, string | string[]> = {}) {
  if (route.name !== 'messages') {
    void router.push({ name: 'messages', query })
  }
  emit('navigate')
}

function pickTarget(id: number) {
  toggleTarget(id)
  goMessages()
}
function clearTarget() {
  if (targetFilter.value !== '') {
    toggleTarget(targetFilter.value)
    goMessages()
  } else {
    emit('navigate')
  }
}
function pickTag(name: string) {
  toggleTag(name)
  goMessages(tagFilter.value.length ? { tag: tagFilter.value } : {})
}
function pickRating(value: number) {
  toggleRating(value)
  goMessages()
}
function pickStatus(value: 'active' | 'deleted' | 'all') {
  toggleStatus(value)
  goMessages()
}

const ratingOptions = [5, 4, 3, 2, 1] as const
const statusOptions: { value: 'active' | 'deleted' | 'all'; label: () => string; dot: string }[] = [
  { value: 'active', label: () => L.value.statusActive, dot: '#10b981' },
  { value: 'deleted', label: () => '已删除', dot: '#ef4444' },
  { value: 'all', label: () => '全部', dot: '#a1a1aa' },
]

/* 来源行的稳定色点：按 chat_id 取调色板，同一来源永远同色 */
const DOT_COLORS = ['#ef4444', '#f97316', '#eab308', '#10b981', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899']
function dotColor(id: number) {
  return DOT_COLORS[Math.abs(id) % DOT_COLORS.length]
}

/** 顶部「当前筛选」：逐项可移除，另有一键清空（与搜索框旁的清除按钮等价） */
const activeFilters = computed(() => {
  const items: { label: string; clear: () => void }[] = []
  if (q.value) {
    const kw = q.value
    items.push({ label: `“${kw}”`, clear: () => (q.value = '') })
  }
  if (mediaType.value) {
    const mt = mediaType.value
    items.push({
      label: vocabTypeLabel(L.value, mt),
      clear: () => toggleMedia(mt),
    })
  }
  if (rating.value !== '') {
    const r = rating.value
    items.push({
      label: r === 0 ? L.value.unrated : L.value.ratingHint[r - 1],
      clear: () => toggleRating(r),
    })
  }
  for (const t of tagFilter.value) items.push({ label: `#${t}`, clear: () => removeTag(t) })
  if (targetFilter.value !== '') {
    const tid = targetFilter.value
    const t = targets.value.find((x) => x.chat_id === tid)
    items.push({ label: t?.name || `目标 ${tid}`, clear: () => toggleTarget(tid) })
  }
  if (statusFilter.value !== 'active') {
    const s = statusFilter.value
    items.push({
      label: s === 'deleted' ? '已删除' : '全部',
      clear: () => toggleStatus(s),
    })
  }
  return items
})

onMounted(loadStats)
</script>

<template>
  <div class="px-2 pb-4">
    <!-- 当前筛选：激活时可逐项移除 / 一键清空 -->
    <section v-if="isFilterActive">
      <h3 class="flex items-center gap-2 px-2 pb-1.5 pt-4 text-[11px] font-medium text-steam-dim">
        <span class="grid size-5 shrink-0 place-items-center rounded-md bg-gold/10 text-gold">
          <ListFilter class="size-3" />
        </span>
        当前筛选
      </h3>
      <div class="ml-4 border-l border-ink-line pl-3">
        <div class="flex flex-wrap gap-1.5 py-1 pl-1 pr-1">
          <span
            v-for="(f, i) in activeFilters"
            :key="f.label + i"
            class="inline-flex items-center gap-1 rounded-full border border-gold/40 bg-gold/10 py-0.5 pl-2 pr-1 text-[11px] text-gold"
          >
            {{ f.label }}
            <button
              type="button"
              class="grid h-4 w-4 cursor-pointer place-items-center rounded-full transition-opacity hover:opacity-60"
              :aria-label="`移除筛选 ${f.label}`"
              @click="f.clear()"
            >
              <svg viewBox="0 0 24 24" class="h-2.5 w-2.5" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m6 6 12 12M18 6 6 18" /></svg>
            </button>
          </span>
          <button
            type="button"
            class="inline-flex cursor-pointer items-center rounded-full px-2 py-0.5 text-[11px] text-steam-dim underline underline-offset-2 transition-colors hover:text-steam"
            @click="resetFilters(); goMessages()"
          >
            清空
          </button>
        </div>
      </div>
    </section>

    <!-- 来源与目标 -->
    <section v-if="targets.length">
      <h3 class="flex items-center gap-2 px-2 pb-1.5 pt-4 text-[11px] font-medium text-steam-dim">
        <span class="grid size-5 shrink-0 place-items-center rounded-md bg-gold/10 text-gold">
          <Send class="size-3" />
        </span>
        来源与目标
      </h3>
      <div class="ml-4 border-l border-ink-line pl-3">
        <button
          type="button"
          class="flex h-8 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors"
          :class="targetFilter === '' ? 'bg-gold/10 font-medium text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
          :aria-pressed="targetFilter === ''"
          @click="clearTarget"
        >
          <!-- 全部来源：白色圆点（中性语义），浅色面板上加描边保证可辨 -->
          <span class="h-2 w-2 shrink-0 rounded-full bg-white ring-1 ring-ink-line"></span>
          全部来源
        </button>
        <button
          v-for="t in targets"
          :key="t.chat_id"
          type="button"
          class="flex h-8 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors"
          :class="targetFilter === t.chat_id ? 'bg-gold/10 font-medium text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
          :aria-pressed="targetFilter === t.chat_id"
          @click="pickTarget(t.chat_id)"
        >
          <span class="h-2 w-2 shrink-0 rounded-full" :style="{ background: dotColor(t.chat_id) }"></span>
          <span class="min-w-0 truncate">{{ t.name || `目标 ${t.chat_id}` }}</span>
          <span class="ml-auto shrink-0 font-mono text-[10.5px] tabular-nums text-steam-dim/70">{{ t.count }}</span>
        </button>
      </div>
    </section>

    <!-- 标签（多选交集） -->
    <section v-if="tagIndex.length">
      <h3 class="flex items-center gap-2 px-2 pb-1.5 pt-4 text-[11px] font-medium text-steam-dim">
        <span class="grid size-5 shrink-0 place-items-center rounded-md bg-gold/10 text-gold">
          <TagsIcon class="size-3" />
        </span>
        {{ L.tag }}
      </h3>
      <div class="ml-4 border-l border-ink-line pl-3">
        <button
          v-for="tag in tagIndex"
          :key="tag.name"
          type="button"
          class="flex h-8 w-full cursor-pointer items-center gap-1.5 rounded-md px-2 text-left text-[13px] transition-colors"
          :class="tagFilter.includes(tag.name) ? 'bg-gold/10 font-medium text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
          :aria-pressed="tagFilter.includes(tag.name)"
          @click="pickTag(tag.name)"
        >
          <span class="min-w-0 truncate">#{{ tag.name }}</span>
          <span
            class="ml-auto shrink-0 rounded-full px-1.5 font-mono text-[10px] tabular-nums"
            :class="tagFilter.includes(tag.name) ? 'bg-gold/20 text-gold' : 'bg-ink-raised text-steam-dim/80'"
          >
            {{ tag.count }}
          </span>
        </button>
      </div>
    </section>

    <!-- 评分 -->
    <section>
      <h3 class="flex items-center gap-2 px-2 pb-1.5 pt-4 text-[11px] font-medium text-steam-dim">
        <span class="grid size-5 shrink-0 place-items-center rounded-md bg-gold/10 text-gold">
          <Star class="size-3" />
        </span>
        {{ L.rating }}
      </h3>
      <div class="ml-4 border-l border-ink-line pl-3">
        <button
          v-for="n in ratingOptions"
          :key="n"
          type="button"
          class="flex h-8 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors"
          :class="rating === n ? 'bg-gold/10 font-medium text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
          :aria-pressed="rating === n"
          @click="pickRating(n)"
        >
          <Star class="h-3.5 w-3.5 shrink-0" :class="rating === n ? 'fill-gold/30' : ''" />
          {{ L.ratingHint[n - 1] }}
        </button>
        <button
          type="button"
          class="flex h-8 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors"
          :class="rating === 0 ? 'bg-gold/10 font-medium text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
          :aria-pressed="rating === 0"
          @click="pickRating(0)"
        >
          <Star class="h-3.5 w-3.5 shrink-0" />
          {{ L.unrated }}
        </button>
      </div>
    </section>

    <!-- 状态 -->
    <section>
      <h3 class="flex items-center gap-2 px-2 pb-1.5 pt-4 text-[11px] font-medium text-steam-dim">
        <span class="grid size-5 shrink-0 place-items-center rounded-md bg-gold/10 text-gold">
          <CircleDot class="size-3" />
        </span>
        状态
      </h3>
      <div class="ml-4 border-l border-ink-line pl-3 pb-1">
        <button
          v-for="op in statusOptions"
          :key="op.value"
          type="button"
          class="flex h-8 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-left text-[13px] transition-colors"
          :class="statusFilter === op.value ? 'bg-gold/10 font-medium text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
          :aria-pressed="statusFilter === op.value"
          @click="pickStatus(op.value)"
        >
          <span class="h-2 w-2 shrink-0 rounded-full" :style="{ background: op.dot }"></span>
          {{ op.label() }}
        </button>
      </div>
    </section>
  </div>
</template>
