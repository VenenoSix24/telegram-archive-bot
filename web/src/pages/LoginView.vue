<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import { AuthError, login } from '@/lib/api'
import { APP_VERSION } from '@/lib/version'
import { isVault } from '@/lib/vocab'

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
  <!-- 标准后台：居中登录卡（首屏 fade-up 仪式感，B7） -->
  <div v-if="isVault" class="grid min-h-screen place-items-center bg-ink-bg px-4">
    <form
      class="anim-fade-up-slow w-full max-w-sm rounded-xl border border-ink-line bg-ink-surface p-8 shadow-sm"
      @submit.prevent="submit"
    >
      <div class="flex items-center gap-3">
        <span class="grid h-10 w-10 place-items-center rounded-xl bg-steam font-mono text-[15px] font-bold text-ink-bg">A</span>
        <div>
          <p class="text-[17px] font-semibold text-steam">归档库</p>
          <p class="mt-0.5 font-mono text-[9px] tracking-[0.22em] text-steam-dim/60">TG ARCHIVE MANAGER</p>
        </div>
      </div>

      <label for="token" class="mb-2 mt-6 block text-sm text-steam">访问令牌</label>
      <Input
        id="token"
        v-model="token"
        type="password"
        placeholder="输入 WEB_TOKEN"
        autocomplete="current-password"
      />

      <Transition name="v-dialog">
        <p v-if="error" key="error" role="alert" class="mt-3 text-sm text-destructive">{{ error }}</p>
      </Transition>

      <Button type="submit" class="mt-6 w-full" :disabled="busy || !token">
        {{ busy ? '验证中…' : '登录' }}
      </Button>

      <p class="mt-5 border-t border-ink-line pt-3 text-center font-mono text-[9px] tracking-[0.18em] text-steam-dim/60">
        v{{ APP_VERSION }}
      </p>
    </form>
  </div>

  <!-- 素材志：扉页登录（卡 fade-up 慢一档，朱印延迟轻按浮现，B7） -->
  <div v-else class="grid min-h-screen place-items-center bg-ink-bg px-4">
    <form
      class="anim-fade-up-slow w-full max-w-sm border border-ink-line bg-ink-surface p-8"
      @submit.prevent="submit"
    >
      <div class="flex items-center gap-3.5">
        <svg
          class="mast-seal anim-scale-in hidden h-11 w-11 shrink-0 text-gold"
          style="animation-delay: 180ms"
          viewBox="0 0 52 52"
          aria-hidden="true"
        >
          <rect x="2" y="2" width="48" height="48" rx="5" fill="none" stroke="currentColor" stroke-width="3.5" />
          <text x="26" y="37" text-anchor="middle" font-size="27" font-weight="700" fill="currentColor">档</text>
        </svg>
        <div>
          <p class="font-display text-2xl font-bold tracking-[0.22em] text-steam">素材志</p>
          <p class="mt-1.5 font-mono text-[9.5px] tracking-[0.28em] text-steam-dim">TG ARCHIVE CATALOGUE</p>
        </div>
      </div>
      <div class="mast-rules hidden" aria-hidden="true"></div>

      <label for="token" class="mb-2 mt-6 block text-sm text-steam">访问令牌</label>
      <Input
        id="token"
        v-model="token"
        type="password"
        placeholder="输入 WEB_TOKEN"
        autocomplete="current-password"
      />

      <Transition name="v-dialog">
        <p v-if="error" key="error" role="alert" class="mt-3 text-sm text-destructive">{{ error }}</p>
      </Transition>

      <Button type="submit" class="mt-6 w-full" :disabled="busy || !token">
        {{ busy ? '验证中…' : '进入归档库' }}
      </Button>

      <p class="mt-5 border-t border-ink-line pt-3 text-center font-mono text-[9px] tracking-[0.2em] text-steam-dim/60">
        PRIVATE COLLECTION · v{{ APP_VERSION }}
      </p>
    </form>
  </div>
</template>
