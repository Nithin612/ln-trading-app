/**
 * API client auth contract.
 *
 * Regression cover for a bug that made two whole features unusable: the
 * journal and portfolio API modules never took a token parameter, so all 17
 * of their calls went out with no Authorization header and 401'd against a
 * live backend. Page tests mock the API modules, so nothing caught it — the
 * seam between the module and the client was untested. These tests exercise
 * that seam through a mocked fetch.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api/client'
import { authApi } from '@/lib/api/auth'
import { journalApi } from '@/lib/api/journal'
import { getNetWorth } from '@/lib/api/portfolio'
import { useAuthStore } from '@/store/authStore'

function mockFetch(body: unknown = {}) {
  const spy = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
  })
  vi.stubGlobal('fetch', spy)
  return spy
}

/** The Authorization header of the Nth (default first) fetch call. */
function authHeader(spy: ReturnType<typeof mockFetch>, call = 0): string | undefined {
  const init = spy.mock.calls[call][1] as { headers: Record<string, string> }
  return init.headers['Authorization']
}

describe('api client — token resolution', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    useAuthStore.setState({ accessToken: null, user: null })
  })

  it('attaches the store token when the call site passes none', async () => {
    useAuthStore.setState({ accessToken: 'store-token', user: null })
    const spy = mockFetch()

    await api.get('/anything')

    expect(authHeader(spy)).toBe('Bearer store-token')
  })

  it('prefers an explicitly passed token over the store', async () => {
    useAuthStore.setState({ accessToken: 'store-token', user: null })
    const spy = mockFetch()

    await api.get('/anything', 'explicit-token')

    expect(authHeader(spy)).toBe('Bearer explicit-token')
  })

  it('sends no Authorization header when logged out', async () => {
    const spy = mockFetch()

    await api.get('/anything')

    expect(authHeader(spy)).toBeUndefined()
  })

  it('never attaches a stale token to login or refresh', async () => {
    useAuthStore.setState({ accessToken: 'expired-token', user: null })
    const spy = mockFetch({ access_token: 'fresh' })

    await authApi.login('a@b.com', 'pw')
    await authApi.refresh()

    expect(authHeader(spy, 0)).toBeUndefined()
    expect(authHeader(spy, 1)).toBeUndefined()
  })
})

describe('journal + portfolio reach the API authenticated', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    useAuthStore.setState({ accessToken: 'live-token', user: null })
  })

  // The exact calls the pasted server log showed 401'ing.
  it('journal list carries the bearer token', async () => {
    const spy = mockFetch({ total: 0, entries: [] })

    await journalApi.list({ limit: 20, offset: 0 })

    expect(spy.mock.calls[0][0]).toContain('/journal/')
    expect(authHeader(spy)).toBe('Bearer live-token')
  })

  it('journal emotion analytics carries the bearer token', async () => {
    const spy = mockFetch({})

    await journalApi.analytics()

    expect(authHeader(spy)).toBe('Bearer live-token')
  })

  it('portfolio net-worth carries the bearer token', async () => {
    const spy = mockFetch({})

    await getNetWorth()

    expect(spy.mock.calls[0][0]).toContain('/portfolio/net-worth')
    expect(authHeader(spy)).toBe('Bearer live-token')
  })

  it('journal mutations carry the token too, not just reads', async () => {
    const spy = mockFetch({})

    await journalApi.create({ trade_date: '2026-08-07' })
    await journalApi.delete('some-id')

    expect(authHeader(spy, 0)).toBe('Bearer live-token')
    expect(authHeader(spy, 1)).toBe('Bearer live-token')
  })
})
