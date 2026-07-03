import { create } from 'zustand'
import type { UserOut } from '@/lib/api/auth'

interface AuthState {
  accessToken: string | null
  user: UserOut | null
  setAuth: (token: string, user: UserOut) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAuth: (accessToken, user) => set({ accessToken, user }),
  clearAuth: () => set({ accessToken: null, user: null }),
}))
