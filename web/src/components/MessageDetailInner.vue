<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Image as ImageIcon,
  Link2,
  Pencil,
  Plus,
  Send,
  Tag as TagIcon,
  X,
} from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import { patchMessage } from '@/lib/api'
import Button from '@/components/ui/Button.vue'
import StarRating from '@/components/ui/StarRating.vue'
import MediaGlyph from '@/components/MediaGlyph.vue'
import { displayChatId, durationLabel, formatTime, sizeLabel, splitBodyTitleDesc } from '@/lib/format'
import { toastError, toastSuccess } from '@/composables/useToast'
import { archiveLinkOf, sourceLinkOf } from '@/lib/links'
import { isVault, typeLabel as vocabTypeLabel, useVocab } from '@/lib/vocab'
import { sanitizeTelegramHtml } from '@/lib/telegramHtml'

/*
 * 详情内容（抽屉与常驻面板两种模式共用）。
 * pane=true（标准后台）：无遮罩无滚动锁，Esc/关闭钮交由父级收起面板；
 * 素材志抽屉：行为与重构前完全一致。
 */
const props = withDefaults(defineProps<{ message: Message | null; pane?: boolean }>(), {
  pane: false,
})
const emit = defineEmits<{ close: []; update: [Message] }>()

const router = useRouter()
const L = useVocab()
const newTag = ref('')
const busy = ref(false)
const error = ref('')
const tagEditing = ref(false)
const drawerThumbFailed = ref(false)
const scrollEl = ref<HTMLElement | null>(null)
const bodyDraft = ref('')
const bodyHtmlDraft = ref('')
const editingBody = ref(false)
let lockedScrollY = 0
let savedRootOverflow = ''
let savedBodyStyles: Partial<Record<'overflow' | 'position' | 'top' | 'width' | 'paddingRight', string>> | null = null

function lockBody() {
  if (props.pane || savedBodyStyles || typeof window === 'undefined') return
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
  // iOS（含 App 内置浏览器）对 body overflow:hidden 不完全生效，滚轮/触摸会穿透到页面；
  // 根元素一并锁住，配合滚动区的 overscroll-contain 双保险
  savedRootOverflow = document.documentElement.style.overflow
  document.documentElement.style.overflow = 'hidden'
}

function unlockBody() {
  if (!savedBodyStyles || typeof window === 'undefined') return
  const { body } = document
  for (const [property, value] of Object.entries(savedBodyStyles)) {
    body.style[property as 'overflow' | 'position' | 'top' | 'width' | 'paddingRight'] = value ?? ''
  }
  savedBodyStyles = null
  document.documentElement.style.overflow = savedRootOverflow
  savedRootOverflow = ''
  window.scrollTo(0, lockedScrollY)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.message) emit('close')
}

// 同一素材的字段回写（如评分后 PATCH 返回）不应重置编辑中的草稿，
// 因此按素材身份（id + target）判断是否真的换了消息，而不是按对象引用。
let lastIdentity: string | null = null

watch(() => props.message, (message) => {
  if (message && !props.pane) lockBody()
  else unlockBody()

  const identity = message ? `${message.id}:${message.target_id ?? ''}` : null
  if (identity === lastIdentity) return
  lastIdentity = identity

  newTag.value = ''
  error.value = ''
  drawerThumbFailed.value = false
  tagEditing.value = false
  bodyDraft.value = message?.original_text ?? ''
  bodyHtmlDraft.value = message?.original_html ?? ''
  editingBody.value = false
  // 换了素材：详情栏滚动回顶部（面板模式常驻，不清零会停在上条的浏览位置）
  void nextTick(() => {
    if (scrollEl.value) scrollEl.value.scrollTop = 0
  })
})

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  unlockBody()
})

const showThumb = computed(
  () => props.message?.media_type === 'photo' || props.message?.media_type === 'video',
)

const thumbSrc = computed(() => {
  if (!props.message) return ''
  const target = props.message.target_id
  return `/api/v1/messages/${props.message.id}/thumb${target == null ? '' : `?target_id=${target}`}`
})

