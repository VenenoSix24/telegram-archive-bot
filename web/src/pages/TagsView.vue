<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Loader2, Tag as TagIcon } from 'lucide-vue-next'
import { getTags } from '@/lib/api'
import type { TagCount } from '@/lib/types'

const counts = ref<TagCount[] | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    counts.value = (await getTags()).items
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="mx-auto max-w-6xl px-6 py-8">
    <header class="mb-6">
      <h1 class="font-display text-3xl font-semibold tracking-tight">标签</h1>
      <p class="mt-1 text-sm text-steam-dim">所有归档消息使用的标签，点标签查看对应素材</p>
    </header>

    <div v-if="loading" class="flex items-center gap-2 text-steam-dim">
      <Loader2 class="h-4 w-4 animate-spin" /> 载入中…
    </div>

    <div v-else-if="counts?.length" class="flex flex-wrap gap-2">
      <RouterLink
        v-for="c in counts"
        :key="c.name"
        :to="{ name: 'messages', query: { tag: c.name } }"
        class="inline-flex items-center gap-1.5 rounded-full border border-ink-line bg-ink-surface px-3 py-1.5 text-sm transition-colors hover:border-gold hover:text-gold"
      >
        <TagIcon class="h-3.5 w-3.5" />
        {{ c.name }}
        <span class="font-mono text-xs text-steam-dim">{{ c.count }}</span>
      </RouterLink>
    </div>

    <p v-else class="text-sm text-steam-dim">还没有标签</p>
  </div>
</template>