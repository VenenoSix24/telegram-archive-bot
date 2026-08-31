<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { sanitizeTelegramHtml } from '@/lib/telegramHtml'
import { Calendar, Film, Link2, Plus, Send, Tag as TagIcon, X } from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import { patchMessage } from '@/lib/api'
import Button from '@/components/ui/Button.vue'
import StarRating from '@/components/ui/StarRating.vue'
import { durationLabel, formatTime, sizeLabel } from '@/lib/format'
import { toastError, toastSuccess } from '@/composables/useToast'
import { archiveLinkOf, sourceLinkOf } from '@/lib/links'

const props = defineProps<{ message: Message | null }>()
const emit = defineEmits<{ close: []; update: [Message] }>()

const newTag = ref('')
const busy = ref(false)
const error = ref('')
const drawerThumbFailed = ref(false)
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

watch(() => props.message, (message) => {
  if (message) lockBody()
  else unlockBody()

  newTag.value = ''
  error.value = ''
  drawerThumbFailed.value = false
})

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  unlockBody()
})

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
const safeOriginalHtml = computed(() => {
  if (!props.message) return ''
  return sanitizeTelegramHtml(props.message.original_html, props.message.original_text)
})

async function setRating(n: number) {
  if (!props.message) return
  await mutate({ rating: n }, n === 0 ? '已清除评级' : `评级设为 ${n} 星`)
}

async function addTag() {
  const name = newTag.value.trim()
  if (!name || !props.message || props.message.tags.some((t) => t.name === name)) return
  await mutate({ add_tags: [name] }, `已添加标签「${name}」`)
  newTag.value = ''
}

async function removeTag(tagName: string) {
  if (!props.message) return
  await mutate({ remove_tag_names: [tagName] }, `已移除标签「${tagName}」`)
}

