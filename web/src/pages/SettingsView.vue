<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Loader2, Plus, Trash2, Save, RotateCcw, Palette } from 'lucide-vue-next'
import { getConfig, getStats, putConfig } from '@/lib/api'
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
  } catch (e) {
    error.value = e instanceof Error ? e.message : '配置读取失败'
  } finally {
    loading.value = false
  }
})

function addSource() {
  form.source_chats.push({ chat_id: null, name: '', default_tags: [], target_channel_ids: [], private: true })
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
            <h3 class="text-sm font-medium text-steam">源群 {{ i + 1 }}</h3>
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
              <span class="mb-1 block text-xs text-steam-dim">chat_id（必填）</span>
              <input
                v-model="s.chat_id"
                type="number"
                placeholder="频道内部 ID"
                class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                :aria-label="`源群 ${i + 1} chat_id`"
              />
              <label class="mt-2 flex items-center gap-2 text-xs text-steam-dim">
                <input v-model="s.private" type="checkbox" class="h-4 w-4 accent-gold" /> 私密
              </label>
            </label>
            <label class="min-w-0">
              <span class="mb-1 block text-xs text-steam-dim">名称</span>
              <input
                v-model="s.name"
                type="text"
                placeholder="名称"
                class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
                :aria-label="`源群 ${i + 1} 名称`"
              />
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
            <label class="min-w-0 sm:col-span-2 md:col-span-1">
              <span class="mb-1 block text-xs text-steam-dim">目标频道</span>
              <select
                v-model="s.target_channel_ids"
                multiple
                class="min-h-20 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-2 py-1 text-sm text-steam focus:border-gold focus:outline-none"
                :aria-label="`源群 ${i + 1} 目标频道`"
              >
                <option v-for="target in form.target_channels" :key="String(target.chat_id)" :value="target.chat_id">
                  {{ target.name || `频道 ${target.chat_id}` }}
                </option>
              </select>
            </label>
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
          <input
            v-model.number="target.chat_id"
            type="number"
            placeholder="频道内部 ID"
            class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
            :aria-label="`目标频道 ${i + 1} chat_id`"
          />
          <input
            v-model="target.name"
            type="text"
            placeholder="名称（可留空自动读取）"
            class="h-9 w-full min-w-0 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
            :aria-label="`目标频道 ${i + 1} 名称`"
          />
          <button type="button" class="justify-self-end rounded-md p-2 text-steam-dim transition-colors hover:bg-destructive/20 hover:text-destructive cursor-pointer" :aria-label="`删除目标频道 ${i + 1}`" @click="removeTarget(i)">
            <Trash2 class="h-4 w-4" />
          </button>
        </div>
        <p v-if="!form.target_channels.length" class="text-xs text-steam-dim">还没有目标频道</p>
        <p class="mt-2 text-xs text-steam-dim/80">源群未选择独立目标时，将归档到全部目标频道。</p>
        <label class="mt-3 flex items-center gap-2 text-sm text-steam">
          <input v-model="form.sync_target_edits" type="checkbox" class="h-4 w-4 accent-gold" />
          Telegram 目标消息编辑时同步到其他目标
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
        <h2 class="mb-3 text-sm font-medium text-steam">Telegram 名称</h2>
        <p class="text-xs leading-5 text-steam-dim">群组和频道名称将在正式启动时由已登录账号自动读取；这里填写的名称会作为自定义显示名称。</p>
      </section>

      <!-- 搜索模板 + 管理员 -->
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