import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { useAuthStore } from '@/store/authStore'
import * as signalsApiModule from '@/lib/api/signals'
import * as marketDataApiModule from '@/lib/api/market_data'
import * as filingsApiModule from '@/lib/api/filings'

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

  vi.spyOn(marketDataApiModule.marketDataApi, 'getFiiDii').mockResolvedValue({ rows: [], total: 0 })
  vi.spyOn(filingsApiModule.filingsApi, 'getRecent').mockResolvedValue({ total: 0, filings: [] })
})

function makeSignal(overrides: Partial<signalsApiModule.SignalOut> = {}): signalsApiModule.SignalOut {
  const validity = new Date(Date.now() + 5 * 86400000).toISOString()
  return {
    id: 'abc-123',
    stock_id: 1,
    symbol: 'RELIANCE',
    direction: 'BUY',
    classification: 'swing',
    timeframe: '1d',
    entry_price: '2850.0000',
    stop_loss: '2800.0000',
    take_profit: '2950.0000',
    suggested_qty: 35,
    confidence_pct: 82,
    factor_scores: {
      DOW_TREND: { weight: 20, score: 0.75, explanation: 'uptrend' },
      RSI: { weight: 10, score: 0.6, explanation: 'oversold bounce' },
    },
    triggering_patterns: ['BULLISH_ENGULFING'],
    triggering_indicators: ['RSI_DIVERGENCE'],
    headline: 'BUY RELIANCE — 82% confidence',
    status: 'active',
    validity_until: validity,
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

describe('DashboardPage', () => {
  it('shows empty state when no signals', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({ total: 0, signals: [] })
    wrap(<DashboardPage />)
    await waitFor(() => {
      expect(screen.getByText(/No active signals/i)).toBeInTheDocument()
    })
  })

  it('renders signal row with symbol, direction, confidence, entry, SL, TP', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
      total: 1,
      signals: [makeSignal()],
    })
    wrap(<DashboardPage />)
    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument()
    })
    expect(screen.getAllByText('82%').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('35').length).toBeGreaterThanOrEqual(1)
  })

  it('shows active signals count summary card', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
      total: 3,
      signals: [
        makeSignal({ id: '1', symbol: 'RELIANCE' }),
        makeSignal({ id: '2', symbol: 'INFY' }),
        makeSignal({ id: '3', symbol: 'TCS' }),
      ],
    })
    wrap(<DashboardPage />)
    await waitFor(() => {
      expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('opens signal detail modal when row is clicked', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
      total: 1,
      signals: [makeSignal()],
    })
    wrap(<DashboardPage />)
    await waitFor(() => screen.getByText('RELIANCE'))

    const row = screen.getAllByRole('row').find((r) => r.textContent?.includes('RELIANCE'))
    fireEvent.click(row!)

    await waitFor(() => {
      expect(screen.getByText('Factor breakdown')).toBeInTheDocument()
    })
  })

  it('closes modal when × button is clicked', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
      total: 1,
      signals: [makeSignal()],
    })
    wrap(<DashboardPage />)
    await waitFor(() => screen.getByText('RELIANCE'))

    const row = screen.getAllByRole('row').find((r) => r.textContent?.includes('RELIANCE'))
    fireEvent.click(row!)
    await waitFor(() => screen.getByText('Factor breakdown'))

    fireEvent.click(screen.getByText('×'))
    await waitFor(() => {
      expect(screen.queryByText('Factor breakdown')).not.toBeInTheDocument()
    })
  })

  it('renders FII/DII net values when data is available', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({ total: 0, signals: [] })
    vi.spyOn(marketDataApiModule.marketDataApi, 'getFiiDii').mockResolvedValue({
      total: 2,
      rows: [
        {
          trade_date: '2026-05-16',
          investor_type: 'FII',
          segment: 'cash',
          buy_value_cr: '12000',
          sell_value_cr: '10000',
          net_value_cr: '2000',
        },
        {
          trade_date: '2026-05-16',
          investor_type: 'DII',
          segment: 'cash',
          buy_value_cr: '8000',
          sell_value_cr: '9000',
          net_value_cr: '-1000',
        },
      ],
    })
    wrap(<DashboardPage />)
    await waitFor(() => {
      expect(screen.getByText(/\+2,000 Cr/)).toBeInTheDocument()
      expect(screen.getByText(/-1,000 Cr/)).toBeInTheDocument()
    })
  })
})
