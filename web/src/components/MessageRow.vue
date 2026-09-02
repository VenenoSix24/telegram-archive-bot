<script setup lang="ts">
import type { Message } from '@/lib/types'
import StarRating from '@/components/ui/StarRating.vue'
import MediaGlyph from '@/components/MediaGlyph.vue'
import { useMessageCard } from '@/composables/useMessageCard'

/*
 * 标准后台列表视图行：桌面双行布局；元信息按「媒体类型 → 频道（重点色）→
 * 标签 → 编号/文件」排布，手机端保持同一结构只收窄次要列。
 * 根用 div[role=button]：行内要嵌星级按钮，button 套 button 是非法嵌套。
 */
const props = defineProps<{ message: Message; selected?: boolean }>()
const emit = defineEmits<{ open: []; rate: [number] }>()

const {
  thumbFailed,
  onImgLoad,
  showThumb,
  thumbSrc,
  isDead,
  title,
  typeLabel,
  fileLine,
  chanLabel,
  dateShort,
} = useMessageCard(() => props.message)
</script>

<template>
  <div
    role="button"
    tabindex="0"
    :aria-label="'打开条目：' + title"
    class="flex w-full cursor-pointer items-center gap-3.5 border-b border-ink-line/60 px-3.5 py-2.5 text-left transition-colors last:border-b-0 hover:bg-ink-raised/70 focus-visible:outline-none"
    :class="selected ? 'bg-gold/5' : ''"
    @click="emit('open')"
    @keydown.enter.prevent="emit('open')"
    @keydown.space.prevent="emit('open')"
  >
    <!-- 缩略图：16:9 画布；图片深色托底完整展示，绘制封面跟随主题深浅色 -->
    <div
      class="aspect-video w-16 shrink-0 overflow-hidden rounded-lg border border-ink-line sm:w-20"
      :class="showThumb && !thumbFailed ? 'vthumb' : 'bg-ink-raised'"
    >
      <img
        v-if="showThumb && !thumbFailed"
        v-img-fade
        :src="thumbSrc"
        :alt="'素材 #' + message.id"
        loading="lazy"
        class="h-full w-full object-contain"
        :class="isDead && 'opacity-40 grayscale'"
        @load="onImgLoad"
        @error="thumbFailed = true"
      />
      <MediaGlyph
        v-else
        mini
        :type="message.media_type"
        :id="message.id"
        :file-name="message.file_name"
      />
    </div>

    <div class="min-w-0 flex-1">
      <!-- 行 1：标题 + 评分（窄屏显示星数，桌面右侧有可点的星级组） -->
      <div class="flex items-center gap-2">
        <p class="min-w-0 flex-1 truncate text-[13.5px] font-medium text-steam" :class="isDead && 'text-steam-dim line-through'">
          {{ title }}
        </p>
        <span
          v-if="message.rating"
          class="hidden shrink-0 font-mono text-[10.5px] text-gold min-[480px]:inline md:hidden"
        >
          ★ {{ message.rating }}
        </span>
      </div>
      <!-- 行 2：媒体类型 → 频道（重点色）→ 标签 → 编号/文件（次要列窄屏收起） -->
      <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-steam-dim">
        <span class="shrink-0 rounded bg-gold/10 px-1.5 py-px font-medium text-gold">{{ typeLabel }}</span>
        <span v-if="chanLabel" class="min-w-0 max-w-[9rem] truncate font-medium text-gold">{{ chanLabel }}</span>
        <span
          v-for="t in message.tags.slice(0, 2)"
          :key="t.name + t.type"
          class="min-w-0 max-w-[7.5rem] truncate rounded-full bg-ink-raised px-2 py-px"
        >
          #{{ t.name }}
        </span>
        <span class="hidden shrink-0 font-mono text-[10.5px] text-steam-dim/60 min-[480px]:inline">#{{ message.id }}</span>
        <span v-if="fileLine" class="hidden font-mono text-[10px] min-[480px]:inline">{{ fileLine }}</span>
        <span v-if="isDead" class="shrink-0 rounded border border-destructive/30 px-1.5 py-px text-destructive">已删除</span>
      </div>
    </div>

    <!-- 就地评分（桌面）：星级组可点，不触发行打开 -->
    <StarRating
      class="hidden shrink-0 md:inline-flex"
      :value="message.rating"
      size="sm"
      interactive
      @change="(n: number) => emit('rate', n)"
    />
    <span class="w-11 shrink-0 text-right font-mono text-[10.5px] tabular-nums text-steam-dim">
      {{ dateShort }}
    </span>
  </div>
</template>
