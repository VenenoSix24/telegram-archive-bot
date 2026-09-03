<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import Chart from 'chart.js/auto'
import type { ChartConfiguration } from 'chart.js'
import Button from '@/components/ui/Button.vue'
import { getTrend } from '@/lib/api'
import type { TrendPoint } from '@/lib/types'

/** 与后端口径一致：缺省近 30 天（服务端收敛 1..90） */
const DAYS = 30

const state = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const loadError = ref('')
const items = ref<TrendPoint[]>([])
const canvasEl = ref<HTMLCanvasElement | null>(null)

let chart: Chart<'bar'> | null = null
let settleTimer: ReturnType<typeof setTimeout> | undefined
let themeObserver: MutationObserver | undefined

/** token 是「R G B」三元组文本（见 themes/*.css），canvas 里拼 rgb(... / alpha) */
function tint(name: string, alpha = 1): string {
  const triplet = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return `rgb(${triplet || '120 120 120'} / ${alpha})`
}

/** 用当前主题 token 画图；animate=false 用于主题重绘，避免每次重播入场动画 */
function paint(animate: boolean) {
  if (!canvasEl.value || items.value.length === 0) return
  chart?.destroy()
  const family = getComputedStyle(document.body).fontFamily
  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: items.value.map((p) => p.date),
      datasets: [
        {
          label: '归档',
          data: items.value.map((p) => p.count),
          backgroundColor: tint('--gold', 0.78),
          hoverBackgroundColor: tint('--gold'),
          maxBarThickness: 16,
          categoryPercentage: 0.9,
          barPercentage: 0.9,
          borderRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: animate ? { duration: 450, easing: 'easeOutQuart' } : false,
      layout: { padding: { top: 8 } },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          // --steam 兼作反白底：浅色模式=深底白字，暗色模式=浅底深字
          backgroundColor: tint('--steam', 0.94),
          titleColor: tint('--ink-surface'),
          bodyColor: tint('--ink-surface'),
          titleFont: { family },
          bodyFont: { family },
          padding: 10,
          cornerRadius: 8,
          displayColors: false,
          callbacks: {
            label: (item) => `归档 ${item.parsed.y} 件`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: tint('--steam-dim'),
            font: { family, size: 10 },
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 10,
            callback: (_value, index, ticks) => {
              // 轴标签压成 M/D；完整日期留在 tooltip 标题（即分类 label 本身）
              const label = ticks[index]?.label ?? ''
              const text = Array.isArray(label) ? label.join(' ') : label
              return text.slice(5).replace('-', '/')
            },
          },
        },
        y: {
          beginAtZero: true,
          border: { display: false },
          grid: { color: tint('--ink-line') },
          ticks: {
            color: tint('--steam-dim'),
            font: { family, size: 10 },
            maxTicksLimit: 5,
            precision: 0,
          },
        },
      },
    },
  }
  chart = new Chart(canvasEl.value, config)
}

/** data-* 属性先变、主题 CSS（动态 import）后到：立即重绘一次，400ms 后再补一次等 token 落定 */
function scheduleRepaint() {
  requestAnimationFrame(() => paint(false))
  clearTimeout(settleTimer)
  settleTimer = setTimeout(() => paint(false), 400)
}

async function load() {
  state.value = 'loading'
  try {
    const body = await getTrend(DAYS)
    items.value = body.items
    state.value = items.value.some((p) => p.count > 0) ? 'ready' : 'empty'
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '数据加载失败'
    state.value = 'error'
    return
  }
  if (state.value === 'ready') {
    await nextTick()
    paint(true)
  }
}

onMounted(() => {
  // 观察根节点 data-theme/data-mode/data-accent：主题、配色、明暗（含 system
  // 跟随系统翻转——它不经过任何响应式 ref，watch 导出 computed 会漏掉这种情况）
  themeObserver = new MutationObserver(scheduleRepaint)
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'data-mode', 'data-accent'],
  })
  void load()
})

onBeforeUnmount(() => {
  themeObserver?.disconnect()
  clearTimeout(settleTimer)
  chart?.destroy()
  chart = null
})
</script>

<template>
  <section class="overflow-hidden rounded-xl border border-ink-line bg-ink-surface shadow-sm" aria-label="归档趋势">
    <div class="flex items-center border-b border-ink-line px-4 py-2.5 text-[13px] font-semibold text-steam">
      近 30 天归档趋势
      <span class="ml-auto font-mono text-[10px] font-normal tracking-[0.14em] text-steam-dim/60">TREND</span>
    </div>

    <!-- 画布容器定高：chart.js responsive 依赖父级尺寸撑开 -->
    <div v-if="state === 'ready'" class="relative h-52 px-4 pb-3 pt-1">
      <canvas ref="canvasEl" />
    </div>
    <div v-else-if="state === 'loading'" class="m-4 h-44 animate-pulse rounded-lg bg-ink-raised" aria-hidden="true" />
    <p v-else-if="state === 'empty'" class="px-4 py-10 text-center text-[13px] text-steam-dim">
      近 30 天还没有归档记录。
    </p>
    <div v-else class="flex flex-col items-center gap-3 px-4 py-8 text-steam-dim">
      <p class="text-sm">{{ loadError || '数据加载失败' }}</p>
      <Button variant="secondary" size="sm" @click="load">重试</Button>
    </div>
  </section>
</template>
