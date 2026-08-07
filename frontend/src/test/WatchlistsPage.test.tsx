import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { WatchlistsPage } from '@/features/watchlists/WatchlistsPage'
import type { Watchlist } from '@/lib/api/watchlists'

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ accessToken: 'tok' }),
}))

// Live quotes are injected per test via `liveQuotes` so the price/change
// columns can be asserted without a socket.
let liveQuotes: Record<string, { symbol: string; ltp: number; ts: string }> = {}
vi.mock('@/hooks/useLiveQuotes', () => ({
  useLiveQuotes: () => ({
    quotes: liveQuotes,
    candles: {},
    signals: [],
    connected: true,
    authFailed: false,
  }),
}))

vi.mock('@/lib/api/watchlists', () => ({
  watchlistsApi: {
    list: vi.fn(),
    create: vi.fn(),
    rename: vi.fn(),
    remove: vi.fn(),
    addStock: vi.fn(),
    removeStock: vi.fn(),
  },
}))

vi.mock('@/lib/api/stocks', () => ({
  stocksApi: { list: vi.fn() },
}))

import { stocksApi } from '@/lib/api/stocks'
import { watchlistsApi } from '@/lib/api/watchlists'

const WL: Watchlist = {
  id: 1,
  name: 'Breakouts',
  created_at: '2026-07-11T00:00:00Z',
  updated_at: '2026-07-11T00:00:00Z',
  items: [
    {
      stock_id: 42,
      symbol: 'RELIANCE',
      company_name: 'Reliance Industries',
      added_at: '2026-07-11T00:00:00Z',
      prev_close: '2000.00',
    },
  ],
}

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <WatchlistsPage />
    </QueryClientProvider>,
  )
}

