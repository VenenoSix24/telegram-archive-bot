<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { sanitizeTelegramHtml } from '@/lib/telegramHtml'
import {
  FileText,
  Film,
  Headphones,
  Link2,
  Music,
  Plus,
  Send,
  Sticker,
  Tag as TagIcon,
  X,
  File as FileIcon,
} from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import { patchMessage } from '@/lib/api'
import Button from '@/components/ui/Button.vue'
import StarRating from '@/components/ui/StarRating.vue'
import { displayChatId, durationLabel, formatTime, sizeLabel, splitBodyTitleDesc } from '@/lib/format'
import { toastError, toastSuccess } from '@/composables/useToast'
import { archiveLinkOf, sourceLinkOf } from '@/lib/links'

const props = defineProps<{ message: Message | null }>()
const emit = defineEmits<{ close: []; update: [Message] }>()

const newTag = ref('')
const busy = ref(false)
const error = ref('')
const drawerThumbFailed = ref(false)
const bodyDraft = ref('')
const bodyHtmlDraft = ref('')
const editingBody = ref(false)
let lockedScrollY = 0
let savedBodyStyles: Partial<Record<'overflow' | 'position' | 'top' | 'width' | 'paddingRight', string>> | null = null

function lockBody() {
  if (savedBodyStyles || typeof window === 'undefined') return
  lockedScrollY = window.scrollY
  const { body } = document
  savedBodyStyles = {
    overflow: body.style.overflow,
    position: body.style.position,
    top: body.style.top,
    width: body.style.width,
    paddingRight: body.style.paddingRight,
  }
  const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
  body.style.overflow = 'hidden'
  body.style.position = 'fixed'
  body.style.top = `-${lockedScrollY}px`
  body.style.width = '100%'
  if (scrollbarWidth) body.style.paddingRight = `${scrollbarWidth}px`
}

function unlockBody() {
  if (!savedBodyStyles || typeof window === 'undefined') return
  const { body } = document
  for (const [property, value] of Object.entries(savedBodyStyles)) {
    body.style[property as 'overflow' | 'position' | 'top' | 'width' | 'paddingRight'] = value ?? ''
  }
  savedBodyStyles = null
  window.scrollTo(0, lockedScrollY)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.message) emit('close')
}

// 同一素材的字段回写（如评分后 PATCH 返回）不应重置编辑中的草稿，
// 因此按素材身份（id + target）判断是否真的换了消息，而不是按对象引用。
let lastIdentity: string | null = null

watch(() => props.message, (message) => {
  if (message) lockBody()
  else unlockBody()

  const identity = message ? `${message.id}:${message.target_id ?? ''}` : null
  if (identity === lastIdentity) return
  lastIdentity = identity

  newTag.value = ''
  error.value = ''
  drawerThumbFailed.value = false
  bodyDraft.value = message?.original_text ?? ''
  bodyHtmlDraft.value = message?.original_html ?? ''
  editingBody.value = false
})

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  unlockBody()
})

