import { ref } from 'vue'

/**
 * 按图片真实宽高比动态设置容器比例，避免竖版/横版缩略图被 aspect-video 硬裁。
 * 占位用 4/3 起步，onload 后按 naturalWidth/Height 精确对齐，几乎无 CLS。
 */
export function useAspectRatio() {
  const ratio = ref<string>('4 / 3')

  function onLoad(e: Event) {
    const img = e.target as HTMLImageElement
    if (img.naturalWidth > 0 && img.naturalHeight > 0) {
      ratio.value = `${img.naturalWidth} / ${img.naturalHeight}`
    }
  }

  return { ratio, onLoad }
}