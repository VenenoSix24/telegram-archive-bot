import { computed } from 'vue'
import { currentTheme } from '@/composables/useTheme'

/**
 * 布局变体：素材志（编辑志排印，顶栏 + 目录栏）与标准后台（三栏资产库，
 * 侧栏 + 视图切换 + 常驻详情面板）。组件允许按变体分支「布局结构」；
 * 颜色与字体仍一律走 token（data-theme），组件不写具体色值。
 */
export type LayoutVariant = 'editorial' | 'vault'

export const variant = computed<LayoutVariant>(() =>
  currentTheme.value === 'minimal' ? 'vault' : 'editorial',
)
export const isVault = computed(() => variant.value === 'vault')

/**
 * 词汇表：同一概念在两个变体下的说法。
 * 素材志沿用编辑志词汇（图版/影像/辑册…），标准后台按用户定稿全面现代化
 * （图片/视频/相册/文件/文本/标签…）。只有真正随变体变化的词才进这里。
 */
const WORDS = {
  editorial: {
    photo: '图版',
    video: '影像',
    album: '辑册',
    document: '附件',
    text: '抄本',
    audio: '音频',
    voice: '语音',
    sticker: '贴纸',
    other: '其他',
    fallback: '归档',
    tag: '类目',
    rating: '评鉴',
    ratingHint: ['普通', '可留', '有用', '优质', '珍藏'] as const,
    ratingTapHint: '点击评鉴',
    unrated: '待评鉴',
    statusActive: '活跃',
    all: '全卷',
    noMatch: '查无此件',
    noMatchHint: '目录下没有匹配的条目，',
    reset: '重置目录',
    loading: '载入中…',
    searchPlaceholder: '检索本卷…',
    untitled: '无题',
    previewFailed: '图版加载失败',
    noPreview: '无图版',
  },
  vault: {
    photo: '图片',
    video: '视频',
    album: '相册',
    document: '文件',
    text: '文本',
    audio: '音频',
    voice: '语音',
    sticker: '贴纸',
    other: '其他',
    fallback: '归档',
    tag: '标签',
    rating: '评分',
    ratingHint: ['1 星', '2 星', '3 星', '4 星', '5 星'] as const,
    ratingTapHint: '点击评分',
    unrated: '未评分',
    statusActive: '正常',
    all: '全部',
    noMatch: '没有匹配的归档条目',
    noMatchHint: '换个关键词，或',
    reset: '清除筛选',
    loading: '加载中…',
    searchPlaceholder: '搜索归档、标签、文件名…',
    untitled: '未命名',
    previewFailed: '预览加载失败',
    noPreview: '无预览',
  },
} as const

export type Vocab = (typeof WORDS)[LayoutVariant]

const words = computed<Vocab>(() => WORDS[variant.value])

export function useVocab() {
  return words
}

/** 媒体类型 → 当前变体词汇。 */
export function typeLabel(v: Vocab, mediaType: string): string {
  const value = (v as unknown as Record<string, unknown>)[mediaType]
  return typeof value === 'string' ? value : v.fallback
}
