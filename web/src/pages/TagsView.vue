<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getTags } from '@/lib/api'
import type { TagCount } from '@/lib/types'
import Button from '@/components/ui/Button.vue'

const counts = ref<TagCount[] | null>(null)
const loading = ref(true)
const loadError = ref('')

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
  <div class="mx-auto max-w-3xl px-5 py-8 min-[820px]:px-8">
    <header class="mb-7 flex items-end justify-between gap-4">
      <div>
        <h1 class="font-display text-2xl font-bold tracking-[0.18em] text-steam min-[480px]:text-3xl">类目</h1>
        <p class="mt-2 font-mono text-[10.5px] tracking-[0.3em] text-steam-dim">INDEX OF TAGS</p>
      </div>
      <p v-if="counts" class="pb-1 font-mono text-[11px] text-steam-dim">共 {{ counts.length }} 个</p>
    </header>

    <div v-if="loading" class="space-y-3" aria-hidden="true">
      <div v-for="i in 6" :key="i" class="h-4 animate-pulse bg-ink-raised" />
    </div>

    <!-- 加载失败不能伪装成空态 -->
    <div v-else-if="loadError" class="flex flex-col items-center gap-3 border-t border-ink-line py-16 text-steam-dim">
      <p class="text-sm">{{ loadError }}</p>
      <Button variant="secondary" size="sm" @click="load">重试</Button>
    </div>

    <!-- 总目：与素材页目录同构的点线条目 -->
    <ul v-else-if="counts?.length" class="divide-y divide-ink-line">
      <li v-for="c in counts" :key="c.name">
        <RouterLink
          :to="{ name: 'messages', query: { tag: c.name } }"
          class="group flex cursor-pointer items-baseline gap-2.5 py-3"
        >
          <span class="shrink-0 text-[15px] text-steam transition-colors group-hover:text-gold">{{ c.name }}</span>
          <span class="hidden flex-1 border-b border-dotted border-steam-dim/50 sm:block" aria-hidden="true"></span>
          <span class="ml-auto shrink-0 font-mono text-sm tabular-nums text-steam-dim transition-colors group-hover:text-gold sm:ml-0">
            {{ c.count }}
          </span>
        </RouterLink>
      </li>
    </ul>

    <div v-else class="border-t border-ink-line py-16 text-center">
      <p class="empty-title font-display text-xl text-steam">尚无类目</p>
      <p class="mt-2 text-[13px] text-steam-dim">在抽屉里给素材加注标签后，会汇总在这里。</p>
    </div>
  </div>
</template>
