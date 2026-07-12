import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AlertBell } from '@/features/alerts/AlertBell'
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

import { stocksApi } from '@/lib/api/stocks'
import { watchlistsApi } from '@/lib/api/watchlists'

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
  })

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
    stream.alerts = [ALERT, { ...ALERT, id: '1752212345679-0' }]
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
    expect(screen.getByText('future_condition')).toBeInTheDocument()
    expect(screen.getByText(/future_source/)).toBeInTheDocument()
  })

  it('badge caps its display at 99+', () => {
    stream.alerts = Array.from({ length: 100 }, (_, i) => ({
      ...ALERT,
      id: `id-${i}`,
    }))
    vi.mocked(stocksApi.get).mockResolvedValue({ id: 42, symbol: 'RELIANCE' } as never)
    setup()
    expect(screen.getByTestId('alert-unseen')).toHaveTextContent('99+')
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
