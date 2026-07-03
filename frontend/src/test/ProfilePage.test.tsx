import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { useAuthStore } from '@/store/authStore'
import * as authApiModule from '@/lib/api/auth'

const USER = {
  id: 1,
  email: 'nithin@example.com',
  full_name: 'Nithin Raj',
  role: 'admin',
  capital_inr: '500000',
  risk_per_trade_pct: '2',
  daily_loss_limit_pct: '3',
  max_trades_per_day: 5,
  is_active: true,
  trading_mode: 'paper',
  created_at: '2025-01-15T00:00:00Z',
  updated_at: '2025-01-15T00:00:00Z',
}

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProfilePage', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: 'tok', user: USER })
    vi.spyOn(authApiModule.authApi, 'me').mockResolvedValue(USER)
  })

  it('renders user name and email', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText('Nithin Raj').length).toBeGreaterThanOrEqual(1))
    expect(screen.getAllByText('nithin@example.com').length).toBeGreaterThanOrEqual(1)
  })

  it('shows admin badge for admin role', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText('Admin').length).toBeGreaterThanOrEqual(1))
  })

  it('shows paper trading mode badge', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText(/Paper Trading/).length).toBeGreaterThanOrEqual(1))
  })

  it('shows capital stat card', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText(/5,00,000/).length).toBeGreaterThanOrEqual(1))
  })

  it('shows risk per trade stat card', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText('2%').length).toBeGreaterThanOrEqual(1))
  })

  it('shows max trades per day stat card', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText('5').length).toBeGreaterThanOrEqual(1))
  })

  it('shows account details section', async () => {
    setup()
    await waitFor(() => expect(screen.getByText('Account Details')).toBeInTheDocument())
    expect(screen.getByText('Risk Parameters')).toBeInTheDocument()
  })

  it('shows Active status', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText('Active').length).toBeGreaterThanOrEqual(1))
  })

  it('renders initials avatar with NR', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText('NR').length).toBeGreaterThanOrEqual(1))
  })

  it('shows daily loss limit in risk parameters', async () => {
    setup()
    await waitFor(() => expect(screen.getByText('3%')).toBeInTheDocument())
  })

  it('shows member since label', async () => {
    setup()
    await waitFor(() => expect(screen.getByText('Member since')).toBeInTheDocument())
  })

  it('shows footer note about contacting admin', async () => {
    setup()
    await waitFor(() => expect(screen.getByText(/contact your admin/i)).toBeInTheDocument())
  })
})
