<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Layers2, Link2, Play, Send } from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import StarRating from '@/components/ui/StarRating.vue'
import MediaGlyph from '@/components/MediaGlyph.vue'
import { useMessageCard } from '@/composables/useMessageCard'
import { useThumbMode } from '@/composables/useDisplayPrefs'
import { useVocab } from '@/lib/vocab'

/*
 * 标准后台卡片。封面按显示偏好三态（useDisplayPrefs）：
 * 完整展示 = 4:3 画布 + 深色托底 + object-contain（竖图完整）；
 * 裁剪填充 = 4:3 画布 + object-cover（卡片完全统一）；
 * 瀑布流   = 原始比例（onload 后按真实宽高比对齐）。
 * 卡身：#编号 + 频道（重点色）+ 标签两行自适应（放不下的收进 +N）
 * + 页脚归档/来源链接（与素材志图签脚同源字段）。
 */
const props = defineProps<{ message: Message; selected?: boolean }>()
const emit = defineEmits<{ rate: [number]; open: [] }>()

const {
  ratio,
  thumbFailed,
  onImgLoad,
  showThumb,
  thumbSrc,
  isDead,
  isAlbum,
  typeLabel,
  title,
  durationLabelText,
  chanLabel,
  dateShort,
  archiveUrl,
  sourceUrl,
} = useMessageCard(() => props.message)
const L = useVocab()
const { thumbMode } = useThumbMode()
const masonry = computed(() => thumbMode.value === 'masonry')

/* 瀑布流下封面跟随真实比例（ratio 初始 4/3，onload 后精确对齐）；统一模式固定 4:3 */
const canvasStyle = computed(() =>
  masonry.value && showThumb.value && !thumbFailed.value ? { aspectRatio: ratio.value } : undefined,
)

/* 标签两行自适应：容器裁在两行高，ResizeObserver 量出第三行起的个数给 +N */
const tagWrap = ref<HTMLElement | null>(null)
const visibleTags = ref(Number.MAX_SAFE_INTEGER)
let tagRO: ResizeObserver | null = null
function measureTags() {
  const wrap = tagWrap.value
  if (!wrap || wrap.clientWidth === 0) return
  const pills = Array.from(wrap.querySelectorAll<HTMLElement>('[data-tag-pill]'))
  let count = pills.length
  for (let i = 0; i < pills.length; i++) {
    if (pills[i].offsetTop > 30) {
      count = i
      break
    }
  }
  visibleTags.value = count
}
onMounted(() => {
  tagRO = new ResizeObserver(measureTags)
  if (tagWrap.value) tagRO.observe(tagWrap.value)
})
onBeforeUnmount(() => tagRO?.disconnect())
watch(
  () => props.message.tags,
  () => {
    visibleTags.value = Number.MAX_SAFE_INTEGER
    void nextTick(measureTags)
  },
)
</script>

