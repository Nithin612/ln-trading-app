import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import * as tradingApiModule from '@/lib/api/trading'
import { PositionsPage } from '@/features/trading/PositionsPage'
import { TradeHistoryPage } from '@/features/trading/TradeHistoryPage'
import { DailyPnlCard } from '@/features/trading/DailyPnlCard'
import { PaperRecordCard } from '@/features/trading/PaperRecordCard'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, is_active: true, trading_mode: 'paper', allow_offmarket_entry: false, profit_lock_enabled: false,
  created_at: '', updated_at: '',
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: 'test-token', user: mockUser })
})

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

function makePosition(overrides: Partial<tradingApiModule.PositionOut> = {}): tradingApiModule.PositionOut {
  return {
    id: 'pos-001',
    user_id: 1,
    stock_id: 1,
    symbol: 'RELIANCE',
    mode: 'paper',
    side: 'LONG',
    quantity: 35,
    avg_entry_price: '2850.0000',
    current_sl: '2800.0000',
    current_tp: '2950.0000',
    trail_state: 'none',
    unrealized_pnl: '500.00',
    realized_pnl: '0',
    charges: null,
    exit_price: null,
    exit_reason: null,
    current_price: '2860.0000',
    peak_price: null,
    peak_pnl: null,
    health: null,
    opened_at: new Date().toISOString(),
    closed_at: null,
    signal_id: 'sig-001',
    // V2: the mock's default is the honest one for a row that HAS a current_price —
    // a live tick. Tests that care about the degraded states override it.
    price_state: 'live',
    stranded: false,
    ...overrides,
  }
}

function makeHealth(
  overrides: Partial<tradingApiModule.PositionHealth> = {},
): tradingApiModule.PositionHealth {
  return {
    verdict: 'cut',
    reasons: [
      { code: 'thesis_break', severity: 'cut', detail: 'Price ₹2799 through stop ₹2800.' },
    ],
    drawdown_r: 1.1,
    rr_remaining: 0.4,
    regime_er: 0.2,
    ...overrides,
  }
}

function makeDailyPnl(overrides: Partial<tradingApiModule.DailyPnlOut> = {}): tradingApiModule.DailyPnlOut {
  return {
    trade_date: '2026-05-21',
    realized_pnl: '0',
    total_unrealized_pnl: '0',
    open_count: 0,
    closed_count: 0,
    circuit_breaker_triggered: false,
    daily_loss_limit_inr: '3000',
    trades_taken_today: 0,
    max_trades_per_day: 2,
    ...overrides,
  }
}

describe('DailyPnlCard', () => {
  it('renders P&L and circuit breaker OK state', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(
      makeDailyPnl({ realized_pnl: '1500.00' })
    )
    wrap(<DailyPnlCard />)
    await waitFor(() => {
      expect(screen.getByText(/\+₹1,500/)).toBeInTheDocument()
    })
    expect(screen.getByText(/OK/i)).toBeInTheDocument()
  })

  it('shows total unrealised P&L across open positions', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(
      makeDailyPnl({ realized_pnl: '500.00', total_unrealized_pnl: '1250.00', open_count: 3 }),
    )
    wrap(<DailyPnlCard />)
    await waitFor(() => expect(screen.getByText(/Unreal\. \(open\)/)).toBeInTheDocument())
    expect(screen.getByText(/\+₹1,250/)).toBeInTheDocument()
  })

  it('shows BREAKER ON when circuit breaker is triggered', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(
      makeDailyPnl({ circuit_breaker_triggered: true, realized_pnl: '-3500.00' })
    )
    wrap(<DailyPnlCard />)
    await waitFor(() => {
      expect(screen.getByText(/BREAKER ON/i)).toBeInTheDocument()
    })
  })

  it('shows negative P&L in red', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(
      makeDailyPnl({ realized_pnl: '-1000.00' })
    )
    wrap(<DailyPnlCard />)
    await waitFor(() => {
      expect(screen.getByText(/-₹1,000/)).toBeInTheDocument()
    })
  })
})

