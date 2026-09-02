/**
 * 进场 stagger（G 节 B2/B6）：前 cap 项每项 +step 逐个出现；
 * 其余项统一延迟到 cap*step 作为收尾波进入——不能给 0ms 抢跑，
 * 否则首屏上半有序、下半同帧放完，节奏感断裂（用户实测反馈）。
 * 返回值用作 animationDelay / transitionDelay 内联样式。
 */
export const STAGGER_STEP = 30
export const STAGGER_CAP = 12

export function staggerDelay(index: number, step = STAGGER_STEP, cap = STAGGER_CAP): string {
  return `${Math.min(index, cap) * step}ms`
}
