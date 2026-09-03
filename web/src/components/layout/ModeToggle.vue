<script setup lang="ts">
import { Monitor, Moon, Sun } from 'lucide-vue-next'
import { currentMode, setMode, type Mode } from '@/composables/useTheme'

/*
 * J1 明暗切换回归「点击循环」：浅色 → 深色 → 跟随系统 → 浅色。
 * 按钮图标反映当前选择（system 显示显示器），不再弹菜单。
 * 尺寸/圆角由使用方传入——三处壳（侧栏底 / 移动顶条 / 素材志顶栏）各不相同。
 */
const NEXT: Record<Mode, Mode> = { light: 'dark', dark: 'system', system: 'light' }

const LABELS: Record<Mode, string> = {
  light: '浅色（点击切深色）',
  dark: '深色（点击切跟随系统）',
  system: '跟随系统（点击切浅色）',
}

defineProps<{ buttonClass: string }>()
</script>

<template>
  <button
    type="button"
    class="flex cursor-pointer items-center justify-center text-steam-dim transition active:scale-95 hover:bg-ink-raised hover:text-steam"
    :class="buttonClass"
    :aria-label="LABELS[currentMode]"
    :title="LABELS[currentMode]"
    @click="setMode(NEXT[currentMode])"
  >
    <Monitor v-if="currentMode === 'system'" class="h-4 w-4" />
    <Moon v-else-if="currentMode === 'dark'" class="h-4 w-4" />
    <Sun v-else class="h-4 w-4" />
  </button>
</template>