describe('PositionsPage', () => {
  beforeEach(() => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(makeDailyPnl())
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makePaperRecord())
  })

  it('shows empty state when no open positions', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 0,
      positions: [],
    })
    wrap(<PositionsPage />)
    await waitFor(() => {
      expect(screen.getByText(/No open positions/i)).toBeInTheDocument()
    })
  })

  it('renders an open position row', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [makePosition()],
    })
    wrap(<PositionsPage />)
    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument()
    })
    expect(screen.getByText('LONG')).toBeInTheDocument()
    expect(screen.getByText('35')).toBeInTheDocument()
  })

  it('shows the current market price alongside entry', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [makePosition({ current_price: '2999.0000' })],
    })
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    expect(screen.getByText(/2,999/)).toBeInTheDocument()
  })

  it('shows close button on each position row', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [makePosition()],
    })
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    // Close button (X icon) should be present
    const closeBtn = screen.getByTitle('Close position')
    expect(closeBtn).toBeInTheDocument()
  })

  it('shows update SL button on each position row', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [makePosition()],
    })
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    expect(screen.getByTitle('Update SL')).toBeInTheDocument()
  })

  it('opens close dialog when close button clicked', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [makePosition()],
    })
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    fireEvent.click(screen.getByTitle('Close position'))
    await waitFor(() => {
      // Dialog has both h2 title and confirm button with "Close Position"
      expect(screen.getAllByText(/Close Position/).length).toBeGreaterThan(0)
    })
  })

  it('shows unrealized P&L in green for profit', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [makePosition({ unrealized_pnl: '1750.00' })],
    })
    wrap(<PositionsPage />)
    await waitFor(() => {
      expect(screen.getByText(/\+₹1,750/)).toBeInTheDocument()
    })
  })

  it('flags a structurally-dead position with a CUT health badge', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [makePosition({ health: makeHealth() })],
    })
    wrap(<PositionsPage />)
    await waitFor(() => expect(screen.getByText('CUT')).toBeInTheDocument())
    // primary reason surfaced inline, full detail available on hover
    expect(screen.getByText('stop broken')).toBeInTheDocument()
    expect(screen.getByTitle(/through stop ₹2800/)).toBeInTheDocument()
  })

  it('shows a WATCH badge with the extra-reason count', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [
        makePosition({
          health: makeHealth({
            verdict: 'watch',
            reasons: [
              { code: 'trend_dead', severity: 'watch', detail: 'Daily trend efficiency 0.20 — choppy.' },
              { code: 'stale', severity: 'watch', detail: 'Held past the validity window.' },
            ],
          }),
        }),
      ],
    })
    wrap(<PositionsPage />)
    await waitFor(() => expect(screen.getByText('WATCH')).toBeInTheDocument())
    expect(screen.getByText(/trend dead \+1/)).toBeInTheDocument()
  })

  it('renders no badge for a healthy position', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [makePosition({ health: makeHealth({ verdict: 'hold', reasons: [] }) })],
    })
    wrap(<PositionsPage />)
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.queryByText('CUT')).not.toBeInTheDocument()
    expect(screen.queryByText('WATCH')).not.toBeInTheDocument()
  })
})

