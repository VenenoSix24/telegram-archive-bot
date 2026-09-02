<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  ChevronDown,
  ChevronRight,
  Download,
  Loader2,
  MoveDown,
  MoveUp,
  Palette,
  Plus,
  RotateCcw,
  Save,
  Trash2,
  TriangleAlert,
  Upload,
  X,
} from 'lucide-vue-next'
import { backup, backupDownloadUrl, deleteBackup, getConfig, getStats, importBackup, listBackups, putConfig, resetDatabase, restoreBackup } from '@/lib/api'
import type { BackupItem, EditableConfig } from '@/lib/types'
import { isVault } from '@/lib/vocab'
import Button from '@/components/ui/Button.vue'
import Select from '@/components/ui/Select.vue'
import TagInput from '@/components/ui/TagInput.vue'
import { toastError, toastSuccess } from '@/composables/useToast'
import { displayChatId, sizeLabel } from '@/lib/format'
import { cn } from '@/lib/utils'
import {
  currentMode, currentTheme, setMode, setTheme,
  type Mode, type ThemeKey,
} from '@/composables/useTheme'
import { useThumbMode, type ThumbMode } from '@/composables/useDisplayPrefs'

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const openTargetMenu = ref<number | null>(null)
const opsBusy = ref(false)
const backups = ref<BackupItem[]>([])
const importKind = ref<'config' | 'database'>('config')
const importFile = ref<File | null>(null)

const templateBlocks = [
  { key: 'rating', label: '评级' },
  { key: 'tags', label: 'Tag' },
  { key: 'body', label: '正文' },
  { key: 'source', label: '来源链接' },
]

const themeOptions: { key: ThemeKey; label: string }[] = [
  { key: 'collection', label: '素材志（朱砂）' },
  { key: 'minimal', label: '标准后台（蓝灰）' },
]
const modeOptions: { key: Mode; label: string }[] = [
  { key: 'system', label: '跟随系统' },
  { key: 'dark', label: '深色' },
  { key: 'light', label: '浅色' },
]
const thumbnailMediaOptions = [
  { key: 'first_video' as const, label: '组内第一个视频' },
  { key: 'first' as const, label: '组内第一条媒体' },
]
const thumbnailSourceOptions = [
  { key: 'auto' as const, label: '自动（归档优先，源消息回退）' },
  { key: 'archive' as const, label: '归档频道' },
  { key: 'source' as const, label: '源消息' },
]

/* 显示偏好：缩略图展示三模式（纯前端，两套主题通用） */
const { thumbMode, setThumbMode } = useThumbMode()
const thumbModeOptions: { key: ThumbMode; label: string; hint: string }[] = [
  { key: 'fit', label: '完整展示', hint: '4:3 画布深色托底，竖图完整不裁' },
  { key: 'crop', label: '裁剪填充', hint: '全部裁满 4:3，卡片完全统一' },
  { key: 'masonry', label: '瀑布流', hint: '原始比例，高低错落' },
]

/** Vue reactive 代理无法 structuredClone，配置全是纯 JSON 结构，用 JSON 深拷贝。 */
function _clone<T>(input: T): T {
  return JSON.parse(JSON.stringify(input))
}

const form = reactive<EditableConfig>({
  source_chats: [],
  target_channels: [],
  forward_interval: 3,
  retry_count: 3,
  show_link: true,
  preserve_original: true,
  rating_enabled: true,
  admins: [],
  thumbnail_media: 'first_video' as 'first_video' | 'first',
  thumbnail_source: 'auto' as 'auto' | 'archive' | 'source',
  message_template: ['rating', 'tags', 'body', 'source'],
})

/** 最终落盘前不覆盖：保存改的是提交内容，页面状态独立 */
let saved: EditableConfig | null = null

/* 有改动才浮出保存栏，长表单不用滚到底找按钮 */
const dirty = computed(() => saved !== null && JSON.stringify(form) !== JSON.stringify(saved))

