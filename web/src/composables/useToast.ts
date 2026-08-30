import { reactive } from 'vue'

export type ToastKind = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  kind: ToastKind
  text: string
}

const state = reactive<{ toasts: Toast[] }>({ toasts: [] })
let seq = 0

function push(kind: ToastKind, text: string, ttl = 2400) {
  const id = ++seq
  state.toasts.push({ id, kind, text })
  setTimeout(() => {
    const i = state.toasts.findIndex((t) => t.id === id)
    if (i >= 0) state.toasts.splice(i, 1)
  }, ttl)
}

export function useToast() {
  return {
    toasts: state.toasts,
    success: (text: string) => push('success', text),
    error: (text: string) => push('error', text),
    info: (text: string) => push('info', text),
  }
}

export function toastSuccess(text: string) {
  push('success', text)
}
export function toastError(text: string) {
  push('error', text)
}
export function toastInfo(text: string) {
  push('info', text)
}