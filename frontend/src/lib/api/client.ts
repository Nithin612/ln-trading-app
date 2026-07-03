const BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; token?: string; formData?: FormData } = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  if (!options.formData) {
    headers['Content-Type'] = 'application/json'
  }
  if (options.token) {
    headers['Authorization'] = `Bearer ${options.token}`
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
}
