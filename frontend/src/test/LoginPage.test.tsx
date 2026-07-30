import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from '@/pages/LoginPage'
import { useAuthStore } from '@/store/authStore'
import * as authApiModule from '@/lib/api/auth'
import { ApiError } from '@/lib/api/client'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importActual) => {
  const actual = await importActual<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

const mockUser = {
  id: 1, email: 'a@example.com', full_name: 'A', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, is_active: true, trading_mode: 'paper', allow_offmarket_entry: false, profit_lock_enabled: false,
  created_at: '', updated_at: '',
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, user: null })
  mockNavigate.mockReset()
})

function setup() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  it('renders email and password fields', () => {
    setup()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('calls login and navigates on success', async () => {
    vi.spyOn(authApiModule.authApi, 'login').mockResolvedValue({
      access_token: 'tok', token_type: 'bearer', user: mockUser,
    })
    setup()

    await userEvent.type(screen.getByLabelText(/email/i), 'a@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'Secret123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'))
  })

  it('shows error on 401', async () => {
    vi.spyOn(authApiModule.authApi, 'login').mockRejectedValue(
      new ApiError(401, 'Invalid email or password'),
    )
    setup()

    await userEvent.type(screen.getByLabelText(/email/i), 'a@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() =>
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument(),
    )
  })

  it('shows deactivated message on 403', async () => {
    vi.spyOn(authApiModule.authApi, 'login').mockRejectedValue(
      new ApiError(403, 'Account is deactivated'),
    )
    setup()

    await userEvent.type(screen.getByLabelText(/email/i), 'a@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'Secret123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() =>
      expect(screen.getByText(/account is deactivated/i)).toBeInTheDocument(),
    )
  })
})
