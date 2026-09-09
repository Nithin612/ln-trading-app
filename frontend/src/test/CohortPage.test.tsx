import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, it, expect, vi } from 'vitest'

import { useAuthStore } from '@/store/authStore'
import * as analyticsApiModule from '@/lib/api/analytics'
import type { GateCohortResponse } from '@/lib/api/analytics'
import { CohortPage } from '@/features/analytics/CohortPage'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, profit_lock_enabled: false, is_active: true,
  trading_mode: 'paper', created_at: '', updated_at: '',
}

function cohort(o: Partial<GateCohortResponse> = {}): GateCohortResponse {
  return {
    gate_key: 'regime_adx', gate: 'regime_gate', gate_status: 'reverted',
    supported: true, reason: null, scanned: 10, cohort_count: 1,
    cohort_realized_r: -1.2, cohort_realized_pnl_pct: -5.0,
    trades: [
      {
        signal_id: 's1', symbol: 'SRTL', direction: 'BUY',
        entry: 100, stop_loss: 95, take_profit: 110, confidence_pct: 78,
        reason: 'transitional ADX regime', outcome_status: 'sl_first',
        realized_pnl_pct: -5.0, realized_r: -1.2, entry_date: '2026-03-02',
        bars: [
          { t: '2026-03-01', o: 100, h: 102, low: 99, c: 101 },
          { t: '2026-03-02', o: 101, h: 103, low: 100, c: 100 },
        ],
      },
    ],
    ...o,
  }
}

beforeEach(() => { useAuthStore.setState({ accessToken: 'tok', user: mockUser }) })

function setup(key = 'regime_adx') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/analytics/registry/${key}`]}>
        <Routes>
          <Route path="/analytics/registry/:gateKey" element={<CohortPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CohortPage (U20)', () => {
  it('renders the would-block trades as a contact sheet', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateCohort').mockResolvedValue(cohort())
    setup()
    expect(await screen.findByText('SRTL')).toBeInTheDocument()
    expect(screen.getByText(/of 10 scanned/)).toBeInTheDocument()
    expect(screen.getByText('-1.20R total')).toBeInTheDocument()
    expect(screen.getByText(/transitional ADX regime/)).toBeInTheDocument()
    expect(screen.getByText(/stopped/)).toBeInTheDocument() // outcome glyph
  })

  it('shows the unsupported message for a live-state gate', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateCohort').mockResolvedValue(
      cohort({ supported: false, gate: '', gate_status: 'shadow', reason: 'needs live state', trades: [], cohort_count: 0 }),
    )
    setup('chase')
    expect(await screen.findByText(/No signal-only cohort/i)).toBeInTheDocument()
    expect(screen.getByText(/needs live state/)).toBeInTheDocument()
  })

  it('shows an empty state when the cohort is empty', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateCohort').mockResolvedValue(
      cohort({ cohort_count: 0, cohort_realized_r: null, cohort_realized_pnl_pct: null, trades: [] }),
    )
    setup()
    expect(await screen.findByText(/No trades in the would-block cohort/i)).toBeInTheDocument()
  })
})
