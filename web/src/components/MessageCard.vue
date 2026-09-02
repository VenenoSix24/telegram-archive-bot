<script setup lang="ts">
import { computed } from 'vue'
import { Layers2, Link2, Play, Send } from 'lucide-vue-next'
import type { Message } from '@/lib/types'
import StarRating from '@/components/ui/StarRating.vue'
import MediaGlyph from '@/components/MediaGlyph.vue'
import { useMessageCard } from '@/composables/useMessageCard'
import { useThumbMode } from '@/composables/useDisplayPrefs'

const props = defineProps<{ message: Message }>()
const emit = defineEmits<{ rate: [number]; open: [] }>()

/* 展示字段与标准后台卡片同源（useMessageCard），仅版式不同 */
const {
  ratio,
  thumbFailed,
  onImgLoad,
  showThumb,
  thumbSrc,
  isDead,
  isAlbum,
  tagNames,
  title,
  desc,
  durationLabelText,
  fileLine,
  ratioText,
  figMeta,
  chanLabel,
  dateShort,
  archiveUrl,
  sourceUrl,
} = useMessageCard(() => props.message)

/* 显示偏好：瀑布流 = 本主题原生装裱（真实比例）；统一画布 = 4:3 + 托底（完整/裁剪随偏好） */
const { thumbMode } = useThumbMode()
const masonry = computed(() => thumbMode.value === 'masonry')
const thumbAspect = computed(() =>
  masonry.value ? (showThumb.value && !thumbFailed.value ? ratio.value : '16 / 10') : '16 / 9',
)
</script>

<template>
  <article
    class="card-root group flex cursor-pointer break-inside-avoid flex-col"
    :class="masonry ? 'mb-6' : ''"
    role="button"
    tabindex="0"
    :aria-label="'打开条目：' + title"
    @click="emit('open')"
    @keydown.enter.prevent="emit('open')"
    @keydown.space.prevent="emit('open')"
  >
    <!-- 装裱图版：白边 + 发丝线；文本/文件/音频等无原生缩略图类型走绘制封面（与标准后台一致，用户定稿） -->
    <div
      class="plate-el relative border bg-ink-surface p-2.5 transition-[border-color,box-shadow] duration-200"
      :class="isDead ? 'border-dashed border-ink-line' : 'border-ink-line'"
    >
      <div
        class="plate-box relative overflow-hidden"
        :class="!masonry && showThumb && !thumbFailed ? 'vthumb' : ''"
        :style="{ aspectRatio: thumbAspect }"
      >
        <img
          v-if="showThumb && !thumbFailed"
          v-img-fade
          :src="thumbSrc"
          :alt="'素材 #' + message.id"
          loading="lazy"
          class="h-full w-full transition-transform duration-300 group-hover:scale-[1.015]"
          :class="[masonry || thumbMode === 'crop' ? 'object-cover' : 'object-contain', isDead && 'opacity-40 grayscale']"
          @load="onImgLoad"
          @error="thumbFailed = true"
        />
        <div
          v-else
          class="flex h-full w-full flex-col items-center justify-center gap-2 bg-ink-raised text-steam-dim/70"
        >
          <div class="h-16 w-44">
            <MediaGlyph :type="message.media_type" :id="message.id" :file-name="message.file_name" />
          </div>
          <span
            v-if="fileLine"
            class="max-w-[85%] truncate px-3 text-center font-mono text-[10px] tracking-[0.14em]"
          >
            {{ fileLine }}
          </span>
        </div>

        <!-- 归属目标标识：多副本时一眼分辨来自哪个频道/群组 -->
        <span
          v-if="chanLabel"
          class="absolute left-2 top-2 z-[2] max-w-[75%] truncate rounded-sm border border-ink-line bg-ink-surface/90 px-2 py-0.5 font-mono text-[10px] text-steam"
        >
          {{ chanLabel }}
        </span>

        <!-- 比例角标：均匀网格主题（标准后台）固定高裁切时标示真实比例；默认隐藏 -->
        <span v-if="ratioText" class="plate-ratio hidden" aria-hidden="true">{{ ratioText }}</span>

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
    <div class="card-body flex flex-1 flex-col px-1 pt-3">
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

      <!-- 图签脚：频道 · 日期 / 标签 -->
      <div
        class="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 font-mono text-[10px] text-steam-dim"
        @click.stop
      >
        <span v-if="dateShort || chanLabel" class="shrink-0">
          {{ chanLabel }}<template v-if="dateShort"> · {{ dateShort }}</template>
        </span>
        <span v-if="message.tags.length" class="min-w-0 truncate">#{{ tagNames.join(' #') }}</span>
      </div>
      <!-- 链接与星级同行：标签再长也不把评级挤走 -->
      <div class="card-foot mt-1.5 flex items-center gap-3" @click.stop>
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
        <StarRating
          class="ml-auto shrink-0"
          :value="message.rating"
          size="sm"
          interactive
          @change="(n: number) => emit('rate', n)"
        />
      </div>
    </div>
  </article>
</template>