async function load() {
  error.value = ''
  try {
    const cfg = await getConfig()
    Object.assign(form, cfg)
    /* saved 必须从 form 克隆：接口响应的 key 顺序与 form 不同，
       直接存响应会导致 JSON 比对永远不等（进页面就误报有改动） */
    saved = _clone(form)
    await getStats() // 触发一次预热，顺带确认后端可用
    await loadBackups()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '配置读取失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function addSource() {
  form.source_chats.push({
    chat_id: null,
    name: '',
    default_tags: [],
    target_channel_ids: [],
    private: true,
  })
  expandedSource.value = form.source_chats.length - 1
}

/* 手风琴：一次只展开一个来源的编辑表单 */
const expandedSource = ref<number | null>(null)

/* 章节锚点：长表单快速跳转；标签随布局变体现代化 */
const anchors = computed(() => [
  { id: 'sec-theme', label: '外观' },
  { id: 'sec-sources', label: isVault.value ? '来源' : '输入' },
  { id: 'sec-targets', label: isVault.value ? '目标' : '输出' },
  { id: 'sec-template', label: isVault.value ? '模板' : '版式' },
  { id: 'sec-admin', label: '管理' },
  { id: 'sec-backups', label: '备份' },
])
function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function removeSource(idx: number) {
  form.source_chats.splice(idx, 1)
}

function addTarget() {
  form.target_channels.push({ chat_id: null, name: '', private: true })
  expandedTarget.value = form.target_channels.length - 1
}

/* 目标与来源同款手风琴 */
const expandedTarget = ref<number | null>(null)

function removeTarget(idx: number) {
  const removed = form.target_channels[idx]?.chat_id
  form.target_channels.splice(idx, 1)
  if (expandedTarget.value === idx) expandedTarget.value = null
  if (removed != null) {
    for (const source of form.source_chats) {
      source.target_channel_ids = source.target_channel_ids.filter((id) => id !== removed)
    }
  }
}

function addAdmin() {
  form.admins.push(0)
}

function removeAdmin(idx: number) {
  form.admins.splice(idx, 1)
}

function targetLabel(target: { chat_id: number | null; name: string }, fallback = '未命名目标') {
  return target.name || (target.chat_id == null ? fallback : `目标 ${displayChatId(target.chat_id)}`)
}

// 目标频道下拉：点击菜单外任意位置关闭，不必再点一次按钮
function onDocumentClick(event: MouseEvent) {
  const node = event.target as HTMLElement | null
  if (!node?.closest('[data-target-menu]')) openTargetMenu.value = null
}
onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

function toggleTarget(source: EditableConfig['source_chats'][number], id: number | null) {
  if (id == null) return
  const selected = source.target_channel_ids.includes(id)
  source.target_channel_ids = selected
    ? source.target_channel_ids.filter((targetId) => targetId !== id)
    : [...source.target_channel_ids, id]
}

function resetName(item: { name: string }) {
  item.name = ''
}

function moveTemplateBlock(index: number, direction: -1 | 1) {
  const next = index + direction
  if (next < 0 || next >= form.message_template.length) return
  const layout = [...form.message_template]
  ;[layout[index], layout[next]] = [layout[next], layout[index]]
  form.message_template = layout
}

function toggleTemplateBlock(key: string) {
  if (key === 'body') return
  form.message_template = form.message_template.includes(key)
    ? form.message_template.filter((block) => block !== key)
    : [...form.message_template, key]
}

function templatePreviewBlock(key: string) {
  return {
    rating: '推荐指数：⭐⭐⭐⭐',
    tags: '#游戏 #MOD',
    body: '示例正文：<b>粗体内容</b> 与链接',
    source: '来自：\nhttps://t.me/example/123',
  }[key] || ''
}

function backupDate(item: BackupItem) {
  return item.created_at.slice(0, 10)
}

/* 备份按类型折叠：平时收起只看计数，操作都在行内 */
const openGroups = ref({ config: false, database: false })
const configBackups = computed(() => backups.value.filter((item) => item.kind === 'config'))
const databaseBackups = computed(() => backups.value.filter((item) => item.kind === 'database'))

function selectImportFile(event: Event) {
  importFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

async function save() {
  // 来源会话 ID 必填；收集缺项提示，而不是默默写坏配置
  if (!form.target_channels.length || form.target_channels.some((target) => !target.chat_id)) {
    error.value = '请至少配置一个有效的目标'
    toastError(error.value)
    return
  }
  const empty = form.source_chats.filter((s) => !s.chat_id)
  if (empty.length) {
    error.value = `${empty.length} 个来源缺少会话 ID，保存被取消`
    toastError(error.value)
    return
  }
  saving.value = true
  error.value = ''
  try {
    const updated = await putConfig(_clone(form))
    Object.assign(form, updated)
    saved = _clone(form)
    toastSuccess('已保存，重启进程后生效')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
    toastError(error.value)
  } finally {
    saving.value = false
  }
}

function reset() {
  if (saved) Object.assign(form, _clone(saved))
}

async function loadBackups() {
  try {
    backups.value = (await listBackups()).items
  } catch (e) {
    toastError(e instanceof Error ? e.message : '无法读取备份')
  }
}

async function backupItem(kind: 'config' | 'database') {
  opsBusy.value = true
  try {
    const result = await backup(kind)
    toastSuccess(`备份已创建：${result.backup.name}`)
    await loadBackups()
  } catch (e) {
    toastError(e instanceof Error ? e.message : '备份失败')
  } finally {
    opsBusy.value = false
  }
}

async function restoreItem(item: BackupItem) {
  if (!window.confirm(`确认恢复 ${item.name}？当前文件会先自动备份。`)) return
  opsBusy.value = true
  try {
    const result = await restoreBackup(item.name)
    toastSuccess(`${result.kind === 'database' ? '数据库' : '配置'}已恢复，请重启进程`)
    await loadBackups()
  } catch (e) {
    toastError(e instanceof Error ? e.message : '恢复失败')
  } finally {
    opsBusy.value = false
  }
}

async function deleteItem(item: BackupItem) {
  if (!window.confirm(`确认删除备份 ${item.name}？删除后不可恢复。`)) return
  opsBusy.value = true
  try {
    await deleteBackup(item.name)
    toastSuccess('备份已删除')
    await loadBackups()
  } catch (e) {
    toastError(e instanceof Error ? e.message : '删除失败')
  } finally {
    opsBusy.value = false
  }
}

async function importSelectedBackup() {
  if (!importFile.value) return
  if (!window.confirm(`确认导入${importKind.value === 'database' ? '数据库' : '配置'}备份？当前文件会先自动备份。`)) return
  opsBusy.value = true
  try {
    const result = await importBackup(importKind.value, importFile.value)
    toastSuccess(`${result.kind === 'database' ? '数据库' : '配置'}已导入，请重启进程`)
    importFile.value = null
    await loadBackups()
  } catch (e) {
    toastError(e instanceof Error ? e.message : '导入失败')
  } finally {
    opsBusy.value = false
  }
}

async function resetDb() {
  if (!window.confirm('确认重置数据库？所有归档记录将被清空，且操作前会自动备份。')) return
  opsBusy.value = true
  try {
    await resetDatabase()
    toastSuccess('数据库已重置，请重启进程')
  } catch (e) {
    toastError(e instanceof Error ? e.message : '数据库重置失败')
  } finally {
    opsBusy.value = false
  }
}
</script>

<template>
  <div class="mx-auto px-4 py-8 pb-28 sm:px-6" :class="isVault ? 'max-w-5xl' : 'max-w-4xl'">
    <header class="mb-5">
      <h1 class="font-display text-2xl font-bold text-steam min-[480px]:text-3xl" :class="isVault ? 'tracking-normal' : 'tracking-[0.18em]'">
        {{ isVault ? '设置' : '设 置' }}
      </h1>
      <p v-if="!isVault" class="mt-2 font-mono text-[10.5px] tracking-[0.3em] text-steam-dim">COLOPHON</p>
      <p v-else class="mt-1 font-mono text-[10px] tracking-[0.14em] text-steam-dim/60">SETTINGS</p>
    </header>

    <!-- 章节锚点：长表单快速跳转 -->
    <nav class="mb-7 flex flex-wrap gap-2" aria-label="章节导航">
      <button
        v-for="a in anchors"
        :key="a.id"
        type="button"
        class="cursor-pointer rounded-full border border-ink-line px-3 py-1 text-xs text-steam-dim transition-colors hover:border-gold hover:text-gold"
        @click="scrollToSection(a.id)"
      >
        {{ a.label }}
      </button>
    </nav>

    <!-- 骨架 -->
    <div v-if="loading" class="space-y-6" aria-hidden="true">
      <div v-for="i in 4" :key="i" class="rounded-xl border border-ink-line p-4">
        <div class="h-3.5 w-32 animate-pulse bg-ink-raised" />
        <div class="mt-4 h-9 animate-pulse bg-ink-raised" />
      </div>
    </div>

    <template v-else>
      <p v-if="error && !form.target_channels" role="alert" class="mb-4 break-words text-sm leading-5 text-destructive">
        {{ error }} <button type="button" class="cursor-pointer underline underline-offset-4" @click="load">重试</button>
      </p>

      <!-- 外观：纯前端即时生效，放最前 -->
      <section id="sec-theme" class="mb-8 scroll-mt-20">
        <div class="mb-4 flex items-baseline gap-3 border-b border-ink-line pb-2">
          <Palette class="h-3.5 w-3.5 self-center text-gold" />
          <h2 class="font-display text-base font-bold text-steam" :class="isVault ? 'tracking-normal' : 'tracking-[0.2em]'">外观</h2>
          <span class="font-mono text-[9px] tracking-[0.26em] text-steam-dim">THEME</span>
          <span class="ml-auto font-mono text-[9px] text-steam-dim/70">即时生效</span>
        </div>
        <div class="grid gap-5 sm:grid-cols-2">
          <div>
            <p class="mb-2 text-xs text-steam-dim">配色主题</p>
            <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="配色主题">
              <button
                v-for="t in themeOptions"
                :key="t.key"
                type="button"
                role="radio"
                :aria-checked="currentTheme === t.key"
                :class="cn(
                  'cursor-pointer rounded-full border px-3 py-1.5 text-sm transition-colors',
                  currentTheme === t.key
                    ? 'border-gold text-gold'
                    : 'border-ink-line text-steam-dim hover:text-steam',
                )"
                @click="setTheme(t.key)"
              >
                {{ t.label }}
              </button>
            </div>
            <p class="mt-2 text-xs text-steam-dim/70">暗房印样已定稿待实现。</p>
          </div>
          <div>
            <p class="mb-2 text-xs text-steam-dim">明暗模式</p>
            <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="明暗模式">
              <button
                v-for="m in modeOptions"
                :key="m.key"
                type="button"
                role="radio"
                :aria-checked="currentMode === m.key"
                :class="cn(
                  'cursor-pointer rounded-full border px-3 py-1.5 text-sm transition-colors',
                  currentMode === m.key
                    ? 'border-gold text-gold'
                    : 'border-ink-line text-steam-dim hover:text-steam',
                )"
                @click="setMode(m.key)"
              >
                {{ m.label }}
              </button>
            </div>
          </div>
        </div>

        <!-- 缩略图展示：显示偏好，两套主题通用 -->
        <div class="mt-6">
          <p class="mb-2 text-xs text-steam-dim">缩略图展示</p>
          <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="缩略图展示">
            <button
              v-for="opt in thumbModeOptions"
              :key="opt.key"
              type="button"
              role="radio"
              :aria-checked="thumbMode === opt.key"
              :class="cn(
                'cursor-pointer rounded-full border px-3 py-1.5 text-sm transition-colors',
                thumbMode === opt.key
                  ? 'border-gold text-gold'
                  : 'border-ink-line text-steam-dim hover:text-steam',
              )"
              @click="setThumbMode(opt.key)"
            >
              {{ opt.label }}
            </button>
          </div>
          <p class="mt-2 text-xs text-steam-dim/70">
            {{ thumbModeOptions.find((opt) => opt.key === thumbMode)?.hint }}。即时生效，按主题独立记忆——切主题自动切到该主题的上次选择；未选择过时取主题默认（素材志瀑布流 / 标准后台完整展示）。
          </p>
        </div>
      </section>

      <form @submit.prevent="save">
        <!-- 一 · 输入：列表行 + 展开编辑 -->
        <section id="sec-sources" class="mb-8 scroll-mt-20">
          <div class="mb-4 flex items-baseline gap-3 border-b border-ink-line pb-2">
            <span v-if="!isVault" class="font-display text-sm font-bold text-gold">一</span>
            <h2 class="font-display text-base font-bold text-steam" :class="isVault ? 'tracking-normal' : 'tracking-[0.2em]'">
              {{ isVault ? '来源' : '输入 · 来源' }}
            </h2>
            <span class="font-mono text-[9px] tracking-[0.26em] text-steam-dim">SOURCES</span>
            <Button type="button" variant="secondary" size="sm" class="ml-auto" @click="addSource">
              <Plus class="h-3.5 w-3.5" /> 新增
            </Button>
          </div>

          <div v-for="(s, i) in form.source_chats" :key="i" class="mb-2 overflow-hidden rounded-xl border border-ink-line bg-ink-surface">
            <!-- 收起态：概要行，一眼看清有几个源、各自接什么 -->
            <button
              type="button"
              class="flex w-full cursor-pointer items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-ink-raised/50"
              :aria-expanded="expandedSource === i"
              @click="expandedSource = expandedSource === i ? null : i"
            >
              <component :is="expandedSource === i ? ChevronDown : ChevronRight" class="h-4 w-4 shrink-0 text-steam-dim" />
              <span class="min-w-0 truncate text-sm font-medium text-steam">{{ s.name || `来源 ${i + 1}` }}</span>
              <span v-if="s.chat_id != null" class="hidden shrink-0 font-mono text-[10px] text-steam-dim sm:inline">
                {{ displayChatId(s.chat_id) }}
              </span>
              <span class="ml-auto shrink-0 font-mono text-[10px] text-steam-dim">
                {{ s.default_tags.length }} 个默认 tag · {{ s.target_channel_ids.length ? `${s.target_channel_ids.length} 个目标` : '全部目标' }}
              </span>
            </button>

            <!-- 展开态：编辑表单，字段配常驻说明 -->
            <div v-if="expandedSource === i" class="border-t border-ink-line px-4 py-4">
              <div class="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
                <div class="min-w-0">
                  <label class="mb-1 block text-xs text-steam-dim" :for="`src-chat-${i}`">会话 ID（必填）</label>
                  <input
                    :id="`src-chat-${i}`"
                    v-model.number="s.chat_id"
                    type="number"
                    placeholder="例如 123456789"
                    class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                    :aria-label="`来源 ${i + 1} 会话 ID`"
                  />
                  <p class="mt-1 text-xs text-steam-dim/70">Telegram 会话 ID，群组或频道均可；在会话里发送 /id 即可查询。</p>
                  <label class="mt-2.5 flex items-center gap-2 text-xs text-steam-dim">
                    <input v-model="s.private" type="checkbox" class="h-4 w-4 accent-gold" /> 私密频道
                  </label>
                </div>
                <div class="min-w-0">
                  <label class="mb-1 block text-xs text-steam-dim" :for="`src-name-${i}`">名称</label>
                  <div class="flex gap-1.5">
                    <input
                      :id="`src-name-${i}`"
                      v-model="s.name"
                      type="text"
                      placeholder="留空自动获取"
                      class="h-9 min-w-0 flex-1 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                      :aria-label="`来源 ${i + 1} 名称`"
                    />
                    <button
                      v-if="s.name"
                      type="button"
                      class="cursor-pointer rounded-md border border-ink-line px-2 text-steam-dim hover:text-steam"
                      :aria-label="`重置来源 ${i + 1} 名称`"
                      title="恢复自动名称"
                      @click="resetName(s)"
                    >
                      <X class="h-4 w-4" />
                    </button>
                  </div>
                  <p class="mt-1 text-xs text-steam-dim/70">留空则自动获取 Telegram 会话名，也可自定义备注名。</p>
                </div>
                <div class="min-w-0">
                  <span class="mb-1 block text-xs text-steam-dim">默认 Tag</span>
                  <TagInput v-model="s.default_tags" />
                  <p class="mt-1 text-xs text-steam-dim/70">来自此来源的素材尚未打标时，自动加注这些标签。</p>
                </div>
                <div class="min-w-0">
                  <span class="mb-1 block text-xs text-steam-dim">目标频道</span>
                  <div class="relative" data-target-menu>
                    <button
                      type="button"
                      class="flex h-9 w-full cursor-pointer items-center justify-between gap-2 rounded-md border border-ink-line bg-ink-raised px-3 text-left text-sm text-steam focus:border-gold focus:outline-none"
                      :aria-expanded="openTargetMenu === i"
                      :aria-label="`来源 ${i + 1} 目标`"
                      @click="openTargetMenu = openTargetMenu === i ? null : i"
                    >
                      <span class="truncate">
                        {{ s.target_channel_ids.length ? `${s.target_channel_ids.length} 个目标` : '全部目标' }}
                      </span>
                      <ChevronDown class="h-4 w-4 shrink-0 text-steam-dim" />
                    </button>
                    <div v-if="openTargetMenu === i" class="absolute left-0 right-0 z-20 mt-1 max-h-56 overflow-auto rounded-md border border-ink-line bg-ink-surface p-1 shadow-lg">
                      <button
                        v-for="target in form.target_channels"
                        :key="String(target.chat_id)"
                        type="button"
                        class="flex w-full cursor-pointer items-center gap-2 rounded px-2 py-2 text-left text-sm hover:bg-ink-raised"
                        @click="toggleTarget(s, target.chat_id)"
                      >
                        <span class="flex h-4 w-4 items-center justify-center rounded border border-ink-line text-xs" :class="s.target_channel_ids.includes(target.chat_id as number) ? 'border-gold bg-gold text-ink' : ''">{{ s.target_channel_ids.includes(target.chat_id as number) ? '✓' : '' }}</span>
                        <span class="truncate">{{ targetLabel(target) }}</span>
                      </button>
                      <p v-if="!form.target_channels.length" class="px-2 py-2 text-xs text-steam-dim">请先在「输出」章节添加目标</p>
                    </div>
                  </div>
                  <p class="mt-1 text-xs text-steam-dim/70">不选则归档到全部目标频道。</p>
                </div>
              </div>
              <button
                type="button"
                class="mt-4 inline-flex cursor-pointer items-center gap-1.5 text-xs text-steam-dim transition-colors hover:text-destructive"
                @click="expandedSource = null; removeSource(i)"
              >
                <Trash2 class="h-3.5 w-3.5" /> 删除此来源
              </button>
            </div>
          </div>
          <p v-if="!form.source_chats.length" class="text-xs text-steam-dim">还没有来源，点击右上「新增」接入（群组或频道均可）。</p>
        </section>

        <!-- 二 · 输出 -->
        <section id="sec-targets" class="mb-8 scroll-mt-20">
          <div class="mb-4 flex items-baseline gap-3 border-b border-ink-line pb-2">
            <span v-if="!isVault" class="font-display text-sm font-bold text-gold">二</span>
            <h2 class="font-display text-base font-bold text-steam" :class="isVault ? 'tracking-normal' : 'tracking-[0.2em]'">
              {{ isVault ? '目标' : '输出 · 目标' }}
            </h2>
            <span class="font-mono text-[9px] tracking-[0.26em] text-steam-dim">TARGETS</span>
            <Button type="button" variant="secondary" size="sm" class="ml-auto" @click="addTarget">
              <Plus class="h-3.5 w-3.5" /> 新增
            </Button>
          </div>
          <!-- 与来源同款：概要行 + 手风琴展开编辑 -->
          <div v-for="(target, i) in form.target_channels" :key="i" class="mb-2 overflow-hidden rounded-xl border border-ink-line bg-ink-surface">
            <button
              type="button"
              class="flex w-full cursor-pointer items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-ink-raised/50"
              :aria-expanded="expandedTarget === i"
              @click="expandedTarget = expandedTarget === i ? null : i"
            >
              <component :is="expandedTarget === i ? ChevronDown : ChevronRight" class="h-4 w-4 shrink-0 text-steam-dim" />
              <span class="min-w-0 truncate text-sm font-medium text-steam">{{ target.name || `目标 ${i + 1}` }}</span>
              <span v-if="target.chat_id != null" class="hidden shrink-0 font-mono text-[10px] text-steam-dim sm:inline">
                {{ displayChatId(target.chat_id) }}
              </span>
              <span class="ml-auto shrink-0 font-mono text-[10px] text-steam-dim">
                {{ target.private ? '私密' : '公开' }}
              </span>
            </button>

            <div v-if="expandedTarget === i" class="border-t border-ink-line px-4 py-4">
              <div class="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
                <div class="min-w-0">
                  <label class="mb-1 block text-xs text-steam-dim" :for="`tgt-chat-${i}`">会话 ID（必填）</label>
                  <input
                    :id="`tgt-chat-${i}`"
                    v-model.number="target.chat_id"
                    type="number"
                    placeholder="例如 -100111222333"
                    class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                    :aria-label="`目标 ${i + 1} 会话 ID`"
                  />
                  <p class="mt-1 text-xs text-steam-dim/70">Telegram 会话 ID，频道或群组均可；发送 /id 即可查询。</p>
                  <label class="mt-2.5 flex items-center gap-2 text-xs text-steam-dim">
                    <input v-model="target.private" type="checkbox" class="h-4 w-4 accent-gold" /> 私密会话
                  </label>
                </div>
                <div class="min-w-0">
                  <label class="mb-1 block text-xs text-steam-dim" :for="`tgt-name-${i}`">名称</label>
                  <div class="flex gap-1.5">
                    <input
                      :id="`tgt-name-${i}`"
                      v-model="target.name"
                      type="text"
                      placeholder="留空自动获取"
                      class="h-9 min-w-0 flex-1 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                      :aria-label="`目标 ${i + 1} 名称`"
                    />
                    <button
                      v-if="target.name"
                      type="button"
                      class="cursor-pointer rounded-md border border-ink-line px-2 text-steam-dim hover:text-steam"
                      :aria-label="`重置目标 ${i + 1} 名称`"
                      title="恢复自动名称"
                      @click="resetName(target)"
                    >
                      <X class="h-4 w-4" />
                    </button>
                  </div>
                  <p class="mt-1 text-xs text-steam-dim/70">留空则自动获取 Telegram 会话名，也可自定义备注名。</p>
                </div>
              </div>
              <button
                type="button"
                class="mt-4 inline-flex cursor-pointer items-center gap-1.5 text-xs text-steam-dim transition-colors hover:text-destructive"
                @click="expandedTarget = null; removeTarget(i)"
              >
                <Trash2 class="h-3.5 w-3.5" /> 删除此目标
              </button>
            </div>
          </div>
          <p v-if="!form.target_channels.length" class="text-xs text-steam-dim">还没有目标，点击右上「新增」接入（频道或群组均可）。</p>
          <p class="mt-2 text-xs text-steam-dim/80">来源未单独指定目标时，将归档到全部目标。</p>
        </section>

        <!-- 三 · 版式 -->
        <section id="sec-template" class="mb-8 scroll-mt-20">
          <div class="mb-4 flex items-baseline gap-3 border-b border-ink-line pb-2">
            <span v-if="!isVault" class="font-display text-sm font-bold text-gold">三</span>
            <h2 class="font-display text-base font-bold text-steam" :class="isVault ? 'tracking-normal' : 'tracking-[0.2em]'">
              {{ isVault ? '模板与发送' : '版式 · 模板与发送' }}
            </h2>
            <span class="font-mono text-[9px] tracking-[0.26em] text-steam-dim">TEMPLATE</span>
          </div>

          <div class="mb-5 rounded-xl border border-ink-line bg-ink-surface p-4">
            <h3 class="mb-1 text-sm font-medium text-steam">归档消息模板</h3>
            <p class="mb-3 text-xs leading-5 text-steam-dim">调整区块顺序或隐藏可选区块。保存后仅影响新归档的消息，已有素材保持原样。</p>
            <div class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(12rem,.8fr)]">
              <div class="space-y-1.5">
                <div v-for="(key, index) in form.message_template" :key="key" class="flex items-center gap-2 rounded-md border border-ink-line bg-ink-raised px-2 py-1.5">
                  <span class="min-w-0 flex-1 text-sm text-steam">{{ templateBlocks.find((block) => block.key === key)?.label }}</span>
                  <button type="button" class="cursor-pointer rounded p-1 text-steam-dim hover:bg-ink-line hover:text-steam disabled:opacity-40" :disabled="index === 0" :aria-label="`上移 ${key}`" @click="moveTemplateBlock(index, -1)"><MoveUp class="h-4 w-4" /></button>
                  <button type="button" class="cursor-pointer rounded p-1 text-steam-dim hover:bg-ink-line hover:text-steam disabled:opacity-40" :disabled="index === form.message_template.length - 1" :aria-label="`下移 ${key}`" @click="moveTemplateBlock(index, 1)"><MoveDown class="h-4 w-4" /></button>
                  <button v-if="key !== 'body'" type="button" class="cursor-pointer rounded p-1 text-steam-dim hover:bg-destructive/20 hover:text-destructive" :aria-label="`隐藏 ${key}`" @click="toggleTemplateBlock(key)"><X class="h-4 w-4" /></button>
                </div>
                <div class="flex flex-wrap gap-1.5 pt-1">
                  <button v-for="block in templateBlocks.filter((block) => !form.message_template.includes(block.key))" :key="block.key" type="button" class="cursor-pointer rounded-md border border-dashed border-ink-line px-2 py-1 text-xs text-steam-dim hover:border-gold hover:text-gold" @click="toggleTemplateBlock(block.key)">显示 {{ block.label }}</button>
                </div>
              </div>
              <div class="rounded-md border border-ink-line bg-ink-raised/50 p-3">
                <p class="mb-2 text-xs text-steam-dim">新消息预览</p>
                <div class="whitespace-pre-wrap text-sm leading-relaxed text-steam">
                  <template v-for="(key, index) in form.message_template" :key="key">
                    <span v-if="index">{{ '\n\n' }}</span>{{ templatePreviewBlock(key) }}
                  </template>
                </div>
              </div>
            </div>
          </div>

          <div class="mb-5 rounded-xl border border-ink-line bg-ink-surface p-4">
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <label class="mb-1 block text-xs text-steam-dim" for="fwd-interval">发送间隔（秒）</label>
                <input
                  id="fwd-interval"
                  v-model.number="form.forward_interval"
                  type="number"
                  min="0.5"
                  step="0.5"
                  class="h-9 w-full rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam focus:border-gold focus:outline-none"
                />
                <p class="mt-1 text-xs text-steam-dim/70">两条归档之间的最小间隔，防频控；0.5 起步。</p>
              </div>
              <div>
                <label class="mb-1 block text-xs text-steam-dim" for="retry">失败重试次数</label>
                <input
                  id="retry"
                  v-model.number="form.retry_count"
                  type="number"
                  min="0"
                  class="h-9 w-full rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam focus:border-gold focus:outline-none"
                />
                <p class="mt-1 text-xs text-steam-dim/70">单条归档失败后的自动重试上限，0 表示不重试。</p>
              </div>
            </div>
            <div class="mt-4 grid gap-2 sm:grid-cols-3">
              <label class="flex items-center gap-2 text-sm text-steam">
                <input v-model="form.show_link" type="checkbox" class="h-4 w-4 accent-gold" />
                显示「来自：」来源链接
              </label>
              <label class="flex items-center gap-2 text-sm text-steam">
                <input v-model="form.preserve_original" type="checkbox" class="h-4 w-4 accent-gold" />
                保留原消息 hashtag
              </label>
              <label class="flex items-center gap-2 text-sm text-steam">
                <input v-model="form.rating_enabled" type="checkbox" class="h-4 w-4 accent-gold" />
                启用 Rating
              </label>
            </div>
          </div>

          <div class="rounded-xl border border-ink-line bg-ink-surface p-4">
            <h3 class="mb-3 text-sm font-medium text-steam">缩略图</h3>
            <div class="grid gap-4 sm:grid-cols-2">
              <label class="min-w-0">
                <span class="mb-1 block text-xs text-steam-dim">Album 缩略图媒体</span>
                <Select v-model="form.thumbnail_media" class="w-full">
                  <option v-for="option in thumbnailMediaOptions" :key="option.key" :value="option.key">{{ option.label }}</option>
                </Select>
              </label>
              <label class="min-w-0">
                <span class="mb-1 block text-xs text-steam-dim">缩略图来源</span>
                <Select v-model="form.thumbnail_source" class="w-full">
                  <option v-for="option in thumbnailSourceOptions" :key="option.key" :value="option.key">{{ option.label }}</option>
                </Select>
              </label>
            </div>
          </div>
        </section>

        <!-- 四 · 管理 -->
        <section id="sec-admin" class="mb-8 scroll-mt-20">
          <div class="mb-4 flex items-baseline gap-3 border-b border-ink-line pb-2">
            <span v-if="!isVault" class="font-display text-sm font-bold text-gold">四</span>
            <h2 class="font-display text-base font-bold text-steam" :class="isVault ? 'tracking-normal' : 'tracking-[0.2em]'">
              {{ isVault ? '管理' : '管理 · 权限与检索' }}
            </h2>
            <span class="font-mono text-[9px] tracking-[0.26em] text-steam-dim">ADMIN</span>
          </div>
          <div class="rounded-xl border border-ink-line bg-ink-surface p-4">
            <div class="mb-2 flex items-center justify-between">
              <h3 class="text-sm font-medium text-steam">管理员 ID</h3>
              <Button type="button" variant="secondary" size="sm" @click="addAdmin">
                <Plus class="h-3.5 w-3.5" /> 新增
              </Button>
            </div>
            <p class="mb-3 text-xs text-steam-dim/70">在源群里发指令（/status /tag /rating 等）仅对这些用户生效。</p>
            <div v-for="(a, i) in form.admins" :key="i" class="mb-2 flex items-center gap-2">
              <input
                v-model.number="form.admins[i]"
                type="number"
                placeholder="User ID"
                class="h-9 w-full cursor-pointer rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
              />
              <button
                type="button"
                class="cursor-pointer rounded-md p-2 text-steam-dim transition-colors hover:bg-destructive/20 hover:text-destructive"
                :aria-label="`删除管理员 ${i + 1}`"
                @click="removeAdmin(i)"
              >
                <Trash2 class="h-4 w-4" />
              </button>
            </div>
          </div>
        </section>

        <!-- 五 · 备份与维护 -->
        <section id="sec-backups" class="mb-8 scroll-mt-20">
          <div class="mb-4 flex items-baseline gap-3 border-b border-ink-line pb-2">
            <span v-if="!isVault" class="font-display text-sm font-bold text-gold">五</span>
            <h2 class="font-display text-base font-bold text-steam" :class="isVault ? 'tracking-normal' : 'tracking-[0.2em]'">
              {{ isVault ? '备份与维护' : '备份 · 维护' }}
            </h2>
            <span class="font-mono text-[9px] tracking-[0.26em] text-steam-dim">BACKUPS</span>
          </div>

          <div class="rounded-xl border border-ink-line bg-ink-surface p-4">
            <p class="mb-3 text-xs leading-5 text-steam-dim">
              恢复与导入前都会先自动备份当前文件，完成后需重启进程。备份可下载保存到本地，也可单个删除。
            </p>
            <div class="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" size="sm" :disabled="opsBusy" @click="backupItem('config')">备份配置</Button>
              <Button type="button" variant="secondary" size="sm" :disabled="opsBusy" @click="backupItem('database')">备份数据库</Button>
            </div>

            <!-- 配置备份折叠组 -->
            <div class="mt-4 border-t border-ink-line pt-1">
              <button
                type="button"
                class="flex w-full cursor-pointer items-center gap-2 py-2.5 text-left text-sm text-steam transition-colors hover:text-gold"
                :aria-expanded="openGroups.config"
                @click="openGroups.config = !openGroups.config"
              >
                <component :is="openGroups.config ? ChevronDown : ChevronRight" class="h-4 w-4 text-steam-dim" />
                配置备份
                <span class="font-mono text-xs text-steam-dim">{{ configBackups.length }}</span>
              </button>
              <ul v-if="openGroups.config && configBackups.length" class="divide-y divide-ink-line pb-2">
                <li v-for="item in configBackups" :key="item.name" class="flex items-center gap-2 py-2">
                  <div class="min-w-0 flex-1">
                    <p class="truncate font-mono text-[11px] text-steam">{{ item.name }}</p>
                    <p class="font-mono text-[9px] text-steam-dim">{{ backupDate(item) }} · {{ sizeLabel(item.size) }}</p>
                  </div>
                  <a :href="backupDownloadUrl(item.name)" class="shrink-0 cursor-pointer p-1.5 text-steam-dim transition-colors hover:text-gold" :aria-label="`下载 ${item.name}`" title="下载">
                    <Download class="h-4 w-4" />
                  </a>
                  <button type="button" class="shrink-0 cursor-pointer p-1.5 text-steam-dim transition-colors hover:text-gold" :aria-label="`恢复 ${item.name}`" title="恢复" @click="restoreItem(item)">
                    <RotateCcw class="h-4 w-4" />
                  </button>
                  <button type="button" class="shrink-0 cursor-pointer p-1.5 text-steam-dim transition-colors hover:text-destructive" :aria-label="`删除 ${item.name}`" title="删除" @click="deleteItem(item)">
                    <Trash2 class="h-4 w-4" />
                  </button>
                </li>
              </ul>
              <p v-else-if="openGroups.config" class="pb-2 text-xs text-steam-dim">暂无配置备份</p>
            </div>

            <!-- 数据库备份折叠组 -->
            <div class="border-t border-ink-line pt-1">
              <button
                type="button"
                class="flex w-full cursor-pointer items-center gap-2 py-2.5 text-left text-sm text-steam transition-colors hover:text-gold"
                :aria-expanded="openGroups.database"
                @click="openGroups.database = !openGroups.database"
              >
                <component :is="openGroups.database ? ChevronDown : ChevronRight" class="h-4 w-4 text-steam-dim" />
                数据库备份
                <span class="font-mono text-xs text-steam-dim">{{ databaseBackups.length }}</span>
              </button>
              <ul v-if="openGroups.database && databaseBackups.length" class="divide-y divide-ink-line pb-2">
                <li v-for="item in databaseBackups" :key="item.name" class="flex items-center gap-2 py-2">
                  <div class="min-w-0 flex-1">
                    <p class="truncate font-mono text-[11px] text-steam">{{ item.name }}</p>
                    <p class="font-mono text-[9px] text-steam-dim">{{ backupDate(item) }} · {{ sizeLabel(item.size) }}</p>
                  </div>
                  <a :href="backupDownloadUrl(item.name)" class="shrink-0 cursor-pointer p-1.5 text-steam-dim transition-colors hover:text-gold" :aria-label="`下载 ${item.name}`" title="下载">
                    <Download class="h-4 w-4" />
                  </a>
                  <button type="button" class="shrink-0 cursor-pointer p-1.5 text-steam-dim transition-colors hover:text-gold" :aria-label="`恢复 ${item.name}`" title="恢复" @click="restoreItem(item)">
                    <RotateCcw class="h-4 w-4" />
                  </button>
                  <button type="button" class="shrink-0 cursor-pointer p-1.5 text-steam-dim transition-colors hover:text-destructive" :aria-label="`删除 ${item.name}`" title="删除" @click="deleteItem(item)">
                    <Trash2 class="h-4 w-4" />
                  </button>
                </li>
              </ul>
              <p v-else-if="openGroups.database" class="pb-2 text-xs text-steam-dim">暂无数据库备份</p>
            </div>

            <!-- 从本地导入 -->
            <div class="border-t border-ink-line pt-3">
              <p class="mb-2 text-xs text-steam-dim">从本地导入</p>
              <div class="flex flex-wrap items-center gap-2">
                <Select v-model="importKind" aria-label="导入备份类型">
                  <option value="config">配置文件</option>
                  <option value="database">数据库</option>
                </Select>
                <input type="file" class="min-w-0 text-xs text-steam-dim file:mr-2 file:cursor-pointer file:rounded-md file:border-0 file:bg-ink-raised file:px-2 file:py-1.5 file:text-xs file:text-steam hover:file:bg-ink-line" accept=".bak,.yaml,.yml,.sqlite,.db" @change="selectImportFile" />
                <Button type="button" variant="secondary" size="sm" :disabled="opsBusy || !importFile" @click="importSelectedBackup"><Upload class="h-3.5 w-3.5" /> 导入</Button>
              </div>
            </div>
          </div>

          <!-- 危险区：与常规操作隔离 -->
          <div class="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-destructive/40 bg-destructive/5 p-4">
            <TriangleAlert class="h-4 w-4 shrink-0 text-destructive" />
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-destructive">重置数据库</p>
              <p class="text-xs text-steam-dim">清空全部归档记录，操作前自动备份，完成后需重启进程。</p>
            </div>
            <Button type="button" variant="destructive" size="sm" :disabled="opsBusy" @click="resetDb">重置…</Button>
          </div>
        </section>

        <p v-if="error && form.target_channels" role="alert" class="mb-4 break-words text-sm leading-5 text-destructive">{{ error }}</p>

        <!-- 吸底保存栏：有改动才出现；移动端抬高避开底部 tab 栏 -->
        <div v-if="dirty" class="sticky z-30" :class="isVault ? 'bottom-4' : 'bottom-20 md:bottom-4'">
          <div class="flex flex-wrap items-center gap-3 rounded-xl border border-gold/50 bg-ink-surface/95 px-4 py-3 shadow-lg backdrop-blur">
            <span class="text-xs text-steam-dim">有未保存的修改</span>
            <div class="ml-auto flex gap-2">
              <Button type="button" variant="secondary" size="sm" :disabled="saving" @click="reset">
                <RotateCcw class="h-3.5 w-3.5" /> 撤销
              </Button>
              <Button type="submit" size="sm" :disabled="saving">
                <Loader2 v-if="saving" class="h-3.5 w-3.5 animate-spin" />
                <Save v-else class="h-3.5 w-3.5" />
                {{ saving ? '保存中…' : '保存配置' }}
              </Button>
            </div>
            <span class="w-full text-[11px] leading-4 text-steam-dim/70 sm:w-auto">保存后需重启进程生效（已自动备份 config.yaml.bak）</span>
          </div>
        </div>
      </form>
    </template>
  </div>
</template>
