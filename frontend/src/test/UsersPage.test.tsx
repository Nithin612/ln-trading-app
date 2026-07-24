import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { UsersPage } from '@/pages/admin/UsersPage'
import { useAuthStore } from '@/store/authStore'
import * as usersApiModule from '@/lib/api/users'

const mockUser = {
  id: 1, email: 'admin@example.com', full_name: 'Admin', role: 'admin',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, is_active: true, trading_mode: 'paper', allow_offmarket_entry: false,
  created_at: '', updated_at: '',
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: 'admin-tok', user: mockUser })
})

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('UsersPage', () => {
  it('shows user list when loaded', async () => {
    vi.spyOn(usersApiModule.usersApi, 'list').mockResolvedValue({
      items: [mockUser],
      total: 1, page: 1, size: 20, pages: 1,
    })

    setup()
    await waitFor(() => expect(screen.getByText('Admin')).toBeInTheDocument())
    expect(screen.getByText('admin@example.com')).toBeInTheDocument()
  })

  it('shows New User button for admin', async () => {
    vi.spyOn(usersApiModule.usersApi, 'list').mockResolvedValue({
      items: [], total: 0, page: 1, size: 20, pages: 0,
    })

    setup()
    expect(screen.getByRole('button', { name: /new user/i })).toBeInTheDocument()
  })

  it('opens create modal on button click', async () => {
    vi.spyOn(usersApiModule.usersApi, 'list').mockResolvedValue({
      items: [], total: 0, page: 1, size: 20, pages: 0,
    })

    setup()
    await userEvent.click(screen.getByRole('button', { name: /new user/i }))
    expect(screen.getByRole('heading', { name: /new user/i })).toBeInTheDocument()
  })
})