const typeLabel = computed(() =>
  props.message ? vocabTypeLabel(L.value, props.message.media_type) : '',
)

const durationLabelText = computed(() => durationLabel(props.message?.duration ?? null))
const figMeta = computed(() =>
  [typeLabel.value, durationLabelText.value].filter(Boolean).join(' · '),
)

/* 文件行只放文件名与大小；时长已在「类型」行展示（用户反馈，不重复） */
const metaLine = computed(() => {
  if (props.message == null) return ''
  const parts: string[] = []
  if (props.message.file_name) parts.push(props.message.file_name)
  if (props.message.file_size != null) parts.push(sizeLabel(props.message.file_size))
  return parts.join(' · ')
})

const openUrl = computed(() => {
  if (!props.message) return null
  return archiveLinkOf(props.message) || sourceLinkOf(props.message)
})

const archiveUrlOf = computed(() => (props.message ? archiveLinkOf(props.message) : null))
const srcUrl = computed(() => (props.message ? sourceLinkOf(props.message) : null))
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
  return split.title || props.message.file_name || L.value.untitled
})

const ratingHint = computed(() => {
  const r = activeRating.value
  return r > 0 ? `${r} 星 · ${L.value.ratingHint[r - 1]}` : L.value.ratingTapHint
})

/* 详情数据表按行渲染：一行一个边框，dt/dd 高度随内容自适应且横线永远对齐 */
const metaRows = computed(() => {
  const m = props.message
  if (!m) return []
  const vault = isVault.value
  const rows: { label: string; value: string; href?: string }[] = []
  const chan = m.targets[0]?.name || displayChatId(m.target_chat_id)
  if (chan) rows.push({ label: vault ? '保存位置' : '归档位置', value: chan })
  if (m.target_message_id != null) {
    rows.push({ label: vault ? '目标消息' : '归档消息', value: `#${m.target_message_id}` })
  }
  rows.push({ label: vault ? '来源' : '来源频道', value: displayChatId(m.source_chat_id) })
  rows.push({ label: '来源消息', value: `#${m.source_message_id}` })
  rows.push({ label: '归档时间', value: formatTime(m.created_at) })
  if (figMeta.value) rows.push({ label: vault ? '类型' : '体例', value: figMeta.value })
  if (metaLine.value) rows.push({ label: '文件', value: metaLine.value })
  if (srcUrl.value) rows.push({ label: vault ? '链接' : '来源', value: srcUrl.value, href: srcUrl.value })
  return rows
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

/* 点标签跳到该标签的筛选列表；常驻面板在宽屏保持打开（不遮挡结果） */
function jumpToTag(tagName: string) {
  if (props.pane && window.innerWidth >= 1280) {
    void router.push({ name: 'messages', query: { tag: tagName } })
    return
  }
  emit('close')
  void router.push({ name: 'messages', query: { tag: tagName } })
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
  <!-- 面板空态：常驻详情栏在未选中时给出引导（仅标准后台面板模式会渲染到） -->
  <Transition name="v-dialog" mode="out-in">
    <div v-if="!message" key="empty" class="flex flex-1 flex-col items-center justify-center gap-2.5 p-10 text-center">
      <ImageIcon class="h-7 w-7 text-steam-dim/40" />
      <p class="text-[12.5px] leading-relaxed text-steam-dim/80">
        在列表中选择一条素材<br>详情与操作会常驻在这里
      </p>
    </div>

    <div v-else :key="message.material_id" class="flex min-h-0 flex-1 flex-col">
      <header class="flex flex-none items-center justify-between border-b border-ink-line py-2.5 pl-5 pr-2.5">
        <span v-if="!pane" class="font-mono text-[11px] tracking-[0.22em] text-steam-dim">
          图 · 藏品 <b class="font-semibold text-gold">{{ message.id }}</b>
        </span>
        <span v-else class="flex items-baseline gap-2">
          <b class="text-[13.5px] font-semibold text-steam">详情</b>
          <span class="font-mono text-[10.5px] text-steam-dim">#{{ message.id }}</span>
        </span>
        <button
          type="button"
          class="flex h-11 w-11 cursor-pointer items-center justify-center rounded-md text-steam-dim transition active:scale-95 hover:bg-ink-raised hover:text-steam"
          aria-label="关闭详情"
          @click="emit('close')"
        >
          <X class="h-5 w-5" />
        </button>
      </header>

      <div ref="scrollEl" class="min-h-0 flex-1 overflow-y-auto overscroll-contain [scrollbar-gutter:stable]">
        <!-- 预览：真实比例不裁切，横图通栏 / 竖图居中限高 -->
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
        <div v-else class="border-b border-ink-line px-6 py-10 text-center text-steam-dim">
          <div class="mx-auto mb-2 h-16 w-44">
            <MediaGlyph :type="message.media_type" :id="message.id" :file-name="message.file_name" />
          </div>
          <p class="font-mono text-[11px] tracking-[0.24em]">
            {{ typeLabel }} · {{ showThumb ? L.previewFailed : L.noPreview }}
          </p>
        </div>

        <p v-if="!pane" class="border-b border-ink-line px-6 py-2.5 font-mono text-[11px] tracking-[0.2em] text-steam-dim">
          图 · 藏品 <b class="font-semibold text-gold">{{ message.id }}</b><span class="ml-3">{{ figMeta }}</span>
          <span class="ml-3">归档于 {{ formatTime(message.created_at) }}</span>
        </p>

        <div class="px-6 pb-9 pt-5">
          <h2 class="font-display text-[21px] font-bold leading-snug text-steam">{{ drawerTitle }}</h2>

          <!-- 素材信息：标准后台用无边框键值行（标签左 / 值右），告别表格观感；素材志保留数据表 -->
          <dl v-if="isVault" class="mt-5 space-y-2.5">
            <div v-for="row in metaRows" :key="row.label" class="flex items-baseline justify-between gap-4">
              <dt class="w-16 shrink-0 text-[11px] leading-5 text-steam-dim">{{ row.label }}</dt>
              <dd class="min-w-0 flex-1 text-right text-[12.5px] leading-5 text-steam">
                <a
                  v-if="row.href"
                  :href="row.href"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex max-w-full items-center gap-1 text-gold hover:underline"
                >
                  <Link2 class="h-3 w-3 shrink-0 self-center" />
                  <span class="truncate">{{ row.value }}</span>
                </a>
                <span v-else class="block break-words font-mono text-[12px]">{{ row.value }}</span>
              </dd>
            </div>
          </dl>
          <dl v-else class="mt-4 border-t border-steam">
            <div
              v-for="row in metaRows"
              :key="row.label"
              class="flex items-baseline gap-x-6 border-b border-ink-line last:border-b-0"
            >
              <dt class="w-16 shrink-0 py-2.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">
                {{ row.label }}
              </dt>
              <dd class="min-w-0 flex-1 py-2 text-[13px] text-steam">
                <a
                  v-if="row.href"
                  :href="row.href"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex max-w-full min-w-0 items-baseline gap-1.5 hover:text-gold"
                >
                  <Link2 class="h-3.5 w-3.5 shrink-0 self-center" />
                  <span class="break-all">{{ row.value }}</span>
                </a>
                <span v-else class="block break-words font-mono text-[12.5px]">{{ row.value }}</span>
              </dd>
            </div>
          </dl>

          <!-- 正文 -->
          <!-- eslint-disable vue/no-v-html -->
          <div
            v-if="activeBody || activeRendered"
            class="telegram-content mt-5 text-sm leading-relaxed text-steam"
            v-html="sanitizeTelegramHtml(message.original_html, activeBody || activeRendered)"
          />
          <p v-else class="mt-5 text-sm text-steam-dim/60">暂无正文</p>
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

          <!-- 标签：点按跳筛选；铅笔进编辑态后点按移除 -->
          <div class="mt-6">
            <div class="mb-2 flex items-center gap-1.5 font-mono text-[10px] tracking-[0.22em] text-steam-dim">
              <TagIcon class="h-3.5 w-3.5" /> {{ L.tag }} · TAGS
              <button
                type="button"
                class="ml-auto cursor-pointer rounded p-1 transition-colors"
                :class="tagEditing ? 'bg-gold/15 text-gold' : 'text-steam-dim hover:text-steam'"
                :aria-pressed="tagEditing"
                :title="tagEditing ? '完成编辑' : `编辑${L.tag}`"
                :aria-label="tagEditing ? '完成编辑' : `编辑${L.tag}`"
                @click="tagEditing = !tagEditing"
              >
                <Pencil class="h-3.5 w-3.5" />
              </button>
            </div>
            <TransitionGroup tag="div" name="v-list" class="flex flex-wrap gap-2">
              <button
                v-for="tag in activeTags"
                :key="tag.name + tag.type"
                type="button"
                :disabled="busy && tagEditing"
                class="inline-flex cursor-pointer items-center gap-1 border border-ink-line bg-ink-surface px-2.5 py-1 font-mono text-[11px] transition-colors disabled:cursor-default"
                :class="[isVault ? 'rounded-full' : 'rounded-sm', tagEditing
                  ? 'text-steam hover:border-destructive/50 hover:text-destructive'
                  : 'text-steam-dim hover:border-gold hover:text-gold']"
                :title="tagEditing ? `移除「${tag.name}」` : `查看「${tag.name}」`"
                @click="tagEditing ? removeTag(tag.name) : jumpToTag(tag.name)"
              >
                #{{ tag.name }}
                <X v-if="tagEditing" class="h-3 w-3" />
              </button>
              <span v-if="!activeTags.length" key="empty" class="text-xs text-steam-dim/60">暂无{{ L.tag }}</span>
            </TransitionGroup>
            <p class="mt-1.5 text-xs text-steam-dim/70">
              {{ tagEditing ? `正在编辑：点${L.tag}即移除，再点铅笔完成。` : `点${L.tag}查看对应素材；误触删除用右上铅笔进入编辑态。` }}
            </p>

            <div class="mt-3 flex gap-2">
              <input
                v-model="newTag"
                type="text"
                :placeholder="`添加${L.tag}…`"
                :disabled="busy"
                class="h-9 min-w-0 flex-1 rounded-sm border border-ink-line bg-ink-surface px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none disabled:opacity-50"
                @keyup.enter="addTag"
              />
              <Button size="sm" variant="secondary" :disabled="busy || !newTag.trim()" @click="addTag">
                <Plus class="h-3.5 w-3.5" /> 添加
              </Button>
            </div>
          </div>

          <!-- 评分 -->
          <div class="mt-6 flex items-center gap-3 border-t border-ink-line pt-5">
            <span class="font-display text-[13px] text-steam-dim" :class="isVault ? '' : 'tracking-[0.3em]'">{{ isVault ? L.rating : '评 鉴' }}</span>
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

      <footer v-if="openUrl" class="grid gap-2 border-t border-ink-line p-4" :class="archiveUrlOf && srcUrl ? 'grid-cols-2' : 'grid-cols-1'">
        <a
          v-if="archiveUrlOf"
          :href="archiveUrlOf"
          target="_blank"
          rel="noopener"
          class="flex items-center justify-center gap-2 bg-gold px-3 py-3 text-sm font-semibold tracking-wide text-ink-bg transition-[filter,transform] hover:brightness-110 active:scale-[0.985]"
          :class="isVault ? 'rounded-[10px]' : 'rounded-sm'"
        >
          <Send class="h-4 w-4" />
          归档频道
        </a>
        <a
          v-if="srcUrl"
          :href="srcUrl"
          target="_blank"
          rel="noopener"
          class="flex items-center justify-center gap-2 border border-ink-line px-3 py-3 text-sm text-steam transition-colors hover:border-gold hover:text-gold"
          :class="isVault ? 'rounded-[10px]' : 'rounded-sm'"
        >
          <Link2 class="h-4 w-4" />
          来源消息
        </a>
      </footer>
    </div>
  </Transition>
</template>
