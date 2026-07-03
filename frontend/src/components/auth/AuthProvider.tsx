import { useEffect, useState } from 'react'
import { authApi } from '@/lib/api/auth'
import { useAuthStore } from '@/store/authStore'

interface AuthProviderProps {
  children: React.ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const setAuth = useAuthStore((s) => s.setAuth)
  // Start ready if we already have a token (same-session navigation, not page refresh)
  const [ready, setReady] = useState(() => useAuthStore.getState().accessToken !== null)

  useEffect(() => {
    // If a token was already in store, nothing to restore
    if (useAuthStore.getState().accessToken) return

    authApi
      .refresh()
      .then((data) => authApi.me(data.access_token).then((user) => setAuth(data.access_token, user)))
      .catch(() => { /* no valid cookie — proceed to login */ })
      .finally(() => { setReady(true) })
  // Intentional mount-only effect — store reference stable, setAuth stable
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!ready) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--color-surface)',
          color: 'var(--color-text-muted)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.875rem',
        }}
      >
        Loading…
      </div>
    )
  }

  return <>{children}</>
}
