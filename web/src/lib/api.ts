import type {
  EditableConfig,
  Message,
  MessagesResponse,
  Stats,
  TagsResponse,
} from '@/lib/types'

/** 未登录（cookie 失效）时的统一跳转。 */
export class AuthError extends Error {}

/** 401 全局处理：清本地会话标记，统一跳登录页（避免空壳白屏）。 */
function onUnauthorized() {
  sessionStorage.removeItem('archive_authed')
  const path = window.location.hash.replace(/^#/, '/') || '/'
  if (path !== '/login') {
    window.location.hash = '/login'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...init,
  })
  if (resp.status === 401) {
    onUnauthorized()
    throw new AuthError('session expired')
  }
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${await resp.text()}`)
  }
  return resp.json() as Promise<T>
}

export async function login(token: string): Promise<{ ok: boolean }> {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ token }) })
}

export async function logout(): Promise<{ ok: boolean }> {
  return request('/auth/logout', { method: 'POST' })
}

export async function getStats(): Promise<Stats> {
  return request('/stats')
}

export async function getTags(): Promise<TagsResponse> {
  return request('/tags')
}

export async function getConfig(): Promise<EditableConfig> {
  return request('/config')
}

export async function putConfig(cfg: EditableConfig): Promise<EditableConfig> {
  return request('/config', { method: 'PUT', body: JSON.stringify(cfg) })
}

export async function backup(kind: 'config' | 'database'): Promise<{ path: string }> {
  return request('/ops/backup', { method: 'POST', body: JSON.stringify({ kind }) })
}

export async function listBackups(): Promise<{ items: string[] }> {
  return request('/ops/backups')
}

export async function restoreBackup(name: string): Promise<{ ok: boolean; kind: string }> {
  return request('/ops/restore', { method: 'POST', body: JSON.stringify({ name }) })
}

export async function resetDatabase(): Promise<{ ok: boolean }> {
  return request('/ops/reset-database', {
    method: 'POST',
    body: JSON.stringify({ confirm: 'RESET DATABASE' }),
  })
}

export interface MessageQuery {
  q?: string
  tag?: string
  media_type?: string
  rating?: number
  source_chat_id?: number
  target_chat_id?: number
  limit?: number
  offset?: number
  status?: 'active' | 'deleted' | 'all'
}

export async function listMessages(query: MessageQuery = {}): Promise<MessagesResponse> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  }
  const qs = params.toString()
  return request(`/messages${qs ? `?${qs}` : ''}`)
}

export async function getMessage(id: number): Promise<Message> {
  return request(`/messages/${id}`)
}

export async function patchMessage(
  id: number,
  change: {
    target_id?: number
    body?: string
    body_html?: string
    add_tags?: string[]
    remove_tag_names?: string[]
    rating?: number
  },
): Promise<Message> {
  return request(`/messages/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(change),
  })
}