describe('TradeHistoryPage', () => {
  beforeEach(() => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(makeDailyPnl())
    vi.spyOn(tradingApiModule.tradingApi, 'getShadowCompare').mockResolvedValue({
      total: 0,
      comparisons: [],
    })
  })

  it('shows peak and capture % (incl. layered) from the shadow comparator', async () => {
    const closed = makePosition({
      id: 'pos-cap',
      closed_at: new Date().toISOString(),
      realized_pnl: '1020.89',
    })
    vi.spyOn(tradingApiModule.tradingApi, 'getHistory').mockResolvedValue({
      total: 1,
      positions: [closed],
    })
    vi.spyOn(tradingApiModule.tradingApi, 'getShadowCompare').mockResolvedValue({
      total: 1,
      comparisons: [
        {
          position_id: 'pos-cap',
          symbol: 'RELIANCE',
          side: 'SHORT',
          quantity: 547,
          entry: '556.75',
          original_sl: '563.00',
          classification: 'swing',
          bars: 151,
          peak_price: '546.90',
          peak_gross: '5388.00',
          actual_exit_price: '553.62',
          actual_net: '1020.89',
          actual_capture_pct: 0.19,
          actual_exit_off_tape: false,
          policies: [
            {
              policy: 'layered',
              exit_price: '551.89',
              exit_time: null,
              exit_net: '1984.00',
              still_open: false,
              capture_pct: 0.37,
            },
          ],
          note: null,
        },
      ],
    })
    wrap(<TradeHistoryPage />)
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText(/5,388/)).toBeInTheDocument() // peak (gross)
    expect(screen.getByText('19%')).toBeInTheDocument() // actual capture
    expect(screen.getByText(/1,984/)).toBeInTheDocument() // after-lock ₹ (realistic keep)
    expect(screen.getByText(/37%/)).toBeInTheDocument() // after-lock capture
  })

  it('flags an off-tape (stale-price) close and shows the real after-lock value', async () => {
    // Regression: the 07-27 LENSKART closed 08:30 pre-open on a stale price
    // (556.35) that never traded — peak (real ₹218) < realised (fictional
    // ₹2,711). The row must flag it and show the true-tape outcome, not a
    // nonsensical 1239% capture.
    const closed = makePosition({
      id: 'pos-off',
      closed_at: new Date().toISOString(),
      realized_pnl: '2711.54',
    })
    vi.spyOn(tradingApiModule.tradingApi, 'getHistory').mockResolvedValue({
      total: 1,
      positions: [closed],
    })
    vi.spyOn(tradingApiModule.tradingApi, 'getShadowCompare').mockResolvedValue({
      total: 1,
      comparisons: [
        {
          position_id: 'pos-off',
          symbol: 'RELIANCE',
          side: 'SHORT',
          quantity: 547,
          entry: '562.55',
          original_sl: '563.00',
          classification: 'swing',
          bars: 320,
          peak_price: '562.15',
          peak_gross: '250.00',
          actual_exit_price: '556.35',
          actual_net: '2711.54',
          actual_capture_pct: null,
          actual_exit_off_tape: true,
          policies: [
            {
              policy: 'layered',
              exit_price: '563.00',
              exit_time: null,
              exit_net: '-930.00',
              still_open: false,
              capture_pct: null,
            },
          ],
          note: 'exit off-tape (stale/pre-open close) — realised P&L unreliable',
        },
      ],
    })
    wrap(<TradeHistoryPage />)
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText('⚠ off-tape')).toBeInTheDocument() // capture flagged, no % shown
    expect(screen.getByText(/250/)).toBeInTheDocument() // peak still shown (real tape)
    expect(screen.getByText(/₹930/)).toBeInTheDocument() // after-lock = true-price outcome (loss)
  })

  it('shows empty state when no history', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getHistory').mockResolvedValue({
      total: 0,
      positions: [],
    })
    wrap(<TradeHistoryPage />)
    await waitFor(() => {
      expect(screen.getByText(/No trade history/i)).toBeInTheDocument()
    })
  })

  it('renders closed trade rows', async () => {
    const closed = makePosition({
      closed_at: new Date().toISOString(),
      realized_pnl: '2000.00',
    })
    vi.spyOn(tradingApiModule.tradingApi, 'getHistory').mockResolvedValue({
      total: 1,
      positions: [closed],
    })
    wrap(<TradeHistoryPage />)
    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument()
    })
    // Summary card + table row both render the P&L — at least one must be present
    expect(screen.getAllByText(/\+₹2,000/).length).toBeGreaterThan(0)
  })

  it('shows exit price and reason (auto) for an SL/TP-closed trade', async () => {
    const closed = makePosition({
      closed_at: new Date().toISOString(),
      realized_pnl: '2000.00',
      exit_price: '2909.0000',
      exit_reason: 'tp_hit',
    })
    vi.spyOn(tradingApiModule.tradingApi, 'getHistory').mockResolvedValue({
      total: 1,
      positions: [closed],
    })
    wrap(<TradeHistoryPage />)
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText(/2,909/)).toBeInTheDocument() // exit price
    expect(screen.getByText('Target')).toBeInTheDocument() // tp_hit label
    expect(screen.getByText(/· auto/)).toBeInTheDocument()
  })

  it('labels a manual close as manual', async () => {
    const closed = makePosition({
      closed_at: new Date().toISOString(),
      realized_pnl: '100.00',
      exit_price: '2860.0000',
      exit_reason: 'manual',
    })
    vi.spyOn(tradingApiModule.tradingApi, 'getHistory').mockResolvedValue({
      total: 1,
      positions: [closed],
    })
    wrap(<TradeHistoryPage />)
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText('Manual')).toBeInTheDocument()
    expect(screen.getByText(/· manual/)).toBeInTheDocument()
  })

  it('shows losing trade in red', async () => {
    const closed = makePosition({
      closed_at: new Date().toISOString(),
      realized_pnl: '-700.00',
    })
    vi.spyOn(tradingApiModule.tradingApi, 'getHistory').mockResolvedValue({
      total: 1,
      positions: [closed],
    })
    wrap(<TradeHistoryPage />)
    await waitFor(() => {
      // Summary card + table row both render the P&L — check at least one is present
      expect(screen.getAllByText(/-₹700/).length).toBeGreaterThan(0)
    })
  })
})

