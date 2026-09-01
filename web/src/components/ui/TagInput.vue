<script setup lang="ts">
import { ref } from 'vue'
import { X } from 'lucide-vue-next'
import Badge from '@/components/ui/Badge.vue'

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
  <div class="flex min-h-9 w-full min-w-0 items-center gap-1 overflow-hidden rounded-md border border-ink-line bg-ink-raised px-2 focus-within:border-gold">
    <div v-if="model.length" class="flex min-w-0 shrink items-center gap-1 overflow-x-auto py-1">
      <span v-for="tag in model" :key="tag" class="inline-flex shrink-0 items-center gap-0.5">
        <Badge tone="source">{{ tag }}</Badge>
        <button
          type="button"
          class="rounded p-0.5 text-steam-dim hover:bg-destructive/20 hover:text-destructive"
          :aria-label="`移除默认 Tag ${tag}`"
          @click="remove(tag)"
        >
          <X class="h-3 w-3" />
        </button>
      </span>
    </div>
    <input
      v-model="draft"
      type="text"
      class="h-7 min-w-[9rem] flex-1 bg-transparent px-1 text-sm text-steam placeholder:text-steam-dim/60 focus:outline-none"
      placeholder="输入后按回车或逗号添加，可粘贴多个"
      @keydown="onKeydown"
      @blur="commit"
    />
  </div>
</template>
