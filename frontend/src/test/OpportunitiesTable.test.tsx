import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { OpportunitiesTable } from '@/features/alerts/OpportunitiesTable'
import * as signalsApiModule from '@/lib/api/signals'
import * as tradingApiModule from '@/lib/api/trading'
import { useAuthStore } from '@/store/authStore'
import { useTradingHaltStore } from '@/store/tradingHaltStore'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'T', role: 'user', capital_inr: '100000',
  risk_per_trade_pct: '2', daily_loss_limit_pct: '3', max_trades_per_day: 5,
  allow_offmarket_entry: true, profit_lock_enabled: false, is_active: true,
  trading_mode: 'paper', created_at: '', updated_at: '',
}

// Live quotes hook is mocked — the table's job is presenting ranked signals + live price.
const quotesState: { quotes: Record<string, { symbol: string; ltp: number; ts: string }>; candles: Record<string, unknown>; connected: boolean } = {
  quotes: {}, candles: {}, connected: true,
}
vi.mock('@/hooks/useLiveQuotes', () => ({ useLiveQuotes: () => quotesState }))

function sig(o: Partial<signalsApiModule.SignalOut> = {}): signalsApiModule.SignalOut {
  return {
    id: 'sig-1', stock_id: 42, symbol: 'RELIANCE', direction: 'BUY', classification: 'swing',
    timeframe: '1d', entry_price: '100.0000', stop_loss: '96.0000', take_profit: '112.0000',
    suggested_qty: 10, confidence_pct: 82,
    factor_scores: { A: { weight: 20, score: 0.8, explanation: '' } },
    triggering_patterns: [], triggering_indicators: [], headline: 'BUY RELIANCE', status: 'active',
    created_at: '2026-08-20T00:00:00Z', validity_until: '2026-09-20T00:00:00Z',
    sources_count: 1, near_expiry: false, days_valid_remaining: 25, regime_er: 0.5, choppy: false,
    ...o,
  } as signalsApiModule.SignalOut
}

function renderTable() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OpportunitiesTable />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({ accessToken: 'tok', user: mockUser })
  useTradingHaltStore.setState({ halted: false })
  quotesState.quotes = {}
  quotesState.connected = true
})

afterEach(() => vi.restoreAllMocks())

describe('OpportunitiesTable', () => {
  it('shows a skeleton while loading', () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockReturnValue(new Promise(() => {}))
    const { container } = renderTable()
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull()
  })

  it('renders ranked rows with the live price + trade plan, top pick starred', async () => {
    quotesState.quotes = { RELIANCE: { symbol: 'RELIANCE', ltp: 100.5, ts: '' }, TCS: { symbol: 'TCS', ltp: 50, ts: '' } }
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
      total: 2,
      signals: [
        sig({ id: 'a', symbol: 'RELIANCE', confidence_pct: 95 }),
        sig({ id: 'b', symbol: 'TCS', confidence_pct: 74, stock_id: 43, entry_price: '48', stop_loss: '46', take_profit: '54' }),
      ],
    })
    renderTable()
    const table = within(await screen.findByRole('table', { name: /opportunities/i }))
    await waitFor(() => expect(table.getByText('RELIANCE')).toBeInTheDocument())
    expect(table.getByText('TCS')).toBeInTheDocument()
    expect(table.getByText('₹100.50')).toBeInTheDocument() // live price via PriceCell
    expect(table.getByText('₹96.00')).toBeInTheDocument() // SL of the RELIANCE plan
    expect(table.getAllByText('Top').length).toBeGreaterThanOrEqual(1) // top-N flagged
  })

  it('recomputes the anti-chase guardrail against the LIVE price', async () => {
    // entry 100, SL 96 → 1R=4, don't-chase limit = 101.32. A live tick past it → "chasing".
    quotesState.quotes = { RELIANCE: { symbol: 'RELIANCE', ltp: 105, ts: '' } }
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({ total: 1, signals: [sig()] })
    renderTable()
    await waitFor(() => expect(screen.getByText(/chasing/i)).toBeInTheDocument())
    expect(screen.getByText(/past entry/i)).toBeInTheDocument()
  })

  it('shows the empty state when no signals are active', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({ total: 0, signals: [] })
    renderTable()
    expect(await screen.findByText(/No active signals/i)).toBeInTheDocument()
  })

  it('shows an error state with retry when the request fails', async () => {
    const spy = vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockRejectedValue(new Error('boom'))
    renderTable()
    expect(await screen.findByText(/Couldn't load signals/i)).toBeInTheDocument()
    spy.mockResolvedValue({ total: 0, signals: [] })
    await userEvent.click(screen.getByRole('button', { name: /Retry/i }))
    await waitFor(() => expect(screen.getByText(/No active signals/i)).toBeInTheDocument())
  })

  it('paper-trades a signal in its own direction', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({ total: 1, signals: [sig()] })
    const place = vi.spyOn(tradingApiModule.tradingApi, 'placeOrder').mockResolvedValue({
      side: 'BUY', filled_qty: 10, symbol: 'RELIANCE',
    } as never)
    renderTable()
    const btn = await screen.findByRole('button', { name: /Paper BUY RELIANCE/i })
    await userEvent.click(btn)
    await waitFor(() =>
      expect(place).toHaveBeenCalledWith({ signal_id: 'sig-1', side: 'BUY' }, 'tok'),
    )
  })

  it('disables the trade button while the kill switch is engaged', async () => {
    useTradingHaltStore.setState({ halted: true })
    vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({ total: 1, signals: [sig()] })
    renderTable()
    expect(await screen.findByRole('button', { name: /Paper BUY RELIANCE/i })).toBeDisabled()
  })
})
