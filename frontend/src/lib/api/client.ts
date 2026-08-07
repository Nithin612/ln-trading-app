import { useAuthStore } from '@/store/authStore'

const BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Resolve the bearer token for a request.
 *
 * The access token lives in memory (Zustand) — `credentials: 'include'` only
 * carries the refresh COOKIE, which `get_current_user` does not accept. So a
 * call that forgets to pass a token is not "unauthenticated but working": it
 * is a hard 401. Two whole features (journal, portfolio) shipped that way —
 * every one of their 17 calls omitted the argument and 401'd against a live
 * backend, invisible to the suite because page tests mock the API module.
 *
 * Falling back to the store makes the token the client's business, not each
 * call site's. An explicit argument still wins (tests and the auth flow pass
 * one deliberately); `anonymous` opts out entirely for login/refresh.
 */
function resolveToken(explicit: string | undefined, anonymous: boolean): string | undefined {
  if (anonymous) return undefined
  if (explicit) return explicit
  return useAuthStore.getState().accessToken ?? undefined
}

async function request<T>(
  method: string,
  path: string,
  options: {
    body?: unknown
    token?: string
    formData?: FormData
    anonymous?: boolean
  } = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  if (!options.formData) {
    headers['Content-Type'] = 'application/json'
  }
  const token = resolveToken(options.token, options.anonymous ?? false)
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: options.formData ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const raw = (body as { detail?: unknown }).detail
    let message: string
    if (typeof raw === 'string') {
      message = raw
    } else if (Array.isArray(raw) && raw.length > 0) {
      // Pydantic 422 validation errors — take the first one and clean it up
      const first = raw[0] as { msg?: string; loc?: string[] }
      const field = first.loc?.slice(1).join('.') ?? ''
      const reason = first.msg?.replace(/^value is not a valid email address: /, '') ?? 'Invalid value'
      message = field ? `${field}: ${reason}` : reason
    } else {
      message = res.statusText
    }
    throw new ApiError(res.status, message)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string, token?: string) => request<T>('GET', path, { token }),
  post: <T>(path: string, body: unknown, token?: string) =>
    request<T>('POST', path, { body, token }),
  postForm: <T>(path: string, formData: FormData, token?: string) =>
    request<T>('POST', path, { formData, token }),
  put: <T>(path: string, body: unknown, token?: string) =>
    request<T>('PUT', path, { body, token }),
  patch: <T>(path: string, body: unknown, token?: string) =>
    request<T>('PATCH', path, { body, token }),
  delete: <T>(path: string, token?: string) => request<T>('DELETE', path, { token }),

  /** Login / refresh — these MINT the token, so they must never carry a stale one. */
  anon: {
    post: <T>(path: string, body: unknown) =>
      request<T>('POST', path, { body, anonymous: true }),
  },
}
