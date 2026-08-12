import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SeasonalityPanel } from '@/pages/stocks/SeasonalityPanel'
import { useAuthStore } from '@/store/authStore'
import * as seasonalityApiModule from '@/lib/api/seasonality'

beforeEach(() => {
  useAuthStore.setState({
    accessToken: 'test-token',
    user: {
      id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
      capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
      max_trades_per_day: 2, is_active: true, trading_mode: 'paper',
      allow_offmarket_entry: false, profit_lock_enabled: false,
      created_at: '', updated_at: '',
    },
  })
})

const emptyMonths = Array.from({ length: 12 }, (_, i) => ({
  month: i + 1, n: 0, positive: 0, pct_positive: null, avg_return_pct: null,
  median_return_pct: null, best_return_pct: null, worst_return_pct: null,
  avg_positive_pct: null, avg_negative_pct: null,
}))

function wrap(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SeasonalityPanel', () => {
  it('renders the monthly table and the directional average', async () => {
    const months = emptyMonths.map((m) =>
      m.month === 8
        ? {
            ...m, n: 12, positive: 1, pct_positive: 8.33, avg_return_pct: -3.2,
            median_return_pct: -2, best_return_pct: 5, worst_return_pct: -19.1,
            avg_positive_pct: 5, avg_negative_pct: -6,
          }
        : m,
    )
    vi.spyOn(seasonalityApiModule.seasonalityApi, 'get').mockResolvedValue({
      stock_id: 1, total_observations: 40, years_covered: 5,
      first_month: '2021-02-01', last_month: '2026-07-01', months,
    })

    wrap(<SeasonalityPanel stockId={1} />)

    expect(await screen.findByText(/Monthly return bias/i)).toBeInTheDocument()
    expect(screen.getByText('Aug')).toBeInTheDocument()
    // −3.2% average renders with the down glyph, not colour alone
    expect(screen.getByText(/▼ -3.20%/)).toBeInTheDocument()
    // Aug has n=12 (robust) → no thin-sample footnote shown
    expect(screen.queryByText(/fewer than 5 years of data/i)).not.toBeInTheDocument()
  })

  it('renders a loading skeleton while the request is in flight', () => {
    vi.spyOn(seasonalityApiModule.seasonalityApi, 'get').mockImplementation(
      () => new Promise(() => {}), // never resolves → stays in the loading state
    )

    const { container } = wrap(<SeasonalityPanel stockId={1} />)

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
    expect(screen.queryByText(/Monthly return bias/i)).not.toBeInTheDocument()
  })

  it('flags thin (low-year) months as not tradeable', async () => {
    const months = emptyMonths.map((m) =>
      m.month === 3
        ? {
            ...m, n: 2, positive: 1, pct_positive: 50, avg_return_pct: 4,
            median_return_pct: 4, best_return_pct: 8, worst_return_pct: -1,
            avg_positive_pct: 8, avg_negative_pct: -1,
          }
        : m,
    )
    vi.spyOn(seasonalityApiModule.seasonalityApi, 'get').mockResolvedValue({
      stock_id: 1, total_observations: 2, years_covered: 2,
      first_month: '2024-03-01', last_month: '2025-03-01', months,
    })

    const { container } = wrap(<SeasonalityPanel stockId={1} />)

    // the per-cell affordance: a thin-sample footnote + the marked row
    expect(await screen.findByText(/fewer than 5 years of data/i)).toBeInTheDocument()
    expect(container.querySelector('tr[data-thin="true"]')).toBeInTheDocument()
  })

  it('shows an empty state when there is no history', async () => {
    vi.spyOn(seasonalityApiModule.seasonalityApi, 'get').mockResolvedValue({
      stock_id: 1, total_observations: 0, years_covered: 0,
      first_month: null, last_month: null, months: emptyMonths,
    })

    wrap(<SeasonalityPanel stockId={1} />)

    expect(await screen.findByText(/Not enough history/i)).toBeInTheDocument()
  })

  it('shows an error state when the request fails', async () => {
    vi.spyOn(seasonalityApiModule.seasonalityApi, 'get').mockRejectedValue(new Error('boom'))

    wrap(<SeasonalityPanel stockId={1} />)

    expect(await screen.findByText(/Couldn't load seasonality/i)).toBeInTheDocument()
  })
})
