import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AlertBell } from '@/features/alerts/AlertBell'
import { chaseGuidance } from '@/features/alerts/alertPresentation'
import type { LiveAlert } from '@/hooks/useAlertStream'
import type { Stock } from '@/lib/api/stocks'

const stream = {
  alerts: [] as LiveAlert[],
  connected: true,
  authFailed: false,
  styles: [] as string[],
  setStyles: vi.fn(),
  watchlist: null as number | null,
  setWatchlist: vi.fn(),
}

vi.mock('@/hooks/useAlertStream', () => ({
  useAlertStream: () => stream,
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ accessToken: 'tok' }),
}))

vi.mock('@/lib/api/stocks', () => ({
  stocksApi: { get: vi.fn() },
}))

vi.mock('@/lib/api/watchlists', () => ({
  watchlistsApi: { list: vi.fn() },
}))

vi.mock('@/lib/api/signals', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@/lib/api/signals')>()
  return { ...mod, signalsApi: { getById: vi.fn() } }
})

import { stocksApi } from '@/lib/api/stocks'
import { watchlistsApi } from '@/lib/api/watchlists'
import { signalsApi } from '@/lib/api/signals'
import type { SignalOut } from '@/lib/api/signals'

const ALERT: LiveAlert = {
  id: '1752212345678-0',
  sid: 42,
  levelId: '1001',
  tag: 'cross_up',
  price: '2850.5000',
  ts: 1752212345, // 2026-07-11 ~09:49 IST
  day: '2026-07-11',
  source: 'pdh',
  style: 'market',
  signalId: null,
}

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <AlertBell />
    </QueryClientProvider>,
  )
}

