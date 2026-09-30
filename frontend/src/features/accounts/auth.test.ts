import { beforeEach, describe, expect, it, vi } from 'vitest'
import { get } from 'svelte/store'
import { authenticatedRequest, clearSession, login, logout, session } from './auth'
import { apiRequest } from '../../shared/api'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('account session', () => {
  beforeEach(() => {
    const values = new Map<string, string>()
    vi.stubGlobal('sessionStorage', {
      getItem: (key: string) => values.get(key) || null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    })
    clearSession()
    vi.restoreAllMocks()
  })

  it('refreshes once on 401 and stores the rotated refresh token', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ access: 'old', refresh: 'refresh-1' }))
      .mockResolvedValueOnce(json({ detail: 'Expired' }, 401))
      .mockResolvedValueOnce(json({ access: 'new', refresh: 'refresh-2' }))
      .mockResolvedValueOnce(json({ email: 'member@example.com' }))
    vi.stubGlobal('fetch', fetchMock)

    await login('member@example.com', 'password')
    await authenticatedRequest('/api/v1/auth/me/')

    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect((fetchMock.mock.calls[3][1].headers as Headers).get('Authorization')).toBe('Bearer new')
    expect(get(session)?.refresh).toBe('refresh-2')
    expect(JSON.parse(sessionStorage.getItem('dj-moo-session') || 'null').refresh).toBe('refresh-2')
  })

  it('shares one refresh request across concurrent 401 responses', async () => {
    let profileCalls = 0
    let refreshCalls = 0
    let releaseInitialResponses!: (responses: Response[]) => void
    let releaseRefresh!: (response: Response) => void
    let announceRefresh!: () => void
    const initialResponses = new Promise<Response[]>((resolve) => { releaseInitialResponses = resolve })
    const refreshResponse = new Promise<Response>((resolve) => { releaseRefresh = resolve })
    const refreshStarted = new Promise<void>((resolve) => { announceRefresh = resolve })
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith('/login/')) return Promise.resolve(json({ access: 'old', refresh: 'refresh-1' }))
      if (path.endsWith('/token/refresh/')) {
        refreshCalls += 1
        announceRefresh()
        return refreshResponse
      }
      const currentProfileCall = ++profileCalls
      if (profileCalls === 2) releaseInitialResponses([json({ detail: 'Expired' }, 401), json({ detail: 'Expired' }, 401)])
      if (currentProfileCall <= 2) return initialResponses.then((responses) => responses[currentProfileCall - 1])
      return Promise.resolve(json({ email: 'member@example.com' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    await login('member@example.com', 'password')
    const requests = [
      authenticatedRequest('/api/v1/auth/me/'),
      authenticatedRequest('/api/v1/auth/me/'),
    ]
    await refreshStarted
    expect(refreshCalls).toBe(1)
    releaseRefresh(json({ access: 'new', refresh: 'refresh-2' }))
    await expect(Promise.all(requests)).resolves.toEqual([
      { email: 'member@example.com' },
      { email: 'member@example.com' },
    ])
    expect(fetchMock).toHaveBeenCalledTimes(6)
    expect(get(session)?.refresh).toBe('refresh-2')
  })

  it('clears the session even if logout cannot reach the server', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json({ access: 'a', refresh: 'r' }))
      .mockRejectedValueOnce(new Error('offline')))
    await login('member@example.com', 'password')
    await expect(logout()).rejects.toThrow('offline')
    expect(get(session)).toBeNull()
  })

  it('sends the refresh token to logout and clears the local session', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ access: 'a', refresh: 'r' }))
      .mockResolvedValueOnce(json({ message: 'logged out' }))
    vi.stubGlobal('fetch', fetchMock)

    await login('member@example.com', 'password')
    await logout()

    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/logout/')
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({ refresh: 'r' })
    expect(get(session)).toBeNull()
    expect(sessionStorage.getItem('dj-moo-session')).toBeNull()
  })
})

describe('API response handling', () => {
  it('accepts a 204 response without attempting to parse a JSON body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, {
      status: 204,
      headers: { 'Content-Type': 'application/json' },
    })))

    await expect(apiRequest<null>('/api/v1/auth/me/delete/', { method: 'DELETE' })).resolves.toBeNull()
  })
})