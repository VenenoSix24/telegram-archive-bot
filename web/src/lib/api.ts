import type {
  Message,
  MessagesResponse,
  Stats,
  TagsResponse,
} from '@/lib/types'

/** 未登录（cookie 失效）时的统一跳转。 */
export class AuthError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...init,
  })
  if (resp.status === 401) {
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

export interface MessageQuery {
  q?: string
  tag?: string
  media_type?: string
  rating?: number
  source_chat_id?: number
  limit?: number
  offset?: number
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