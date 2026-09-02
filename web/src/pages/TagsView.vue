<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getTags } from '@/lib/api'
import type { TagCount } from '@/lib/types'
import Button from '@/components/ui/Button.vue'

const counts = ref<TagCount[] | null>(null)
const loading = ref(true)
const loadError = ref('')

/* 按使用次数降序：热门类目天然排前面，扫一眼即得 */
const sorted = computed(() => [...(counts.value ?? [])].sort((a, b) => b.count - a.count))

async function load() {
  loadError.value = ''
  try {
    counts.value = (await getTags()).items
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-4xl px-5 py-8 min-[820px]:px-8">
    <header class="mb-7 flex items-end justify-between gap-4">
      <div>
        <h1 class="font-display text-2xl font-bold tracking-[0.18em] text-steam min-[480px]:text-3xl">类 目</h1>
        <p class="mt-2 font-mono text-[10.5px] tracking-[0.3em] text-steam-dim">INDEX OF TAGS</p>
      </div>
      <p v-if="counts" class="pb-1 font-mono text-[11px] text-steam-dim">共 {{ counts.length }} 个 · 按使用排序</p>
    </header>

    <div v-if="loading" class="flex flex-wrap gap-2" aria-hidden="true">
      <div v-for="i in 10" :key="i" class="h-8 w-20 animate-pulse rounded-full bg-ink-raised" />
    </div>

    <!-- 加载失败不能伪装成空态 -->
    <div v-else-if="loadError" class="flex flex-col items-center gap-3 border-t border-ink-line py-16 text-steam-dim">
      <p class="text-sm">{{ loadError }}</p>
      <Button variant="secondary" size="sm" @click="load">重试</Button>
    </div>

    <!-- 热度 chip 云：名称 + 计数，点击直达该类目图录 -->
    <div v-else-if="sorted.length" class="flex flex-wrap gap-2">
      <RouterLink
        v-for="c in sorted"
        :key="c.name"
        :to="{ name: 'messages', query: { tag: c.name } }"
        class="inline-flex items-baseline gap-1.5 rounded-full border border-ink-line bg-ink-surface px-3.5 py-1.5 transition-colors hover:border-gold hover:text-gold"
      >
        <span class="text-sm">{{ c.name }}</span>
        <span class="font-mono text-xs tabular-nums text-steam-dim">{{ c.count }}</span>
      </RouterLink>
    </div>

    <div v-else class="border-t border-ink-line py-16 text-center">
      <p class="empty-title font-display text-xl text-steam">尚无类目</p>
      <p class="mt-2 text-[13px] text-steam-dim">在抽屉里给素材加注标签后，会汇总在这里。</p>
    </div>
  </div>
</template>
