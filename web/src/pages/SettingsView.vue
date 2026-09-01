<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ChevronDown, Loader2, Plus, Trash2, Save, RotateCcw, Palette, X } from 'lucide-vue-next'
import { getConfig, getStats, putConfig, backup, resetDatabase, listBackups, restoreBackup } from '@/lib/api'
import type { EditableConfig } from '@/lib/types'
import Button from '@/components/ui/Button.vue'
import { toastError, toastSuccess } from '@/composables/useToast'
import { cn } from '@/lib/utils'
import {
  currentMode, currentTheme, setMode, setTheme,
  type Mode, type ThemeKey,
} from '@/composables/useTheme'

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const openTargetMenu = ref<number | null>(null)
const opsBusy = ref(false)
const backups = ref<string[]>([])
const selectedBackup = ref('')

const themeOptions: { key: ThemeKey; label: string }[] = [
  { key: 'projector', label: '放映室（琥珀）' },
  { key: 'midnight', label: '深海（冰青）' },
  { key: 'moss', label: '苔原（苔绿）' },
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
  url_template: null,
  admins: [],
  thumbnail_media: 'first_video' as 'first_video' | 'first',
  thumbnail_source: 'auto' as 'auto' | 'archive' | 'source',
  sync_target_edits: false,
})

/** 最终落盘前不覆盖：保存改的是提交内容，页面状态独立 */
let saved: EditableConfig | null = null

onMounted(async () => {
  try {
    const cfg = await getConfig()
    Object.assign(form, cfg)
    saved = _clone(cfg)
    await getStats() // 触发一次预热，顺带确认后端可用
    await loadBackups()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '配置读取失败'
  } finally {
    loading.value = false
  }
})

function addSource() {
  form.source_chats.push({
    chat_id: null,
    name: '',
    default_tags: [],
    target_channel_ids: [],
    private: true,
  })
}

function removeSource(idx: number) {
  form.source_chats.splice(idx, 1)
}

function addTarget() {
  form.target_channels.push({ chat_id: null, name: '', private: true })
}

