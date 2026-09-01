<script setup lang="ts">
import { computed, ref } from 'vue'
import { FileText, Film, Headphones, Link2, Music, Send, Sticker, File as FileIcon } from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import StarRating from '@/components/ui/StarRating.vue'
import { durationLabel } from '@/lib/format'
import { useAspectRatio } from '@/composables/useAspectRatio'
import { archiveLinkOf, sourceLinkOf } from '@/lib/links'

const props = defineProps<{ message: Message }>()
const emit = defineEmits<{ rate: [number]; open: [] }>()

const { ratio, onLoad } = useAspectRatio()
const thumbFailed = ref(false)

const archiveUrl = computed(() => archiveLinkOf(props.message))
const sourceUrl = computed(() => sourceLinkOf(props.message))

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

const thumbSrc = computed(() => {
  const target = props.message.target_id
  return `/api/v1/messages/${props.message.id}/thumb${target == null ? '' : `?target_id=${target}`}`
})

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
const targetLabel = computed(() => props.message.targets[0]?.name || '')
const materialLabel = computed(() => `#${props.message.id}${targetLabel.value ? ` · ${targetLabel.value}` : ''}`)
const mediaLabel = computed(() => ({
  photo: '图片', video: '视频', audio: '音频', voice: '语音',
  sticker: '贴纸', document: '文件', text: '文本', other: '其他',
}[props.message.media_type] || '素材'))
</script>

<template>
  <article
    class="group cursor-pointer flex flex-col overflow-hidden rounded-card border border-ink-line bg-ink-surface transition-shadow duration-200 hover:shadow-glow focus-within:shadow-glow"
    @click="emit('open')"
  >
    <!-- 媒体区：photo/video 渲染缩略图；失败显示占位图标 -->
    <div
      v-if="showThumb && !thumbFailed"
      class="relative w-full overflow-hidden bg-ink-raised"
      :style="{ aspectRatio: ratio }"
    >
      <span class="absolute left-2 top-2 max-w-[70%] truncate rounded bg-ink-bg/80 px-1.5 py-0.5 font-mono text-[11px] text-steam">
        {{ materialLabel }}
      </span>
      <img
        :src="thumbSrc"
        :alt="'消息 #' + message.id"
        loading="lazy"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
        @load="onLoad"
        @error="thumbFailed = true"
      />
      <span
        v-if="durationLabelText"
        class="absolute bottom-2 right-2 rounded bg-ink-bg/80 px-1.5 py-0.5 font-mono text-[11px] text-steam"
      >
        {{ durationLabelText }}
      </span>
      <span class="absolute bottom-2 left-2 rounded bg-ink-bg/75 px-1.5 py-0.5 font-mono text-[10px] text-steam-dim">{{ mediaLabel }}</span>
    </div>
    <div v-else class="relative flex aspect-[16/9] w-full items-center justify-center overflow-hidden bg-ink-raised text-steam-dim/45">
      <component :is="mediaIcon ?? Film" class="h-10 w-10" />
      <span class="absolute left-2 top-2 max-w-[70%] truncate rounded bg-ink-bg/80 px-1.5 py-0.5 font-mono text-[11px] text-steam">
        {{ materialLabel }}
      </span>
      <span class="absolute bottom-2 left-2 rounded bg-ink-bg/75 px-1.5 py-0.5 font-mono text-[10px] text-steam-dim">{{ mediaLabel }}</span>
    </div>

    <!-- 评分区：星级即控件，浏览时直接改 -->
    <div class="flex min-h-11 items-center justify-between gap-2 px-3 pt-2" @click.stop>
      <StarRating :value="message.rating" size="lg" interactive @change="(n) => emit('rate', n)" />
      <span class="sr-only">{{ materialLabel }}</span>
    </div>

    <!-- tags -->
    <div v-if="message.tags.length" class="flex flex-wrap gap-1 px-3 pt-1.5" @click.stop>
      <Badge v-for="tag in message.tags" :key="tag.name + tag.type" :tone="tag.type">
        {{ tag.name }}
      </Badge>
    </div>

    <div class="min-h-[4.75rem] px-3 pt-2">
      <p v-if="body" class="line-clamp-3 text-sm leading-relaxed text-steam/90">{{ body }}</p>
      <p v-else-if="fileInfo" class="line-clamp-2 font-mono text-xs leading-relaxed text-steam-dim">{{ fileInfo }}</p>
      <p v-else class="text-xs text-steam-dim/60">无正文</p>
    </div>

    <!-- 底部：归档频道 + 源链接（双按钮） -->
    <div class="mt-auto flex items-center gap-2 border-t border-ink-line px-3 py-2" @click.stop>
      <a
        v-if="archiveUrl"
        :href="archiveUrl"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center gap-1 text-xs text-steam-dim transition-colors hover:text-gold"
      >
        <Send class="h-3.5 w-3.5" />
        归档
      </a>
      <a
        v-if="sourceUrl"
        :href="sourceUrl"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center gap-1 text-xs text-steam-dim transition-colors hover:text-gold"
      >
        <Link2 class="h-3.5 w-3.5" />
        来源
      </a>
      <span
        v-if="!archiveUrl && !sourceUrl"
        class="inline-flex items-center gap-1 text-xs text-steam-dim/60"
      >
        无链接
      </span>
    </div>
  </article>
</template>