describe('AlertBell', () => {
  beforeEach(() => {
    localStorage.clear() // entry-only default persists here — reset per test
    stream.alerts = []
    stream.connected = true
    stream.authFailed = false
    stream.styles = []
    stream.setStyles = vi.fn()
    stream.watchlist = null
    stream.setWatchlist = vi.fn()
    vi.mocked(stocksApi.get).mockReset()
    vi.mocked(watchlistsApi.list).mockReset()
    vi.mocked(watchlistsApi.list).mockResolvedValue([])
    vi.mocked(signalsApi.getById).mockReset()
  })

  const ENTRY_ALERT: LiveAlert = { ...ALERT, tag: 'zone_enter', source: 'entry_zone' }

  // A BUY signal at ₹100 with SL ₹96 → 1R = ₹4, so the don't-chase ceiling is
  // 100 + 0.33·4 = ₹101.32.
  const makeSignal = (o: Partial<SignalOut> = {}): SignalOut =>
    ({
      id: 'sig-1',
      stock_id: 42,
      symbol: 'RELIANCE',
      direction: 'BUY',
      classification: 'swing',
      timeframe: '1h',
      entry_price: '100.0000',
      stop_loss: '96.0000',
      take_profit: '112.0000',
      suggested_qty: 10,
      confidence_pct: 78,
      factor_scores: {},
      triggering_patterns: [],
      triggering_indicators: [],
      headline: 'test',
      status: 'active',
      validity_until: '2026-07-23T10:00:00+00:00',
      created_at: '2026-07-16T05:00:00+00:00',
      sources_count: 1,
      near_expiry: false,
      days_valid_remaining: 4,
      regime_er: 0.5,
      choppy: false,
      ...o,
    }) as SignalOut

  it('shows the empty state when no alerts have arrived', () => {
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    expect(screen.getByText('No alerts yet')).toBeInTheDocument()
    expect(screen.getByText(/stream here in real time/)).toBeInTheDocument()
  })

  it('renders alert rows: sid fallback first, then the resolved symbol', async () => {
    let resolve: (v: Stock) => void = () => {}
    vi.mocked(stocksApi.get).mockReturnValue(
      new Promise<Stock>((r) => {
        resolve = r
      }),
    )
    stream.alerts = [ALERT]
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    // ALERT is a PDH cross, not an entry-zone trigger → reveal it
    fireEvent.click(screen.getByRole('checkbox'))

    // symbol not yet loaded → sid placeholder, but the alert itself renders
    expect(screen.getByText('#42')).toBeInTheDocument()
    expect(screen.getByText('Crossed above')).toBeInTheDocument()
    expect(screen.getByText(/PDH/)).toBeInTheDocument()
    expect(screen.getByText(/2,850\.50/)).toBeInTheDocument()

    resolve({ id: 42, symbol: 'RELIANCE' } as Stock)
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.queryByText('#42')).not.toBeInTheDocument()
  })

  it('unseen badge counts new alerts and clears on open', () => {
    // Badge counts the VISIBLE set — use entry-zone alerts (the default view)
    stream.alerts = [ENTRY_ALERT, { ...ENTRY_ALERT, id: '1752212345679-0' }]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    setup()
    expect(screen.getByTestId('alert-unseen')).toHaveTextContent('2')
    fireEvent.click(screen.getByTestId('alert-bell'))
    expect(screen.queryByTestId('alert-unseen')).not.toBeInTheDocument()
  })

  it('unknown tag/source degrade to raw strings instead of hiding the alert', () => {
    stream.alerts = [{ ...ALERT, tag: 'future_condition', source: 'future_source' }]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    fireEvent.click(screen.getByRole('checkbox')) // non-entry source → reveal it
    expect(screen.getByText('future_condition')).toBeInTheDocument()
    expect(screen.getByText(/future_source/)).toBeInTheDocument()
  })

  it('badge caps its display at 99+', () => {
    stream.alerts = Array.from({ length: 100 }, (_, i) => ({
      ...ENTRY_ALERT,
      id: `id-${i}`,
    }))
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    setup()
    expect(screen.getByTestId('alert-unseen')).toHaveTextContent('99+')
  })

  it('defaults to entry-only: shows entry-zone triggers, hides other alerts', () => {
    stream.alerts = [
      { ...ENTRY_ALERT, id: 'e', price: '111.0000' },
      { ...ALERT, id: 'p', tag: 'cross_up', source: 'pdh', price: '222.0000' },
    ]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    expect(screen.getByText('Entered zone')).toBeInTheDocument()
    expect(screen.getByText(/111\.00/)).toBeInTheDocument()
    // the PDH cross is hidden by default
    expect(screen.queryByText('Crossed above')).not.toBeInTheDocument()
    expect(screen.queryByText(/222\.00/)).not.toBeInTheDocument()
  })

  it('toggling entry-only off reveals all triggers and persists the choice', () => {
    stream.alerts = [
      { ...ENTRY_ALERT, id: 'e', price: '111.0000' },
      { ...ALERT, id: 'p', tag: 'cross_up', source: 'pdh', price: '222.0000' },
    ]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    fireEvent.click(screen.getByRole('checkbox'))
    expect(screen.getByText('Entered zone')).toBeInTheDocument()
    expect(screen.getByText('Crossed above')).toBeInTheDocument()
    expect(localStorage.getItem('alertbell:entryOnly')).toBe('0')
  })

  it('shows the entry-only empty state when only non-entry alerts exist', () => {
    stream.alerts = [{ ...ALERT, tag: 'cross_up', source: 'pdh' }]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    expect(screen.getByText('No entry signals yet')).toBeInTheDocument()
  })

  // ── Anti-chase guardrail ──────────────────────────────────────────────────
  it('shows BUY + entry + the don’t-chase ceiling for an entry-zone alert', async () => {
    // Trigger ₹100.50 is inside the ceiling (₹101.32) → not chasing.
    stream.alerts = [{ ...ENTRY_ALERT, id: 'e', price: '100.5000', signalId: 'sig-1' }]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    vi.mocked(signalsApi.getById).mockResolvedValue(makeSignal())
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    await waitFor(() => expect(screen.getByText('BUY')).toBeInTheDocument())
    expect(screen.getByText(/₹100\.00/)).toBeInTheDocument() // ideal entry
    expect(screen.getByText(/chase.*₹101\.32/)).toBeInTheDocument()
    expect(screen.queryByText(/chasing/)).not.toBeInTheDocument()
  })

  it('warns when the trigger price has already run past the ceiling', async () => {
    // Trigger ₹102 is past the ₹101.32 ceiling → +2.00% past entry.
    stream.alerts = [{ ...ENTRY_ALERT, id: 'e', price: '102.0000', signalId: 'sig-1' }]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    vi.mocked(signalsApi.getById).mockResolvedValue(makeSignal())
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    await waitFor(() =>
      expect(screen.getByText(/chasing \+2\.00% past entry/)).toBeInTheDocument(),
    )
    expect(screen.queryByText(/don.t chase/)).not.toBeInTheDocument()
  })

  it('flips the guardrail direction for a SELL signal', async () => {
    // SELL entry ₹100, SL ₹104 → floor = 100 − 0.33·4 = ₹98.68; ₹99.50 is inside.
    stream.alerts = [{ ...ENTRY_ALERT, id: 'e', price: '99.5000', signalId: 'sig-1' }]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    vi.mocked(signalsApi.getById).mockResolvedValue(
      makeSignal({ direction: 'SELL', stop_loss: '104.0000' }),
    )
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    await waitFor(() => expect(screen.getByText('SELL')).toBeInTheDocument())
    expect(screen.getByText(/chase.*<.*₹98\.68/)).toBeInTheDocument()
  })

  it('renders no guardrail when the alert carries no signal', () => {
    stream.alerts = [{ ...ENTRY_ALERT, id: 'e', price: '100.5000', signalId: null }]
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    expect(screen.getByText('Entered zone')).toBeInTheDocument()
    expect(screen.queryByText('BUY')).not.toBeInTheDocument()
    expect(vi.mocked(signalsApi.getById)).not.toHaveBeenCalled()
  })

  describe('chaseGuidance (pure)', () => {
    it('computes the BUY ceiling at entry + 0.33R and flags extension', () => {
      const inside = chaseGuidance(makeSignal(), 100.5)
      expect(inside).not.toBeNull()
      expect(inside?.isBuy).toBe(true)
      expect(inside?.entry).toBe(100)
      expect(inside?.limit).toBeCloseTo(101.32, 4)
      expect(inside?.extended).toBe(false)
      expect(inside?.pastEntryPct).toBeCloseTo(0.5, 6)

      const past = chaseGuidance(makeSignal(), 102)
      expect(past?.extended).toBe(true)
      expect(past?.pastEntryPct).toBeCloseTo(2, 6)
    })

    it('computes the SELL floor at entry − 0.33R', () => {
      const s = chaseGuidance(makeSignal({ direction: 'SELL', stop_loss: '104.0000' }), 99)
      expect(s?.isBuy).toBe(false)
      expect(s?.limit).toBeCloseTo(98.68, 4)
      expect(s?.extended).toBe(false) // 99 is still above the floor
      expect(s?.pastEntryPct).toBeCloseTo(1, 6)
    })

    it('returns null when risk is zero or inputs are non-finite', () => {
      expect(chaseGuidance(makeSignal({ stop_loss: '100.0000' }), 100)).toBeNull()
      expect(chaseGuidance(makeSignal({ entry_price: 'nan' }), 100)).toBeNull()
    })
  })

  it('style filter chips toggle the server-side subscription', () => {
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    fireEvent.click(screen.getByRole('button', { name: 'swing', pressed: false }))
    expect(stream.setStyles).toHaveBeenCalledWith(['swing'])
  })

  it('active style chip toggles OFF (removed from the filter)', () => {
    stream.styles = ['swing', 'intraday']
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    fireEvent.click(screen.getByRole('button', { name: 'swing', pressed: true }))
    expect(stream.setStyles).toHaveBeenCalledWith(['intraday'])
  })

  it('watchlist selector renders the scope options from the API', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([
      {
        id: 3,
        name: 'Momo',
        created_at: '2026-07-11T00:00:00Z',
        updated_at: '2026-07-11T00:00:00Z',
        items: [],
      },
    ])
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    await waitFor(() =>
      expect(document.querySelector('[data-slot="select-trigger"]')).not.toBeNull(),
    )
    fireEvent.click(document.querySelector('[data-slot="select-trigger"]')!)
    await waitFor(() => {
      const options = screen.getAllByRole('option')
      expect(options.some((el) => el.textContent?.includes('All stocks'))).toBe(true)
      expect(options.some((el) => el.textContent?.includes('Momo'))).toBe(true)
    })
  })

  it('interacting with the portaled select listbox does not close the panel', async () => {
    // Regression (2026-07-11 smoke): the Select listbox portals to
    // document.body OUTSIDE the popover's panelRef, so choosing a scope
    // option used to fire the outside-mousedown handler, close the
    // panel, and swallow the selection.
    vi.mocked(watchlistsApi.list).mockResolvedValue([
      {
        id: 3,
        name: 'Momo',
        created_at: '2026-07-11T00:00:00Z',
        updated_at: '2026-07-11T00:00:00Z',
        items: [],
      },
    ])
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    await waitFor(() =>
      expect(document.querySelector('[data-slot="select-trigger"]')).not.toBeNull(),
    )
    fireEvent.click(document.querySelector('[data-slot="select-trigger"]')!)
    const option = await waitFor(() => {
      const opts = screen.getAllByRole('option')
      expect(opts.length).toBeGreaterThan(0)
      return opts[0]
    })
    fireEvent.mouseDown(option)
    // panel content survives the portaled-layer interaction
    expect(screen.getByText('Live alerts')).toBeInTheDocument()
  })

  it('hides the watchlist selector when the user has none', () => {
    setup() // beforeEach default: watchlistsApi.list resolves []
    fireEvent.click(screen.getByTestId('alert-bell'))
    expect(document.querySelector('[data-slot="select-trigger"]')).toBeNull()
  })

  it('shows the reconnecting notice while disconnected', () => {
    stream.connected = false
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    expect(screen.getByText('Reconnecting…')).toBeInTheDocument()
  })

  it('shows the sign-in-again notice after an auth-failed close', () => {
    stream.connected = false
    stream.authFailed = true
    setup()
    fireEvent.click(screen.getByTestId('alert-bell'))
    expect(screen.getByText(/sign in again to resume live alerts/)).toBeInTheDocument()
    expect(screen.queryByText('Reconnecting…')).not.toBeInTheDocument()
  })
})
