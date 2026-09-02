import { onBeforeUnmount, ref, watch, type WatchSource } from 'vue'

/**
 * C2 KPI 数字滚动：数值源变化时用 rAF 在 400ms 内从当前值缓出滚到目标值。
 * 遵守 prefers-reduced-motion：直接落位不滚动。
 */
export function useCountUp(source: WatchSource<number>, duration = 400) {
  const display = ref(0)
  let raf = 0

  watch(
    source,
    (target) => {
      cancelAnimationFrame(raf)
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        display.value = target
        return
      }
      const from = display.value
      const start = performance.now()
      const tick = (now: number) => {
        const p = Math.min(1, (now - start) / duration)
        display.value = Math.round(from + (target - from) * (1 - Math.pow(1 - p, 3)))
        if (p < 1) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    },
    { immediate: true },
  )

  onBeforeUnmount(() => cancelAnimationFrame(raf))
  return display
}