<template>
  <article
    class="group flex cursor-pointer flex-col overflow-hidden rounded-xl border bg-ink-surface shadow-sm transition-[transform,box-shadow,border-color] duration-150 hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-none"
    :class="[selected ? 'border-gold ring-2 ring-gold/15' : 'border-ink-line hover:border-steam-dim/40', masonry && 'mb-3.5 break-inside-avoid']"
    role="button"
    tabindex="0"
    :aria-label="'打开条目：' + title"
    @click="emit('open')"
    @keydown.enter.prevent="emit('open')"
    @keydown.space.prevent="emit('open')"
  >
    <!-- 封面：统一模式锁 16:9 画布（overflow-hidden 掐掉 flex 子项的最小高度泄漏，
         否则竖图自然高会撑开画布）；瀑布流按真实比例（缩略图多大画布多大）。
         图片衬深色托底凸显本体；绘制封面（文本/文件/音频）跟随主题深浅色 -->
    <div
      class="relative overflow-hidden border-b border-ink-line"
      :class="[
        showThumb && !thumbFailed ? 'vthumb' : 'bg-ink-raised',
        !masonry || !showThumb || thumbFailed ? 'aspect-video' : '',
      ]"
      :style="canvasStyle"
    >
      <img
        v-if="showThumb && !thumbFailed"
        v-img-fade
        :src="thumbSrc"
        :alt="'归档 #' + message.id"
        loading="lazy"
        class="h-full w-full"
        :class="[masonry || thumbMode === 'crop' ? 'object-cover' : 'object-contain', isDead && 'opacity-40 grayscale']"
        @load="onImgLoad"
        @error="thumbFailed = true"
      />
      <!-- 绘制封面：文本/文件/音频等无原生缩略图的类型 -->
      <MediaGlyph
        v-else
        class="absolute inset-0"
        :type="message.media_type"
        :id="message.id"
        :file-name="message.file_name"
      />

      <!-- 左下：类型；右下：相册/时长 -->
      <span
        class="absolute bottom-1.5 left-1.5 z-[2] rounded-md bg-steam/70 px-1.5 py-0.5 text-[10px] font-medium text-ink-bg backdrop-blur-sm"
      >
        {{ typeLabel }}
      </span>
      <span
        v-if="isAlbum"
        class="absolute bottom-1.5 right-1.5 z-[2] inline-flex items-center gap-1 rounded-md bg-steam/70 px-1.5 py-0.5 font-mono text-[9.5px] text-ink-bg backdrop-blur-sm"
      >
        <Layers2 class="h-2.5 w-2.5" /> {{ L.album }}
      </span>
      <span
        v-else-if="durationLabelText"
        class="absolute bottom-1.5 right-1.5 z-[2] inline-flex items-center gap-1 rounded-md bg-steam/70 px-1.5 py-0.5 font-mono text-[9.5px] text-ink-bg backdrop-blur-sm"
      >
        <Play class="h-2.5 w-2.5" /> {{ durationLabelText }}
      </span>

      <!-- 已删除遮罩 -->
      <div v-if="isDead" class="absolute inset-0 z-[2] flex items-center justify-center bg-ink-bg/55">
        <span class="rounded-full border border-destructive/30 bg-ink-surface/90 px-2.5 py-0.5 text-[11px] text-destructive">
          已删除
        </span>
      </div>
    </div>

    <!-- 卡身 -->
    <div class="flex flex-1 flex-col p-3">
      <div class="flex items-center gap-2">
        <span class="shrink-0 rounded bg-ink-raised px-1.5 py-0.5 font-mono text-[11px] font-semibold text-steam">
          #{{ message.id }}
        </span>
        <span v-if="chanLabel" class="min-w-0 flex-1 truncate text-[12px] font-medium text-gold">
          {{ chanLabel }}
        </span>
        <StarRating
          class="ml-auto shrink-0"
          :value="message.rating"
          size="sm"
          interactive
          @click.stop
          @change="(n: number) => emit('rate', n)"
        />
      </div>
      <h3
        class="mt-2 truncate text-[13.5px] font-semibold text-steam"
        :class="isDead && 'text-steam-dim line-through'"
      >
        {{ title }}
      </h3>

      <!-- 标签：两行自适应，放不下的收进 +N（渐变收边） -->
      <div v-if="message.tags.length" ref="tagWrap" class="relative mt-2 max-h-[48px] overflow-hidden">
        <div class="flex flex-wrap gap-1">
          <span
            v-for="t in message.tags"
            :key="t.name + t.type"
            data-tag-pill
            class="max-w-full truncate rounded-full bg-ink-raised px-2 py-0.5 text-[11px] text-steam-dim"
          >
            #{{ t.name }}
          </span>
        </div>
        <span
          v-if="message.tags.length > visibleTags"
          class="absolute bottom-0 right-0 bg-gradient-to-l from-ink-surface via-ink-surface/95 to-transparent py-0.5 pl-6 text-[11px] font-medium text-gold"
        >
          +{{ message.tags.length - visibleTags }}
        </span>
      </div>

      <!-- 页脚：归档/来源链接（重点交互）+ 日期 -->
      <div
        class="mt-auto flex items-center gap-3 pt-2.5"
        :class="message.tags.length ? 'mt-2' : ''"
      >
        <a
          v-if="archiveUrl"
          :href="archiveUrl"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-1 text-[11px] text-steam-dim transition-colors hover:text-gold"
          :aria-label="`打开归档频道消息 #${message.id}`"
          title="归档频道消息"
          @click.stop
        >
          <Send class="h-3 w-3" /> 归档
        </a>
        <a
          v-if="sourceUrl"
          :href="sourceUrl"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-1 text-[11px] text-steam-dim transition-colors hover:text-gold"
          :aria-label="`打开来源消息 #${message.id}`"
          title="来源消息"
          @click.stop
        >
          <Link2 class="h-3 w-3" /> 来源
        </a>
        <span class="ml-auto shrink-0 font-mono text-[10.5px] tabular-nums text-steam-dim">{{ dateShort }}</span>
      </div>
    </div>
  </article>
</template>
