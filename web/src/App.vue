<script setup lang="ts">
import { RouterView } from 'vue-router'
import ToastContainer from '@/components/ui/ToastContainer.vue'
</script>

<template>
  <!-- 外层只负责 login↔应用整壳的换页（B7）：按 login/app 分 key，
       应用内部导航 key 不变、由 AppLayout 内层的 v-page 接管，避免双重动画 -->
  <RouterView v-slot="{ Component, route }">
    <Transition name="v-page" mode="out-in">
      <component :is="Component" :key="route.name === 'login' ? 'login' : 'app'" />
    </Transition>
  </RouterView>
  <ToastContainer />
</template>
