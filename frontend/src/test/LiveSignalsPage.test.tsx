import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LiveSignalsPage } from '@/features/alerts/LiveSignalsPage'
import type { LiveAlert } from '@/hooks/useAlertStream'
import * as signalsApiModule from '@/lib/api/signals'
import * as stocksApiModule from '@/lib/api/stocks'
import * as tradingApiModule from '@/lib/api/trading'
import * as watchlistsApiModule from '@/lib/api/watchlists'
import { useAuthStore } from '@/store/authStore'
import { useTradingHaltStore } from '@/store/tradingHaltStore'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, profit_lock_enabled: false,
  is_active: true, trading_mode: 'paper', created_at: '', updated_at: '',
}

/** The stream hook is mocked: this page's job is presenting what it yields. */
const streamState = {
  alerts: [] as LiveAlert[],
  connected: true,
  authFailed: false,
  styles: [] as string[],
  setStyles: vi.fn(),
  watchlist: null as number | null,
  setWatchlist: vi.fn(),
}

vi.mock('@/hooks/useAlertStream', () => ({
  useAlertStream: () => streamState,
}))

function makeAlert(o: Partial<LiveAlert> = {}): LiveAlert {
  return {
    id: '1752212345678-0', sid: 42, levelId: '1001', tag: 'zone_enter',
    price: '2850.5000', ts: 1752212345, day: '2026-08-06',
    source: 'entry_zone', style: 'swing', signalId: 'sig-1',
    ...o,
  }
}

