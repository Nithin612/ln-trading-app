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
    blocked: false, blocked_by: null, block_reason: null, unassessed: [],
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

  // ── Eligibility honesty (2026-09-02) ──────────────────────────────────────
  // Before this, 41 of 204 listed rows offered a Buy that the order path was
  // certain to 409. A gate-blocked row must stay VISIBLE but not clickable.
  describe('gate-blocked signals', () => {
    const blocked = () =>
      sig({
        blocked: true,
        blocked_by: 'entry_quality',
        block_reason:
          'Signal fails the entry-quality overlay: only 1 scoring factor(s) (< 2)',
      })

    it('still lists a blocked signal — flagged, never silently hidden', async () => {
      vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
        total: 1, signals: [blocked()],
      })
      renderTable()
      expect(await screen.findByText('RELIANCE')).toBeInTheDocument()
      // Flagged in TWO places: the row badge next to the symbol, and the button
      // label — so the row reads as unavailable whichever the eye lands on first.
      expect(screen.getAllByText(/blocked/i)).toHaveLength(2)
    })

    it('disables the trade button and states the reason', async () => {
      vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
        total: 1, signals: [blocked()],
      })
      renderTable()
      const btn = await screen.findByRole('button', { name: /not tradeable/i })
      expect(btn).toHaveAttribute('aria-disabled', 'true')
    // NOT natively disabled: a native `disabled` drops the button out of the tab order
    // and kills its own tooltip, which made the block reason unreachable by keyboard AND
    // mouse (ui-reviewer HIGH, 2026-09-02). It stays focusable and inert instead.
    expect(btn).not.toBeDisabled()
      expect(btn).toHaveAttribute('title', expect.stringContaining('only 1 scoring factor'))
    })

    it('never fires an order for a blocked signal', async () => {
      vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
        total: 1, signals: [blocked()],
      })
      const place = vi.spyOn(tradingApiModule.tradingApi, 'placeOrder')
      renderTable()
      const btn = await screen.findByRole('button', { name: /not tradeable/i })
      await userEvent.click(btn)
      expect(place).not.toHaveBeenCalled()
    })

    it('renders a VISIBLE marker for a partially-assessed row, and keeps it clickable', async () => {
      // ui-reviewer (2026-09-02) found `TradeBlock.unknown` was returned and read by ZERO
      // call sites while its own docstring promised it "must LOOK different". A
      // title-only affordance is invisible on touch and to a scanning eye, so the marker
      // has to be in the DOM. It is NOT blocked — unknown ≠ blocked — so it stays live.
      vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
        total: 1, signals: [sig({ unassessed: ['liquidity_gate'] })],
      })
      renderTable()
      expect(await screen.findByText('RELIANCE')).toBeInTheDocument()
      expect(screen.getByText(/⚠ unchecked/)).toBeInTheDocument()
      const btn = screen.getByRole('button', { name: /eligibility not fully checked/i })
      expect(btn).toBeEnabled()
      expect(btn).not.toHaveAttribute('aria-disabled')
    })

    it('renders the themed StatusPill for a blocked row, not a hand-rolled badge', async () => {
      // UI_GUIDELINES §19.3: state pills are `StatusPill`, never hand-rolled. The first
      // version hand-built one at text-[9px] (off the §2.3 scale) inside a 0.55-opacity
      // row, which measured 2.15–2.83:1 against a 4.5 AA floor.
      vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
        total: 1, signals: [blocked()],
      })
      renderTable()
      expect(await screen.findByText('RELIANCE')).toBeInTheDocument()
      const pill = screen.getByText('Blocked')
      expect(pill.className).toContain('--color-loss')
      // and the row is NOT dimmed into illegibility
      const row = pill.closest('tr')
      expect(row?.getAttribute('style') ?? '').not.toContain('opacity: 0.55')
    })

    it('leaves an unblocked signal fully tradeable', async () => {
      vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({
        total: 1, signals: [sig()],
      })
      renderTable()
      expect(await screen.findByRole('button', { name: /Paper BUY RELIANCE/i })).toBeEnabled()
    })
  })
})
