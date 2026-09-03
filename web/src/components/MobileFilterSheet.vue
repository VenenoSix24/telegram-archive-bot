<script setup lang="ts">
import { RotateCcw, Search, X } from 'lucide-vue-next'
import { useCatalogFilters } from '@/composables/useCatalogFilters'
import { useVocab } from '@/lib/vocab'
import SidebarCatalog from '@/components/layout/SidebarCatalog.vue'

/*
 * 简约风移动端筛选面板（K4 二次重写）：常驻 DOM + 纯 class 切换的上滑面板，
 * 不再走 v-if 挂载/卸载——Transition 的挂载帧与离场类竞争正是「闪一下」的
 * 根源（参照窄屏详情栏 anim-pane 的既定模式）。样式在 style.css 的
 * .sheet-scrim / .sheet-panel：关闭态延迟翻转 visibility，滑出跑完才真隐藏。
 * 筛选状态来自 useCatalogFilters 单例，与页面、左栏树天然同源。
 */
defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const { q, isFilterActive, resetFilters } = useCatalogFilters()
const L = useVocab()

function reset() {
  resetFilters()
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      class="sheet-scrim fixed inset-0 z-40 bg-ink-bg/50 backdrop-blur-[2px] lg:hidden"
      :class="open && 'sheet-scrim--open'"
      aria-hidden="true"
      @click="emit('close')"
    />
    <div
      class="sheet-panel fixed inset-x-0 bottom-0 z-50 max-h-[72vh] overflow-y-auto overscroll-contain rounded-t-2xl border-t border-ink-line bg-ink-surface pb-[calc(env(safe-area-inset-bottom)+0.75rem)] shadow-2xl lg:hidden"
      :class="open && 'sheet-panel--open'"
      role="dialog"
      aria-modal="true"
      aria-label="筛选归档"
      :aria-hidden="!open"
    >
      <div class="sticky top-0 z-10 flex items-center gap-1 border-b border-ink-line bg-ink-surface/95 px-3 py-2 backdrop-blur">
        <h2 class="text-[14px] font-semibold text-steam">筛选</h2>
        <button
          v-if="isFilterActive"
          type="button"
          class="ml-auto inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-ink-line px-2.5 text-xs text-steam-dim transition-colors hover:border-gold/50 hover:text-gold"
          @click="reset"
        >
          <RotateCcw class="h-3 w-3" /> {{ L.reset }}
        </button>
        <button
          type="button"
          class="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-steam-dim transition active:scale-95 hover:bg-ink-raised hover:text-steam"
          :class="!isFilterActive && 'ml-auto'"
          aria-label="收起筛选"
          @click="emit('close')"
        >
          <X class="h-4 w-4" />
        </button>
      </div>
      <label
        class="mx-3 mt-3 flex h-9 items-center gap-2 rounded-lg border border-ink-line bg-ink-raised px-2.5 transition-[border-color,box-shadow,background-color] [transition-duration:var(--motion-fast)] [transition-timing-function:var(--ease-standard)] focus-within:border-gold focus-within:bg-ink-surface focus-within:ring-2 focus-within:ring-gold/15"
      >
        <Search class="h-4 w-4 shrink-0 text-steam-dim" />
        <input
          v-model="q"
          type="search"
          :placeholder="L.searchPlaceholder"
          aria-label="检索归档"
          class="w-full min-w-0 bg-transparent text-[13px] text-steam focus:outline-none placeholder:text-steam-dim/60"
        />
      </label>
      <SidebarCatalog @navigate="emit('close')" />
    </div>
  </Teleport>
</template>
