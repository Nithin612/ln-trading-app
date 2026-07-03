import { useCallback } from 'react'
import { authApi } from '@/lib/api/auth'
import { ApiError } from '@/lib/api/client'
import { useAuthStore } from '@/store/authStore'

export function useAuth() {
  const { accessToken, user, setAuth, clearAuth } = useAuthStore()

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await authApi.login(email, password)
      setAuth(data.access_token, data.user)
    },
    [setAuth],
  )

  const logout = useCallback(async () => {
    if (accessToken) {
      try {
        await authApi.logout(accessToken)
      } catch {
        // best-effort — clear local state regardless
      }
    }
    clearAuth()
  }, [accessToken, clearAuth])

  const refreshToken = useCallback(async () => {
    try {
      const data = await authApi.refresh()
      if (user) setAuth(data.access_token, user)
      return data.access_token
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearAuth()
      }
      throw err
    }
  }, [user, setAuth, clearAuth])

  return {
    accessToken,
    user,
    isAuthenticated: accessToken !== null,
    isAdmin: user?.role === 'admin',
    login,
    logout,
    refreshToken,
  }
}
