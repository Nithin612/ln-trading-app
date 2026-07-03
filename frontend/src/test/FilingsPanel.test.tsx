import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FilingsPanel } from '@/features/dashboard/FilingsPanel'
import { useAuthStore } from '@/store/authStore'
import * as filingsApiModule from '@/lib/api/filings'
import type { FilingOut } from '@/lib/api/filings'

beforeEach(() => {
  useAuthStore.setState({
    accessToken: 'test-token',
    user: {
      id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
      capital_inr: '500000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
      max_trades_per_day: 5, is_active: true, trading_mode: 'paper',
      created_at: '', updated_at: '',
    },
  })
})

function makeFiling(overrides: Partial<FilingOut> = {}): FilingOut {
  return {
    id: 1,
    stock_id: 1,
    symbol: 'RELIANCE',
    filing_type: 'earnings',
    headline: 'Q4 FY26 Financial Results',
    body: null,
    filing_date: '2026-05-16',
    filing_time: new Date().toISOString(),
    source: 'NSE',
    source_url: null,
    sentiment_score: null,
    is_high_impact: true,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('FilingsPanel', () => {
  it('shows empty state when no filings', async () => {
    vi.spyOn(filingsApiModule.filingsApi, 'getRecent').mockResolvedValue({ total: 0, filings: [] })
    wrap(<FilingsPanel />)
    await waitFor(() => {
      expect(screen.getByText(/No filings in the last/i)).toBeInTheDocument()
    })
  })

  it('renders filing headline and symbol', async () => {
    vi.spyOn(filingsApiModule.filingsApi, 'getRecent').mockResolvedValue({
      total: 1,
      filings: [makeFiling()],
    })
    wrap(<FilingsPanel />)
    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument()
      expect(screen.getByText('Q4 FY26 Financial Results')).toBeInTheDocument()
    })
  })

  it('shows HIGH IMPACT badge for earnings filings', async () => {
    vi.spyOn(filingsApiModule.filingsApi, 'getRecent').mockResolvedValue({
      total: 1,
      filings: [makeFiling({ is_high_impact: true })],
    })
    wrap(<FilingsPanel />)
    await waitFor(() => {
      expect(screen.getByText('HIGH IMPACT')).toBeInTheDocument()
    })
  })

  it('does not show HIGH IMPACT badge for low-impact filings', async () => {
    vi.spyOn(filingsApiModule.filingsApi, 'getRecent').mockResolvedValue({
      total: 1,
      filings: [makeFiling({ filing_type: 'board_meeting', is_high_impact: false })],
    })
    wrap(<FilingsPanel />)
    await waitFor(() => {
      expect(screen.queryByText('HIGH IMPACT')).not.toBeInTheDocument()
    })
  })

  it('shows total count in panel header', async () => {
    vi.spyOn(filingsApiModule.filingsApi, 'getRecent').mockResolvedValue({
      total: 7,
      filings: [makeFiling()],
    })
    wrap(<FilingsPanel hours={24} />)
    await waitFor(() => {
      expect(screen.getByText(/7 in 24h/i)).toBeInTheDocument()
    })
  })
})