function makePaperRecord(
  overrides: Partial<tradingApiModule.PaperRecordOut> = {},
): tradingApiModule.PaperRecordOut {
  return {
    days: [
      { date: '2026-06-01', realized_pnl: '1500', charges: '120', trades: 2, profitable: true, cumulative_pnl: '1500' },
      { date: '2026-06-02', realized_pnl: '-300', charges: '60', trades: 1, profitable: false, cumulative_pnl: '1200' },
    ],
    total_days_traded: 2,
    profitable_days: 1,
    losing_days: 1,
    current_streak: 0,
    best_streak: 1,
    total_realized_pnl: '1200',
    total_charges: '180',
    total_trades: 3,
    win_rate_pct: '50.0',
    target_days: 30,
    start_date: '2026-06-01',
    last_date: '2026-06-02',
    clock_started_at: null,
    ...overrides,
  }
}

describe('PaperRecordCard', () => {
  it('renders the record with net P&L and profitable-day count', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makePaperRecord())
    wrap(<PaperRecordCard />)
    await waitFor(() => expect(screen.getByText('Paper Record')).toBeInTheDocument())
    expect(screen.getByText('1/30')).toBeInTheDocument()          // profitable days / target
    expect(screen.getByText(/Toward 30 profitable days/i)).toBeInTheDocument()
  })

  it('shows an empty state before the first closed trade', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(
      makePaperRecord({ days: [], total_days_traded: 0, profitable_days: 0, losing_days: 0,
        total_realized_pnl: '0', total_charges: '0', total_trades: 0, win_rate_pct: '0.0',
        start_date: null, last_date: null }),
    )
    wrap(<PaperRecordCard />)
    await waitFor(() =>
      expect(screen.getByText(/the 30-day clock starts when you close your first trade/i)).toBeInTheDocument(),
    )
  })

  it('shows an error state with retry', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockRejectedValue(new Error('boom'))
    wrap(<PaperRecordCard />)
    await waitFor(() =>
      expect(screen.getByText(/Could not load the paper record/i)).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('resets the clock on a two-step confirm and reflects the new start date', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makePaperRecord())
    const resetSpy = vi
      .spyOn(tradingApiModule.tradingApi, 'resetPaperClock')
      .mockResolvedValue(
        makePaperRecord({
          days: [], total_days_traded: 0, profitable_days: 0, losing_days: 0,
          total_realized_pnl: '0', total_charges: '0', total_trades: 0, win_rate_pct: '0.0',
          // Evening UTC that is the NEXT day in IST (20:30Z = 02:00 IST) — pins
          // the label to IST, not the raw UTC date.
          start_date: null, last_date: null, clock_started_at: '2026-08-01T20:30:00Z',
        }),
      )
    wrap(<PaperRecordCard />)
    await waitFor(() => expect(screen.getByText('Paper Record')).toBeInTheDocument())

    // Two-step: the first click only arms the confirm (no API call yet).
    fireEvent.click(screen.getByRole('button', { name: /reset clock/i }))
    expect(resetSpy).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /confirm reset/i }))

    await waitFor(() => expect(resetSpy).toHaveBeenCalledTimes(1))
    await waitFor(() =>
      expect(screen.getByText(/counting since 2026-08-02/i)).toBeInTheDocument(),
    )
  })
})

