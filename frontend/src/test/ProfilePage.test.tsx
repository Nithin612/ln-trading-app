import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { useAuthStore } from '@/store/authStore'
import * as authApiModule from '@/lib/api/auth'
import * as usersApiModule from '@/lib/api/users'

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
  trading_mode: 'paper', allow_offmarket_entry: false,
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

  it('shows account details and trading settings sections', async () => {
    setup()
    await waitFor(() => expect(screen.getByText('Account Details')).toBeInTheDocument())
    expect(screen.getByText('Trading Settings')).toBeInTheDocument()
  })

  it('shows Active status', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText('Active').length).toBeGreaterThanOrEqual(1))
  })

  it('renders initials avatar with NR', async () => {
    setup()
    await waitFor(() => expect(screen.getAllByText('NR').length).toBeGreaterThanOrEqual(1))
  })

  it('shows daily loss limit in trading settings', async () => {
    setup()
    await waitFor(() => expect(screen.getByText('Daily loss limit')).toBeInTheDocument())
  })

  it('shows member since label', async () => {
    setup()
    await waitFor(() => expect(screen.getByText('Member since')).toBeInTheDocument())
  })

  it('lets the user edit and save trading settings', async () => {
    const updateSpy = vi
      .spyOn(usersApiModule.usersApi, 'update')
      .mockResolvedValue({ ...USER, capital_inr: '250000' })
    setup()
    await waitFor(() => expect(screen.getByText('Trading Settings')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    const capital = await screen.findByLabelText('Capital (₹)')
    fireEvent.change(capital, { target: { value: '250000' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith('tok', 1, {
        capital_inr: '250000',
        risk_per_trade_pct: '2',
        daily_loss_limit_pct: '3',
        max_trades_per_day: 5,
        allow_offmarket_entry: false,
      }),
    )
  })

  it('includes the off-market-entry toggle in the save payload', async () => {
    const updateSpy = vi
      .spyOn(usersApiModule.usersApi, 'update')
      .mockResolvedValue({ ...USER, allow_offmarket_entry: true })
    setup()
    await waitFor(() => expect(screen.getByText('Trading Settings')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.click(await screen.findByRole('checkbox', { name: /allow off-market entry/i }))
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith(
        'tok', 1, expect.objectContaining({ allow_offmarket_entry: true }),
      ),
    )
  })

  it('blocks save when risk % is out of bounds', async () => {
    setup()
    await waitFor(() => expect(screen.getByText('Trading Settings')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))

    const risk = await screen.findByLabelText('Risk / trade (%)')
    fireEvent.change(risk, { target: { value: '50' } })  // > 10% cap

    expect(screen.getByText(/Risk per trade must be/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
  })
})