describe('WatchlistsPage', () => {
  beforeEach(() => {
    vi.mocked(watchlistsApi.list).mockReset()
    vi.mocked(watchlistsApi.create).mockReset()
    vi.mocked(watchlistsApi.addStock).mockReset()
    vi.mocked(watchlistsApi.removeStock).mockReset()
    vi.mocked(stocksApi.list).mockReset()
    liveQuotes = {}
  })

  describe('live prices', () => {
    // The page used to render symbol + company name and nothing else — the only
    // live surface in the app with no prices on it, while the backend was
    // already fanning ticks out per watchlist.
    it('renders the live LTP for a watched stock', async () => {
      liveQuotes = { RELIANCE: { symbol: 'RELIANCE', ltp: 2100, ts: '' } }
      vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
      setup()
      expect(await screen.findByText('₹2,100.00')).toBeInTheDocument()
    })

    it('computes change% against the last completed close', async () => {
      // 2000 → 2100 is +5.00%, and the glyph carries the direction (colour alone
      // is not a direction).
      liveQuotes = { RELIANCE: { symbol: 'RELIANCE', ltp: 2100, ts: '' } }
      vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
      setup()
      expect(await screen.findByText('▲ +5.00%')).toBeInTheDocument()
    })

    it('shows a down move with the down glyph', async () => {
      liveQuotes = { RELIANCE: { symbol: 'RELIANCE', ltp: 1900, ts: '' } }
      vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
      setup()
      expect(await screen.findByText('▼ -5.00%')).toBeInTheDocument()
    })

    it('renders a dash, not a fake 0%, when no tick has arrived', async () => {
      vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
      setup()
      // Symbol still renders; the price columns stay empty rather than implying
      // the stock is flat.
      expect(await screen.findByText('RELIANCE')).toBeInTheDocument()
      expect(screen.queryByText('▲ +0.00%')).not.toBeInTheDocument()
      expect(screen.queryByText('— 0.00%')).not.toBeInTheDocument()
    })

    it('renders a dash when the stock has no daily bar to compare against', async () => {
      // ~268 series-moved names receive no EOD bars; a null prev_close must not
      // become a division by zero or a bogus percentage.
      liveQuotes = { RELIANCE: { symbol: 'RELIANCE', ltp: 2100, ts: '' } }
      vi.mocked(watchlistsApi.list).mockResolvedValue([
        { ...WL, items: [{ ...WL.items[0], prev_close: null }] },
      ])
      setup()
      expect(await screen.findByText('₹2,100.00')).toBeInTheDocument()
      expect(screen.queryByText(/[▲▼]/)).not.toBeInTheDocument()
    })

    it('does not divide by a zero previous close', async () => {
      liveQuotes = { RELIANCE: { symbol: 'RELIANCE', ltp: 2100, ts: '' } }
      vi.mocked(watchlistsApi.list).mockResolvedValue([
        { ...WL, items: [{ ...WL.items[0], prev_close: '0' }] },
      ])
      setup()
      expect(await screen.findByText('₹2,100.00')).toBeInTheDocument()
      expect(screen.queryByText(/Infinity|NaN/)).not.toBeInTheDocument()
    })
  })

  it('shows a loading skeleton while fetching', () => {
    vi.mocked(watchlistsApi.list).mockReturnValue(new Promise(() => {}))
    setup()
    expect(screen.getByTestId('watchlists-skeleton')).toBeInTheDocument()
  })

  it('shows the error state with a working retry', async () => {
    vi.mocked(watchlistsApi.list).mockRejectedValueOnce(new Error('boom'))
    vi.mocked(watchlistsApi.list).mockResolvedValueOnce([WL])
    setup()
    await waitFor(() =>
      expect(screen.getByText("Couldn't load watchlists")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Breakouts' })).toBeInTheDocument(),
    )
  })

  it('shows the empty state with the create form', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([])
    setup()
    await waitFor(() =>
      expect(screen.getByText('No watchlists yet')).toBeInTheDocument(),
    )
    expect(screen.getByLabelText('New watchlist name')).toBeInTheDocument()
  })

  it('creates a watchlist from the form', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([])
    vi.mocked(watchlistsApi.create).mockResolvedValue({ ...WL, id: 9, name: 'Momo' })
    setup()
    await waitFor(() =>
      expect(screen.getByText('No watchlists yet')).toBeInTheDocument(),
    )
    fireEvent.change(screen.getByLabelText('New watchlist name'), {
      target: { value: 'Momo' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Create/ }))
    await waitFor(() =>
      expect(watchlistsApi.create).toHaveBeenCalledWith('Momo', 'tok'),
    )
  })

  it('renders lists with item counts and the selected detail', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
    setup()
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText('Reliance Industries')).toBeInTheDocument()
    // picker entry (pressed = selected) + detail header both show the name
    expect(
      screen.getByRole('button', { name: /Breakouts/, pressed: true }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Breakouts' })).toBeInTheDocument()
  })

  it('adds a stock from search results', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
    vi.mocked(stocksApi.list).mockResolvedValue({
      items: [{ id: 77, symbol: 'TCS', company_name: 'Tata Consultancy' }],
      total: 1,
      page: 1,
      page_size: 8,
      pages: 1,
    } as never)
    vi.mocked(watchlistsApi.addStock).mockResolvedValue(WL)
    setup()
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Search stocks to add'), {
      target: { value: 'tc' },
    })
    await waitFor(() => expect(screen.getByText('TCS')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /TCS/ }))
    await waitFor(() =>
      expect(watchlistsApi.addStock).toHaveBeenCalledWith(1, 77, 'tok'),
    )
  })

  it('removes a stock from the selected watchlist', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
    vi.mocked(watchlistsApi.removeStock).mockResolvedValue({ ...WL, items: [] })
    setup()
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    fireEvent.click(
      screen.getByRole('button', { name: 'Remove RELIANCE from Breakouts' }),
    )
    await waitFor(() =>
      expect(watchlistsApi.removeStock).toHaveBeenCalledWith(1, 42, 'tok'),
    )
  })
})
