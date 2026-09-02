import { computed, ref } from 'vue'
import { FileText, Film, Headphones, Music, Sticker, File as FileIcon } from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import {
  displayChatId,
  durationLabel,
  ratioLabel,
  shortDate,
  sizeLabel,
  splitBodyTitleDesc,
} from '@/lib/format'
import { useAspectRatio } from '@/composables/useAspectRatio'
import { useVocab, typeLabel } from '@/lib/vocab'
import { archiveLinkOf, sourceLinkOf } from '@/lib/links'

/**
 * 素材卡片与列表行的共用逻辑（两种布局变体的卡片共用，展示字段保持同源）。
 * message 传 getter 以保持 props 响应性。
 */
export function useMessageCard(message: () => Message) {
  const L = useVocab()
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
    switch (message().media_type) {
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
    () => message().media_type === 'photo' || message().media_type === 'video',
  )

  const thumbSrc = computed(() => {
    const target = message().target_id
    return `/api/v1/messages/${message().id}/thumb${target == null ? '' : `?target_id=${target}`}`
  })

  const isDead = computed(() => message().status === 'deleted')
  const isAlbum = computed(() => message().media_group_id != null)
  const isText = computed(() => message().media_type === 'text')

  const typeLabelText = computed(() => typeLabel(L.value, message().media_type))

  const tagNames = computed(() => message().tags.map((t) => t.name))
  const split = computed(() =>
    splitBodyTitleDesc(message().original_text || message().rendered_text || '', tagNames.value),
  )
  const title = computed(() => split.value.title || message().file_name || L.value.untitled)
  const desc = computed(() => (isText.value ? '' : split.value.desc))
  const excerpt = computed(() => split.value.body)

  const durationLabelText = computed(() => durationLabel(message().duration))
  const fileLine = computed(() =>
    [message().file_name, sizeLabel(message().file_size)].filter(Boolean).join(' · '),
  )

  /** 真实比例角标：onload 捕获宽高，约分展示；列表页固定高裁切时标示原比例 */
  const ratioText = computed(() =>
    showThumb.value && !thumbFailed.value
      ? ratioLabel(natural.value?.w ?? null, natural.value?.h ?? null)
      : '',
  )
  const figMeta = computed(() => {
    const parts = [typeLabelText.value]
    if (ratioText.value) parts.push(ratioText.value)
    if (durationLabelText.value) parts.push(durationLabelText.value)
    else if (message().media_type === 'document' && message().file_size != null) {
      parts.push(sizeLabel(message().file_size))
    }
    return parts.filter(Boolean).join(' · ')
  })

  const chanLabel = computed(
    () => message().targets[0]?.name || displayChatId(message().target_chat_id) || '',
  )
  const dateShort = computed(() => shortDate(message().created_at))
  const archiveUrl = computed(() => archiveLinkOf(message()))
  const sourceUrl = computed(() => sourceLinkOf(message()))

  return {
    L,
    ratio,
    thumbFailed,
    onImgLoad,
    mediaIcon,
    showThumb,
    thumbSrc,
    isDead,
    isAlbum,
    isText,
    typeLabel: typeLabelText,
    tagNames,
    title,
    desc,
    excerpt,
    durationLabelText,
    fileLine,
    ratioText,
    figMeta,
    chanLabel,
    dateShort,
    archiveUrl,
    sourceUrl,
  }
}
