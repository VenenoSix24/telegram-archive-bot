<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Message } from '@/lib/types'
import MessageDetailInner from '@/components/MessageDetailInner.vue'

/*
 * 详情容器，两种模式：
 * - 抽屉（素材志/概览页等）：Teleport 遮罩 + 侧滑，行为与重构前一致；
 * - 面板 pane（标准后台素材页）：父级布局中的常驻右栏，窄屏由父级转为覆盖层。
 * 内容与编辑逻辑都在 MessageDetailInner，两种模式零分叉。
 */
const props = withDefaults(defineProps<{ message: Message | null; pane?: boolean }>(), {
  pane: false,
})
const emit = defineEmits<{ close: []; update: [Message] }>()

/* 关闭动画期内容冻结：父级把 message 置 null 时屉体开始滑出，内层 out-in 若
   跟着切空态/清内容，滑出的就是空壳，观感即「关闭=瞬间消失」（用户反馈）。
   抽屉模式冻结最后一条素材，内容随屉体完整滑出后再随父级卸载；
   面板模式维持空态引导不变（常驻栏需要）。 */
const lastMessage = ref<Message | null>(null)
watch(
  () => props.message,
  (m) => {
    if (m) lastMessage.value = m
  },
)
const innerMessage = computed(() => props.message ?? (props.pane ? null : lastMessage.value))
</script>

<template>
  <Teleport to="body" :disabled="pane">
    <!-- 抽屉模式（素材志）：遮罩 fade 与屉体侧滑走 style.css 的 token 级
         drawer-fade / drawer-slide，离场同步收口，滑出全程可见 -->
    <Transition v-if="!pane" name="drawer-fade" appear>
      <div
        v-if="message"
        class="fixed inset-0 z-40 flex justify-end bg-ink-bg/60 backdrop-blur-[2px]"
        @click.self="emit('close')"
      >
        <Transition name="drawer-slide" appear>
          <aside
            v-if="message"
            class="drawer-root relative flex h-full w-full max-w-[500px] flex-col border-l border-ink-line bg-ink-bg shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label="素材详情"
          >
            <span class="drawer-spine absolute inset-x-0 top-0 z-[2] hidden h-1 bg-gold" aria-hidden="true"></span>
            <MessageDetailInner :message="innerMessage" @close="emit('close')" @update="(m) => emit('update', m)" />
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
      <MessageDetailInner pane :message="innerMessage" @close="emit('close')" @update="(m) => emit('update', m)" />
    </aside>
  </Teleport>
</template>
