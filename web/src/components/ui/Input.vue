<script setup lang="ts">
defineProps<{ modelValue?: string; placeholder?: string; type?: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <input
    :type="type ?? 'text'"
    :value="modelValue"
    :placeholder="placeholder"
    class="h-9 w-full rounded-md bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 border border-ink-line transition-colors focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold"
    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>