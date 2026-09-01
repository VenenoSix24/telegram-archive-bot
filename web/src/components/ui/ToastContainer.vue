<script setup lang="ts">
import { CheckCircle2, XCircle, Info } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'

const { toasts } = useToast()

const icons = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}
</script>

<template>
  <Teleport to="body">
    <div
      class="pointer-events-none fixed top-4 left-1/2 z-50 flex max-h-[70vh] -translate-x-1/2 flex-col items-center gap-2 overflow-hidden"
      role="status"
      aria-live="polite"
    >
      <TransitionGroup
        name="toast"
        enter-active-class="transition duration-300 ease-out"
        leave-active-class="transition duration-200 ease-in"
        enter-from-class="-translate-y-2 opacity-0"
        leave-to-class="-translate-y-1 opacity-0"
      >
        <div
          v-for="t in toasts"
          :key="t.id"
          :class="[
            'pointer-events-auto flex items-center gap-2 rounded-full border px-4 py-2 text-sm backdrop-blur',
            t.kind === 'success' && 'border-gold/40 bg-ink-surface/95 text-steam',
            t.kind === 'error' && 'border-destructive/50 bg-ink-surface/95 text-destructive',
            t.kind === 'info' && 'border-ink-line bg-ink-surface/95 text-steam-dim',
          ]"
        >
          <component :is="icons[t.kind]" class="h-4 w-4 shrink-0" />
          <span>{{ t.text }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>