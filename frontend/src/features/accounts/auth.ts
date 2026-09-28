import { get, writable } from 'svelte/store'
import { ApiError, apiRequest } from '../../shared/api'

export type Tokens = { access: string; refresh: string }

const storageKey = 'dj-moo-session'

function storedSession(): Tokens | null {
  if (typeof sessionStorage === 'undefined') return null
  try {
    const value = JSON.parse(sessionStorage.getItem(storageKey) || 'null')
    return typeof value?.access === 'string' && typeof value?.refresh === 'string' ? value : null
  } catch {
    return null
  }
}

export const session = writable<Tokens | null>(storedSession())
let refreshing: Promise<string> | null = null

function save(tokens: Tokens) {
  session.set(tokens)
  if (typeof sessionStorage !== 'undefined') sessionStorage.setItem(storageKey, JSON.stringify(tokens))
}

export function clearSession() {
  session.set(null)
  if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem(storageKey)
}

export async function login(email: string, password: string) {
  const tokens = await apiRequest<Tokens>('/api/v1/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  save(tokens)
}

async function renew(): Promise<string> {
  const current = get(session)
  if (!current) throw new ApiError('ログインしてください。', 401)
  try {
    const updated = await apiRequest<{ access: string; refresh?: string }>(
      '/api/v1/auth/token/refresh/',
      { method: 'POST', body: JSON.stringify({ refresh: current.refresh }) },
    )
    if (get(session)?.refresh !== current.refresh) throw new ApiError('ログインしてください。', 401)
    save({ access: updated.access, refresh: updated.refresh || current.refresh })
    return updated.access
  } catch (error) {
    clearSession()
    throw error
  }
}

export async function authenticatedRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const current = get(session)
  if (!current) throw new ApiError('ログインしてください。', 401)

  const send = (access: string) => {
    const headers = new Headers(options.headers)
    headers.set('Authorization', `Bearer ${access}`)
    return apiRequest<T>(path, { ...options, headers })
  }

  try {
    return await send(current.access)
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error
    try {
      const latest = get(session)
      const access = latest && latest.access !== current.access
        ? latest.access
        : await (refreshing ??= renew().finally(() => { refreshing = null }))
      return await send(access)
    } catch (retryError) {
      if (retryError instanceof ApiError && retryError.status === 401) clearSession()
      throw retryError
    }
  }
}

export async function logout() {
  const current = get(session)
  try {
    if (current) {
      await apiRequest('/api/v1/auth/logout/', {
        method: 'POST',
        body: JSON.stringify({ refresh: current.refresh }),
      })
    }
  } finally {
    clearSession()
  }
}