<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getTags } from '@/lib/api'
import type { TagCount } from '@/lib/types'
import Button from '@/components/ui/Button.vue'
import { isVault, useVocab } from '@/lib/vocab'

const counts = ref<TagCount[] | null>(null)
const loading = ref(true)
const loadError = ref('')
const keyword = ref('')
const L = useVocab()

/* 按使用次数降序：热门标签天然排前面，扫一眼即得；关键词本地过滤 */
const sorted = computed(() => [...(counts.value ?? [])].sort((a, b) => b.count - a.count))
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return kw ? sorted.value.filter((t) => t.name.toLowerCase().includes(kw)) : sorted.value
})
const maxCount = computed(() => Math.max(1, ...filtered.value.map((t) => t.count)))

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
  <!-- 标准后台：管理表格（筛选职责在侧栏树；关键词本地过滤） -->
  <div v-if="isVault" class="mx-auto max-w-6xl px-5 pb-24 pt-6 lg:pb-6">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <h1 class="text-[17px] font-semibold text-steam">{{ L.tag }}</h1>
      <span v-if="counts" class="font-mono text-[10.5px] tabular-nums text-steam-dim">
        {{ filtered.length }} / {{ counts.length }} 个
      </span>
      <!-- 手机端与下方标签卡同宽（max-w-xs 只在 sm+ 生效） -->
      <label class="ml-auto flex h-9 w-full max-w-full items-center gap-2 rounded-lg border border-ink-line bg-ink-surface px-2.5 transition-colors focus-within:border-gold sm:max-w-xs">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="shrink-0 text-steam-dim"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
        <input
          v-model="keyword"
          type="search"
          placeholder="搜索标签…"
          aria-label="搜索标签"
          class="w-full min-w-0 bg-transparent text-[13px] text-steam outline-none placeholder:text-steam-dim/60"
        />
      </label>
    </div>

    <div v-if="loading" class="space-y-2" aria-hidden="true">
      <div v-for="i in 6" :key="i" class="h-11 animate-pulse rounded-xl border border-ink-line bg-ink-surface" />
    </div>

    <div v-else-if="loadError" class="flex flex-col items-center gap-3 rounded-xl border border-ink-line bg-ink-surface py-16 text-steam-dim">
      <p class="text-sm">{{ loadError }}</p>
      <Button variant="secondary" size="sm" @click="load">重试</Button>
    </div>

    <div v-else-if="filtered.length" class="overflow-hidden rounded-xl border border-ink-line bg-ink-surface shadow-sm">
      <div class="flex items-center border-b border-ink-line px-4 py-2 font-mono text-[10px] tracking-[0.14em] text-steam-dim/70">
        <span class="flex-1">{{ L.tag }}</span>
        <span class="w-14 text-right">条目</span>
        <span class="ml-6 hidden w-32 sm:block">热度</span>
      </div>
      <RouterLink
        v-for="c in filtered"
        :key="c.name"
        :to="{ name: 'messages', query: { tag: c.name } }"
        class="flex cursor-pointer items-center border-b border-ink-line/60 px-4 py-2.5 transition-colors last:border-b-0 hover:bg-ink-raised/60"
      >
        <span class="min-w-0 flex-1 truncate text-[13px] font-medium text-steam">#{{ c.name }}</span>
        <span class="w-14 text-right font-mono text-xs tabular-nums text-steam-dim">{{ c.count }}</span>
        <span class="ml-6 hidden h-1.5 w-32 overflow-hidden rounded-full bg-ink-raised sm:block">
          <span class="block h-full rounded-full bg-gold/70" :style="{ width: `${(c.count / maxCount) * 100}%` }" />
        </span>
      </RouterLink>
    </div>

    <div v-else-if="counts && counts.length" class="rounded-xl border border-ink-line bg-ink-surface py-16 text-center">
      <p class="text-[15px] font-semibold text-steam">没有匹配的{{ L.tag }}</p>
      <p class="mt-2 text-[13px] text-steam-dim">换个关键词试试。</p>
    </div>

    <div v-else class="rounded-xl border border-ink-line bg-ink-surface py-16 text-center">
      <p class="text-[15px] font-semibold text-steam">还没有{{ L.tag }}</p>
      <p class="mt-2 text-[13px] text-steam-dim">在详情里给素材加{{ L.tag }}后，会汇总在这里。</p>
    </div>
  </div>

  <!-- 素材志：热度 chip 云 -->
  <div v-else class="mx-auto max-w-4xl px-5 py-8 min-[820px]:px-8">
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
