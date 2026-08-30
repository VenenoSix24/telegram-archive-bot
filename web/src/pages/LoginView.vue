<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import { AuthError, login } from '@/lib/api'

const router = useRouter()
const token = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await login(token.value.trim())
    sessionStorage.setItem('archive_authed', '1')
    router.replace('/dashboard')
  } catch (e) {
    if (e instanceof AuthError) {
      sessionStorage.removeItem('archive_authed')
      router.replace('/login')
    } else {
      error.value = 'Token 错误，请确认.web_token 配置'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="grid min-h-screen place-items-center bg-ink-bg px-4">
    <form
      class="w-full max-w-sm rounded-card border border-ink-line bg-ink-surface p-8"
      @submit.prevent="submit"
    >
      <p class="font-display text-2xl font-semibold tracking-tight text-gold">ARCHIVE</p>
      <p class="mt-1 text-sm text-steam-dim">Telegram 归档库</p>

      <label for="token" class="mt-6 block text-sm font-medium text-steam">访问令牌</label>
      <Input
        id="token"
        v-model="token"
        type="password"
        placeholder="输入 WEB_TOKEN"
        class="mt-2"
        autocomplete="current-password"
      />

      <p v-if="error" role="alert" class="mt-3 text-sm text-destructive">{{ error }}</p>

      <Button type="submit" class="mt-6 w-full" :disabled="busy || !token">
        {{ busy ? '登录中…' : '进入归档库' }}
      </Button>
    </form>
  </div>
</template>