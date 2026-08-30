<script setup lang="ts">
import { computed } from 'vue'
import { cva, type VariantProps } from 'class-variance-authority'

const variants = cva(
  'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium leading-5',
  {
    variants: {
      tone: {
        source: 'bg-ink-raised text-steam-dim',
        original: 'bg-ink-raised text-steam',
        manual: 'bg-gold/15 text-gold',
        active: 'bg-gold text-ink-bg',
      },
    },
    defaultVariants: { tone: 'source' },
  },
)

type Tone = NonNullable<VariantProps<typeof variants>['tone']>
const props = defineProps<{ tone?: Tone }>()
const cls = computed(() => variants({ tone: props.tone }))
</script>

<template>
  <span :class="cls"><slot /></span>
</template>