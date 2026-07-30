import { renderHook, act } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from '@/hooks/useAuth'
import { useAuthStore } from '@/store/authStore'
import * as authApiModule from '@/lib/api/auth'

const mockUser = {
  id: 1,
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'user',
  capital_inr: '100000.00',
  risk_per_trade_pct: '2.00',
  daily_loss_limit_pct: '3.00',
  max_trades_per_day: 2,
  is_active: true,
  trading_mode: 'paper', allow_offmarket_entry: false, profit_lock_enabled: false,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, user: null })
})

describe('useAuth', () => {
  it('starts unauthenticated', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })

  it('login sets token and user', async () => {
    vi.spyOn(authApiModule.authApi, 'login').mockResolvedValue({
      access_token: 'tok123',
      token_type: 'bearer',
      user: mockUser,
    })

    const { result } = renderHook(() => useAuth())
    await act(async () => {
      await result.current.login('test@example.com', 'Secret123')
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.accessToken).toBe('tok123')
    expect(result.current.user?.email).toBe('test@example.com')
  })

  it('logout clears state', async () => {
    useAuthStore.setState({ accessToken: 'tok123', user: mockUser })
    vi.spyOn(authApiModule.authApi, 'logout').mockResolvedValue({ message: 'ok' })

    const { result } = renderHook(() => useAuth())
    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })

  it('isAdmin is true for admin role', () => {
    useAuthStore.setState({ accessToken: 'tok', user: { ...mockUser, role: 'admin' } })
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAdmin).toBe(true)
  })

  it('isAdmin is false for user role', () => {
    useAuthStore.setState({ accessToken: 'tok', user: mockUser })
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAdmin).toBe(false)
  })
})
