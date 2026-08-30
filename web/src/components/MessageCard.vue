<script setup lang="ts">
import { computed } from 'vue'
import { FileText, Film, Headphones, Link2, Music, Send, Sticker, File as FileIcon } from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import StarRating from '@/components/ui/StarRating.vue'
import { durationLabel } from '@/lib/format'

const props = defineProps<{ message: Message }>()
const emit = defineEmits<{ rate: [number]; 'open-source': [] }>()

const mediaIcon = computed(() => {
  switch (props.message.media_type) {
    case 'video': return Film
    case 'audio': return Music
    case 'voice': return Headphones
    case 'sticker': return Sticker
    case 'document': return FileIcon
    case 'photo': return undefined
    default: return FileText
  }
})

const showThumb = computed(
  () => props.message.media_type === 'photo' || props.message.media_type === 'video',
)

const thumbSrc = computed(() => `/api/v1/messages/${props.message.id}/thumb`)

const body = computed(() => {
  const t = props.message.original_text || props.message.rendered_text || ''
  return t.length > 120 ? t.slice(0, 120) + '…' : t
})

const durationLabelText = computed(() => durationLabel(props.message.duration))

const fileInfo = computed(() => {
  const name = props.message.file_name
  if (name) return name
  return ''
})
</script>

<template>
  <article
    class="group flex flex-col overflow-hidden rounded-card border border-ink-line bg-ink-surface transition-shadow duration-200 hover:shadow-glow focus-within:shadow-glow"
  >
    <!-- 媒体区：photo/video 渲染缩略图；其余渲染类型图标占位 -->
    <div
      v-if="showThumb"
      class="relative aspect-video w-full overflow-hidden bg-ink-raised"
    >
      <img
        :src="thumbSrc"
        :alt="'消息 #' + message.id"
        loading="lazy"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
        @error="($event.target as HTMLImageElement).style.display = 'none'"
      />
      <span
        v-if="durationLabelText"
        class="absolute bottom-2 right-2 rounded bg-ink-bg/80 px-1.5 py-0.5 font-mono text-[11px] text-steam"
      >
        {{ durationLabelText }}
      </span>
    </div>
    <div
      v-else
      class="flex aspect-video w-full items-center justify-center bg-ink-raised text-steam-dim/50"
    >
      <component :is="mediaIcon" class="h-10 w-10" />
    </div>

    <!-- 评分区：星级即控件，浏览时直接改 -->
    <div class="flex items-center justify-between px-3 pt-2">
      <StarRating :value="message.rating" size="lg" interactive @change="(n) => emit('rate', n)" />
      <span class="font-mono text-[11px] text-steam-dim">#{{ message.id }}</span>
    </div>

    <!-- tags -->
    <div v-if="message.tags.length" class="flex flex-wrap gap-1 px-3 pt-1.5">
      <Badge v-for="tag in message.tags" :key="tag.name + tag.type" :tone="tag.type">
        {{ tag.name }}
      </Badge>
    </div>

    <!-- 正文 / 文件信息 -->
    <p v-if="body" class="px-3 pb-1 pt-2 text-sm leading-relaxed text-steam/90">{{ body }}</p>
    <p v-else-if="fileInfo" class="truncate px-3 pb-1 pt-2 font-mono text-xs text-steam-dim">
      {{ fileInfo }}
    </p>

    <!-- 底部：来源 + 打开 Telegram -->
    <div class="mt-auto flex items-center gap-2 border-t border-ink-line px-3 py-2">
      <a
        v-if="message.target_url || message.source_url"
        :href="message.target_url || message.source_url!"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center gap-1 text-xs text-steam-dim transition-colors hover:text-gold"
      >
        <Send class="h-3.5 w-3.5" />
        打开 Telegram
      </a>
      <button
        v-else
        type="button"
        class="inline-flex items-center gap-1 text-xs text-steam-dim/70"
        @click="emit('open-source')"
      >
        <Link2 class="h-3.5 w-3.5" />
        无链接
      </button>
      <span v-if="message.source_url" class="ml-auto truncate font-mono text-[10px] text-steam-dim/50">
        {{ message.source_chat_id }}
      </span>
    </div>
  </article>
</template>