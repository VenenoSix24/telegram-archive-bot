import { createApp } from 'vue'
import '@fontsource/sora'
import './style.css'
import App from './App.vue'
import router from './router'
import { imgFade } from '@/lib/imgFade'

createApp(App).use(router).directive('img-fade', imgFade).mount('#app')