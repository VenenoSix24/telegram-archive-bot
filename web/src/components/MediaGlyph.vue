<script setup lang="ts">
import { computed } from 'vue'
import { FileText, Headphones, Music, Sticker, File as FileIcon } from 'lucide-vue-next'

/*
 * 无原生缩略图类型（文本/文件/音频等）的绘制封面：
 * 音频画确定性波形（按素材 id 播种伪随机，同一素材永远同一形状），
 * 文件给图标圆托 + 扩展名，其余回退单图标。mini 用于列表行小缩略图。
 */
const props = withDefaults(
  defineProps<{ type: string; id: number; fileName?: string | null; mini?: boolean }>(),
  { fileName: '', mini: false },
)

const isAudio = computed(() => props.type === 'audio' || props.type === 'voice')
const isDocument = computed(() => props.type === 'document')
const isTextType = computed(() => props.type === 'text')

const icon = computed(() => {
  switch (props.type) {
    case 'audio': return Music
    case 'voice': return Headphones
    case 'sticker': return Sticker
    case 'document': return FileIcon
    default: return FileText
  }
})

const ext = computed(() => {
  const match = props.fileName?.match(/\.([A-Za-z0-9]{1,4})$/)
  return match ? match[1].toUpperCase() : ''
})

const bars = computed(() => {
  let seed = (Math.abs(props.id) * 48271) % 2147483647 || 7
  const out: number[] = []
  for (let i = 0; i < (props.mini ? 9 : 21); i++) {
    seed = (seed * 48271) % 2147483647
    out.push(18 + (seed % 82))
  }
  return out
})
</script>

<template>
  <div class="flex h-full w-full flex-col items-center justify-center gap-2 text-steam-dim/55">
    <!-- 音频：波形（C3：卡片/封面 hover 时轻舞，条目间错峰） -->
    <template v-if="isAudio">
      <component :is="icon" class="text-gold/75" :class="mini ? 'h-3 w-3' : 'h-4 w-4'" />
      <div class="v-wave flex items-center gap-[2.5px]" aria-hidden="true">
        <span
          v-for="(h, i) in bars"
          :key="i"
          class="v-wave-bar w-[3px] shrink-0 rounded-full bg-gold/45"
          :style="{ height: mini ? `${3 + (h % 8)}px` : `${5 + h * 0.3}px`, animationDelay: `${i * 45}ms` }"
        />
      </div>
    </template>

    <!-- 文本：文档行母题（不再铺正文摘录） -->
    <template v-else-if="isTextType && !mini">
      <component :is="icon" class="h-5 w-5" />
      <span class="flex w-12 flex-col gap-[3px]" aria-hidden="true">
        <span class="h-[2.5px] w-full rounded-full bg-steam-dim/30"></span>
        <span class="h-[2.5px] w-full rounded-full bg-steam-dim/25"></span>
        <span class="h-[2.5px] w-2/3 rounded-full bg-steam-dim/20"></span>
      </span>
    </template>

    <!-- 文件：图标圆托 + 扩展名 -->
    <template v-else-if="isDocument && !mini">
      <span class="grid size-11 place-items-center rounded-full bg-steam/[0.045] ring-1 ring-ink-line">
        <component :is="icon" class="h-5 w-5" />
      </span>
      <span v-if="ext" class="font-mono text-[9.5px] tracking-[0.14em] text-steam-dim/70">{{ ext }}</span>
    </template>

    <!-- 其余（含列表行小尺寸）：单图标 -->
    <component :is="icon" v-else :class="mini ? 'h-4 w-4' : 'h-8 w-8'" />
  </div>
</template>