function removeTarget(idx: number) {
  const removed = form.target_channels[idx]?.chat_id
  form.target_channels.splice(idx, 1)
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

function displayChatId(value: number | null) {
  if (value == null) return ''
  const digits = String(Math.abs(value))
  return value < 0 && digits.startsWith('100') ? digits.slice(3) : digits
}

function targetLabel(target: { chat_id: number | null; name: string }, fallback = '未命名频道') {
  return target.name || (target.chat_id == null ? fallback : `频道 ${displayChatId(target.chat_id)}`)
}

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

async function save() {
  // 源群 chat_id 必填；收集缺项提示，而不是默默写坏配置
  if (!form.target_channels.length || form.target_channels.some((target) => !target.chat_id)) {
    error.value = '请至少配置一个有效的目标频道'
    toastError(error.value)
    return
  }
  const empty = form.source_chats.filter((s) => !s.chat_id)
  if (empty.length) {
    error.value = `${empty.length} 个源群缺少 chat_id，保存被取消`
    toastError(error.value)
    return
  }
  saving.value = true
  error.value = ''
  try {
    const updated = await putConfig(_clone(form))
    Object.assign(form, updated)
    saved = _clone(updated)
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

async function restoreSelectedBackup() {
  if (!selectedBackup.value) return
  if (!window.confirm(`确认恢复 ${selectedBackup.value}？当前文件会先自动备份。`)) return
  opsBusy.value = true
  try {
    const result = await restoreBackup(selectedBackup.value)
    toastSuccess(`${result.kind === 'database' ? '数据库' : '配置'}已恢复，请重启进程`)
    await loadBackups()
  } catch (e) {
    toastError(e instanceof Error ? e.message : '恢复失败')
  } finally {
    opsBusy.value = false
  }
}

async function backupItem(kind: 'config' | 'database') {
  opsBusy.value = true
  try {
    const result = await backup(kind)
    toastSuccess(`备份已创建：${result.path}`)
    await loadBackups()
  } catch (e) {
    toastError(e instanceof Error ? e.message : '备份失败')
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
  <div class="mx-auto max-w-4xl px-4 py-8 pb-28 sm:px-6">
    <header class="mb-6 flex items-end justify-between gap-4 md:pb-2">
      <div>
        <h1 class="font-display text-3xl font-semibold tracking-tight">设置</h1>
        <p class="mt-1 text-sm text-steam-dim">外观即时生效，其余配置保存后重启生效</p>
      </div>
    </header>

    <!-- 主题外观（纯前端，localStorage，立即生效） -->
    <section class="mb-5 rounded-card border border-ink-line bg-ink-surface p-4">
      <div class="mb-3 flex items-center gap-1.5 text-sm font-medium text-steam">
        <Palette class="h-4 w-4" /> 主题外观
      </div>
      <p class="mb-2 text-xs text-steam-dim">配色主题</p>
      <div class="mb-4 flex flex-wrap gap-2" role="radiogroup" aria-label="配色主题">
        <button
          v-for="t in themeOptions"
          :key="t.key"
          type="button"
          role="radio"
          :aria-checked="currentTheme === t.key"
          :class="cn(
            'rounded-full border px-3 py-1.5 text-sm transition-colors cursor-pointer',
            currentTheme === t.key
              ? 'border-gold text-gold'
              : 'border-ink-line text-steam-dim hover:text-steam',
          )"
          @click="setTheme(t.key)"
        >
          {{ t.label }}
        </button>
      </div>
      <p class="mb-2 text-xs text-steam-dim">明暗模式</p>
      <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="明暗模式">
        <button
          v-for="m in modeOptions"
          :key="m.key"
          type="button"
          role="radio"
          :aria-checked="currentMode === m.key"
          :class="cn(
            'rounded-full border px-3 py-1.5 text-sm transition-colors cursor-pointer',
            currentMode === m.key
              ? 'border-gold text-gold'
              : 'border-ink-line text-steam-dim hover:text-steam',
          )"
          @click="setMode(m.key)"
        >
          {{ m.label }}
        </button>
      </div>
    </section>

    <div v-if="loading" class="flex items-center gap-2 text-steam-dim">
      <Loader2 class="h-4 w-4 animate-spin" /> 载入中…
    </div>

    <form v-else @submit.prevent="save">
      <!-- 源群 -->
      <section class="mb-5 rounded-card border border-ink-line bg-ink-surface p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-sm font-medium text-steam">源群</h2>
          <Button type="button" variant="secondary" size="sm" @click="addSource">
            <Plus class="h-3.5 w-3.5" /> 新增
          </Button>
        </div>
        <div v-for="(s, i) in form.source_chats" :key="i" class="mb-3 rounded-md border border-ink-line bg-ink-raised/40 p-3 sm:p-4">
          <div class="mb-3 flex items-center justify-between gap-3">
            <h3 class="text-sm font-medium text-steam">{{ s.name || `源群 ${i + 1}` }}</h3>
            <button
              type="button"
              class="shrink-0 rounded-md p-2 text-steam-dim transition-colors hover:bg-destructive/20 hover:text-destructive cursor-pointer"
              :aria-label="`删除源群 ${i + 1}`"
              @click="removeSource(i)"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
          <div class="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-[minmax(0,1.25fr)_minmax(8rem,.75fr)_minmax(10rem,1fr)_minmax(11rem,1.15fr)]">
            <label class="min-w-0">
              <span class="mb-1 block text-xs text-steam-dim">chat_id（必填，填写内部 ID）</span>
              <input
                v-model.number="s.chat_id"
                type="number"
                placeholder="例如 123456789"
                class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                :aria-label="`源群 ${i + 1} chat_id`"
              />
              <label class="mt-2 flex items-center gap-2 text-xs text-steam-dim">
                <input v-model="s.private" type="checkbox" class="h-4 w-4 accent-gold" /> 私密
              </label>
            </label>
            <label class="min-w-0">
              <span class="mb-1 block text-xs text-steam-dim">名称</span>
              <div class="flex gap-1.5">
                <input
                  v-model="s.name"
                  type="text"
                  placeholder="留空自动获取 Telegram 名称"
                  class="h-9 min-w-0 flex-1 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                  :aria-label="`源群 ${i + 1} 名称`"
                />
                <button
                  v-if="s.name"
                  type="button"
                  class="rounded-md border border-ink-line px-2 text-steam-dim hover:text-steam cursor-pointer"
                  :aria-label="`重置源群 ${i + 1} 名称`"
                  title="恢复自动名称"
                  @click="resetName(s)"
                >
                  <X class="h-4 w-4" />
                </button>
              </div>
            </label>
            <label class="min-w-0">
              <span class="mb-1 block text-xs text-steam-dim">默认 Tag</span>
              <input
                :value="s.default_tags.join(' ')"
                placeholder="空格分隔"
                class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                :aria-label="`源群 ${i + 1} 默认 Tag`"
                @input="(e: Event) => { const v = (e.target as HTMLInputElement).value; s.default_tags = v ? v.split(' ').filter(Boolean) : [] }"
              />
            </label>
            <div class="min-w-0 sm:col-span-2 md:col-span-1">
              <span class="mb-1 block text-xs text-steam-dim">目标频道</span>
              <div class="relative">
                <button
                  type="button"
                  class="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-ink-line bg-ink-raised px-3 text-left text-sm text-steam focus:border-gold focus:outline-none cursor-pointer"
                  :aria-expanded="openTargetMenu === i"
                  :aria-label="`源群 ${i + 1} 目标频道`"
                  @click="openTargetMenu = openTargetMenu === i ? null : i"
                >
                  <span class="truncate">
                    {{ s.target_channel_ids.length ? `${s.target_channel_ids.length} 个目标频道` : '全部目标频道' }}
                  </span>
                  <ChevronDown class="h-4 w-4 shrink-0 text-steam-dim" />
                </button>
                <div v-if="openTargetMenu === i" class="absolute left-0 right-0 z-20 mt-1 max-h-56 overflow-auto rounded-md border border-ink-line bg-ink-surface p-1 shadow-lg">
                  <button
                    v-for="target in form.target_channels"
                    :key="String(target.chat_id)"
                    type="button"
                    class="flex w-full items-center gap-2 rounded px-2 py-2 text-left text-sm hover:bg-ink-raised cursor-pointer"
                    @click="toggleTarget(s, target.chat_id)"
                  >
                    <span class="flex h-4 w-4 items-center justify-center rounded border border-ink-line text-xs" :class="s.target_channel_ids.includes(target.chat_id as number) ? 'border-gold bg-gold text-ink' : ''">{{ s.target_channel_ids.includes(target.chat_id as number) ? '✓' : '' }}</span>
                    <span class="truncate">{{ targetLabel(target) }}</span>
                  </button>
                  <p v-if="!form.target_channels.length" class="px-2 py-2 text-xs text-steam-dim">请先添加目标频道</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        <p v-if="!form.source_chats.length" class="text-xs text-steam-dim">还没有源群</p>
      </section>

      <!-- 目标频道 -->
      <section class="mb-5 rounded-card border border-ink-line bg-ink-surface p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-sm font-medium text-steam">目标频道</h2>
          <Button type="button" variant="secondary" size="sm" @click="addTarget">
            <Plus class="h-3.5 w-3.5" /> 新增
          </Button>
        </div>
        <div v-for="(target, i) in form.target_channels" :key="i" class="mb-3 grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_auto]">
          <div class="min-w-0">
            <input
              v-model.number="target.chat_id"
              type="number"
              placeholder="频道内部 ID"
              class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
              :aria-label="`目标频道 ${i + 1} chat_id`"
            />
            <label class="mt-2 flex items-center gap-2 text-xs text-steam-dim">
              <input v-model="target.private" type="checkbox" class="h-4 w-4 accent-gold" /> 私密
            </label>
          </div>
          <div class="flex min-w-0 gap-1.5">
            <input
              v-model="target.name"
              type="text"
              placeholder="留空自动获取 Telegram 名称"
              class="h-9 min-w-0 flex-1 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
              :aria-label="`目标频道 ${i + 1} 名称`"
            />
            <button
              v-if="target.name"
              type="button"
              class="rounded-md border border-ink-line px-2 text-steam-dim hover:text-steam cursor-pointer"
              :aria-label="`重置目标频道 ${i + 1} 名称`"
              title="恢复自动名称"
              @click="resetName(target)"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
          <button type="button" class="justify-self-end rounded-md p-2 text-steam-dim transition-colors hover:bg-destructive/20 hover:text-destructive cursor-pointer" :aria-label="`删除目标频道 ${i + 1}`" @click="removeTarget(i)">
            <Trash2 class="h-4 w-4" />
          </button>
        </div>
        <p v-if="!form.target_channels.length" class="text-xs text-steam-dim">还没有目标频道</p>
        <p class="mt-2 text-xs text-steam-dim/80">源群未选择独立目标时，将归档到全部目标频道。</p>
      </section>

      <section class="mb-5 rounded-card border border-ink-line bg-ink-surface p-4">
        <h2 class="mb-1 text-sm font-medium text-steam">目标消息同步</h2>
        <p class="mb-3 text-xs leading-5 text-steam-dim">默认只更新被编辑的目标消息。开启后，Telegram 中对任一目标消息的正文、Tag 或 Rating 编辑会同步到同一源消息的其他目标副本。</p>
        <label class="flex items-center gap-2 text-sm text-steam">
          <input v-model="form.sync_target_edits" type="checkbox" class="h-4 w-4 accent-gold" />
          同步到所有目标副本
        </label>
      </section>

      <!-- 限速 / 开关 -->
      <section class="mb-5 grid gap-4 rounded-card border border-ink-line bg-ink-surface p-4 sm:grid-cols-2">
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
        </div>
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
      </section>

      <section class="mb-5 rounded-card border border-ink-line bg-ink-surface p-4">
        <h2 class="mb-3 text-sm font-medium text-steam">缩略图</h2>
        <div class="grid gap-4 sm:grid-cols-2">
          <label class="min-w-0">
            <span class="mb-1 block text-xs text-steam-dim">Album 缩略图媒体</span>
            <select v-model="form.thumbnail_media" class="h-9 w-full rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam focus:border-gold focus:outline-none">
              <option v-for="option in thumbnailMediaOptions" :key="option.key" :value="option.key">{{ option.label }}</option>
            </select>
          </label>
          <label class="min-w-0">
            <span class="mb-1 block text-xs text-steam-dim">缩略图来源</span>
            <select v-model="form.thumbnail_source" class="h-9 w-full rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam focus:border-gold focus:outline-none">
              <option v-for="option in thumbnailSourceOptions" :key="option.key" :value="option.key">{{ option.label }}</option>
            </select>
          </label>
        </div>
      </section>

      <section class="mb-5 rounded-card border border-ink-line bg-ink-surface p-4">
        <h2 class="mb-1 text-sm font-medium text-steam">备份与数据库</h2>
        <p class="mb-3 text-xs leading-5 text-steam-dim">配置文件和数据库分开管理。数据库重置会清空归档记录，操作前自动创建备份，完成后需要重启进程。</p>
        <div class="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" size="sm" :disabled="opsBusy" @click="backupItem('config')">备份配置</Button>
          <Button type="button" variant="secondary" size="sm" :disabled="opsBusy" @click="backupItem('database')">备份数据库</Button>
          <Button type="button" variant="secondary" size="sm" :disabled="opsBusy" @click="resetDb">重置数据库</Button>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <select v-model="selectedBackup" class="h-9 min-w-0 flex-1 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam focus:border-gold focus:outline-none">
            <option value="">选择备份以恢复</option>
            <option v-for="item in backups" :key="item" :value="item">{{ item }}</option>
          </select>
          <Button type="button" variant="secondary" size="sm" :disabled="opsBusy || !selectedBackup" @click="restoreSelectedBackup">恢复备份</Button>
        </div>
      </section>

      <section class="mb-5 rounded-card border border-ink-line bg-ink-surface p-4">
        <label class="mb-1 block text-xs text-steam-dim" for="url-template">
          私密频道搜索模板（{tag} 占位）
        </label>
        <input
          id="url-template"
          v-model="form.url_template"
          type="text"
          placeholder="https://t.me/c/123456789?q={tag}"
          class="mb-4 h-9 w-full rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
        />

        <div class="mb-2 flex items-center justify-between">
          <h3 class="text-sm font-medium text-steam">管理员 ID</h3>
          <Button type="button" variant="secondary" size="sm" @click="addAdmin">
            <Plus class="h-3.5 w-3.5" /> 新增
          </Button>
        </div>
        <div v-for="(a, i) in form.admins" :key="i" class="mb-2 flex items-center gap-2">
          <input
            v-model.number="form.admins[i]"
            type="number"
            placeholder="User ID"
            class="h-9 w-full rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
          />
          <button
            type="button"
            class="rounded-md p-2 text-steam-dim transition-colors hover:bg-destructive/20 hover:text-destructive cursor-pointer"
            :aria-label="`删除管理员 ${i + 1}`"
            @click="removeAdmin(i)"
          >
            <Trash2 class="h-4 w-4" />
          </button>
        </div>
      </section>

      <p v-if="error" role="alert" class="mb-4 break-words text-sm leading-5 text-destructive">{{ error }}</p>

      <div class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center sm:gap-3">
        <Button type="submit" :disabled="saving" class="w-full min-w-0 sm:w-auto sm:min-w-28 sm:shrink-0">
          <Save class="h-4 w-4" /> {{ saving ? '保存中…' : '保存配置' }}
        </Button>
        <Button type="button" variant="secondary" class="w-full min-w-0 sm:w-auto sm:shrink-0" @click="reset">
          <RotateCcw class="h-4 w-4" /> 撤销
        </Button>
        <span class="col-span-2 text-xs leading-5 text-steam-dim sm:col-auto sm:max-w-sm">
          保存后需重启进程生效（已自动备份 config.yaml.bak）
        </span>
      </div>
    </form>
  </div>
</template>