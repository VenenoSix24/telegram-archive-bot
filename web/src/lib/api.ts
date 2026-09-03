import type {
  BackupItem,
  EditableConfig,
  Message,
  MessagesResponse,
  Stats,
  TagsResponse,
  TrendResponse,
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

/** 服务器返回 HTML 错误页时透传会污染 UI，统一截断为可读摘要。 */
async function errorMessage(resp: Response): Promise<string> {
  const text = (await resp.text()).trim()
  if (!text || text.startsWith('<')) return `HTTP ${resp.status}`
  return `HTTP ${resp.status}: ${text.slice(0, 200)}`
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
    throw new Error(await errorMessage(resp))
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

/** 近 N 天归档趋势（服务端收敛 1..90，缺数日已补 0） */
export async function getTrend(days = 30): Promise<TrendResponse> {
  return request(`/stats/trend?days=${days}`)
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

export async function backup(kind: 'config' | 'database'): Promise<{ backup: BackupItem }> {
  return request('/ops/backup', { method: 'POST', body: JSON.stringify({ kind }) })
}

export async function listBackups(): Promise<{ items: BackupItem[] }> {
  return request('/ops/backups')
}

export async function restoreBackup(name: string): Promise<{ ok: boolean; kind: string; restart_required: boolean }> {
  return request('/ops/restore', { method: 'POST', body: JSON.stringify({ name }) })
}

export async function runBackupNow(): Promise<{ ok: boolean; name: string }> {
  return request('/ops/backups/run', { method: 'POST' })
}

export async function deleteBackup(name: string): Promise<{ ok: boolean; kind: string }> {
  return request(`/ops/backups/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

export async function importBackup(
  kind: 'config' | 'database',
  file: File,
): Promise<{ ok: boolean; kind: string; restart_required: boolean }> {
  const response = await fetch(`/api/v1/ops/import?kind=${kind}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/octet-stream' },
    body: file,
  })
  if (response.status === 401) {
    onUnauthorized()
    throw new AuthError('session expired')
  }
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<{ ok: boolean; kind: string; restart_required: boolean }>
}

export function backupDownloadUrl(name: string): string {
  return `/api/v1/ops/backups/${encodeURIComponent(name)}`
}

export async function resetDatabase(): Promise<{ ok: boolean }> {
  return request('/ops/reset-database', {
    method: 'POST',
    body: JSON.stringify({ confirm: 'RESET DATABASE' }),
  })
}

export interface MessageQuery {
  q?: string
  /** 多标签交集：每个值单独一个 tag 参数（?tag=A&tag=B） */
  tag?: string | string[]
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
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== '' && item != null) params.append(key, String(item))
      }
    } else {
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