<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  FileText,
  Film,
  Headphones,
  Layers2,
  Link2,
  Music,
  Play,
  Send,
  Sticker,
  File as FileIcon,
} from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import StarRating from '@/components/ui/StarRating.vue'
import {
  displayChatId,
  durationLabel,
  ratioLabel,
  shortDate,
  sizeLabel,
  splitBodyTitleDesc,
} from '@/lib/format'
import { useAspectRatio } from '@/composables/useAspectRatio'
import { archiveLinkOf, sourceLinkOf } from '@/lib/links'

const props = defineProps<{ message: Message }>()
const emit = defineEmits<{ rate: [number]; open: [] }>()

const { ratio, onLoad } = useAspectRatio()
const thumbFailed = ref(false)
const natural = ref<{ w: number; h: number } | null>(null)

function onImgLoad(e: Event) {
  onLoad(e)
  const img = e.target as HTMLImageElement
  if (img.naturalWidth > 0 && img.naturalHeight > 0) {
    natural.value = { w: img.naturalWidth, h: img.naturalHeight }
  }
}

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

const isDead = computed(() => props.message.status === 'deleted')
const isAlbum = computed(() => props.message.media_group_id != null)
const isText = computed(() => props.message.media_type === 'text')

const TYPE_LABEL: Record<string, string> = {
  photo: '图版',
  video: '影像',
  audio: '音频',
  voice: '语音',
  sticker: '贴纸',
  document: '附件',
  text: '抄本',
  other: '其他',
}
const typeLabel = computed(() => TYPE_LABEL[props.message.media_type] ?? '素材')

const tagNames = computed(() => props.message.tags.map((t) => t.name))
const split = computed(() =>
  splitBodyTitleDesc(props.message.original_text || props.message.rendered_text || '', tagNames.value),
)
const title = computed(() => split.value.title || props.message.file_name || '无题')
const desc = computed(() => (isText.value ? '' : split.value.desc))
const excerpt = computed(() => split.value.body)

const durationLabelText = computed(() => durationLabel(props.message.duration))
const fileLine = computed(() =>
  [props.message.file_name, sizeLabel(props.message.file_size)].filter(Boolean).join(' · '),
)

const ratioText = computed(() =>
  showThumb.value && !thumbFailed.value
    ? ratioLabel(natural.value?.w ?? null, natural.value?.h ?? null)
    : '',
)
const figMeta = computed(() => {
  const parts = [typeLabel.value]
  if (ratioText.value) parts.push(ratioText.value)
  if (durationLabelText.value) parts.push(durationLabelText.value)
  else if (props.message.media_type === 'document' && props.message.file_size != null) {
    parts.push(sizeLabel(props.message.file_size))
  }
  return parts.filter(Boolean).join(' · ')
})

const chanLabel = computed(
  () => props.message.targets[0]?.name || displayChatId(props.message.target_chat_id) || '',
)
const dateShort = computed(() => shortDate(props.message.created_at))
const archiveUrl = computed(() => archiveLinkOf(props.message))
const sourceUrl = computed(() => sourceLinkOf(props.message))
</script>

