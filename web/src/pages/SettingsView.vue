<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { getStats } from '@/lib/api'
import type { Stats } from '@/lib/types'

const stats = ref<Stats | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    stats.value = await getStats()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="mx-auto max-w-6xl px-6 py-8">
    <header class="mb-6">
      <h1 class="font-display text-3xl font-semibold tracking-tight">设置</h1>
      <p class="mt-1 text-sm text-steam-dim">运行状态（编辑配置见 config.yaml / .env）</p>
    </header>

    <div v-if="loading" class="flex items-center gap-2 text-steam-dim">
      <Loader2 class="h-4 w-4 animate-spin" /> 载入中…
    </div>

    <div v-else-if="stats" class="grid max-w-2xl gap-4">
      <section class="rounded-card border border-ink-line bg-ink-surface p-4">
        <h2 class="mb-2 text-sm font-medium text-steam">消息</h2>
        <dl class="grid grid-cols-2 gap-y-2 text-sm">
          <dt class="text-steam-dim">总数 / 已归档</dt>
          <dd class="font-mono text-steam">{{ stats.messages.total }} / {{ stats.messages.archived }}</dd>
          <dt class="text-steam-dim">来源群</dt>
          <dd class="font-mono text-steam">{{ stats.messages.sources }}</dd>
          <dt class="text-steam-dim">队列待发 / 失败</dt>
          <dd class="font-mono text-steam">{{ stats.queue.pending }} / {{ stats.queue.failed }}</dd>
        </dl>
        <p class="mt-3 border-t border-ink-line pt-3 text-xs text-steam-dim/70">
          源群 / 目标频道 / 管理员 / 限速等配置项在 <code class="font-mono">config.yaml</code> 与
          <code class="font-mono">.env</code> 中维护（Web 编辑将在后续版本提供）。
        </p>
      </section>
    </div>
  </div>
</template>