<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Film, Image as ImageIcon, FileText, Loader2 } from 'lucide-vue-next'
import { getStats, listMessages } from '@/lib/api'
import type { Message, Stats } from '@/lib/types'
import MessageCard from '@/components/MessageCard.vue'

const stats = ref<Stats | null>(null)
const recent = ref<Message[]>([])
const loading = ref(true)

const typeOrder = ['video', 'photo', 'text']

function statsOf(type: string) {
  return stats.value?.messages.by_type[type] ?? 0
}

onMounted(async () => {
  try {
    stats.value = await getStats()
    recent.value = (await listMessages({ limit: 8 })).items
  } finally {
    loading.value = false
  }
})
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
          <span v-for="t in typeOrder" :key="t" class="inline-flex items-center gap-1.5 text-steam-dim">
            <component :is="t === 'video' ? Film : t === 'photo' ? ImageIcon : FileText" class="h-4 w-4" />
            {{ t === 'video' ? '视频' : t === 'photo' ? '图片' : '文本' }}
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
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MessageCard v-for="m in recent" :key="m.id" :message="m" />
        </div>
      </section>
    </template>
  </div>
</template>