async function mutate(
  change: { rating?: number; add_tags?: string[]; remove_tag_names?: string[] },
  doneText: string,
) {
  if (!props.message) return
  busy.value = true
  error.value = ''
  try {
    const updated = await patchMessage(props.message.id, change)
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
        class="fixed inset-0 z-40 flex justify-end bg-ink-bg/70 backdrop-blur-sm"
        @click.self="emit('close')"
      >
        <Transition
          appear
          enter-active-class="transition-transform duration-250 ease-out"
          leave-active-class="transition-transform duration-200 ease-in"
          enter-from-class="translate-x-8"
          leave-to-class="translate-x-8"
        >
          <aside
            v-if="message"
            class="flex h-full w-full max-w-lg flex-col bg-ink-surface shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label="消息详情"
          >
            <header class="flex items-center justify-between border-b border-ink-line px-5 py-3">
              <div class="flex items-center gap-2 font-mono text-sm text-steam-dim">
                消息 <span class="text-steam">#{{ message.id }}</span>
              </div>
              <button
                type="button"
                class="rounded-md p-1.5 text-steam-dim transition-colors hover:bg-ink-raised hover:text-steam cursor-pointer"
                aria-label="关闭"
                @click="emit('close')"
              >
                <X class="h-4 w-4" />
              </button>
            </header>

            <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              <!-- 媒体：失败显示占位图标 -->
              <div
                v-if="((message.media_type === 'photo' || message.media_type === 'video') && !drawerThumbFailed)"
                class="mb-4 overflow-hidden rounded-card bg-ink-raised"
              >
                <img
                  :src="`/api/v1/messages/${message.id}/thumb`"
                  :alt="'消息 #' + message.id"
                  class="max-h-96 w-full object-contain"
                  @error="drawerThumbFailed = true"
                />
              </div>
              <div
                v-else-if="message.media_type === 'photo' || message.media_type === 'video'"
                class="mb-4 flex h-48 items-center justify-center rounded-card bg-ink-raised text-steam-dim/45"
              >
                <Film class="h-12 w-12" />
              </div>

              <!-- 评级 -->
              <div class="mb-4 flex items-center gap-3">
                <StarRating
                  :value="message.rating"
                  size="lg"
                  interactive
                  :disabled="busy"
                  @change="setRating"
                />
                <span class="text-xs text-steam-dim">{{ message.rating || '未评级' }}</span>
                <button
                  v-if="message.rating"
                  type="button"
                  class="ml-auto inline-flex min-h-8 items-center rounded-md border border-ink-line px-2.5 py-1 text-xs text-steam-dim transition-colors hover:border-gold/50 hover:bg-ink-raised hover:text-gold"
                  :disabled="busy"
                  @click="setRating(0)"
                >
                  清除评级
                </button>
              </div>

              <!-- 元数据 -->
              <p v-if="metaLine" class="mb-3 font-mono text-xs text-steam-dim">{{ metaLine }}</p>

              <!-- 正文 -->
              <!-- eslint-disable vue/no-v-html -->
              <div
                v-if="message.original_text || message.original_html || message.rendered_text"
                class="telegram-content text-sm leading-relaxed text-steam"
                v-html="safeOriginalHtml"
              />
              <!-- eslint-enable vue/no-v-html -->

              <!-- 时间与来源元数据 -->
              <dl class="mt-4 space-y-1.5 border-t border-ink-line pt-3 text-xs text-steam-dim">
                <div class="flex items-center gap-2">
                  <Calendar class="h-3.5 w-3.5 shrink-0" />
                  {{ formatTime(message.created_at) }}
                </div>
                <div class="flex items-center gap-2 font-mono">
                  <span class="w-20 shrink-0 text-steam-dim/70">来源频道</span>
                  <span class="text-steam">{{ message.source_chat_id }}</span>
                </div>
                <div class="flex items-center gap-2 font-mono">
                  <span class="w-20 shrink-0 text-steam-dim/70">来源消息</span>
                  <span class="text-steam">#{{ message.source_message_id }}</span>
                </div>
                <div v-if="message.target_chat_id != null" class="flex items-center gap-2 font-mono">
                  <span class="w-20 shrink-0 text-steam-dim/70">归档频道</span>
                  <span class="text-steam">{{ message.target_chat_id }}</span>
                </div>
                <div v-if="message.target_message_id != null" class="flex items-center gap-2 font-mono">
                  <span class="w-20 shrink-0 text-steam-dim/70">归档消息</span>
                  <span class="text-steam">#{{ message.target_message_id }}</span>
                </div>
                <div v-if="srcUrl" class="flex items-start gap-2">
                  <Link2 class="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <a
                    :href="srcUrl"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="min-w-0 break-all text-steam hover:text-gold"
                  >
                    {{ srcUrl }}
                  </a>
                </div>
              </dl>

              <!-- Tags：点击删除 -->
              <div class="mt-5">
                <div class="mb-2 flex items-center gap-1.5 text-xs font-medium text-steam-dim">
                  <TagIcon class="h-3.5 w-3.5" /> 标签（点击移除）
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="tag in message.tags"
                    :key="tag.name + tag.type"
                    type="button"
                    :disabled="busy"
                    class="cursor-pointer rounded-full bg-ink-raised px-2.5 py-1 text-xs text-steam transition-colors hover:bg-destructive/20 hover:text-destructive disabled:cursor-default"
                    :title="`移除「${tag.name}」`"
                    @click="removeTag(tag.name)"
                  >
                    {{ tag.name }}
                  </button>
                  <span v-if="!message.tags.length" class="text-xs text-steam-dim/60">暂无标签</span>
                </div>

                <!-- 添加标签 -->
                <div class="mt-3 flex gap-2">
                  <input
                    v-model="newTag"
                    type="text"
                    placeholder="添加标签…"
                    :disabled="busy"
                    class="h-9 min-w-0 flex-1 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none disabled:opacity-50"
                    @keyup.enter="addTag"
                  />
                  <Button size="sm" variant="secondary" :disabled="busy || !newTag.trim()" @click="addTag">
                    <Plus class="h-3.5 w-3.5" /> 添加
                  </Button>
                </div>
              </div>

              <p v-if="error" role="alert" class="mt-3 text-xs text-destructive">{{ error }}</p>
            </div>

            <footer v-if="openUrl" class="border-t border-ink-line p-4">
              <a
                :href="openUrl"
                target="_blank"
                rel="noopener"
                class="flex w-full items-center justify-center gap-2 rounded-md bg-gold px-3 py-2.5 text-sm font-medium text-ink-bg transition-colors hover:bg-gold-soft"
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