import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import * as analyticsApiModule from '@/lib/api/analytics'
import type { OutcomeAnalyticsResponse, OutcomeStyleStats } from '@/lib/api/analytics'
import { OutcomesPage } from '@/features/analytics/OutcomesPage'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, profit_lock_enabled: false, is_active: true,
  trading_mode: 'paper', created_at: '', updated_at: '',
}

function styleStat(o: Partial<OutcomeStyleStats> & { style: string }): OutcomeStyleStats {
  return {
    total: 0, entered: 0, wins: 0, losses: 0, no_entry: 0, timed_out: 0, pending: 0,
    sample: 0, hit_rate: null, entry_rate: null, avg_return_pct: null, ...o,
  }
}

function makeResponse(o: Partial<OutcomeAnalyticsResponse> = {}): OutcomeAnalyticsResponse {
  return {
    epoch: '2026-07-19T00:00:00Z',
    total_outcomes: 0,
    styles: [
      styleStat({ style: 'intraday' }), styleStat({ style: 'swing' }),
      styleStat({ style: 'fno' }), styleStat({ style: 'investment' }),
    ],
    ...o,
  }
}

beforeEach(() => { useAuthStore.setState({ accessToken: 'tok', user: mockUser }) })

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}><MemoryRouter><OutcomesPage /></MemoryRouter></QueryClientProvider>,
  )
}

describe('OutcomesPage', () => {
  it('renders per-style cards with hit-rate and breakdown', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getOutcomes').mockResolvedValue(makeResponse({
      total_outcomes: 4,
      styles: [
        styleStat({ style: 'swing', total: 4, sample: 4, entered: 3, wins: 2, losses: 1, no_entry: 1, hit_rate: 2 / 3, avg_return_pct: 3.0 }),
        styleStat({ style: 'intraday' }), styleStat({ style: 'fno' }), styleStat({ style: 'investment' }),
      ],
    }))
    setup()
    await waitFor(() => expect(screen.getByText('Swing')).toBeInTheDocument())
    expect(screen.getByText(/66\.67%/)).toBeInTheDocument()   // 2/3 hit rate
    expect(screen.getByText(/2 win/)).toBeInTheDocument()
    expect(screen.getByText('Intraday')).toBeInTheDocument()  // all four cards render
  })

  it('shows the empty note when no outcomes yet', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getOutcomes').mockResolvedValue(makeResponse())
    setup()
    await waitFor(() => expect(screen.getByText(/No signal outcomes recorded yet/i)).toBeInTheDocument())
    expect(screen.getByText('Investment')).toBeInTheDocument()
  })

  it('shows loading skeletons', () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getOutcomes').mockReturnValue(new Promise(() => {}))
    setup()
    expect(screen.getByLabelText('loading analytics')).toBeInTheDocument()
  })

  it('shows an error state with retry', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getOutcomes').mockRejectedValue(new Error('boom'))
    setup()
    await waitFor(() => expect(screen.getByText(/Could not load outcome analytics/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
