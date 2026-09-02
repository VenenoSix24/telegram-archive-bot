<script setup lang="ts">
import { computed } from 'vue'
import { cva, type VariantProps } from 'class-variance-authority'

const buttonVariants = cva(
  'btn inline-flex items-center justify-center gap-1.5 rounded-md text-sm font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50 cursor-pointer',
  {
    variants: {
      variant: {
        default: 'bg-gold text-ink-bg hover:bg-gold-soft',
        secondary: 'bg-ink-raised text-steam hover:bg-ink-line',
        ghost: 'text-steam-dim hover:bg-ink-raised hover:text-steam',
        destructive: 'bg-destructive text-white hover:opacity-90',
      },
      size: {
        default: 'h-9 px-3',
        sm: 'h-8 px-2.5 text-xs',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

type Variant = NonNullable<VariantProps<typeof buttonVariants>['variant']>
type Size = NonNullable<VariantProps<typeof buttonVariants>['size']>

const props = withDefaults(
  defineProps<{
    variant?: Variant
    size?: Size
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
  }>(),
  { type: 'button' },
)

const classes = computed(() => buttonVariants({ variant: props.variant, size: props.size }))
</script>

<template>
  <button :class="classes" :type="type" :disabled="disabled" :aria-disabled="disabled">
    <slot />
  </button>
</template>