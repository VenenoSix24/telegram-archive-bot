<script setup lang="ts">
import { Check, Monitor, Moon, Sun } from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { currentMode, renderedDark, setMode, type Mode } from '@/composables/useTheme'

/*
 * F4 明暗三态菜单：浅色 / 深色 / 跟随系统。
 * 按钮图标反映「已选状态」而非解析结果（system 显示显示器），
 * 菜单里标注 system 当前解析到的明暗，避免「跟随系统却不知此刻是什么」。
 * 按钮与弹出层定位类由使用方传入——三处壳（侧栏底 / 移动顶条 / 素材志顶栏）
 * 尺寸与圆角各不相同。
 */
const open = ref(false)

function onDocumentClick(event: MouseEvent) {
  const node = event.target as HTMLElement | null
  if (!node?.closest('[data-mode-menu]')) open.value = false
}
onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

const OPTIONS: { key: Mode; label: string; hint: string; icon: typeof Sun }[] = [
  { key: 'light', label: '浅色', hint: '', icon: Sun },
  { key: 'dark', label: '深色', hint: '', icon: Moon },
  { key: 'system', label: '跟随系统', hint: '', icon: Monitor },
]

function pick(m: Mode) {
  setMode(m)
  open.value = false
}

defineProps<{ buttonClass: string; menuClass: string }>()
</script>

<template>
  <div class="relative" data-mode-menu>
    <button
      type="button"
      class="flex cursor-pointer items-center justify-center text-steam-dim transition active:scale-95 hover:bg-ink-raised hover:text-steam"
      :class="buttonClass"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-label="currentMode === 'system' ? '明暗模式：跟随系统' : currentMode === 'dark' ? '明暗模式：深色' : '明暗模式：浅色'"
      title="明暗模式"
      @click="open = !open"
    >
      <Monitor v-if="currentMode === 'system'" class="h-4 w-4" />
      <Moon v-else-if="currentMode === 'dark'" class="h-4 w-4" />
      <Sun v-else class="h-4 w-4" />
    </button>
    <Transition name="v-pop">
      <div
        v-if="open"
        role="menu"
        class="absolute z-50 w-44 rounded-lg border border-ink-line bg-ink-surface p-1 shadow-xl"
        :class="menuClass"
      >
        <button
          v-for="option in OPTIONS"
          :key="option.key"
          type="button"
          role="menuitemradio"
          :aria-checked="currentMode === option.key"
          class="flex w-full cursor-pointer items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors"
          :class="currentMode === option.key ? 'text-gold' : 'text-steam-dim hover:bg-ink-raised hover:text-steam'"
          @click="pick(option.key)"
        >
          <component :is="option.icon" class="h-4 w-4 shrink-0" />
          <span class="flex-1">
            {{ option.label }}
            <span v-if="option.key === 'system' && currentMode === 'system'" class="text-[11px] text-steam-dim">
              （{{ renderedDark ? '当前深色' : '当前浅色' }}）
            </span>
          </span>
          <Check v-if="currentMode === option.key" class="h-3.5 w-3.5 shrink-0" />
        </button>
      </div>
    </Transition>
  </div>
</template>
