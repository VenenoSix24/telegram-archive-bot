<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Loader2, Plus, Trash2, Save, RotateCcw } from 'lucide-vue-next'
import { getConfig, getStats, putConfig } from '@/lib/api'
import type { EditableConfig } from '@/lib/types'
import Button from '@/components/ui/Button.vue'
import { toastError, toastSuccess } from '@/composables/useToast'

const loading = ref(true)
const saving = ref(false)
const error = ref('')

const form = reactive<EditableConfig>({
  source_chats: [],
  target_channel_id: null,
  forward_interval: 3,
  retry_count: 3,
  show_link: true,
  preserve_original: true,
  rating_enabled: true,
  url_template: null,
  admins: [],
})

/** 最终落盘前不覆盖：保存改的是提交内容，页面状态独立 */
let saved: EditableConfig | null = null

onMounted(async () => {
  try {
    const cfg = await getConfig()
    Object.assign(form, cfg)
    saved = structuredClone(cfg)
    await getStats() // 触发一次预热，顺带确认后端可用
  } catch (e) {
    error.value = e instanceof Error ? e.message : '配置读取失败'
  } finally {
    loading.value = false
  }
})

function addSource() {
  form.source_chats.push({ chat_id: null, name: '', default_tags: [], target_channel_id: null })
}

function removeSource(idx: number) {
  form.source_chats.splice(idx, 1)
}

function addAdmin() {
  form.admins.push(0)
}

function removeAdmin(idx: number) {
  form.admins.splice(idx, 1)
}

async function save() {
  // 源群 chat_id 必填；收集缺项提示，而不是默默写坏配置
  const empty = form.source_chats.filter((s) => !s.chat_id)
  if (empty.length) {
    error.value = `${empty.length} 个源群缺少 chat_id，保存被取消`
    toastError(error.value)
    return
  }
  saving.value = true
  error.value = ''
  try {
    const updated = await putConfig(structuredClone(form))
    Object.assign(form, updated)
    saved = structuredClone(updated)
    toastSuccess('已保存，重启进程后生效')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
    toastError(error.value)
  } finally {
    saving.value = false
  }
}

function reset() {
  if (saved) Object.assign(form, structuredClone(saved))
}
</script>

<template>
  <div class="mx-auto max-w-4xl px-6 py-8 pb-28">
    <header class="mb-6 flex items-end justify-between gap-4 md:pb-2">
      <div>
        <h1 class="font-display text-3xl font-semibold tracking-tight">设置</h1>
        <p class="mt-1 text-sm text-steam-dim">修改 config.yaml 白名单项（凭据不可改）</p>
      </div>
    </header>

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
        <div v-for="(s, i) in form.source_chats" :key="i" class="mb-3 flex flex-wrap items-center gap-2">
          <input
            v-model="s.chat_id"
            type="number"
            placeholder="chat_id（如 -100123456789）"
            class="h-9 min-w-0 flex-1 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
            :aria-label="`源群 ${i + 1} chat_id`"
          />
          <input
            v-model="s.name"
            type="text"
            placeholder="名称"
            class="h-9 w-28 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
            :aria-label="`源群 ${i + 1} 名称`"
          />
          <input
            :value="s.default_tags.join(' ')"
            placeholder="默认 Tag（空格分隔）"
            class="h-9 w-40 rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
            :aria-label="`源群 ${i + 1} 默认 Tag`"
            @input="(e: Event) => { const v = (e.target as HTMLInputElement).value; s.default_tags = v ? v.split(' ').filter(Boolean) : [] }"
          />
          <button
            type="button"
            class="rounded-md p-2 text-steam-dim transition-colors hover:bg-destructive/20 hover:text-destructive cursor-pointer"
            :aria-label="`删除源群 ${i + 1}`"
            @click="removeSource(i)"
          >
            <Trash2 class="h-4 w-4" />
          </button>
        </div>
        <p v-if="!form.source_chats.length" class="text-xs text-steam-dim">还没有源群</p>
      </section>

      <!-- 目标频道 -->
      <section class="mb-5 rounded-card border border-ink-line bg-ink-surface p-4">
        <h2 class="mb-3 text-sm font-medium text-steam">总频道（目标）</h2>
        <input
          v-model="form.target_channel_id"
          type="number"
          placeholder="chat_id（如 -100123456789）"
          class="h-9 w-full rounded-md border border-ink-line bg-ink-raised px-3 text-sm text-steam placeholder:text-steam-dim/60 focus:border-gold focus:outline-none"
        />
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

      <p v-if="error" role="alert" class="mb-4 text-sm text-destructive">{{ error }}</p>

      <div class="flex items-center gap-3">
        <Button type="submit" :disabled="saving" class="min-w-28">
          <Save class="h-4 w-4" /> {{ saving ? '保存中…' : '保存配置' }}
        </Button>
        <Button type="button" variant="secondary" @click="reset">
          <RotateCcw class="h-4 w-4" /> 撤销
        </Button>
        <span class="text-xs text-steam-dim">保存后需重启进程生效（已自动备份 config.yaml.bak）</span>
      </div>
    </form>
  </div>
</template>