<template>
  <article
    class="card-root group mb-6 flex cursor-pointer break-inside-avoid flex-col"
    role="button"
    tabindex="0"
    :aria-label="'打开条目：' + title"
    @click="emit('open')"
    @keydown.enter.prevent="emit('open')"
    @keydown.space.prevent="emit('open')"
  >
    <!-- 抄本卡：文本素材走活字版式 -->
    <div
      v-if="isText"
      class="txt-root relative border bg-ink-surface px-5 pb-4 pt-5"
      :class="isDead ? 'border-dashed border-ink-line' : 'border-ink-line'"
    >
      <span class="txt-mark hidden" aria-hidden="true">文</span>
      <p
        class="txt-body line-clamp-6 whitespace-pre-wrap text-sm text-steam"
        :class="isDead && 'opacity-50'"
      >
        {{ excerpt || title }}
      </p>
    </div>

    <!-- 装裱图版：白边 + 发丝线，真实宽高比 -->
    <div
      v-else
      class="plate-el relative border bg-ink-surface p-2.5 transition-[border-color,box-shadow] duration-200"
      :class="isDead ? 'border-dashed border-ink-line' : 'border-ink-line'"
    >
      <div
        class="relative overflow-hidden"
        :style="{ aspectRatio: showThumb && !thumbFailed ? ratio : '16 / 10' }"
      >
        <img
          v-if="showThumb && !thumbFailed"
          :src="thumbSrc"
          :alt="'素材 #' + message.id"
          loading="lazy"
          class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.015]"
          :class="isDead && 'opacity-40 grayscale'"
          @load="onImgLoad"
          @error="thumbFailed = true"
        />
        <div
          v-else
          class="flex h-full w-full flex-col items-center justify-center gap-2.5 bg-ink-raised text-steam-dim/70"
        >
          <component :is="mediaIcon ?? FileText" class="h-9 w-9" />
          <span
            v-if="fileLine"
            class="max-w-[85%] truncate px-3 text-center font-mono text-[10px] tracking-[0.14em]"
          >
            {{ fileLine }}
          </span>
        </div>

        <!-- 角标：相册辑册 / 影像时长 -->
        <span
          v-if="isAlbum"
          class="absolute bottom-2 right-2 z-[2] inline-flex items-center gap-1 rounded-sm border border-ink-line bg-ink-surface/90 px-2 py-0.5 font-mono text-[10px] text-steam"
        >
          <Layers2 class="h-2.5 w-2.5" /> 辑册
        </span>
        <span
          v-else-if="durationLabelText"
          class="absolute bottom-2 right-2 z-[2] inline-flex items-center gap-1 rounded-sm border border-ink-line bg-ink-surface/90 px-2 py-0.5 font-mono text-[10px] text-steam"
        >
          <Play class="h-2.5 w-2.5" /> {{ durationLabelText }}
        </span>

        <span class="album-ribbon hidden" aria-hidden="true"></span>

        <!-- 墓碑：通用小标 + 素材志朱印「废」 -->
        <div v-if="isDead" class="absolute inset-0 z-[2] flex items-center justify-center">
          <span
            class="dead-pill rounded-sm border border-destructive/40 bg-ink-bg/85 px-2 py-0.5 font-mono text-[10px] tracking-[0.2em] text-destructive"
          >
            已删除
          </span>
          <span class="dead-stamp hidden absolute inset-0"><span class="stamp">废</span>已删除</span>
        </div>
      </div>
    </div>

    <!-- 藏品图签 -->
    <div class="flex flex-1 flex-col px-1 pt-3">
      <div class="flex items-center gap-2 font-mono text-[10px] tracking-[0.2em] text-steam-dim">
        <span class="shrink-0 font-semibold" :class="isDead ? 'text-steam-dim' : 'text-gold'">
          藏品 {{ message.id }}
        </span>
        <span class="min-w-0 shrink truncate">{{ figMeta }}</span>
        <span class="flex-1 border-b border-ink-line" aria-hidden="true"></span>
      </div>
      <h3
        class="mt-2 font-display text-[15.5px] font-bold leading-snug text-steam"
        :class="isDead && 'text-steam-dim line-through decoration-1'"
      >
        {{ title }}
      </h3>
      <p v-if="desc" class="mt-1 line-clamp-2 text-xs leading-relaxed text-steam-dim">
        {{ desc }}
      </p>

      <!-- 图签脚：频道 · 日期 / 标签 / 星级（可直接评） -->
      <div
        class="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 font-mono text-[10px] text-steam-dim"
        @click.stop
      >
        <span class="shrink-0">
          {{ chanLabel }}<template v-if="dateShort"> · {{ dateShort }}</template>
        </span>
        <span v-if="message.tags.length" class="min-w-0 truncate">#{{ tagNames.join(' #') }}</span>
        <StarRating
          class="ml-auto shrink-0"
          :value="message.rating"
          size="sm"
          interactive
          @change="(n: number) => emit('rate', n)"
        />
      </div>
      <div v-if="archiveUrl || sourceUrl" class="mt-1.5 flex items-center gap-3" @click.stop>
        <a
          v-if="archiveUrl"
          :href="archiveUrl"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-1 font-mono text-[10px] text-steam-dim transition-colors hover:text-gold"
        >
          <Send class="h-3 w-3" /> 归档
        </a>
        <a
          v-if="sourceUrl"
          :href="sourceUrl"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-1 font-mono text-[10px] text-steam-dim transition-colors hover:text-gold"
        >
          <Link2 class="h-3 w-3" /> 来源
        </a>
      </div>
    </div>
  </article>
</template>
