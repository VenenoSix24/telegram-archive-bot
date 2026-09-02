<script setup lang="ts">
import { ref } from 'vue'
import { X } from 'lucide-vue-next'

const model = defineModel<string[]>({ required: true })
const draft = ref('')

function normalize(values: string[]): string[] {
  const seen = new Set<string>()
  const normalized: string[] = []
  for (const value of values) {
    const name = value.trim()
    if (!name || seen.has(name)) continue
    seen.add(name)
    normalized.push(name)
  }
  return normalized
}

function commit() {
  const values = draft.value.split(/[\s,，]+/).map((value) => value.trim()).filter(Boolean)
  if (values.length) model.value = normalize([...model.value, ...values])
  draft.value = ''
}

function remove(name: string) {
  model.value = model.value.filter((tag) => tag !== name)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',' || event.key === '，') {
    event.preventDefault()
    commit()
  }
}
</script>

<template>
  <!-- flex-wrap：tag 多时换行而不是把 chips 挤进横向滚动条，输入框始终可见 -->
  <div class="flex min-h-9 w-full min-w-0 flex-wrap items-center gap-1 rounded-md border border-ink-line bg-ink-raised px-2 py-1 focus-within:border-gold">
    <template v-if="model.length">
      <!-- 每个 tag 独立描边 chip，× 收进 chip 内部，边界一目了然 -->
      <span
        v-for="tag in model"
        :key="tag"
        class="inline-flex shrink-0 items-center gap-1 rounded-full border border-ink-line bg-ink-surface py-0.5 pl-2 pr-1 text-xs text-steam"
      >
        {{ tag }}
        <button
          type="button"
          class="cursor-pointer rounded-full p-0.5 text-steam-dim transition-colors hover:bg-destructive/20 hover:text-destructive"
          :aria-label="`移除默认 Tag ${tag}`"
          @click="remove(tag)"
        >
          <X class="h-3 w-3" />
        </button>
      </span>
    </template>
    <input
      v-model="draft"
      type="text"
      class="h-7 min-w-[8rem] flex-1 bg-transparent px-1 text-sm text-steam placeholder:text-steam-dim/60 focus:outline-none"
      :placeholder="model.length ? '添加…' : '输入后按回车或逗号添加，可粘贴多个'"
      @keydown="onKeydown"
      @blur="commit"
    />
  </div>
</template>