function makeSignal(o: Partial<signalsApiModule.SignalOut> = {}): signalsApiModule.SignalOut {
  return {
    id: 'sig-1', stock_id: 42, symbol: 'RELIANCE', direction: 'BUY',
    classification: 'swing', timeframe: '1d',
    entry_price: '2850.0000', stop_loss: '2800.0000', take_profit: '2950.0000',
    suggested_qty: 35, confidence_pct: 82, headline: 'BUY RELIANCE',
    status: 'active', created_at: '', validity_until: '',
    ...o,
  } as signalsApiModule.SignalOut
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/live-signals']}>
        <LiveSignalsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({ accessToken: 'tok', user: mockUser })
  useTradingHaltStore.setState({ halted: false })
  streamState.alerts = []
  streamState.connected = true
  streamState.authFailed = false
  streamState.styles = []
  streamState.watchlist = null
  streamState.setStyles = vi.fn()
  streamState.setWatchlist = vi.fn()
  vi.spyOn(watchlistsApiModule.watchlistsApi, 'list').mockResolvedValue([])
  // Only id + symbol are read by the feed (same partial-fixture convention as
  // AlertBell.test.tsx).
  vi.spyOn(stocksApiModule.stocksApi, 'get').mockResolvedValue(
    { id: 42, symbol: 'RELIANCE' } as never,
  )
  vi.spyOn(signalsApiModule.signalsApi, 'getById').mockResolvedValue(makeSignal())
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('LiveSignalsPage', () => {
  it('renders an alert row with its symbol, trigger, level and price', async () => {
    streamState.alerts = [makeAlert()]
    renderPage()
    const feed = within(await screen.findByRole('table', { name: /live alert feed/i }))
    await waitFor(() => expect(feed.getByText('RELIANCE')).toBeInTheDocument())
    expect(feed.getByText('Entered zone')).toBeInTheDocument()
    expect(feed.getByText('Entry zone')).toBeInTheDocument()
    expect(feed.getByText('₹2,850.50')).toBeInTheDocument()
    expect(feed.getByText('swing')).toBeInTheDocument()
  })

  it('labels the feed provisional (at-most-once observability)', () => {
    streamState.alerts = [makeAlert()]
    renderPage()
    expect(screen.getByText('PROVISIONAL')).toBeInTheDocument()
  })

  it('shows the anti-chase guardrail, warning once price runs past the limit', async () => {
    // entry 2850, SL 2800 → 1R = 50, don't-chase limit = 2850 + 0.33*50 = 2866.5
    streamState.alerts = [makeAlert({ price: '2900.0000' })]
    renderPage()
    await waitFor(() => expect(screen.getByText(/chasing/i)).toBeInTheDocument())
    expect(screen.getByText(/past entry/i)).toBeInTheDocument()
  })

  it('shows the don\'t-chase price when the trigger is still inside the band', async () => {
    streamState.alerts = [makeAlert({ price: '2855.0000' })]
    renderPage()
    await waitFor(() => expect(screen.getByText(/don't chase/i)).toBeInTheDocument())
    expect(screen.queryByText(/chasing/i)).not.toBeInTheDocument()
  })

  it('paper-trades the alert\'s originating signal in its own direction', async () => {
    streamState.alerts = [makeAlert()]
    const placeSpy = vi.spyOn(tradingApiModule.tradingApi, 'placeOrder').mockResolvedValue({
      id: 'o1', user_id: 1, signal_id: 'sig-1', stock_id: 42, symbol: 'RELIANCE',
      mode: 'paper', side: 'BUY', order_type: 'MARKET', quantity: 35, price: null,
      status: 'filled', placed_at: '', filled_at: '', filled_price: '2850.0000',
      filled_qty: 35, error_message: null,
    })
    renderPage()
    const btn = await screen.findByRole('button', { name: /Paper BUY RELIANCE/i })
    await userEvent.click(btn)
    await waitFor(() =>
      expect(placeSpy).toHaveBeenCalledWith({ signal_id: 'sig-1', side: 'BUY' }, 'tok'),
    )
  })

  it('refuses to trade while the kill switch is engaged', async () => {
    useTradingHaltStore.setState({ halted: true })
    streamState.alerts = [makeAlert()]
    const placeSpy = vi.spyOn(tradingApiModule.tradingApi, 'placeOrder')
    renderPage()
    const btn = await screen.findByRole('button', { name: /Paper BUY RELIANCE/i })
    expect(btn).toBeDisabled()
    expect(placeSpy).not.toHaveBeenCalled()
  })

  it('filters to entry signals only, client-side', async () => {
    streamState.alerts = [
      makeAlert({ id: 'a1', source: 'entry_zone', tag: 'zone_enter' }),
      makeAlert({ id: 'a2', source: 'pdh', tag: 'cross_up', signalId: null }),
    ]
    renderPage()
    await waitFor(() => expect(screen.getByText('2 alerts this session')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('combobox', { name: /Alert type/i }))
    await userEvent.click(await screen.findByRole('option', { name: /Entry signals only/i }))
    await waitFor(() => expect(screen.getByText('1 alert this session')).toBeInTheDocument())
    expect(screen.queryByText('Crossed above')).not.toBeInTheDocument()
  })

  it('scopes styles server-side (the filter belongs on the socket)', async () => {
    streamState.alerts = [makeAlert()]
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'swing' }))
    expect(streamState.setStyles).toHaveBeenCalledWith(['swing'])
  })

  it('explains an empty feed differently when connected vs offline', () => {
    streamState.alerts = []
    const { unmount } = renderPage()
    expect(screen.getByText(/tailing new alerts only/i)).toBeInTheDocument()
    unmount()

    streamState.connected = false
    renderPage()
    expect(screen.getByText(/Not connected to the alert stream/i)).toBeInTheDocument()
  })

  it('surfaces an auth failure instead of pretending the feed is empty', () => {
    streamState.authFailed = true
    renderPage()
    expect(screen.getByText(/Alert stream signed out/i)).toBeInTheDocument()
  })

  it('offers the notification opt-in and requests permission only on click', async () => {
    const requestPermission = vi.fn().mockResolvedValue('granted')
    vi.stubGlobal('Notification', Object.assign(vi.fn(), {
      permission: 'default',
      requestPermission,
    }))
    streamState.alerts = [makeAlert()]
    renderPage()

    const toggle = screen.getByRole('button', { name: /Notify me/i })
    expect(requestPermission).not.toHaveBeenCalled()   // never auto-prompt
    await userEvent.click(toggle)
    await waitFor(() => expect(requestPermission).toHaveBeenCalledTimes(1))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Notifications on/i })).toBeInTheDocument(),
    )
  })

  it('reports blocked notifications instead of a dead toggle', () => {
    vi.stubGlobal('Notification', Object.assign(vi.fn(), {
      permission: 'denied',
      requestPermission: vi.fn(),
    }))
    renderPage()
    const btn = screen.getByRole('button', { name: /Notifications blocked/i })
    expect(btn).toBeDisabled()
  })

  it('says so when the browser has no Notification API at all', () => {
    vi.stubGlobal('Notification', undefined)
    renderPage()
    expect(screen.getByText(/unsupported in this browser/i)).toBeInTheDocument()
  })
})
