<script setup lang="ts">
withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })

/* defineModel 让 v-model 透传到原生 select；option 由使用方经 slot 传入 */
const model = defineModel<string | number>({ required: true })
</script>

<template>
  <!-- 原生 select 的统一外壳：全站下拉一个观感，键盘/无障碍行为交给原生 -->
  <select
    v-model="model"
    class="h-9 cursor-pointer rounded-md border border-ink-line bg-ink-surface px-2.5 text-sm text-steam transition-colors focus:border-gold focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
    :disabled="disabled"
  >
    <slot />
  </select>
</template>