/**
 * V2 — price truthfulness.
 *
 * The defect these pin: `get_current_price` falls back live → 1m close → daily close and
 * the UI rendered all three identically. A position whose feed had died showed a
 * plausible number from a previous session with nothing marking it, and the unrealized
 * P&L computed from it looked equally real.
 */
describe('PositionsPage — price provenance and stranded holds (V2)', () => {
  beforeEach(() => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(makeDailyPnl())
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makePaperRecord())
  })

  function withPositions(positions: tradingApiModule.PositionOut[]) {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: positions.length,
      positions,
    })
  }

  it('annotates nothing when the price came from a live tick', async () => {
    withPositions([makePosition({ price_state: 'live' })])
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    // Canary: any of the degraded labels appearing here means `live` is being annotated.
    expect(screen.queryByText(/last 1m close/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/prev session close/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/no price/i)).not.toBeInTheDocument()
  })

  it('labels a price that fell back to the last 1m close', async () => {
    withPositions([makePosition({ price_state: 'minute' })])
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    expect(screen.getByText(/last 1m close/i)).toBeInTheDocument()
  })

  it('labels a price that fell back to the previous session close', async () => {
    withPositions([makePosition({ price_state: 'daily' })])
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    expect(screen.getByText(/prev session close/i)).toBeInTheDocument()
  })

  it('labels a position with no price at all', async () => {
    withPositions([makePosition({ current_price: null, price_state: 'none' })])
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    expect(screen.getByText(/^no price$/i)).toBeInTheDocument()
  })

  it('raises a page-level alert naming every stranded holding', async () => {
    withPositions([
      makePosition({ id: 'p1', symbol: 'RELIANCE', stranded: false }),
      makePosition({ id: 'p2', symbol: 'DEADCO', stranded: true, price_state: 'daily' }),
    ])
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('DEADCO'))
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(/1 position has no tradable instrument/i)
    // ⛔ The claim must stay TRUE. `close_position` needs no instrument — it falls back
    // to the last stored close, then to `avg_entry_price`. So "cannot be exited here" was
    // false, and disabling the row's Close button (the review's proposed remedy) would
    // trap the user in the one position they most need out of.
    expect(alert).not.toHaveTextContent(/cannot be .*exited/i)
    expect(alert).toHaveTextContent(/stale close/i)
    // F3 — the claim must hold for its own WORST case too. With no stored close at all the
    // exit is booked against the ENTRY price, not a stale close; the first cut said only
    // "stale close" and was wrong for exactly the position most likely to be stranded.
    expect(alert).toHaveTextContent(/entry price if no close exists/i)
    // F8 — the singular/plural branch once covered "position(s)" and "This name" but left
    // the verb hardcoded, rendering "This name receive no live price" in the common case.
    expect(alert).toHaveTextContent(/This name gets/i)
    expect(alert).not.toHaveTextContent(/name receive /i)
    expect(alert).toHaveTextContent('DEADCO')
    // The clean name must NOT be listed as stranded.
    expect(alert).not.toHaveTextContent('RELIANCE')
  })

  it('raises no stranded alert when every holding has an instrument', async () => {
    withPositions([makePosition({ stranded: false })])
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText('RELIANCE'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

/**
 * V2 — the warning at the point of ACTION.
 *
 * The close dialog offers "leave blank to use current market price". For a position with
 * no live tick that is a promise the backend cannot keep: `close_position` falls back to
 * the last 1m close, then the daily close, then to `avg_entry_price` — booking a FLAT
 * trade at a price the market never printed, straight into `realized_pnl` and the paper
 * record. Blocking the close would be worse; saying what blank resolves to is the fix.
 */
describe('ClosePositionDialog — what "current market price" actually resolves to', () => {
  beforeEach(() => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(makeDailyPnl())
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makePaperRecord())
  })

  async function openCloseDialogFor(position: tradingApiModule.PositionOut) {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1,
      positions: [position],
    })
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText(position.symbol))
    fireEvent.click(screen.getByTitle('Close position'))
    await screen.findByRole('dialog')
  }

  it('promises a market price only when there actually is a live tick', async () => {
    await openCloseDialogFor(makePosition({ price_state: 'live' }))
    expect(screen.getByText(/leave blank to use current market price/i)).toBeInTheDocument()
    expect(screen.queryByText(/no live tick/i)).not.toBeInTheDocument()
  })

  it('names the stale source it will fall back to', async () => {
    await openCloseDialogFor(makePosition({ price_state: 'daily' }))
    expect(screen.getByText(/previous session close/i)).toBeInTheDocument()
    expect(
      screen.queryByText(/leave blank to use current market price/i),
    ).not.toBeInTheDocument()
  })

  it('warns that a priceless close books a flat trade at the ENTRY price', async () => {
    // ⭐ The worst case, and the least visible: the P&L is not merely stale, it is
    // fabricated — a trade at a price that never printed, entering the paper record.
    await openCloseDialogFor(makePosition({ current_price: null, price_state: 'none' }))
    expect(screen.getByText(/books the exit at your entry price/i)).toBeInTheDocument()
    expect(screen.getByText(/never.*printed/i)).toBeInTheDocument()
  })

  it('never blocks the close — the warning replaces a block, it does not add one', async () => {
    await openCloseDialogFor(makePosition({ current_price: null, price_state: 'none' }))
    const confirm = screen.getByRole('button', { name: /close position/i })
    expect(confirm).toBeEnabled()
    expect(confirm).not.toHaveAttribute('aria-disabled', 'true')
  })
})

