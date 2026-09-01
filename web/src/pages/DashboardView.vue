<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Film, Image as ImageIcon, FileText, Loader2, Mic, Music, Sticker } from 'lucide-vue-next'
import { getStats, listMessages } from '@/lib/api'
import type { Message, Stats } from '@/lib/types'
import MessageCard from '@/components/MessageCard.vue'
import MessageDrawer from '@/components/MessageDrawer.vue'
import Button from '@/components/ui/Button.vue'

const stats = ref<Stats | null>(null)
const recent = ref<Message[]>([])
const loading = ref(true)
const loadError = ref('')
const selected = ref<Message | null>(null)

const typeMeta: Record<string, { label: string; icon: unknown }> = {
  video: { label: '视频', icon: Film },
  photo: { label: '图片', icon: ImageIcon },
  document: { label: '文件', icon: FileText },
  audio: { label: '音频', icon: Music },
  voice: { label: '语音', icon: Mic },
  sticker: { label: '贴纸', icon: Sticker },
  text: { label: '文本', icon: FileText },
}

function statsOf(type: string) {
  return stats.value?.messages.by_type[type] ?? 0
}

// 有量的类型才展示，未知类型兜底到文件图标
const shownTypes = computed(() => {
  const keys = new Set([
    ...Object.keys(typeMeta),
    ...Object.keys(stats.value?.messages.by_type ?? {}),
  ])
  return [...keys].filter((type) => statsOf(type) > 0)
})

function onDrawerUpdate(updated: Message) {
  recent.value = recent.value.map((m) => (m.material_id === updated.material_id ? updated : m))
  if (selected.value?.material_id === updated.material_id) selected.value = updated
}

async function load() {
  loadError.value = ''
  try {
    stats.value = await getStats()
    recent.value = (await listMessages({ limit: 8 })).items
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-6xl px-6 py-8">
    <header class="mb-8">
      <h1 class="font-display text-3xl font-semibold tracking-tight">概览</h1>
      <p class="mt-1 text-sm text-steam-dim">你的 Telegram 归档库</p>
    </header>

    <div v-if="loading" class="flex items-center gap-2 text-steam-dim">
      <Loader2 class="h-4 w-4 animate-spin" /> 载入中…
    </div>

    <!-- 加载失败：整块错误态 + 重试，不再静默空白 -->
    <div v-else-if="loadError" class="flex flex-col items-center gap-3 py-16 text-steam-dim">
      <p class="text-sm">{{ loadError }}</p>
      <Button variant="secondary" size="sm" @click="load">重试</Button>
    </div>

    <template v-else-if="stats">
      <!-- 统计卡片：数据优先，金色只给「评级」以外需要强调的数字？这里保持中性 -->
      <section class="grid grid-cols-2 gap-3 md:grid-cols-4" aria-label="统计">
        <div class="rounded-card border border-ink-line bg-ink-surface p-4">
          <p class="text-xs text-steam-dim">总消息</p>
          <p class="mt-1 font-display text-3xl font-semibold tabular-nums">{{ stats.messages.total }}</p>
        </div>
        <div class="rounded-card border border-ink-line bg-ink-surface p-4">
          <p class="text-xs text-steam-dim">已归档</p>
          <p class="mt-1 font-display text-3xl font-semibold tabular-nums">{{ stats.messages.archived }}</p>
        </div>
        <div class="rounded-card border border-ink-line bg-ink-surface p-4">
          <p class="text-xs text-steam-dim">来源群</p>
          <p class="mt-1 font-display text-3xl font-semibold tabular-nums">{{ stats.messages.sources }}</p>
        </div>
        <div class="rounded-card border border-ink-line bg-ink-surface p-4">
          <p class="text-xs text-steam-dim">标签</p>
          <p class="mt-1 font-display text-3xl font-semibold tabular-nums">
            {{ stats.tags.with_messages }}<span class="text-lg text-steam-dim">/{{ stats.tags.total }}</span>
          </p>
        </div>
      </section>

      <!-- 媒体类型占比 -->
      <section class="mt-6 rounded-card border border-ink-line bg-ink-surface p-4">
        <h2 class="mb-3 text-sm font-medium text-steam">媒体构成</h2>
        <div class="flex flex-wrap gap-4 text-sm">
          <span v-for="t in shownTypes" :key="t" class="inline-flex items-center gap-1.5 text-steam-dim">
            <component :is="typeMeta[t]?.icon ?? FileText" class="h-4 w-4" />
            {{ typeMeta[t]?.label ?? t }}
            <span class="font-mono tabular-nums text-steam">{{ statsOf(t) }}</span>
          </span>
        </div>
        <div v-if="stats.queue" class="mt-4 border-t border-ink-line pt-3 text-sm text-steam-dim">
          队列：<span class="font-mono text-steam">{{ stats.queue.pending }}</span> 待发 ·
          <span class="font-mono text-steam">{{ stats.queue.failed }}</span> 失败
        </div>
      </section>

      <!-- 最近归档：签名元素大卡片流 -->
      <section class="mt-8">
        <div class="mb-3 flex items-baseline justify-between">
          <h2 class="text-sm font-medium text-steam">最近归档</h2>
          <RouterLink :to="{ name: 'messages' }" class="text-xs text-gold hover:underline">全部素材 →</RouterLink>
        </div>
        <div v-if="recent.length" class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <MessageCard
            v-for="m in recent"
            :key="m.material_id"
            :message="m"
            @open="selected = m"
          />
        </div>
        <div v-else class="rounded-card border border-dashed border-ink-line p-8 text-center text-sm text-steam-dim">
          还没有归档素材，去源群发一条消息试试
        </div>
        <MessageDrawer :message="selected" @close="selected = null" @update="onDrawerUpdate" />
      </section>
    </template>
  </div>
</template>