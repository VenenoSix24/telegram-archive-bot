<script setup lang="ts">
import { Star } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{ value: number; size?: 'sm' | 'lg'; interactive?: boolean; disabled?: boolean }>(),
  { size: 'sm', interactive: false, disabled: false },
)
const emit = defineEmits<{ change: [number] }>()

const sizes = { sm: 'h-4 w-4', lg: 'h-7 w-7' } as const
const gap = { sm: 'gap-0.5', lg: 'gap-1' } as const

function pick(n: number) {
  if (props.disabled) return
  emit('change', n === props.value ? 0 : n)
}
</script>

<template>
  <div
    class="inline-flex items-center"
    :class="[gap[size], interactive ? 'cursor-pointer' : '']"
    role="radiogroup"
    :aria-label="'评分 ' + value + ' / 5'"
  >
    <button
      v-for="n in 5"
      :key="n"
      type="button"
      :disabled="disabled || !interactive"
      :aria-pressed="n <= value"
      :aria-label="'评 ' + n + ' 分'"
      class="p-1 -m-1 transition-transform duration-150 hover:scale-110 focus-visible:outline-none disabled:cursor-default"
      @click="pick(n)"
    >
      <Star
        :class="[
          sizes[size],
          n <= value ? 'fill-gold text-gold' : (interactive ? 'text-ink-line fill-ink-line' : 'text-ink-line'),
        ]"
      />
    </button>
  </div>
</template>