const mediaIcon = computed(() => {
  switch (props.message?.media_type) {
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
  () => props.message?.media_type === 'photo' || props.message?.media_type === 'video',
)

const thumbSrc = computed(() => {
  if (!props.message) return ''
  const target = props.message.target_id
  return `/api/v1/messages/${props.message.id}/thumb${target == null ? '' : `?target_id=${target}`}`
})

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
const typeLabel = computed(() =>
  props.message ? TYPE_LABEL[props.message.media_type] ?? '素材' : '',
)
const durationLabelText = computed(() => durationLabel(props.message?.duration ?? null))
const figMeta = computed(() =>
  [typeLabel.value, durationLabelText.value].filter(Boolean).join(' · '),
)

const metaLine = computed(() => {
  if (props.message == null) return ''
  const parts: string[] = []
  if (props.message.file_name) parts.push(props.message.file_name)
  if (props.message.file_size != null) parts.push(sizeLabel(props.message.file_size))
  if (durationLabel(props.message.duration)) parts.push(durationLabel(props.message.duration))
  return parts.join(' · ')
})

const openUrl = computed(() => {
  if (!props.message) return null
  return archiveLinkOf(props.message) || sourceLinkOf(props.message)
})

const srcUrl = computed(() => (props.message ? sourceLinkOf(props.message) : null))
const activeTarget = computed(() => props.message?.targets?.[0] ?? null)
const activeRating = computed(() => props.message?.rating ?? 0)
const activeTags = computed(() => props.message?.tags ?? [])
const activeBody = computed(() => props.message?.original_text ?? '')
const activeRendered = computed(() => props.message?.rendered_text ?? '')

/** 卡片标题同源：首行非骨架行，回退文件名 */
const drawerTitle = computed(() => {
  if (!props.message) return ''
  const split = splitBodyTitleDesc(
    props.message.original_text || props.message.rendered_text || '',
    (props.message.tags ?? []).map((t) => t.name),
  )
  return split.title || props.message.file_name || '无题'
})

const RATING_WORDS = ['普通', '可留', '有用', '优质', '珍藏'] as const
const ratingHint = computed(() => {
  const r = activeRating.value
  return r > 0 ? `${r} 星 · ${RATING_WORDS[r - 1]}` : '点击评鉴'
})

function textToHtml(value: string) {
  const escaped = value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped.replace(/\r?\n/g, '<br>')
}

function htmlToText(value: string) {
  const doc = new DOMParser().parseFromString(value, 'text/html')
  return doc.body.textContent ?? ''
}

function startBodyEdit() {
  bodyDraft.value = activeBody.value
  bodyHtmlDraft.value = props.message?.original_html || textToHtml(activeBody.value)
  editingBody.value = true
}

async function saveBody() {
  const body = bodyHtmlDraft.value ? htmlToText(bodyHtmlDraft.value) : bodyDraft.value
  await mutate({ body, body_html: bodyHtmlDraft.value || undefined }, '正文已更新')
  editingBody.value = false
}


async function setRating(n: number) {
  if (!props.message) return
  await mutate({ rating: n }, n === 0 ? '已清除评级' : `评级设为 ${n} 星`)
}

async function addTag() {
  const name = newTag.value.trim()
  if (!name || !props.message || activeTags.value.some((t) => t.name === name)) return
  await mutate({ add_tags: [name] }, `已添加标签「${name}」`)
  newTag.value = ''
}

async function removeTag(tagName: string) {
  if (!props.message) return
  await mutate({ remove_tag_names: [tagName] }, `已移除标签「${tagName}」`)
}

async function mutate(
  change: { target_id?: number; body?: string; body_html?: string; rating?: number; add_tags?: string[]; remove_tag_names?: string[] },
  doneText: string,
) {
  if (!props.message) return
  busy.value = true
  error.value = ''
  try {
    const updated = await patchMessage(props.message.id, {
      ...change,
      target_id: props.message.target_id ?? undefined,
    })
    emit('update', updated)
    toastSuccess(doneText)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
    toastError(e instanceof Error ? e.message : '保存失败')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition
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

            <header class="flex flex-none items-center justify-between border-b border-ink-line py-2.5 pl-6 pr-2.5">
              <span class="font-mono text-[11px] tracking-[0.22em] text-steam-dim">
                图 · 藏品 <b class="font-semibold text-gold">{{ message.id }}</b>
              </span>
              <button
                type="button"
                class="flex h-11 w-11 cursor-pointer items-center justify-center rounded-md text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam"
                aria-label="关闭详情"
                @click="emit('close')"
              >
                <X class="h-5 w-5" />
              </button>
            </header>

            <div class="min-h-0 flex-1 overflow-y-auto">
              <!-- 图版预览：真实比例不裁切，横图通栏 / 竖图居中限高 -->
              <div
                v-if="showThumb && !drawerThumbFailed"
                class="overflow-hidden border-b border-ink-line bg-ink-surface"
              >
                <img
                  :src="thumbSrc"
                  :alt="'素材 #' + message.id"
                  class="mx-auto block max-h-[44vh] w-auto max-w-full object-contain"
                  @error="drawerThumbFailed = true"
                />
              </div>
              <div v-else class="border-b border-ink-line px-6 py-12 text-center text-steam-dim">
                <component :is="mediaIcon ?? Film" class="mx-auto mb-2.5 h-6 w-6" />
                <p class="font-mono text-[11px] tracking-[0.24em]">
                  {{ typeLabel }} · {{ showThumb ? '图版加载失败' : '无图版' }}
                </p>
              </div>

              <p class="d-cap border-b border-ink-line px-6 py-2.5 text-[11px] tracking-[0.2em] text-steam-dim">
                图 · 藏品 <b class="font-semibold text-gold">{{ message.id }}</b>
                <span class="ml-3">{{ figMeta }}</span>
                <span class="ml-3">归档于 {{ formatTime(message.created_at) }}</span>
              </p>

              <div class="px-6 pb-9 pt-5">
                <h2 class="font-display text-[21px] font-bold leading-snug text-steam">{{ drawerTitle }}</h2>

                <!-- 图录数据表 -->
                <dl class="mt-4 grid grid-cols-[auto_1fr] items-baseline gap-x-6 border-t border-steam">
                  <dt class="whitespace-nowrap border-b border-ink-line py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">归档频道</dt>
                  <dd class="min-w-0 break-words border-b border-ink-line py-2 font-mono text-[12.5px] text-steam">
                    {{ activeTarget?.name || displayChatId(message.target_chat_id) }}
                  </dd>
                  <dt v-if="message.target_message_id != null" class="whitespace-nowrap border-b border-ink-line py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">归档消息</dt>
                  <dd v-if="message.target_message_id != null" class="border-b border-ink-line py-2 font-mono text-[12.5px] text-steam">#{{ message.target_message_id }}</dd>
                  <dt class="whitespace-nowrap border-b border-ink-line py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">来源频道</dt>
                  <dd class="border-b border-ink-line py-2 font-mono text-[12.5px] text-steam">{{ displayChatId(message.source_chat_id) }}</dd>
                  <dt class="whitespace-nowrap border-b border-ink-line py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">来源消息</dt>
                  <dd class="border-b border-ink-line py-2 font-mono text-[12.5px] text-steam">#{{ message.source_message_id }}</dd>
                  <dt class="whitespace-nowrap border-b border-ink-line py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">归档时间</dt>
                  <dd class="border-b border-ink-line py-2 font-mono text-[12.5px] text-steam">{{ formatTime(message.created_at) }}</dd>
                  <dt class="whitespace-nowrap border-b border-ink-line py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">体例</dt>
                  <dd class="border-b border-ink-line py-2 text-[13px] text-steam">{{ figMeta }}</dd>
                  <template v-if="metaLine">
                    <dt class="whitespace-nowrap border-b border-ink-line py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">文件</dt>
                    <dd class="min-w-0 break-words border-b border-ink-line py-2 font-mono text-[12.5px] text-steam">{{ metaLine }}</dd>
                  </template>
                  <template v-if="srcUrl">
                    <dt class="whitespace-nowrap border-b border-ink-line py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">来源</dt>
                    <dd class="min-w-0 border-b border-ink-line py-2 text-[13px]">
                      <a
                        :href="srcUrl"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="inline-flex max-w-full items-center gap-1.5 break-all text-steam hover:text-gold"
                      >
                        <Link2 class="h-3.5 w-3.5 shrink-0" />
                        <span class="truncate">{{ srcUrl }}</span>
                      </a>
                    </dd>
                  </template>
                </dl>

                <!-- 正文 -->
                <!-- eslint-disable vue/no-v-html -->
                <div
                  v-if="activeBody || activeRendered"
                  class="telegram-content mt-5 text-sm leading-relaxed text-steam"
                  v-html="sanitizeTelegramHtml(message.original_html, activeBody || activeRendered)"
                />
                <p v-else class="mt-5 text-sm text-steam-dim/60">无正文</p>
                <Button type="button" variant="secondary" size="sm" class="mt-3" :disabled="busy" @click="startBodyEdit">
                  编辑正文
                </Button>
                <div v-if="editingBody" class="mt-3 space-y-2">
                  <textarea
                    v-model="bodyHtmlDraft"
                    rows="7"
                    class="w-full rounded-sm border border-ink-line bg-ink-raised px-3 py-2 font-mono text-sm text-steam focus:border-gold focus:outline-none"
                    aria-label="编辑 Telegram HTML 正文"
                  />
                  <p class="text-xs text-steam-dim">支持 Telegram HTML：&lt;b&gt;粗体&lt;/b&gt;、&lt;i&gt;斜体&lt;/i&gt;、&lt;a href=""&gt;链接&lt;/a&gt;、&lt;code&gt;代码&lt;/code&gt;。</p>
                  <div
                    v-if="bodyHtmlDraft"
                    class="telegram-content rounded-sm border border-ink-line bg-ink-surface p-3 text-sm leading-relaxed text-steam"
                    v-html="sanitizeTelegramHtml(bodyHtmlDraft, bodyDraft)"
                  />
                  <div class="flex gap-2">
                    <Button size="sm" :disabled="busy" @click="saveBody">保存正文</Button>
                    <Button type="button" variant="secondary" size="sm" :disabled="busy" @click="editingBody = false">取消</Button>
                  </div>
                </div>
                <!-- eslint-enable vue/no-v-html -->

                <!-- 类目：点击移除 -->
                <div class="mt-6">
                  <div class="mb-2 flex items-center gap-1.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">
                    <TagIcon class="h-3.5 w-3.5" /> 类目 · TAGS（点击移除）
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-for="tag in activeTags"
                      :key="tag.name + tag.type"
                      type="button"
                      :disabled="busy"
                      class="cursor-pointer rounded-sm border border-ink-line bg-ink-surface px-2.5 py-1 font-mono text-[11px] text-steam-dim transition-colors hover:border-destructive/50 hover:text-destructive disabled:cursor-default"
                      :title="`移除「${tag.name}」`"
                      @click="removeTag(tag.name)"
                    >
                      #{{ tag.name }}
                    </button>
                    <span v-if="!activeTags.length" class="text-xs text-steam-dim/60">暂无类目</span>
                  </div>

                  <div class="mt-3 flex gap-2">
                    <input
                      v-model="newTag"
                      type="text"
                      placeholder="添加类目…"
                      :disabled="busy"
                      class="h-9 min-w-0 flex-1 rounded-sm border border-ink-line bg-ink-surface px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none disabled:opacity-50"
                      @keyup.enter="addTag"
                    />
                    <Button size="sm" variant="secondary" :disabled="busy || !newTag.trim()" @click="addTag">
                      <Plus class="h-3.5 w-3.5" /> 添加
                    </Button>
                  </div>
                </div>

                <!-- 评鉴 -->
                <div class="mt-6 flex items-center gap-3 border-t border-ink-line pt-5">
                  <span class="font-display text-[13px] tracking-[0.3em] text-steam-dim">评 鉴</span>
                  <StarRating
                    :value="activeRating"
                    size="lg"
                    interactive
                    :disabled="busy"
                    @change="setRating"
                  />
                  <span class="font-mono text-[10.5px] text-steam-dim">{{ ratingHint }}</span>
                  <button
                    v-if="message.rating"
                    type="button"
                    class="ml-auto inline-flex min-h-8 cursor-pointer items-center rounded-sm border border-ink-line px-2.5 py-1 text-xs text-steam-dim transition-colors hover:border-gold/50 hover:bg-ink-raised hover:text-gold"
                    :disabled="busy"
                    @click="setRating(0)"
                  >
                    清除
                  </button>
                </div>

                <p v-if="error" role="alert" class="mt-3 text-xs text-destructive">{{ error }}</p>
              </div>
            </div>

            <footer v-if="openUrl" class="border-t border-ink-line p-4">
              <a
                :href="openUrl"
                target="_blank"
                rel="noopener"
                class="flex w-full items-center justify-center gap-2 rounded-sm bg-gold px-3 py-3 text-sm font-semibold tracking-wide text-ink-bg transition-[filter,transform] hover:brightness-110 active:scale-[0.985]"
              >
                <Send class="h-4 w-4" />
                在 Telegram 中打开
              </a>
            </footer>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
