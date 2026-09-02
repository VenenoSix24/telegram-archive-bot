<script setup lang="ts">
import type { Message } from '@/lib/types'
import MessageDetailInner from '@/components/MessageDetailInner.vue'

/*
 * 详情容器，两种模式：
 * - 抽屉（素材志/概览页等）：Teleport 遮罩 + 侧滑，行为与重构前一致；
 * - 面板 pane（标准后台素材页）：父级布局中的常驻右栏，窄屏由父级转为覆盖层。
 * 内容与编辑逻辑都在 MessageDetailInner，两种模式零分叉。
 */
withDefaults(defineProps<{ message: Message | null; pane?: boolean }>(), {
  pane: false,
})
const emit = defineEmits<{ close: []; update: [Message] }>()
</script>

<template>
  <Teleport to="body" :disabled="pane">
    <!-- 抽屉模式（素材志） -->
    <Transition
      v-if="!pane"
      appear
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-150"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="message"
        class="fixed inset-0 z-40 flex justify-end bg-ink-bg/60 backdrop-blur-[2px]"
        @click.self="emit('close')"
      >
        <Transition
          appear
          enter-active-class="transition-transform duration-300 ease-out"
          leave-active-class="transition-transform duration-200 ease-in"
          enter-from-class="translate-x-full"
          leave-to-class="translate-x-full"
        >
          <aside
            v-if="message"
            class="drawer-root relative flex h-full w-full max-w-[500px] flex-col border-l border-ink-line bg-ink-bg shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label="素材详情"
          >
            <span class="drawer-spine absolute inset-x-0 top-0 z-[2] hidden h-1 bg-gold" aria-hidden="true"></span>
            <MessageDetailInner :message="message" @close="emit('close')" @update="(m) => emit('update', m)" />
          </aside>
        </Transition>
      </div>
    </Transition>

    <!-- 面板模式（标准后台）：常驻右栏，内衬圆角毛玻璃面板；空态由 Inner 给出 -->
    <aside
      v-else
      class="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-2xl border border-ink-line bg-ink-surface/85 backdrop-blur-xl backdrop-saturate-150"
      aria-label="素材详情"
    >
      <MessageDetailInner pane :message="message" @close="emit('close')" @update="(m) => emit('update', m)" />
    </aside>
  </Teleport>
</template>
