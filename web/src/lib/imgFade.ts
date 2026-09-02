import type { Directive } from 'vue'

/**
 * v-img-fade（G 节 B4）：网络图加载完成后淡入，缓存图立即显示。
 * 用动画类而非 transition 属性，不覆盖元素既有的 transition（如卡片 hover 缩放）。
 * 加载失败同样显示，交由组件的 @error 分支换成绘制封面。
 */
export const imgFade: Directive<HTMLImageElement> = {
  mounted(el) {
    if (el.complete) return
    el.classList.add('img-fade-pending')
    const reveal = () => {
      el.classList.remove('img-fade-pending')
      el.classList.add('img-fade-in')
    }
    el.addEventListener('load', reveal, { once: true })
    el.addEventListener('error', reveal, { once: true })
  },
}