describe('ClosePositionDialog — the warning is reachable non-visually (F4)', () => {
  beforeEach(() => {
    vi.spyOn(tradingApiModule.tradingApi, 'getDailyPnl').mockResolvedValue(makeDailyPnl())
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makePaperRecord())
  })

  async function openFor(position: tradingApiModule.PositionOut) {
    vi.spyOn(tradingApiModule.tradingApi, 'getOpenPositions').mockResolvedValue({
      total: 1, positions: [position],
    })
    wrap(<PositionsPage />)
    await waitFor(() => screen.getByText(position.symbol))
    fireEvent.click(screen.getByTitle('Close position'))
    await screen.findByRole('dialog')
  }

  it('associates the warning with the price field it describes', async () => {
    // A positional "see the warning above" is meaningless to a screen reader or a
    // magnifier user; `aria-describedby` is what makes the copy reach them deterministically.
    await openFor(makePosition({ price_state: 'daily' }))
    const input = screen.getByLabelText(/exit price/i)
    expect(input).toHaveAttribute('aria-describedby', 'exit-price-warning')
    expect(screen.queryByText(/above/i)).not.toBeInTheDocument()
  })

  it('leaves the field undescribed when there is nothing to warn about', async () => {
    await openFor(makePosition({ price_state: 'live' }))
    expect(screen.getByLabelText(/exit price/i)).not.toHaveAttribute('aria-describedby')
  })

  it('does not claim a priceless close books a FLAT trade', async () => {
    // F2 — `close_position` routes even the entry-price fallback through `simulate_fill`
    // and then nets `fees.py` charges (incl. the flat ₹15.34 DP charge on a delivery
    // sell), so the booked result is a small LOSS. "Flat trade" overstated it.
    await openFor(makePosition({ current_price: null, price_state: 'none' }))
    expect(screen.getByText(/less slippage and charges/i)).toBeInTheDocument()
    expect(screen.queryByText(/a flat trade/i)).not.toBeInTheDocument()
  })
})
