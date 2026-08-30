/* Shadcn-vue 风格工具：合并 class 并解析 tailwind-merge 冲突。 */
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}